"""Pre-configured engineering scenarios and comparison suite for CellForge.

Enables automated execution and cross-scenario evaluation of:
1. Baseline Balanced Cell
2. Additive-Centric Production
3. High-Demand Surge (+50% Target Volume)
4. Quality Stress & High Defect Rate
5. MILP-Optimized Configuration
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import pandas as pd

from cellforge.config import CellConfig, default_cell_config
from cellforge.economics import EconomicsEngine, FinancialSummary
from cellforge.metrics import PerformanceMetrics, calculate_metrics
from cellforge.optimization import CapacityOptimizer
from cellforge.simulation import SimulationEngine, SimulationResults


@dataclass
class ScenarioRunResult:
    """Consolidated outputs for a single simulated scenario."""

    scenario_id: str
    scenario_name: str
    description: str
    config: CellConfig
    simulation_results: SimulationResults
    metrics: PerformanceMetrics
    finances: FinancialSummary


def get_standard_scenarios() -> dict[str, dict[str, Any]]:
    """Return catalog of standard manufacturing scenario specifications."""
    return {
        "baseline": {
            "name": "Baseline Production Cell",
            "description": "Balanced 70/30 conventional/additive production meeting 120-part baseline demand over 160 hours.",
            "modifier": lambda cfg: cfg,
        },
        "additive_centric": {
            "name": "Additive-Centric Route",
            "description": "Strategic shift to 80% LPBF metal additive manufacturing. Demonstrates high capital and powder cost vs reduced machining.",
            "modifier": _modify_additive_centric,
        },
        "high_demand": {
            "name": "High-Demand Surge (+50%)",
            "description": "Production target expanded to 180 parts in 160 hours without adding machines. Tests queue stability and bottleneck saturation.",
            "modifier": _modify_high_demand,
        },
        "quality_stress": {
            "name": "Quality Stress (High Defect)",
            "description": "Elevated defect probabilities (7% conv, 14% add) with lower rework success (65%). Stresses NDT inspection and scrap rates.",
            "modifier": _modify_quality_stress,
        },
    }


def _modify_additive_centric(cfg: CellConfig) -> CellConfig:
    c = copy.deepcopy(cfg)
    c.simulation.route_allocation_ratio = 0.20  # 20% conv, 80% additive
    c.stations["lpbf"].machine_count = 2  # Add second LPBF to handle volume
    return c


def _modify_high_demand(cfg: CellConfig) -> CellConfig:
    c = copy.deepcopy(cfg)
    c.simulation.target_demand_units = 180
    c.simulation.interarrival_mean_min = 23.0  # More frequent part launches
    return c


def _modify_quality_stress(cfg: CellConfig) -> CellConfig:
    c = copy.deepcopy(cfg)
    # Double defect rates and lower rework recovery
    c.quality.rework_success_rate = 0.65
    c.quality.sensitivity = 0.90
    c.quality.specificity = 0.94  # Higher false alarm rate (6%)
    return c


class ScenarioManager:
    """Executes and formats comparative analysis across multiple scenarios."""

    def __init__(self, base_config: CellConfig | None = None):
        self.base_config = base_config or default_cell_config()

    def run_scenario(
        self, scenario_id: str, custom_config: CellConfig | None = None
    ) -> ScenarioRunResult:
        """Run a single scenario and return all associated metrics and financials."""
        catalog = get_standard_scenarios()
        if custom_config is not None:
            cfg = copy.deepcopy(custom_config)
            name = f"Custom: {scenario_id}"
            desc = "User-customized scenario configuration."
        elif scenario_id in catalog:
            item = catalog[scenario_id]
            cfg = item["modifier"](self.base_config)
            name = item["name"]
            desc = item["description"]
        else:
            raise ValueError(f"Unknown scenario identifier: {scenario_id}")

        engine = SimulationEngine(cfg)
        sim_res = engine.run()
        metrics = calculate_metrics(sim_res)
        econ = EconomicsEngine(cfg).calculate_finances(sim_res, metrics)

        return ScenarioRunResult(
            scenario_id=scenario_id,
            scenario_name=name,
            description=desc,
            config=cfg,
            simulation_results=sim_res,
            metrics=metrics,
            finances=econ,
        )

    def run_all_standard_scenarios(self) -> dict[str, ScenarioRunResult]:
        """Execute all standard catalog scenarios."""
        results = {}
        for s_id in get_standard_scenarios():
            results[s_id] = self.run_scenario(s_id)
        return results

    def run_optimization_scenario(
        self, target_demand: int = 140, capital_budget_usd: float = 650000.0
    ) -> ScenarioRunResult:
        """Run MILP optimization and evaluate the recommended configuration in simulation."""
        optimizer = CapacityOptimizer(self.base_config)
        opt_res = optimizer.optimize(
            target_demand=target_demand, capital_budget_usd=capital_budget_usd
        )

        # Build config from recommendation
        opt_cfg = copy.deepcopy(self.base_config)
        opt_cfg.simulation.target_demand_units = target_demand
        opt_cfg.simulation.route_allocation_ratio = opt_res.conventional_ratio
        for st_name, count in opt_res.recommended_machine_counts.items():
            if st_name in opt_cfg.stations:
                opt_cfg.stations[st_name].machine_count = max(1, count)

        opt_engine = SimulationEngine(opt_cfg)
        sim_res = opt_engine.run()
        metrics = calculate_metrics(sim_res)
        econ = EconomicsEngine(opt_cfg).calculate_finances(sim_res, metrics)

        return ScenarioRunResult(
            scenario_id="optimized",
            scenario_name="MILP-Optimized Configuration",
            description=f"Optimal equipment portfolio generated by SciPy MILP for D={target_demand}, Budget=${capital_budget_usd:,.0f}.",
            config=opt_cfg,
            simulation_results=sim_res,
            metrics=metrics,
            finances=econ,
        )

    @staticmethod
    def build_comparison_dataframe(
        scenario_results: dict[str, ScenarioRunResult],
    ) -> pd.DataFrame:
        """Generate side-by-side comparison table of key production and economic KPIs."""
        records = []
        for s_id, s_run in scenario_results.items():
            m = s_run.metrics
            f = s_run.finances
            records.append(
                {
                    "Scenario ID": s_id,
                    "Scenario Name": s_run.scenario_name,
                    "Parts Started": m.parts_started,
                    "Conforming Parts": m.conforming_parts,
                    "Scrapped Parts": m.scrapped_parts,
                    "Throughput (units/hr)": round(m.throughput_per_hour, 2),
                    "Mean Lead Time (min)": round(m.mean_lead_time_min, 1),
                    "Median Lead Time (min)": round(m.median_lead_time_min, 1),
                    "P95 Lead Time (min)": round(m.p95_lead_time_min, 1),
                    "Time-Weighted WIP": round(m.time_weighted_avg_wip, 1),
                    "Bottleneck Station": m.bottleneck_station_name,
                    "Bottleneck Util (%)": round(m.bottleneck_utilization_pct, 1),
                    "First-Pass Yield (%)": round(m.first_pass_yield_pct, 1),
                    "Overall Yield (%)": round(m.overall_yield_pct, 1),
                    "Scrap Rate (%)": round(m.scrap_rate_pct, 1),
                    "On-Time Delivery (%)": round(m.on_time_delivery_pct, 1),
                    "Total CAPEX ($)": round(f.total_installed_capex_usd, 0),
                    "Operating Cost ($)": round(f.cost_breakdown.total_operating_cost_usd, 0),
                    "Cost / Conforming Part ($)": round(f.cost_per_conforming_part_usd, 2),
                    "Break-Even Units": round(f.break_even.break_even_units, 1),
                    "Payback Period (yrs)": round(f.break_even.payback_period_years, 2),
                    "Total Energy (kWh)": round(m.total_energy_kwh, 1),
                }
            )
        return pd.DataFrame(records)
