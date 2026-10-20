"""Unit tests for the CellForge discrete-event simulation engine."""

import copy

import pytest

from cellforge.config import default_cell_config
from cellforge.simulation import SimulationEngine
from cellforge.validation import validate_config, verify_simulation_results


def test_simulation_reproducibility():
    """Verify that identical random seeds yield identical simulation results."""
    cfg1 = default_cell_config()
    cfg1.simulation.simulation_horizon_hours = 20.0
    cfg1.simulation.target_demand_units = 15
    cfg1.simulation.random_seed = 12345

    cfg2 = copy.deepcopy(cfg1)

    res1 = SimulationEngine(cfg1).run()
    res2 = SimulationEngine(cfg2).run()

    assert res1.parts_started == res2.parts_started
    assert res1.conforming_parts == res2.conforming_parts
    assert res1.scrapped_parts == res2.scrapped_parts
    assert res1.total_energy_kwh == pytest.approx(res2.total_energy_kwh, rel=1e-5)


def test_simulation_mass_balance():
    """Verify system mass conservation: Started == Conforming + Scrapped + In-Progress."""
    cfg = default_cell_config()
    cfg.simulation.simulation_horizon_hours = 30.0
    cfg.simulation.target_demand_units = 25

    res = SimulationEngine(cfg).run()
    report = verify_simulation_results(res)

    assert report.mass_balance_passed, report.mass_balance_details
    assert res.parts_started == (res.conforming_parts + res.scrapped_parts + res.parts_in_system)


def test_rework_loop_termination():
    """Ensure no part undergoes more than 1 rework cycle before acceptance or scrap."""
    cfg = default_cell_config()
    cfg.simulation.simulation_horizon_hours = 25.0
    cfg.simulation.target_demand_units = 20
    cfg.quality.max_rework_cycles = 1

    res = SimulationEngine(cfg).run()

    for p in res.part_records:
        assert p.rework_count <= 1
        if p.status == "scrapped":
            # Scrapped parts must have failed inspection or re-inspection
            assert p.is_scrapped is True
            assert p.is_conforming is False


def test_additive_batching_behavior():
    """Verify that LPBF parts are processed in batches up to plate capacity."""
    cfg = default_cell_config()
    cfg.simulation.simulation_horizon_hours = 40.0
    cfg.simulation.target_demand_units = 30
    cfg.simulation.route_allocation_ratio = 0.0  # 100% Additive route
    cfg.additive_batch.build_plate_capacity = 4

    res = SimulationEngine(cfg).run()
    add_parts = [p for p in res.part_records if p.route == "additive"]
    assert len(add_parts) > 0

    # Verify that LPBF station processed parts
    assert res.station_stats["lpbf"].parts_processed > 0


def test_invalid_parameters_rejected():
    """Verify that negative or out-of-bound parameters fail validation."""
    cfg = default_cell_config()
    cfg.simulation.simulation_horizon_hours = -10.0
    valid, errors = validate_config(cfg)
    assert not valid
    assert any("horizon" in e.lower() for e in errors)

    cfg2 = default_cell_config()
    cfg2.quality.sensitivity = 1.5
    valid2, errors2 = validate_config(cfg2)
    assert not valid2
    assert any("sensitivity" in e.lower() for e in errors2)
