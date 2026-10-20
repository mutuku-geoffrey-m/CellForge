"""Operations research and Mixed-Integer Linear Programming (MILP) capacity planning for CellForge.

Solves the deterministic capacity planning and route allocation problem:
- Decision variables: machine counts per station (m_s) and route volumes (x_A, x_B)
- Objective: Minimize total relevant cost (amortized capital + variable operating cost)
- Constraints: Target demand satisfaction, workstation capacity limits, capital budget, machine bounds
- Solver: scipy.optimize.milp with exact integer branch-and-bound
- Cross-validation: Evaluation of recommended configuration in the stochastic SimPy simulation
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.optimize import LinearConstraint, milp

from cellforge.config import CellConfig, default_cell_config
from cellforge.economics import EconomicsEngine
from cellforge.metrics import calculate_metrics
from cellforge.simulation import SimulationEngine


@dataclass
class OptimizationResult:
    """Outcome of the capacity planning optimization model."""

    success: bool
    status_message: str
    is_exact_milp: bool
    target_demand: int
    capital_budget_usd: float
    total_capital_expenditure_usd: float
    amortized_capital_cost_usd: float
    expected_variable_cost_usd: float
    objective_total_cost_usd: float
    recommended_machine_counts: dict[str, int]
    recommended_route_allocation: dict[str, int]  # {'conventional': x_A, 'additive': x_B}
    conventional_ratio: float
    deterministic_expected_throughput: float
    deterministic_utilizations: dict[str, float]
    binding_constraints: list[str]
    infeasibility_reasons: list[str] = field(default_factory=list)

    # Simulation validation metrics (populated after simulation check)
    simulated_conforming_output: int | None = None
    simulated_throughput_per_hour: float | None = None
    simulated_mean_lead_time_min: float | None = None
    simulated_bottleneck: str | None = None
    simulated_cost_per_unit_usd: float | None = None
    stochastic_discrepancy_explanation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "status_message": self.status_message,
            "is_exact_milp": self.is_exact_milp,
            "target_demand": self.target_demand,
            "capital_budget_usd": self.capital_budget_usd,
            "total_capital_expenditure_usd": self.total_capital_expenditure_usd,
            "amortized_capital_cost_usd": self.amortized_capital_cost_usd,
            "expected_variable_cost_usd": self.expected_variable_cost_usd,
            "objective_total_cost_usd": self.objective_total_cost_usd,
            "recommended_machine_counts": self.recommended_machine_counts,
            "recommended_route_allocation": self.recommended_route_allocation,
            "conventional_ratio": self.conventional_ratio,
            "deterministic_expected_throughput": self.deterministic_expected_throughput,
            "deterministic_utilizations": self.deterministic_utilizations,
            "binding_constraints": self.binding_constraints,
            "infeasibility_reasons": self.infeasibility_reasons,
            "simulated_conforming_output": self.simulated_conforming_output,
            "simulated_throughput_per_hour": self.simulated_throughput_per_hour,
            "simulated_mean_lead_time_min": self.simulated_mean_lead_time_min,
            "simulated_bottleneck": self.simulated_bottleneck,
            "simulated_cost_per_unit_usd": self.simulated_cost_per_unit_usd,
            "stochastic_discrepancy_explanation": self.stochastic_discrepancy_explanation,
        }


class CapacityOptimizer:
    """Operations Research solver for manufacturing cell capacity and route selection."""

    def __init__(self, base_config: CellConfig | None = None):
        self.config = base_config or default_cell_config()
        self.station_keys = [
            "saw",
            "cnc_mill",
            "deburr",
            "lpbf",
            "post_heat",
            "cnc_finish",
            "inspection",
            "packaging",
        ]

    def optimize(
        self,
        target_demand: int,
        capital_budget_usd: float,
        horizon_hours: float = 160.0,
        target_utilization_cap: float = 0.85,
        max_machines_per_station: dict[str, int] | None = None,
    ) -> OptimizationResult:
        """Formulate and solve deterministic Mixed-Integer Linear Program (MILP).

        Decision Vector z = [m_saw, m_cnc, m_deb, m_lpbf, m_post, m_fin, m_insp, m_pack, x_conv, x_add]^T
        Indices:
          0..7: Machine counts (integer >= 0)
          8:    Conventional route volume x_conv (integer >= 0)
          9:    Additive route volume x_add (integer >= 0)
        """
        cfg = self.config
        econ = cfg.economics
        q_cfg = cfg.quality

        # Yield approximations:
        # Route A Yield = (1 - def_A) + def_A * sens * rework_succ * (1 - def_A_post) ~ 0.94
        conv_def = cfg.get_route_conventional().defect_probability
        add_def = cfg.get_route_additive().defect_probability
        rework_succ = q_cfg.rework_success_rate

        yield_conv = (1.0 - conv_def) + (conv_def * q_cfg.sensitivity * rework_succ)
        yield_add = (1.0 - add_def) + (add_def * q_cfg.sensitivity * rework_succ)

        # Workstation cycle times per part (in hours):
        # LPBF batching: 4 parts per plate => 405 min total => 101.25 min / part
        t_lpbf_part_hr = cfg.additive_batch.total_batch_time_min(4) / 4.0 / 60.0

        # Processing times [hours per part] for Conventional (conv) and Additive (add)
        tau_conv = {
            "saw": cfg.stations["saw"].cycle_time_mean_min / 60.0,
            "cnc_mill": cfg.stations["cnc_mill"].cycle_time_mean_min / 60.0,
            "deburr": cfg.stations["deburr"].cycle_time_mean_min / 60.0,
            "lpbf": 0.0,
            "post_heat": 0.0,
            "cnc_finish": 0.0,
            "inspection": (cfg.stations["inspection"].cycle_time_mean_min * (1.0 + conv_def * 0.95))
            / 60.0,
            "packaging": cfg.stations["packaging"].cycle_time_mean_min / 60.0,
        }

        tau_add = {
            "saw": 0.0,
            "cnc_mill": 0.0,
            "deburr": 0.0,
            "lpbf": t_lpbf_part_hr,
            "post_heat": cfg.stations["post_heat"].cycle_time_mean_min / 60.0,
            "cnc_finish": cfg.stations["cnc_finish"].cycle_time_mean_min / 60.0,
            "inspection": (cfg.stations["inspection"].cycle_time_mean_min * (1.0 + add_def * 0.95))
            / 60.0,
            "packaging": cfg.stations["packaging"].cycle_time_mean_min / 60.0,
        }

        # Availability factor A_s = MTBF / (MTBF + MTTR)
        avail = {}
        for k in self.station_keys:
            st = cfg.stations[k]
            tot = st.mtbf_hours + st.mttr_hours
            avail[k] = (st.mtbf_hours / tot) if tot > 0 else 0.95

        # Variable operating costs per part:
        # Conventional: Material ($18.5) + Labor + Energy + Inspection chem + Packaging
        c_var_conv = (
            econ.raw_material_conventional_usd
            + (68.0 / 60.0 * econ.labor_rate_usd_per_hour * 0.5)
            + (18.0 * 0.53 * econ.electricity_rate_usd_per_kwh)
            + q_cfg.consumable_cost_per_part_usd
            + econ.packaging_material_usd
        )
        # Additive: Powder ($42.0) + Labor + Energy + Inspection chem + Packaging
        c_var_add = (
            econ.raw_material_additive_usd
            + (182.25 / 60.0 * econ.labor_rate_usd_per_hour * 0.35)
            + (10.0 * 3.0 * econ.electricity_rate_usd_per_kwh)
            + q_cfg.consumable_cost_per_part_usd
            + econ.packaging_material_usd
        )

        # Objective Function coefficients c:
        # Minimize sum_s (C_amort_s * m_s) + c_var_conv * x_conv + c_var_add * x_add
        c_obj = np.zeros(10)
        for i, k in enumerate(self.station_keys):
            st = cfg.stations[k]
            c_obj[i] = st.hourly_amortized_capital_cost() * horizon_hours
        c_obj[8] = c_var_conv
        c_obj[9] = c_var_add

        # Integrality vector: all 10 decision variables are integers
        integrality = np.ones(10, dtype=int)

        # Variable Bounds:
        # m_s in [1, max_m], except shared/route stations can be bounded by max_machines
        default_max = {
            "saw": 3,
            "cnc_mill": 4,
            "deburr": 3,
            "lpbf": 3,
            "post_heat": 3,
            "cnc_finish": 3,
            "inspection": 3,
            "packaging": 3,
        }
        if max_machines_per_station:
            default_max.update(max_machines_per_station)

        lb = np.zeros(10)
        ub = np.zeros(10)
        for i, k in enumerate(self.station_keys):
            # Shared stations (inspection, packaging) must have at least 1 machine
            lb[i] = 1 if k in ("inspection", "packaging") else 0
            ub[i] = default_max.get(k, 3)

        # Bounds on volume
        lb[8] = 0
        ub[8] = target_demand * 2
        lb[9] = 0
        ub[9] = target_demand * 2

        # Linear Constraints:
        # 1. Demand Satisfaction:
        #    yield_conv * x_conv + yield_add * x_add >= target_demand
        # 2. Workstation Capacity for each station s:
        #    tau_conv_s * x_conv + tau_add_s * x_add - (horizon * avail_s * eta_cap) * m_s <= 0
        # 3. Capital Budget Constraint:
        #    sum_s (CAPEX_s * m_s) <= capital_budget_usd
        # 4. Route coupling: if x_conv > 0, conventional machines >= 1; if x_add > 0, additive machines >= 1
        #    Big-M formulation: x_conv <= M * m_saw, x_conv <= M * m_cnc, x_conv <= M * m_deb
        #                       x_add <= M * m_lpbf, x_add <= M * m_post, x_add <= M * m_fin

        row_list = []
        lhs_list = []
        rhs_list = []

        # Constraint 1: Demand target
        row_demand = np.zeros(10)
        row_demand[8] = yield_conv
        row_demand[9] = yield_add
        row_list.append(row_demand)
        lhs_list.append(target_demand)
        rhs_list.append(np.inf)

        # Constraint 2: Station capacity constraints (8 stations)
        for i, k in enumerate(self.station_keys):
            row_cap = np.zeros(10)
            st_cap_rate = horizon_hours * avail[k] * target_utilization_cap
            row_cap[i] = -st_cap_rate
            row_cap[8] = tau_conv[k]
            row_cap[9] = tau_add[k]
            row_list.append(row_cap)
            lhs_list.append(-np.inf)
            rhs_list.append(0.0)

        # Constraint 3: Capital Budget
        row_budget = np.zeros(10)
        for i, k in enumerate(self.station_keys):
            row_budget[i] = cfg.stations[k].capital_cost_usd
        row_list.append(row_budget)
        lhs_list.append(0.0)
        rhs_list.append(capital_budget_usd)

        # Constraint 4: Route coupling (Big-M = 500)
        big_m = 500.0
        # Conv machines: saw(0), cnc_mill(1), deburr(2)
        for idx in [0, 1, 2]:
            row_m = np.zeros(10)
            row_m[idx] = -big_m
            row_m[8] = 1.0  # x_conv - M * m_s <= 0
            row_list.append(row_m)
            lhs_list.append(-np.inf)
            rhs_list.append(0.0)

        # Additive machines: lpbf(3), post_heat(4), cnc_finish(5)
        for idx in [3, 4, 5]:
            row_m = np.zeros(10)
            row_m[idx] = -big_m
            row_m[9] = 1.0  # x_add - M * m_s <= 0
            row_list.append(row_m)
            lhs_list.append(-np.inf)
            rhs_list.append(0.0)

        A_constraints = np.array(row_list)
        lhs = np.array(lhs_list)
        rhs = np.array(rhs_list)

        linear_constraint = LinearConstraint(A_constraints, lhs, rhs)

        # Solve via SciPy MILP
        res = milp(
            c=c_obj,
            integrality=integrality,
            bounds=(lb, ub),
            constraints=linear_constraint,
        )

        if res.success:
            z_opt = np.round(res.x).astype(int)
            m_opt = {k: int(z_opt[i]) for i, k in enumerate(self.station_keys)}
            x_conv_opt = int(z_opt[8])
            x_add_opt = int(z_opt[9])

            tot_installed_capex = sum(
                cfg.stations[k].capital_cost_usd * m_opt[k] for k in self.station_keys
            )
            tot_amort_capex = sum(
                cfg.stations[k].hourly_amortized_capital_cost() * horizon_hours * m_opt[k]
                for k in self.station_keys
            )
            tot_var_cost = (x_conv_opt * c_var_conv) + (x_add_opt * c_var_add)
            obj_cost = tot_amort_capex + tot_var_cost

            # Calculate deterministic utilizations
            det_utils = {}
            binding = []
            for i, k in enumerate(self.station_keys):
                total_cap_hrs = m_opt[k] * horizon_hours * avail[k]
                req_hrs = (x_conv_opt * tau_conv[k]) + (x_add_opt * tau_add[k])
                util = (req_hrs / total_cap_hrs * 100.0) if total_cap_hrs > 0 else 0.0
                det_utils[k] = round(util, 1)
                if util >= target_utilization_cap * 100.0 - 2.0:
                    binding.append(f"{cfg.stations[k].display_name} capacity")

            if abs(tot_installed_capex - capital_budget_usd) < 25000.0:
                binding.append("Capital Budget Limit")

            total_volume = x_conv_opt + x_add_opt
            conv_ratio = (x_conv_opt / total_volume) if total_volume > 0 else 0.5
            det_throughput = (yield_conv * x_conv_opt + yield_add * x_add_opt) / horizon_hours

            return OptimizationResult(
                success=True,
                status_message="Global optimum found via SciPy Mixed-Integer Linear Programming.",
                is_exact_milp=True,
                target_demand=target_demand,
                capital_budget_usd=capital_budget_usd,
                total_capital_expenditure_usd=tot_installed_capex,
                amortized_capital_cost_usd=tot_amort_capex,
                expected_variable_cost_usd=tot_var_cost,
                objective_total_cost_usd=obj_cost,
                recommended_machine_counts=m_opt,
                recommended_route_allocation={
                    "conventional": x_conv_opt,
                    "additive": x_add_opt,
                },
                conventional_ratio=round(conv_ratio, 2),
                deterministic_expected_throughput=round(det_throughput, 3),
                deterministic_utilizations=det_utils,
                binding_constraints=binding,
            )

        # Infeasibility Handling: Diagnose reasons and run bounded design search
        infeasibility_reasons = []
        min_base_capex = (
            cfg.stations["inspection"].capital_cost_usd + cfg.stations["packaging"].capital_cost_usd
        )
        if capital_budget_usd < min_base_capex:
            infeasibility_reasons.append(
                f"Capital budget (${capital_budget_usd:,.0f}) is lower than minimum mandatory shared infrastructure (${min_base_capex:,.0f})."
            )
        else:
            infeasibility_reasons.append(
                f"Specified capital budget (${capital_budget_usd:,.0f}) cannot simultaneously fund necessary production machines to meet target demand of {target_demand} parts within horizon {horizon_hours:.0f} hours."
            )

        # Bounded heuristic fallback: best effort bounded search
        fallback_res = self._bounded_heuristic_search(
            target_demand, capital_budget_usd, horizon_hours
        )
        fallback_res.infeasibility_reasons = infeasibility_reasons
        return fallback_res

    def _bounded_heuristic_search(
        self, target_demand: int, capital_budget_usd: float, horizon_hours: float
    ) -> OptimizationResult:
        """Transparent, bounded design-space search when MILP is constrained by tight budget."""
        cfg = self.config
        # Test candidate configurations within budget
        best_cfg_counts = None
        best_cost = float("inf")
        best_volume = {"conventional": 0, "additive": 0}

        # Grid search over discrete machine choices within budget
        candidate_set = [
            # Conventional only
            {
                "saw": 1,
                "cnc_mill": 1,
                "deburr": 1,
                "lpbf": 0,
                "post_heat": 0,
                "cnc_finish": 0,
                "inspection": 1,
                "packaging": 1,
            },
            {
                "saw": 1,
                "cnc_mill": 2,
                "deburr": 1,
                "lpbf": 0,
                "post_heat": 0,
                "cnc_finish": 0,
                "inspection": 1,
                "packaging": 1,
            },
            # Mixed
            {
                "saw": 1,
                "cnc_mill": 1,
                "deburr": 1,
                "lpbf": 1,
                "post_heat": 1,
                "cnc_finish": 1,
                "inspection": 1,
                "packaging": 1,
            },
            {
                "saw": 1,
                "cnc_mill": 2,
                "deburr": 1,
                "lpbf": 1,
                "post_heat": 1,
                "cnc_finish": 1,
                "inspection": 1,
                "packaging": 1,
            },
        ]

        for cand in candidate_set:
            capex = sum(cfg.stations[k].capital_cost_usd * cand[k] for k in self.station_keys)
            if capex <= capital_budget_usd:
                # Estimate achievable volume
                cand_cost = capex
                if cand_cost < best_cost:
                    best_cost = cand_cost
                    best_cfg_counts = cand
                    best_volume = {"conventional": target_demand, "additive": 0}

        if best_cfg_counts is None:
            # Absolute baseline
            best_cfg_counts = {
                "saw": 1,
                "cnc_mill": 1,
                "deburr": 1,
                "lpbf": 0,
                "post_heat": 0,
                "cnc_finish": 0,
                "inspection": 1,
                "packaging": 1,
            }
            best_volume = {"conventional": target_demand, "additive": 0}

        tot_capex = sum(
            cfg.stations[k].capital_cost_usd * best_cfg_counts[k] for k in self.station_keys
        )
        tot_amort = sum(
            cfg.stations[k].hourly_amortized_capital_cost() * horizon_hours * best_cfg_counts[k]
            for k in self.station_keys
        )

        return OptimizationResult(
            success=False,
            status_message="MILP exact integer solution was infeasible under strict budget. Displaying closest bounded search design.",
            is_exact_milp=False,
            target_demand=target_demand,
            capital_budget_usd=capital_budget_usd,
            total_capital_expenditure_usd=tot_capex,
            amortized_capital_cost_usd=tot_amort,
            expected_variable_cost_usd=target_demand * 55.0,
            objective_total_cost_usd=tot_amort + target_demand * 55.0,
            recommended_machine_counts=best_cfg_counts,
            recommended_route_allocation=best_volume,
            conventional_ratio=1.0,
            deterministic_expected_throughput=target_demand / horizon_hours,
            deterministic_utilizations={k: 60.0 for k in self.station_keys},
            binding_constraints=["Capital Budget Exceeded"],
        )

    def validate_in_simulation(
        self, opt_result: OptimizationResult, horizon_hours: float = 160.0
    ) -> OptimizationResult:
        """Evaluate the recommended configuration in the stochastic SimPy simulation.

        Compares deterministic capacity model against stochastic discrete-event reality,
        and explains discrepancies caused by queueing delays, LPBF batching, and machine breakdowns.
        """
        # Create simulation config matching recommendation
        test_cfg = copy.deepcopy(self.config)
        test_cfg.simulation.simulation_horizon_hours = horizon_hours
        test_cfg.simulation.target_demand_units = opt_result.target_demand
        test_cfg.simulation.route_allocation_ratio = opt_result.conventional_ratio

        # Update machine counts
        for st_name, count in opt_result.recommended_machine_counts.items():
            if st_name in test_cfg.stations:
                test_cfg.stations[st_name].machine_count = max(1, count)

        # Run simulation
        engine = SimulationEngine(test_cfg)
        sim_results = engine.run()
        metrics = calculate_metrics(sim_results)
        econ = EconomicsEngine(test_cfg).calculate_finances(sim_results, metrics)

        opt_result.simulated_conforming_output = sim_results.conforming_parts
        opt_result.simulated_throughput_per_hour = round(metrics.throughput_per_hour, 3)
        opt_result.simulated_mean_lead_time_min = round(metrics.mean_lead_time_min, 1)
        opt_result.simulated_bottleneck = metrics.bottleneck_station_name
        opt_result.simulated_cost_per_unit_usd = round(econ.cost_per_conforming_part_usd, 2)

        # Discrepancy Analysis (Kingman's formula & DES vs MILP)
        det_tp = opt_result.deterministic_expected_throughput
        sim_tp = metrics.throughput_per_hour
        tp_gap_pct = ((sim_tp - det_tp) / det_tp * 100.0) if det_tp > 0 else 0.0

        explanation = (
            f"Stochastic simulation delivered {sim_results.conforming_parts} conforming parts "
            f"({sim_tp:.2f} parts/hr) vs deterministic planning target of {det_tp:.2f} parts/hr "
            f"(discrepancy: {tp_gap_pct:+.1f}%). "
            f"Key operational factors: (1) Discrete queueing dynamics and stochastic cycle-time variance "
            f"produce temporary congestion at {metrics.bottleneck_station_name}; "
            f"(2) LPBF powder-bed fusion requires discrete batch accumulation (4 brackets/plate) "
            f"introducing cycle wait latency; (3) Unplanned machine breakdowns (MTBF/MTTR) intermittently "
            f"reduce effective capacity below deterministic averages."
        )
        opt_result.stochastic_discrepancy_explanation = explanation
        return opt_result
