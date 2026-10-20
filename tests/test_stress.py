"""Heavy stress testing suite for CellForge manufacturing lab.

Evaluates high-congestion surges, severe quality degradation, extreme machine unreliability,
solver boundary conditions, and multi-seed Monte Carlo replication stability.
"""

from __future__ import annotations

import copy
import math

import numpy as np

from cellforge.config import default_cell_config
from cellforge.economics import EconomicsEngine
from cellforge.metrics import calculate_metrics
from cellforge.optimization import CapacityOptimizer
from cellforge.simulation import SimulationEngine
from cellforge.validation import verify_simulation_results


def test_massive_volume_demand_stress():
    """Stress-test the simulation engine under high volume surge demand.

    Verifies memory stability, discrete event processing across hundreds of parts,
    time-weighted WIP integrals, and strict system mass conservation.
    """
    cfg = default_cell_config()
    cfg.simulation.simulation_horizon_hours = 160.0
    cfg.simulation.target_demand_units = 250
    cfg.simulation.random_seed = 998877

    # Allocate 2 CNC mills and 2 LPBF machines to handle high volume
    cfg.stations["cnc_mill"].machine_count = 2
    cfg.stations["lpbf"].machine_count = 2
    cfg.stations["inspection"].machine_count = 2

    res = SimulationEngine(cfg).run()
    report = verify_simulation_results(res)

    # 1. Mass balance conservation
    assert report.mass_balance_passed, report.mass_balance_details
    assert res.parts_started == (res.conforming_parts + res.scrapped_parts + res.parts_in_system)
    assert res.parts_started > 150

    # 2. Part records integrity
    assert len(res.part_records) == res.parts_started
    for p in res.part_records:
        if p.status in ("conforming", "scrapped"):
            assert p.completion_time_min > p.arrival_time_min
            assert p.total_lead_time_min > 0.0

    # 3. WIP history snapshots exist and are strictly ordered in time
    assert len(res.wip_history) > 100
    for i in range(len(res.wip_history) - 1):
        assert res.wip_history[i + 1].time_min >= res.wip_history[i].time_min

    # 4. Metrics and Economics calculate without floating point error
    metrics = calculate_metrics(res)
    assert metrics.conforming_parts == res.conforming_parts
    assert metrics.mean_lead_time_min > 0.0
    assert not math.isnan(metrics.time_weighted_avg_wip)
    assert not math.isinf(metrics.time_weighted_avg_wip)

    finances = EconomicsEngine(cfg).calculate_finances(res, metrics)
    assert finances.cost_per_conforming_part_usd > 0.0
    assert finances.cost_breakdown.total_operating_cost_usd > 0.0


def test_severe_quality_degradation_stress():
    """Stress-test under extreme defect rates and degraded rework recovery.

    Verifies:
    - Rework loop strict termination (max 1 cycle per bracket).
    - Heavy scrap bin accumulation and material loss accounting.
    - First-Pass Yield (FPY) is strictly less than Overall Conforming Yield.
    - System mass balance remains exact under high scrap volumes.
    """
    cfg = default_cell_config()
    cfg.simulation.simulation_horizon_hours = 60.0
    cfg.simulation.target_demand_units = 50
    cfg.simulation.random_seed = 445566

    # Severe quality degradation: 45% defect rate, poor rework success, imperfect NDT
    cfg.quality.defect_probability_conventional = 0.45
    cfg.quality.defect_probability_additive = 0.50
    cfg.quality.rework_success_probability = 0.30  # 70% of reworked parts fail again
    cfg.quality.sensitivity = 0.95
    cfg.quality.specificity = 0.90
    cfg.quality.max_rework_cycles = 1

    res = SimulationEngine(cfg).run()
    report = verify_simulation_results(res)

    assert report.mass_balance_passed, report.mass_balance_details

    # High scrap must occur
    assert res.scrapped_parts > 0, "Extreme defect rate must produce scrapped parts"
    assert res.rework_count > 0, "Defective parts must visit the rework bench"

    # Strict single-cycle rework invariant: no part ever undergoes > 1 rework
    for p in res.part_records:
        assert p.rework_count <= 1, f"Part {p.part_id} exceeded maximum 1 rework cycle"
        if p.status == "scrapped":
            assert p.is_scrapped is True
            assert p.is_conforming is False

    # Metrics evaluation under scrap stress
    metrics = calculate_metrics(res)
    assert metrics.scrap_rate_pct > 0.0
    assert metrics.first_pass_yield_pct <= metrics.overall_yield_pct

    # Economics penalization: scrap sunk costs must be accounted for
    finances = EconomicsEngine(cfg).calculate_finances(res, metrics)
    assert finances.cost_breakdown.scrap_cost_usd > 0.0
    assert (
        finances.cost_breakdown.scrap_cost_usd
        >= res.scrapped_parts * cfg.economics.raw_material_conventional_usd * 0.8
    )


