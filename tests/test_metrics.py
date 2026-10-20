"""Unit tests for CellForge performance metrics and KPI calculations."""

import pytest

from cellforge.config import default_cell_config
from cellforge.metrics import calculate_metrics
from cellforge.simulation import SimulationEngine


def test_metrics_calculation_consistency():
    """Verify that all high-level volume and flow rate KPIs are mathematically consistent."""
    cfg = default_cell_config()
    cfg.simulation.simulation_horizon_hours = 25.0
    cfg.simulation.target_demand_units = 20

    res = SimulationEngine(cfg).run()
    metrics = calculate_metrics(res)

    assert metrics.parts_started == res.parts_started
    assert metrics.conforming_parts == res.conforming_parts
    assert metrics.scrapped_parts == res.scrapped_parts
    assert metrics.throughput_per_hour >= 0.0
    assert metrics.throughput_per_shift == pytest.approx(
        metrics.throughput_per_hour * cfg.simulation.shift_duration_hours
    )
    assert 0.0 <= metrics.overall_yield_pct <= 100.0
    assert 0.0 <= metrics.first_pass_yield_pct <= 100.0
    assert 0.0 <= metrics.scrap_rate_pct <= 100.0


def test_availability_and_utilization_distinction():
    """Verify that machine availability and machine utilization are tracked as distinct metrics."""
    cfg = default_cell_config()
    cfg.simulation.simulation_horizon_hours = 30.0
    cfg.simulation.target_demand_units = 25

    res = SimulationEngine(cfg).run()
    metrics = calculate_metrics(res)

    for kpi in metrics.station_kpis.values():
        # Availability is percentage of planned time machine was not broken down
        assert 0.0 <= kpi.availability_pct <= 100.0
        # Raw utilization is percentage of planned time machine was actively servicing parts
        assert 0.0 <= kpi.raw_utilization_pct <= 100.0
        # OEE must be <= 100% and decomposed into A x P x Q
        assert 0.0 <= kpi.oee_pct <= 100.0
        expected_oee = (
            (kpi.oee_availability / 100.0)
            * (kpi.oee_performance / 100.0)
            * (kpi.oee_quality / 100.0)
            * 100.0
        )
        assert kpi.oee_pct == pytest.approx(expected_oee, rel=1e-3)


def test_zero_completions_edge_case():
    """Verify that runs with zero completed parts do not raise division-by-zero errors."""
    cfg = default_cell_config()
    cfg.simulation.simulation_horizon_hours = 0.5  # Very short, no part finishes
    cfg.simulation.target_demand_units = 10

    res = SimulationEngine(cfg).run()
    metrics = calculate_metrics(res)

    assert metrics.parts_completed >= 0
    assert metrics.throughput_per_hour >= 0.0
    assert metrics.mean_lead_time_min >= 0.0
    assert metrics.flow_efficiency_pct >= 0.0
    assert metrics.energy_per_conforming_part_kwh >= 0.0


def test_bottleneck_identification():
    """Verify that a valid bottleneck station is identified."""
    cfg = default_cell_config()
    cfg.simulation.simulation_horizon_hours = 25.0
    cfg.simulation.target_demand_units = 20

    res = SimulationEngine(cfg).run()
    metrics = calculate_metrics(res)

    assert metrics.bottleneck_station in cfg.stations
    assert metrics.bottleneck_utilization_pct >= 0.0
    assert len(metrics.bottleneck_station_name) > 0
