"""Discrete-event simulation engine for CellForge manufacturing lab.

Implements SimPy-based discrete-event simulation modeling:
- Multi-route manufacturing (Conventional subtractive vs Metal LPBF additive)
- Machine queues and parallel capacities
- LPBF build plate batching and post-processing
- Stochastic cycle times and machine reliability (MTBF / MTTR breakdowns)
- Shared dye-penetrant NDT inspection with type I / type II errors
- Single-cycle rework loops and scrap tracking
- Energy consumption and time-weighted WIP tracking
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import simpy

from cellforge.config import CellConfig


@dataclass
class StationEvent:
    """Record of a part's experience at a specific workstation."""

    station: str
    queue_enter_time: float
    service_start_time: float
    service_end_time: float
    wait_duration_min: float
    service_duration_min: float
    machine_index: int = 0


@dataclass
class PartRecord:
    """Comprehensive lifecycle log for an individual manufactured bracket."""

    part_id: int
    route: Literal["conventional", "additive"]
    arrival_time_min: float
    start_time_min: float = 0.0
    completion_time_min: float = 0.0
    is_defective_physical: bool = False
    initial_inspection_passed: bool = False
    rework_count: int = 0
    rework_succeeded: bool = False
    is_conforming: bool = False
    is_scrapped: bool = False
    status: Literal["in_progress", "conforming", "scrapped"] = "in_progress"
    on_time: bool = True
    station_history: list[StationEvent] = field(default_factory=list)

    @property
    def total_lead_time_min(self) -> float:
        """Total time elapsed from system entry to completion or scrap (minutes)."""
        if self.completion_time_min > self.arrival_time_min:
            return self.completion_time_min - self.arrival_time_min
        return 0.0

    @property
    def total_waiting_time_min(self) -> float:
        """Sum of all queueing delays across visited workstations (minutes)."""
        return sum(e.wait_duration_min for e in self.station_history)

    @property
    def total_processing_time_min(self) -> float:
        """Sum of all active machining, build, and inspection durations (minutes)."""
        return sum(e.service_duration_min for e in self.station_history)


@dataclass
class WIPSnapshot:
    """Snapshot of work-in-progress and queue status at a discrete simulation time."""

    time_min: float
    total_wip: int
    conventional_wip: int
    additive_wip: int
    station_queues: dict[str, int]
    station_busy: dict[str, int]


@dataclass
class BreakdownRecord:
    """Log of a machine breakdown and repair incident."""

    station: str
    machine_id: int
    failure_time_min: float
    repair_end_time_min: float
    duration_min: float


@dataclass
class StationStats:
    """Aggregated operational statistics for a workstation."""

    name: str
    display_name: str
    machine_count: int
    parts_processed: int
    total_busy_machine_min: float
    total_downtime_machine_min: float
    breakdown_count: int
    active_energy_kwh: float
    idle_energy_kwh: float
    avg_queue_length: float
    max_queue_length: int


@dataclass
class SimulationResults:
    """Comprehensive output bundle returned by the simulation engine."""

    config: CellConfig
    simulation_duration_min: float
    parts_started: int
    parts_completed: int
    conforming_parts: int
    scrapped_parts: int
    parts_in_system: int
    first_pass_conforming: int
    rework_count: int
    rework_success_count: int
    missed_defects_escaped: int
    false_alarm_rejections: int
    part_records: list[PartRecord]
    station_stats: dict[str, StationStats]
    breakdown_records: list[BreakdownRecord]
    wip_history: list[WIPSnapshot]
    total_energy_kwh: float


