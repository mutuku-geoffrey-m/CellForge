"""Unit tests for the CellForge engineering economics and financial accounting module."""

import pytest

from cellforge.config import default_cell_config
from cellforge.economics import EconomicsEngine
from cellforge.metrics import calculate_metrics
from cellforge.simulation import SimulationEngine


def test_economics_cost_accounting():
    """Verify that all cost categories sum correctly to total relevant cost."""
    cfg = default_cell_config()
    cfg.simulation.simulation_horizon_hours = 25.0
    cfg.simulation.target_demand_units = 20

    res = SimulationEngine(cfg).run()
    metrics = calculate_metrics(res)
    econ = EconomicsEngine(cfg)
    fin = econ.calculate_finances(res, metrics)

    cb = fin.cost_breakdown

    # Total operating cost must equal sum of operating components
    expected_op = (
        cb.material_usd
        + cb.labor_usd
        + cb.energy_usd
        + cb.inspection_consumables_usd
        + cb.rework_usd
        + cb.facility_overhead_usd
    )
    assert cb.total_operating_cost_usd == pytest.approx(expected_op, rel=1e-4)

    # Total relevant cost = amortized capital + total operating
    expected_relevant = cb.capital_amortized_usd + cb.total_operating_cost_usd
    assert cb.total_relevant_cost_usd == pytest.approx(expected_relevant, rel=1e-4)

    # Unit cost per conforming part
    if res.conforming_parts > 0:
        expected_unit = cb.total_relevant_cost_usd / res.conforming_parts
        assert fin.cost_per_conforming_part_usd == pytest.approx(expected_unit, rel=1e-4)


def test_breakeven_and_payback():
    """Verify break-even volume formula and capital payback period behavior."""
    cfg = default_cell_config()
    cfg.simulation.simulation_horizon_hours = 30.0
    cfg.simulation.target_demand_units = 25

    res = SimulationEngine(cfg).run()
    metrics = calculate_metrics(res)
    fin = EconomicsEngine(cfg).calculate_finances(res, metrics)

    be = fin.break_even
    assert be.selling_price_per_unit_usd == cfg.economics.target_sale_price_usd
    assert be.break_even_units >= 0.0
    assert be.payback_period_years >= 0.0


def test_route_crossover_economic_curve():
    """Verify conventional vs additive cost-volume crossover curve calculation."""
    cfg = default_cell_config()
    econ = EconomicsEngine(cfg)
    comp = econ._compute_route_crossover()

    assert len(comp.volumes) > 0
    assert len(comp.conventional_unit_costs) == len(comp.volumes)
    assert len(comp.additive_unit_costs) == len(comp.volumes)

    # At small volume (e.g. 5 units), additive should have lower or competitive setup amortization
    # At large volume (e.g. 1000 units), conventional should be cheaper per unit
    assert comp.conventional_unit_costs[-1] < comp.additive_unit_costs[-1]
    assert comp.crossover_volume_units > 0.0
