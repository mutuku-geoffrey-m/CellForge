"""Unit tests for the CellForge capacity planning and MILP optimization engine."""

from cellforge.config import default_cell_config
from cellforge.optimization import CapacityOptimizer


def test_milp_optimization_feasibility():
    """Verify that the MILP capacity planner finds an optimal integer solution under normal budget."""
    cfg = default_cell_config()
    optimizer = CapacityOptimizer(cfg)

    target_demand = 120
    budget_usd = 650000.0
    horizon_hours = 160.0

    res = optimizer.optimize(
        target_demand=target_demand,
        capital_budget_usd=budget_usd,
        horizon_hours=horizon_hours,
    )

    assert res.success is True
    assert res.is_exact_milp is True

    # Budget constraint must be strictly respected
    assert res.total_capital_expenditure_usd <= budget_usd

    # Integer machine counts
    for count in res.recommended_machine_counts.values():
        assert isinstance(count, int)
        assert count >= 0

    # Route volumes must satisfy demand
    vol = res.recommended_route_allocation
    assert (vol["conventional"] + vol["additive"]) >= target_demand

    # Expected throughput must be positive
    assert res.deterministic_expected_throughput > 0.0


def test_milp_infeasibility_under_tight_budget():
    """Verify that an impossible equipment budget is diagnosed as infeasible with transparent fallback."""
    cfg = default_cell_config()
    optimizer = CapacityOptimizer(cfg)

    # Minimum base shared stations alone exceed $20,000
    res = optimizer.optimize(
        target_demand=200,
        capital_budget_usd=10000.0,
        horizon_hours=160.0,
    )

    assert res.success is False
    assert len(res.infeasibility_reasons) > 0
    assert any("budget" in r.lower() for r in res.infeasibility_reasons)


def test_simulation_validation_of_recommendation():
    """Verify that the recommended configuration can be evaluated in the stochastic SimPy simulation."""
    cfg = default_cell_config()
    optimizer = CapacityOptimizer(cfg)

    res = optimizer.optimize(
        target_demand=60,
        capital_budget_usd=500000.0,
        horizon_hours=80.0,
    )

    validated = optimizer.validate_in_simulation(res, horizon_hours=80.0)

    assert validated.simulated_conforming_output is not None
    assert validated.simulated_conforming_output >= 0
    assert validated.simulated_throughput_per_hour is not None
    assert validated.stochastic_discrepancy_explanation is not None
    assert len(validated.stochastic_discrepancy_explanation) > 0