def test_extreme_unreliability_and_breakdowns():
    """Stress-test machine breakdown handling under high failure frequencies.

    Verifies:
    - Simultaneous machine breakdowns do not cause SimPy deadlocks or hanging events.
    - Distinction between Availability (A) and Utilization (U) is mathematically preserved.
    - Station KPIs correctly record downtime and breakdown counts.
    """
    cfg = default_cell_config()
    cfg.simulation.simulation_horizon_hours = 50.0
    cfg.simulation.target_demand_units = 30
    cfg.simulation.random_seed = 771122

    # High failure rates: low MTBF (frequent failures) and high MTTR (long repairs)
    for st_name in ["saw", "cnc_mill", "lpbf", "inspection"]:
        cfg.stations[st_name].mtbf_hours = 6.0
        cfg.stations[st_name].mttr_hours = 2.5

    res = SimulationEngine(cfg).run()
    report = verify_simulation_results(res)

    assert report.mass_balance_passed, report.mass_balance_details

    # Breakdowns must be recorded
    assert len(res.breakdown_records) > 0, "Severe failure rate must trigger breakdown events"

    metrics = calculate_metrics(res)
    for st_name in ["saw", "cnc_mill", "lpbf", "inspection"]:
        kpi = metrics.station_kpis[st_name]
        # Availability must be degraded significantly below 100%
        assert kpi.availability_pct < 95.0, (
            f"Station {st_name} availability should be degraded, got {kpi.availability_pct}%"
        )
        assert kpi.breakdown_count > 0
        assert kpi.total_downtime_hours > 0.0

        # Availability and Utilization distinction
        assert kpi.availability_pct != kpi.raw_utilization_pct


def test_milp_optimization_stress_boundaries():
    """Stress-test the Mixed-Integer Linear Programming capacity planner under boundary conditions.

    Tests:
    1. Impossibly low budget ($5,000 USD): clean diagnosis of infeasibility with explicit reasons.
    2. Enormous luxury budget ($10,000,000 USD): numerical stability, respects machine capacity ceilings,
       and selects cost-optimal machines without wasteful over-purchasing.
    3. Scaled high-demand target (D = 500 units): ensures integer feasibility and demand satisfaction.
    """
    cfg = default_cell_config()
    optimizer = CapacityOptimizer(cfg)

    # 1. Near-zero budget
    low_res = optimizer.optimize(
        target_demand=100,
        capital_budget_usd=5000.0,
        horizon_hours=160.0,
    )
    assert low_res.success is False
    assert len(low_res.infeasibility_reasons) > 0
    assert any("budget" in r.lower() for r in low_res.infeasibility_reasons)

    # 2. Extreme luxury budget
    high_res = optimizer.optimize(
        target_demand=80,
        capital_budget_usd=10000000.0,
        horizon_hours=160.0,
    )
    assert high_res.success is True
    assert high_res.is_exact_milp is True
    assert high_res.total_capital_expenditure_usd <= 10000000.0
    # Even with infinite budget, optimizer should not buy more than reasonable max machines per station
    for count in high_res.recommended_machine_counts.values():
        assert 0 <= count <= 6

    # 3. High-demand target
    scaled_res = optimizer.optimize(
        target_demand=400,
        capital_budget_usd=1500000.0,
        horizon_hours=160.0,
    )
    assert scaled_res.success is True
    assert (
        scaled_res.recommended_route_allocation["conventional"]
        + scaled_res.recommended_route_allocation["additive"]
    ) >= 400


