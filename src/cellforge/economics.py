"""Engineering economics and cost analysis engine for CellForge.

Computes capital expenditure amortization, fixed and variable operational costs,
cost per conforming unit, break-even production volumes, capital payback period,
and the conventional vs additive cost-volume crossover curve.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cellforge.config import CellConfig
from cellforge.metrics import PerformanceMetrics
from cellforge.simulation import SimulationResults


@dataclass
class CostBreakdown:
    """Detailed categorization of manufacturing expenses."""

    capital_amortized_usd: float
    material_usd: float
    labor_usd: float
    energy_usd: float
    inspection_consumables_usd: float
    rework_usd: float
    scrap_cost_usd: float
    facility_overhead_usd: float
    total_operating_cost_usd: float
    total_relevant_cost_usd: float  # Capital amortized + Operating expenses


@dataclass
class BreakEvenAnalysis:
    """Break-even and investment payback metrics."""

    selling_price_per_unit_usd: float
    variable_cost_per_conforming_usd: float
    fixed_cost_horizon_usd: float
    break_even_units: float
    annual_conforming_capacity: float
    annual_net_cash_flow_usd: float
    total_capex_usd: float
    payback_period_years: float
    return_on_investment_pct: float


@dataclass
class RouteEconomicsComparison:
    """Cost comparison between standalone Conventional and Additive routes across volumes."""

    volumes: list[int]
    conventional_unit_costs: list[float]
    additive_unit_costs: list[float]
    crossover_volume_units: float  # Batch size where conventional becomes cheaper than additive


@dataclass
class FinancialSummary:
    """Master financial and engineering economics report."""

    total_installed_capex_usd: float
    amortized_capital_cost_usd: float
    cost_breakdown: CostBreakdown
    cost_per_conforming_part_usd: float
    cost_per_started_part_usd: float
    break_even: BreakEvenAnalysis
    route_comparison: RouteEconomicsComparison

    def to_dict(self) -> dict[str, Any]:
        """Convert financial report to dictionary format."""
        return {
            "total_installed_capex_usd": self.total_installed_capex_usd,
            "amortized_capital_cost_usd": self.amortized_capital_cost_usd,
            "cost_breakdown": self.cost_breakdown.__dict__,
            "cost_per_conforming_part_usd": self.cost_per_conforming_part_usd,
            "cost_per_started_part_usd": self.cost_per_started_part_usd,
            "break_even": self.break_even.__dict__,
            "route_comparison": {
                "volumes": self.route_comparison.volumes,
                "conventional_unit_costs": self.route_comparison.conventional_unit_costs,
                "additive_unit_costs": self.route_comparison.additive_unit_costs,
                "crossover_volume_units": self.route_comparison.crossover_volume_units,
            },
        }


class EconomicsEngine:
    """Engineering economics and accounting calculation engine."""

    def __init__(self, config: CellConfig):
        self.config = config

    def calculate_finances(
        self, results: SimulationResults, metrics: PerformanceMetrics
    ) -> FinancialSummary:
        """Calculate complete manufacturing financial statement from simulation run."""
        cfg = self.config
        econ = cfg.economics
        horizon_hours = results.simulation_duration_min / 60.0

        # 1. Capital Expenditure & Depreciation Amortization
        total_capex = 0.0
        amortized_capex = 0.0

        for st_name, st_cfg in cfg.stations.items():
            st_capex = st_cfg.capital_cost_usd * st_cfg.machine_count
            total_capex += st_capex
            hourly_rate = st_cfg.hourly_amortized_capital_cost()
            amortized_capex += hourly_rate * st_cfg.machine_count * horizon_hours

        # 2. Direct Material Costs
        conv_parts_started = sum(1 for p in results.part_records if p.route == "conventional")
        add_parts_started = sum(1 for p in results.part_records if p.route == "additive")

        mat_conv = conv_parts_started * econ.raw_material_conventional_usd
        mat_add = add_parts_started * econ.raw_material_additive_usd
        packaging_mat = results.conforming_parts * econ.packaging_material_usd
        total_material = mat_conv + mat_add + packaging_mat

        # 3. Direct Manufacturing Labor Costs
        total_labor_cost = 0.0
        for st_name, s_stat in results.station_stats.items():
            st_cfg = cfg.stations[st_name]
            busy_hours = s_stat.total_busy_machine_min / 60.0
            operator_hours = busy_hours * st_cfg.labor_ratio
            total_labor_cost += operator_hours * econ.labor_rate_usd_per_hour

        # 4. Electrical Energy Costs
        total_energy_cost = results.total_energy_kwh * econ.electricity_rate_usd_per_kwh

        # 5. NDT Inspection Consumables
        # Each inspection pass uses chemicals (penetrant, remover, developer)
        total_inspections = (
            results.station_stats["inspection"].parts_processed
            if "inspection" in results.station_stats
            else results.first_pass_conforming + (results.rework_count * 2)
        )
        inspection_chem_cost = total_inspections * cfg.quality.consumable_cost_per_part_usd

        # 6. Rework Bench Costs
        rework_hours = (results.rework_count * cfg.quality.rework_cycle_time_min) / 60.0
        rework_cost = rework_hours * econ.rework_labor_rate_usd_per_hour

        # 7. Scrap Value Sunk Loss
        # Material + estimated wasted processing sunk into scrapped parts
        scrap_cost = 0.0
        for p in results.part_records:
            if p.status == "scrapped":
                raw_cost = (
                    econ.raw_material_conventional_usd
                    if p.route == "conventional"
                    else econ.raw_material_additive_usd
                )
                scrap_cost += raw_cost + (
                    p.total_processing_time_min / 60.0 * econ.labor_rate_usd_per_hour * 0.5
                )

        # 8. Fixed Facility Overhead
        facility_overhead = econ.facility_overhead_usd_per_hour * horizon_hours

        # Aggregated Cost Totals
        total_operating = (
            total_material
            + total_labor_cost
            + total_energy_cost
            + inspection_chem_cost
            + rework_cost
            + facility_overhead
        )
        total_relevant = amortized_capex + total_operating

        cost_breakdown = CostBreakdown(
            capital_amortized_usd=amortized_capex,
            material_usd=total_material,
            labor_usd=total_labor_cost,
            energy_usd=total_energy_cost,
            inspection_consumables_usd=inspection_chem_cost,
            rework_usd=rework_cost,
            scrap_cost_usd=scrap_cost,
            facility_overhead_usd=facility_overhead,
            total_operating_cost_usd=total_operating,
            total_relevant_cost_usd=total_relevant,
        )

        conforming_count = results.conforming_parts
        unit_cost = (total_relevant / conforming_count) if conforming_count > 0 else 0.0
        started_count = results.parts_started
        started_unit_cost = (total_relevant / started_count) if started_count > 0 else 0.0

        # 9. Break-Even & Payback Analysis
        fixed_costs = amortized_capex + facility_overhead
        variable_costs = total_relevant - fixed_costs
        var_cost_per_unit = (variable_costs / conforming_count) if conforming_count > 0 else 0.0

        p = econ.target_sale_price_usd
        contribution_margin = max(0.01, p - var_cost_per_unit)
        break_even_units = fixed_costs / contribution_margin if contribution_margin > 0 else 0.0

        # Annualized projections (assumes 2000 operational hours / year ~ 1 single-shift work year)
        annual_scale = (2000.0 / horizon_hours) if horizon_hours > 0 else 12.5
        annual_units = conforming_count * annual_scale
        annual_revenue = annual_units * p
        annual_costs = (amortized_capex + total_operating) * annual_scale
        annual_cash_flow = annual_revenue - annual_costs

        if annual_cash_flow > 0:
            payback_years = total_capex / annual_cash_flow
            roi_pct = (annual_cash_flow / total_capex) * 100.0
        else:
            payback_years = 99.9  # Non-recovering under current production rate
            roi_pct = 0.0

        break_even = BreakEvenAnalysis(
            selling_price_per_unit_usd=p,
            variable_cost_per_conforming_usd=var_cost_per_unit,
            fixed_cost_horizon_usd=fixed_costs,
            break_even_units=break_even_units,
            annual_conforming_capacity=annual_units,
            annual_net_cash_flow_usd=annual_cash_flow,
            total_capex_usd=total_capex,
            payback_period_years=payback_years,
            return_on_investment_pct=roi_pct,
        )

        # 10. Route Economics Crossover Analysis (Unit Cost vs Production Volume)
        route_comp = self._compute_route_crossover()

        return FinancialSummary(
            total_installed_capex_usd=total_capex,
            amortized_capital_cost_usd=amortized_capex,
            cost_breakdown=cost_breakdown,
            cost_per_conforming_part_usd=unit_cost,
            cost_per_started_part_usd=started_unit_cost,
            break_even=break_even,
            route_comparison=route_comp,
        )

    def _compute_route_crossover(self) -> RouteEconomicsComparison:
        """Evaluate unit cost curves across production volumes to identify economic crossover."""
        cfg = self.config
        econ = cfg.economics

        # Conventional Route:
        # Fixed tooling, programming, and setup CAM amortized across batch
        conv_setup_fixed_usd = 1800.0  # CAM programming, fixture fabrication, soft jaws
        # Variable per bracket: raw billet + cutting + 32 min CNC + 10 min deburr + inspection + packaging
        conv_cycle_min = 8.0 + 32.0 + 10.0 + 12.0 + 6.0  # 68 min = 1.13 hrs
        conv_hourly_op = (
            econ.labor_rate_usd_per_hour * 0.5
            + (18.0 * econ.electricity_rate_usd_per_kwh)
            + (95000 / 25000)
        )
        conv_var_per_unit = (
            econ.raw_material_conventional_usd
            + (conv_cycle_min / 60.0 * conv_hourly_op)
            + cfg.quality.consumable_cost_per_part_usd
            + econ.packaging_material_usd
        )

        # Additive Route (LPBF):
        # Near-zero dedicated tooling/fixtures; low setup
        add_setup_fixed_usd = 450.0  # Build job file slicing, laser parameters verification
        # Variable per bracket: spherical powder (42.0) + build chamber share + support removal + finish mill
        # 4 parts per plate take 405 min => 101.25 min per bracket in LPBF
        add_cycle_min = 101.25 + 45.0 + 18.0 + 12.0 + 6.0  # 182.25 min = 3.04 hrs
        add_hourly_op = (
            econ.labor_rate_usd_per_hour * 0.35
            + (10.0 * econ.electricity_rate_usd_per_kwh)
            + (320000 / 20000)
        )
        add_var_per_unit = (
            econ.raw_material_additive_usd
            + (add_cycle_min / 60.0 * add_hourly_op)
            + cfg.quality.consumable_cost_per_part_usd
            + econ.packaging_material_usd
        )

        volumes = [5, 10, 25, 50, 75, 100, 150, 200, 300, 500, 750, 1000]
        conv_costs = []
        add_costs = []

        for v in volumes:
            c_conv = (conv_setup_fixed_usd / v) + conv_var_per_unit
            c_add = (add_setup_fixed_usd / v) + add_var_per_unit
            conv_costs.append(round(c_conv, 2))
            add_costs.append(round(c_add, 2))

        # Analytical Crossover: Fixed_Conv + N * Var_Conv = Fixed_Add + N * Var_Add
        # N * (Var_Add - Var_Conv) = Fixed_Conv - Fixed_Add
        delta_fixed = conv_setup_fixed_usd - add_setup_fixed_usd
        delta_var = add_var_per_unit - conv_var_per_unit

        if delta_var > 0 and delta_fixed > 0:
            crossover = delta_fixed / delta_var
        else:
            crossover = 0.0

        return RouteEconomicsComparison(
            volumes=volumes,
            conventional_unit_costs=conv_costs,
            additive_unit_costs=add_costs,
            crossover_volume_units=round(crossover, 1),
        )