class SimulationEngine:
    """Core SimPy discrete-event simulation engine for CellForge."""

    def __init__(self, config: CellConfig):
        self.config = config
        self.rng = np.random.default_rng(config.simulation.random_seed)

        self.env: simpy.Environment = simpy.Environment()
        self.resources: dict[str, simpy.Resource] = {}
        self.station_queues: dict[str, int] = {}
        self.station_busy: dict[str, int] = {}

        # Accounting accumulators per station
        self.station_parts_processed: dict[str, int] = {}
        self.station_busy_time: dict[str, float] = {}
        self.station_downtime: dict[str, float] = {}
        self.station_breakdown_count: dict[str, int] = {}

        # Queue tracking time-weighted integrals
        self.last_queue_update_time: dict[str, float] = {}
        self.queue_time_integral: dict[str, float] = {}
        self.max_queue_length: dict[str, int] = {}

        # LPBF batch staging
        self.lpbf_staging: list[tuple[PartRecord, simpy.Event]] = []
        self.lpbf_batch_trigger: simpy.Event | None = None

        # Data collection
        self.part_records: list[PartRecord] = []
        self.breakdown_records: list[BreakdownRecord] = []
        self.wip_history: list[WIPSnapshot] = []

        # Part counter
        self.next_part_id: int = 1

        # Initialize resources and tracking structures
        for name, st in config.stations.items():
            self.resources[name] = simpy.Resource(self.env, capacity=st.machine_count)
            self.station_queues[name] = 0
            self.station_busy[name] = 0
            self.station_parts_processed[name] = 0
            self.station_busy_time[name] = 0.0
            self.station_downtime[name] = 0.0
            self.station_breakdown_count[name] = 0
            self.last_queue_update_time[name] = 0.0
            self.queue_time_integral[name] = 0.0
            self.max_queue_length[name] = 0

    def _sample_cycle_time(self, mean_min: float, std_min: float) -> float:
        """Draw a positive stochastic processing duration using a truncated normal."""
        if std_min <= 0.0:
            return max(0.1, mean_min)
        val = self.rng.normal(mean_min, std_min)
        return max(0.1, float(val))

    def _update_queue_integral(self, station: str):
        """Update the time-weighted queue length integral."""
        now = self.env.now
        dt = now - self.last_queue_update_time[station]
        if dt > 0:
            self.queue_time_integral[station] += self.station_queues[station] * dt
            self.last_queue_update_time[station] = now

    def _record_wip_snapshot(self):
        """Take a snapshot of current system-wide WIP and station queues."""
        active_parts = [p for p in self.part_records if p.status == "in_progress"]
        conv_wip = sum(1 for p in active_parts if p.route == "conventional")
        add_wip = sum(1 for p in active_parts if p.route == "additive")

        self.wip_history.append(
            WIPSnapshot(
                time_min=self.env.now,
                total_wip=len(active_parts),
                conventional_wip=conv_wip,
                additive_wip=add_wip,
                station_queues=dict(self.station_queues),
                station_busy=dict(self.station_busy),
            )
        )

    def _breakdown_process(self, station: str, machine_idx: int):
        """Simulate stochastic machine breakdowns and repair cycles."""
        st_cfg = self.config.stations[station]
        mtbf_min = st_cfg.mtbf_hours * 60.0
        mttr_min = st_cfg.mttr_hours * 60.0

        if mtbf_min <= 0 or mttr_min <= 0:
            return

        while True:
            # Time until next breakdown (exponential distribution)
            time_to_fail = float(self.rng.exponential(mtbf_min))
            yield self.env.timeout(time_to_fail)

            # Repair duration (lognormal distribution around MTTR)
            sigma = 0.35
            mu = math.log(mttr_min) - 0.5 * (sigma**2)
            repair_duration = float(self.rng.lognormal(mu, sigma))

            # Acquire 1 machine capacity to take it offline for repair
            req = self.resources[station].request()
            yield req

            fail_start = self.env.now
            self.station_breakdown_count[station] += 1
            yield self.env.timeout(repair_duration)

            fail_end = self.env.now
            actual_downtime = fail_end - fail_start
            self.station_downtime[station] += actual_downtime

            self.breakdown_records.append(
                BreakdownRecord(
                    station=station,
                    machine_id=machine_idx,
                    failure_time_min=fail_start,
                    repair_end_time_min=fail_end,
                    duration_min=actual_downtime,
                )
            )

            self.resources[station].release(req)

    def _lpbf_batch_manager(self):
        """Coordinate batching of additive brackets onto LPBF build substrates."""
        lpbf_cfg = self.config.stations["lpbf"]
        batch_cfg = self.config.additive_batch
        max_batch_size = batch_cfg.build_plate_capacity

        while True:
            # Wait until at least 1 part is staged
            if len(self.lpbf_staging) == 0:
                self.lpbf_batch_trigger = self.env.event()
                yield self.lpbf_batch_trigger
                self.lpbf_batch_trigger = None

            # Collect available parts up to build plate capacity
            # If fewer than capacity, wait short timeout unless simulation is closing
            if len(self.lpbf_staging) < max_batch_size:
                # Wait up to 60 minutes for more parts to form full batch
                timeout_ev = self.env.timeout(60.0)
                more_parts_ev = self.env.event()
                self.lpbf_batch_trigger = more_parts_ev

                res = yield timeout_ev | more_parts_ev
                if more_parts_ev in res:
                    pass
                self.lpbf_batch_trigger = None

            batch_parts = self.lpbf_staging[:max_batch_size]
            self.lpbf_staging = self.lpbf_staging[len(batch_parts) :]

            if not batch_parts:
                continue

            parts_in_batch = len(batch_parts)

            # Request LPBF machine
            req = self.resources["lpbf"].request()
            yield req

            self._update_queue_integral("lpbf")
            self.station_queues["lpbf"] -= parts_in_batch
            self.station_busy["lpbf"] += 1
            self._record_wip_snapshot()

            service_start = self.env.now
            # Calculate batch cycle time: prep + (count * exposure) + cool
            base_time = batch_cfg.total_batch_time_min(parts_in_batch)
            actual_time = self._sample_cycle_time(base_time, lpbf_cfg.cycle_time_std_min)

            yield self.env.timeout(actual_time)

            service_end = self.env.now
            self.station_busy["lpbf"] -= 1
            self.station_parts_processed["lpbf"] += parts_in_batch
            self.station_busy_time["lpbf"] += actual_time
            self.resources["lpbf"].release(req)

            # Release all batch parts
            for part, done_event in batch_parts:
                part.station_history.append(
                    StationEvent(
                        station="lpbf",
                        queue_enter_time=service_start,
                        service_start_time=service_start,
                        service_end_time=service_end,
                        wait_duration_min=0.0,
                        service_duration_min=actual_time,
                    )
                )
                done_event.succeed()

            self._record_wip_snapshot()

    def _process_station(self, part: PartRecord, station_name: str) -> bool:
        """Simulate a standard non-batched workstation visit."""
        st_cfg = self.config.stations[station_name]
        queue_enter = self.env.now

        self._update_queue_integral(station_name)
        self.station_queues[station_name] += 1
        self.max_queue_length[station_name] = max(
            self.max_queue_length[station_name], self.station_queues[station_name]
        )
        self._record_wip_snapshot()

        req = self.resources[station_name].request()
        yield req

        service_start = self.env.now
        wait_duration = service_start - queue_enter

        self._update_queue_integral(station_name)
        self.station_queues[station_name] -= 1
        self.station_busy[station_name] += 1
        self._record_wip_snapshot()

        service_duration = self._sample_cycle_time(
            st_cfg.cycle_time_mean_min, st_cfg.cycle_time_std_min
        )
        yield self.env.timeout(service_duration)

        service_end = self.env.now
        self.station_busy[station_name] -= 1
        self.station_parts_processed[station_name] += 1
        self.station_busy_time[station_name] += service_duration
        self.resources[station_name].release(req)

        part.station_history.append(
            StationEvent(
                station=station_name,
                queue_enter_time=queue_enter,
                service_start_time=service_start,
                service_end_time=service_end,
                wait_duration_min=wait_duration,
                service_duration_min=service_duration,
            )
        )
        self._record_wip_snapshot()
        return True

    def _inspect_part(self, part: PartRecord) -> bool:
        """Simulate dye-penetrant surface inspection and rework decision."""
        yield from self._process_station(part, "inspection")

        q_cfg = self.config.quality
        is_defective = part.is_defective_physical

        # Non-destructive testing detection logic:
        # P(Flagged | Defective) = sensitivity (True Positive)
        # P(Flagged | Conforming) = 1 - specificity (False Positive)
        if is_defective:
            detected = bool(self.rng.random() < q_cfg.sensitivity)
        else:
            detected = bool(self.rng.random() > q_cfg.specificity)

        if not detected:
            # Inspection accepted the part
            if part.rework_count == 0:
                part.initial_inspection_passed = True
            part.is_conforming = True
            return True

        # Part was flagged as defective
        if part.rework_count == 0:
            part.initial_inspection_passed = False
            # First failure triggers rework cycle
            part.rework_count = 1

            # Rework bench process
            rework_duration = self._sample_cycle_time(
                q_cfg.rework_cycle_time_min, q_cfg.rework_cycle_time_min * 0.15
            )
            rework_start = self.env.now
            yield self.env.timeout(rework_duration)
            rework_end = self.env.now

            part.station_history.append(
                StationEvent(
                    station="rework_bench",
                    queue_enter_time=rework_start,
                    service_start_time=rework_start,
                    service_end_time=rework_end,
                    wait_duration_min=0.0,
                    service_duration_min=rework_duration,
                )
            )

            # Rework remediation probability
            if is_defective:
                success = bool(self.rng.random() < q_cfg.rework_success_rate)
                if success:
                    part.is_defective_physical = False  # Defect cured
                    part.rework_succeeded = True
                else:
                    part.rework_succeeded = False
            else:
                # Was a false alarm; part remains conforming
                part.rework_succeeded = True

            # Send back to inspection for re-inspection
            yield from self._process_station(part, "inspection")

            # Re-inspection evaluation
            if part.is_defective_physical:
                re_detected = bool(self.rng.random() < q_cfg.sensitivity)
            else:
                re_detected = bool(self.rng.random() > q_cfg.specificity)

            if not re_detected:
                part.is_conforming = True
                return True
            else:
                # Failed re-inspection -> Scrap!
                part.is_conforming = False
                part.is_scrapped = True
                part.status = "scrapped"
                return False
        else:
            # Already reworked once, cannot rework again -> Scrap!
            part.is_conforming = False
            part.is_scrapped = True
            part.status = "scrapped"
            return False

    def _part_lifecycle(self, part: PartRecord):
        """Manage full manufacturing flow for a bracket from entry to completion."""
        part.start_time_min = self.env.now

        if part.route == "conventional":
            # 1. Bandsaw Cutting
            yield from self._process_station(part, "saw")
            # 2. CNC Machining
            yield from self._process_station(part, "cnc_mill")
            # 3. Deburring
            yield from self._process_station(part, "deburr")

        elif part.route == "additive":
            # 1. Metal Powder-Bed Fusion (LPBF Batch)
            self._update_queue_integral("lpbf")
            self.station_queues["lpbf"] += 1
            self.max_queue_length["lpbf"] = max(
                self.max_queue_length["lpbf"], self.station_queues["lpbf"]
            )
            self._record_wip_snapshot()

            done_event = self.env.event()
            self.lpbf_staging.append((part, done_event))

            if self.lpbf_batch_trigger and not self.lpbf_batch_trigger.triggered:
                self.lpbf_batch_trigger.succeed()

            yield done_event

            # 2. Support Removal & Stress-Relief Furnace
            yield from self._process_station(part, "post_heat")
            # 3. Precision CNC Finishing
            yield from self._process_station(part, "cnc_finish")

        # 4. Shared Quality Inspection (Dye-Penetrant NDT)
        conforming = yield from self._inspect_part(part)

        if conforming:
            # 5. Packaging & Dispatch
            yield from self._process_station(part, "packaging")
            part.status = "conforming"
            part.is_conforming = True
        else:
            part.status = "scrapped"
            part.is_scrapped = True

        part.completion_time_min = self.env.now
        deadline_min = self.config.simulation.delivery_deadline_hours * 60.0
        part.on_time = part.completion_time_min <= deadline_min
        self._record_wip_snapshot()

    def _part_generator(self):
        """Generate jobs entering production according to schedule or arrival process."""
        target = self.config.simulation.target_demand_units
        horizon_min = self.config.simulation.simulation_horizon_hours * 60.0
        ratio = self.config.simulation.route_allocation_ratio
        conv_defect_prob = self.config.get_route_conventional().defect_probability
        add_defect_prob = self.config.get_route_additive().defect_probability

        # Calculate expected launch count factoring in anticipated yield loss (~92-95%)
        planned_starts = math.ceil(target / 0.92)

        # Space out arrivals across horizon or launch according to planned interarrival
        mean_interarrival = self.config.simulation.interarrival_mean_min

        for i in range(planned_starts):
            if self.env.now >= horizon_min:
                break

            # Route selection based on allocation ratio
            is_conventional = bool(self.rng.random() < ratio)
            route: Literal["conventional", "additive"] = (
                "conventional" if is_conventional else "additive"
            )

            # Intrinsic defect occurrence
            defect_prob = conv_defect_prob if is_conventional else add_defect_prob
            is_defective = bool(self.rng.random() < defect_prob)

            part = PartRecord(
                part_id=self.next_part_id,
                route=route,
                arrival_time_min=self.env.now,
                is_defective_physical=is_defective,
            )
            self.next_part_id += 1
            self.part_records.append(part)
            self._record_wip_snapshot()

            self.env.process(self._part_lifecycle(part))

            # Inter-arrival delay
            if self.config.simulation.arrival_mode == "poisson":
                dt = float(self.rng.exponential(mean_interarrival))
            else:
                # Scheduled batch releases with small ±10% schedule noise
                dt = max(
                    1.0,
                    float(self.rng.normal(mean_interarrival, mean_interarrival * 0.10)),
                )

            yield self.env.timeout(dt)

    def run(self) -> SimulationResults:
        """Execute the discrete-event simulation until the horizon expires."""
        horizon_min = self.config.simulation.simulation_horizon_hours * 60.0

        # Start breakdown processes for each workstation machine
        for st_name, st_cfg in self.config.stations.items():
            for m_idx in range(st_cfg.machine_count):
                self.env.process(self._breakdown_process(st_name, m_idx))

        # Start LPBF batch coordinator
        self.env.process(self._lpbf_batch_manager())

        # Start job releases
        self.env.process(self._part_generator())

        # Record initial WIP
        self._record_wip_snapshot()

        # Execute simulation
        self.env.run(until=horizon_min)

        # Final queue integral flush
        for st_name in self.config.stations:
            self._update_queue_integral(st_name)

        # Final WIP record
        self._record_wip_snapshot()

        # Build station statistics
        station_stats: dict[str, StationStats] = {}
        total_energy_kwh = 0.0

        for st_name, st_cfg in self.config.stations.items():
            busy_min = self.station_busy_time[st_name]
            downtime_min = self.station_downtime[st_name]
            parts_done = self.station_parts_processed[st_name]

            # Energy calculations
            busy_hours = busy_min / 60.0
            total_machine_hours = st_cfg.machine_count * (horizon_min / 60.0)
            idle_hours = max(0.0, total_machine_hours - busy_hours - (downtime_min / 60.0))

            active_energy = busy_hours * st_cfg.power_kw
            idle_energy = idle_hours * st_cfg.idle_power_kw
            total_energy_kwh += active_energy + idle_energy

            avg_queue = self.queue_time_integral[st_name] / horizon_min if horizon_min > 0 else 0.0

            station_stats[st_name] = StationStats(
                name=st_name,
                display_name=st_cfg.display_name,
                machine_count=st_cfg.machine_count,
                parts_processed=parts_done,
                total_busy_machine_min=busy_min,
                total_downtime_machine_min=downtime_min,
                breakdown_count=self.station_breakdown_count[st_name],
                active_energy_kwh=active_energy,
                idle_energy_kwh=idle_energy,
                avg_queue_length=avg_queue,
                max_queue_length=self.max_queue_length[st_name],
            )

        # High-level tallies
        started = len(self.part_records)
        completed = sum(1 for p in self.part_records if p.status in ("conforming", "scrapped"))
        conforming = sum(1 for p in self.part_records if p.status == "conforming")
        scrapped = sum(1 for p in self.part_records if p.status == "scrapped")
        in_sys = sum(1 for p in self.part_records if p.status == "in_progress")
        first_pass = sum(1 for p in self.part_records if p.initial_inspection_passed)
        reworked = sum(1 for p in self.part_records if p.rework_count > 0)
        rework_succ = sum(1 for p in self.part_records if p.rework_succeeded)

        # Quality escape & false alarm tracking
        escaped = sum(
            1 for p in self.part_records if p.status == "conforming" and p.is_defective_physical
        )
        false_alarms = sum(
            1
            for p in self.part_records
            if not p.initial_inspection_passed and not p.is_defective_physical
        )

        return SimulationResults(
            config=self.config,
            simulation_duration_min=horizon_min,
            parts_started=started,
            parts_completed=completed,
            conforming_parts=conforming,
            scrapped_parts=scrapped,
            parts_in_system=in_sys,
            first_pass_conforming=first_pass,
            rework_count=reworked,
            rework_success_count=rework_succ,
            missed_defects_escaped=escaped,
            false_alarm_rejections=false_alarms,
            part_records=self.part_records,
            station_stats=station_stats,
            breakdown_records=self.breakdown_records,
            wip_history=self.wip_history,
            total_energy_kwh=total_energy_kwh,
        )