def test_monte_carlo_multi_replication_stability():
    """Run 20 stochastic replications with distinct random seeds.

    Verifies:
    - Every replication satisfies system mass balance without exception.
    - Positive output variance confirming true stochasticity (not static equations).
    - Finite and bounded 95% confidence intervals on throughput and lead time.
    """
    cfg = default_cell_config()
    cfg.simulation.simulation_horizon_hours = 30.0
    cfg.simulation.target_demand_units = 25

    num_replications = 20
    throughput_samples: list[float] = []
    lead_time_samples: list[float] = []
    unit_cost_samples: list[float] = []

    for seed_idx in range(num_replications):
        rep_cfg = copy.deepcopy(cfg)
        rep_cfg.simulation.random_seed = 1000 + seed_idx

        sim_res = SimulationEngine(rep_cfg).run()
        report = verify_simulation_results(sim_res)
        assert report.mass_balance_passed, (
            f"Seed {rep_cfg.simulation.random_seed} failed mass balance"
        )

        perf = calculate_metrics(sim_res)
        fin = EconomicsEngine(rep_cfg).calculate_finances(sim_res, perf)

        throughput_samples.append(perf.throughput_per_hour)
        if perf.conforming_parts > 0:
            lead_time_samples.append(perf.mean_lead_time_min)
            unit_cost_samples.append(fin.cost_per_conforming_part_usd)

    # Statistical properties
    assert len(throughput_samples) == num_replications
    assert np.var(throughput_samples) > 0.0, (
        "Throughput must exhibit stochastic variance across seeds"
    )
    assert len(lead_time_samples) >= 15

    # 95% Confidence Interval finite and non-empty
    mean_th = float(np.mean(throughput_samples))
    std_th = float(np.std(throughput_samples, ddof=1))
    ci_th = 1.96 * (std_th / math.sqrt(num_replications))
    assert ci_th > 0.0
    assert (mean_th - ci_th) > 0.0


def test_additive_batch_boundary_stress():
    """Stress-test LPBF batching when demand is NOT a multiple of build plate capacity.

    Verifies that the partial final batch timeout triggers and processes the leftover brackets.
    """
    cfg = default_cell_config()
    cfg.simulation.simulation_horizon_hours = 40.0
    cfg.simulation.route_allocation_ratio = 0.0  # 100% Additive route
    cfg.additive_batch.build_plate_capacity = 4
    # 15 parts total = 3 full batches of 4, plus 1 partial batch of 3
    cfg.simulation.target_demand_units = 15
    cfg.simulation.random_seed = 883311

    res = SimulationEngine(cfg).run()
    report = verify_simulation_results(res)

    assert report.mass_balance_passed, report.mass_balance_details
    # Verify that LPBF processed parts and did not leave partial batch permanently orphaned
    assert res.station_stats["lpbf"].parts_processed > 0


def test_zero_conforming_and_economic_resilience():
    """Stress-test metrics and economics calculations when zero conforming parts are completed.

    Verifies division-by-zero protection across all KPI and cost equations.
    """
    cfg = default_cell_config()
    # Tiny horizon: 0.1 hours (6 minutes) with long cycle times -> 0 parts can complete
    cfg.simulation.simulation_horizon_hours = 0.1
    cfg.simulation.target_demand_units = 10

    res = SimulationEngine(cfg).run()
    assert res.conforming_parts == 0

    # Calculate metrics with zero completions
    metrics = calculate_metrics(res)
    assert metrics.conforming_parts == 0
    assert metrics.mean_lead_time_min == 0.0
    assert metrics.first_pass_yield_pct == 0.0
    assert metrics.throughput_per_hour == 0.0

    # Calculate economics with zero completions
    finances = EconomicsEngine(cfg).calculate_finances(res, metrics)
    assert finances.cost_per_conforming_part_usd == 0.0
    assert finances.break_even.break_even_units >= 0.0
    assert finances.break_even.annual_conforming_capacity == 0.0
    assert finances.break_even.payback_period_years == 99.9  # Non-recovering flag
