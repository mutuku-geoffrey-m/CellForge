"""Production performance metrics and KPI calculations for CellForge.

Implements rigorous, mathematically verified industrial engineering metrics:
- Throughput & Flow Rates
- Lead Time Distributions (Mean, Median, P95)
- Little's Law WIP Validation
- True Machine Availability vs Utilization
- Standard Overall Equipment Effectiveness (OEE = A x P x Q)
- First-Pass Yield (FPY), Rework & Scrap Rates
- Workstation Bottleneck Identification
- On-Time Delivery (OTD)
- Energy & Environmental Intensity
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from cellforge.simulation import SimulationResults


@dataclass
class StationKPI:
    """Detailed operational KPIs for an individual workstation."""

    name: str
    display_name: str
    machine_count: int
    parts_processed: int
    availability_pct: float
    raw_utilization_pct: float
    effective_utilization_pct: float
    oee_pct: float
    oee_availability: float
    oee_performance: float
    oee_quality: float
    avg_queue_length: float
    max_queue_length: int
    mean_wait_time_min: float
    total_downtime_hours: float
    breakdown_count: int
    active_energy_kwh: float
    idle_energy_kwh: float


@dataclass
class PerformanceMetrics:
    """System-level manufacturing engineering key performance indicators."""

    # Volume & Throughput
    parts_started: int
    parts_completed: int
    conforming_parts: int
    scrapped_parts: int
    wip_ending: int
    time_weighted_avg_wip: float
    throughput_per_hour: float
    throughput_per_shift: float

    # Lead Time & Flow Dynamics (minutes)
    mean_lead_time_min: float
    median_lead_time_min: float
    std_lead_time_min: float
    p90_lead_time_min: float
    p95_lead_time_min: float
    mean_wait_time_min: float
    mean_processing_time_min: float
    flow_efficiency_pct: float  # Value-add processing time / Total Lead Time

    # Little's Law Consistency
    littles_law_expected_wip: float
    littles_law_error_pct: float

    # Quality & Reliability
    first_pass_yield_pct: float
    overall_yield_pct: float
    rework_rate_pct: float
    scrap_rate_pct: float
    on_time_delivery_pct: float
    ndt_escape_count: int
    ndt_false_alarms: int

    # Equipment & Operations
    bottleneck_station: str
    bottleneck_station_name: str
    bottleneck_utilization_pct: float
    system_avg_availability_pct: float
    system_avg_utilization_pct: float
    station_kpis: dict[str, StationKPI]

    # Energy Consumption
    total_energy_kwh: float
    energy_per_conforming_part_kwh: float

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to a flat/nested dictionary for reporting."""
        res = {k: v for k, v in self.__dict__.items() if k != "station_kpis"}
        res["station_kpis"] = {k: v.__dict__ for k, v in self.station_kpis.items()}
        return res


def calculate_metrics(results: SimulationResults) -> PerformanceMetrics:
    """Calculate all standard industrial engineering KPIs from simulation results.

    Guarantees division-by-zero protection and maintains strict mathematical consistency.
    """
    cfg = results.config
    horizon_hours = results.simulation_duration_min / 60.0
    shift_hours = cfg.simulation.shift_duration_hours

    # 1. Volume & Counts
    started = results.parts_started
    completed = results.parts_completed
    conforming = results.conforming_parts
    scrapped = results.scrapped_parts
    wip_ending = results.parts_in_system

    # Throughput
    th_per_hour = (conforming / horizon_hours) if horizon_hours > 0 else 0.0
    th_per_shift = th_per_hour * shift_hours

    # 2. Lead Time Statistics (Conforming Parts)
    conforming_records = [p for p in results.part_records if p.status == "conforming"]
    all_completed_records = [
        p for p in results.part_records if p.status in ("conforming", "scrapped")
    ]

    if conforming_records:
        lead_times = [p.total_lead_time_min for p in conforming_records]
        wait_times = [p.total_waiting_time_min for p in conforming_records]
        proc_times = [p.total_processing_time_min for p in conforming_records]

        mean_lt = float(np.mean(lead_times))
        median_lt = float(np.median(lead_times))
        std_lt = float(np.std(lead_times))
        p90_lt = float(np.percentile(lead_times, 90))
        p95_lt = float(np.percentile(lead_times, 95))

        mean_wait = float(np.mean(wait_times))
        mean_proc = float(np.mean(proc_times))
        flow_eff = (mean_proc / mean_lt * 100.0) if mean_lt > 0 else 0.0
    else:
        mean_lt = median_lt = std_lt = p90_lt = p95_lt = mean_wait = mean_proc = flow_eff = 0.0

    # 3. Work-in-Progress (WIP) Integration
    if results.wip_history:
        # Time-weighted average WIP: sum(WIP_i * dt_i) / Total_Time
        total_time = results.simulation_duration_min
        wip_integral = 0.0
        for i in range(len(results.wip_history) - 1):
            wip_val = results.wip_history[i].total_wip
            dt = results.wip_history[i + 1].time_min - results.wip_history[i].time_min
            wip_integral += wip_val * dt
        tw_avg_wip = wip_integral / total_time if total_time > 0 else 0.0
    else:
        tw_avg_wip = 0.0

    # Little's Law Validation: L = lambda * W
    # lambda = throughput per min, W = mean lead time in min
    th_per_min = th_per_hour / 60.0
    littles_wip = th_per_min * mean_lt
    if tw_avg_wip > 0:
        littles_error_pct = abs(tw_avg_wip - littles_wip) / tw_avg_wip * 100.0
    else:
        littles_error_pct = 0.0

    # 4. Quality Rates
    inspected_count = results.first_pass_conforming + results.rework_count
    if inspected_count > 0:
        fpy = (results.first_pass_conforming / inspected_count) * 100.0
        rework_rate = (results.rework_count / inspected_count) * 100.0
    else:
        fpy = 0.0
        rework_rate = 0.0

    overall_yield = (conforming / started * 100.0) if started > 0 else 0.0
    scrap_rate = (scrapped / started * 100.0) if started > 0 else 0.0

    if all_completed_records:
        on_time_count = sum(
            1 for p in all_completed_records if p.on_time and p.status == "conforming"
        )
        otd = (on_time_count / len(all_completed_records)) * 100.0
    else:
        otd = 100.0 if conforming > 0 else 0.0

    # 5. Station-Level KPIs, Availability & True OEE
    station_kpis: dict[str, StationKPI] = {}
    max_util = -1.0
    bottleneck_key = ""

    total_avail_sum = 0.0
    total_util_sum = 0.0

    for st_name, s_stat in results.station_stats.items():
        st_cfg = cfg.stations[st_name]
        m_count = s_stat.machine_count
        tot_planned_mach_min = m_count * results.simulation_duration_min

        # Availability = (Planned Time - Downtime) / Planned Time
        downtime_min = s_stat.total_downtime_machine_min
        operating_time_min = max(0.0, tot_planned_mach_min - downtime_min)
        availability = (
            (operating_time_min / tot_planned_mach_min) if tot_planned_mach_min > 0 else 1.0
        )

        # Raw Utilization = Busy Time / Planned Machine Time
        busy_min = s_stat.total_busy_machine_min
        raw_util = (busy_min / tot_planned_mach_min) if tot_planned_mach_min > 0 else 0.0

        # Effective Utilization = Busy Time / Operating (Uptime) Machine Time
        eff_util = (busy_min / operating_time_min) if operating_time_min > 0 else 0.0

        # OEE Components:
        # A = Availability (operating time / planned time)
        # P = Performance = (Ideal Cycle Time * Parts) / Operating Time
        # Q = Quality = Conforming Parts / Total Parts
        oee_a = availability
        ideal_time = st_cfg.cycle_time_mean_min
        ideal_total = s_stat.parts_processed * ideal_time
        oee_p = min(1.0, (ideal_total / operating_time_min)) if operating_time_min > 0 else 1.0

        # Station Quality factor: downstream stations inherit yield or defect check
        if st_name == "inspection":
            oee_q = results.first_pass_conforming / max(1, inspected_count)
        else:
            oee_q = 1.0 - (scrap_rate / 100.0)
        oee_q = max(0.0, min(1.0, oee_q))

        oee = (oee_a * oee_p * oee_q) * 100.0

        # Mean wait time at this station
        st_wait_times = []
        for p in results.part_records:
            for ev in p.station_history:
                if ev.station == st_name:
                    st_wait_times.append(ev.wait_duration_min)
        mean_st_wait = float(np.mean(st_wait_times)) if st_wait_times else 0.0

        # Bottleneck detection based on raw utilization & queue wait
        score = raw_util + (mean_st_wait / 1000.0)
        if score > max_util:
            max_util = score
            bottleneck_key = st_name

        total_avail_sum += availability
        total_util_sum += raw_util

        station_kpis[st_name] = StationKPI(
            name=st_name,
            display_name=s_stat.display_name,
            machine_count=m_count,
            parts_processed=s_stat.parts_processed,
            availability_pct=availability * 100.0,
            raw_utilization_pct=raw_util * 100.0,
            effective_utilization_pct=eff_util * 100.0,
            oee_pct=oee,
            oee_availability=oee_a * 100.0,
            oee_performance=oee_p * 100.0,
            oee_quality=oee_q * 100.0,
            avg_queue_length=s_stat.avg_queue_length,
            max_queue_length=s_stat.max_queue_length,
            mean_wait_time_min=mean_st_wait,
            total_downtime_hours=downtime_min / 60.0,
            breakdown_count=s_stat.breakdown_count,
            active_energy_kwh=s_stat.active_energy_kwh,
            idle_energy_kwh=s_stat.idle_energy_kwh,
        )

    num_stations = max(1, len(station_kpis))
    avg_sys_avail = (total_avail_sum / num_stations) * 100.0
    avg_sys_util = (total_util_sum / num_stations) * 100.0

    bottleneck_disp = (
        station_kpis[bottleneck_key].display_name if bottleneck_key in station_kpis else "None"
    )
    bottleneck_util = (
        station_kpis[bottleneck_key].raw_utilization_pct if bottleneck_key in station_kpis else 0.0
    )

    # 6. Energy Intensity
    tot_energy = results.total_energy_kwh
    energy_per_part = (tot_energy / conforming) if conforming > 0 else 0.0

    return PerformanceMetrics(
        parts_started=started,
        parts_completed=completed,
        conforming_parts=conforming,
        scrapped_parts=scrapped,
        wip_ending=wip_ending,
        time_weighted_avg_wip=tw_avg_wip,
        throughput_per_hour=th_per_hour,
        throughput_per_shift=th_per_shift,
        mean_lead_time_min=mean_lt,
        median_lead_time_min=median_lt,
        std_lead_time_min=std_lt,
        p90_lead_time_min=p90_lt,
        p95_lead_time_min=p95_lt,
        mean_wait_time_min=mean_wait,
        mean_processing_time_min=mean_proc,
        flow_efficiency_pct=flow_eff,
        littles_law_expected_wip=littles_wip,
        littles_law_error_pct=littles_error_pct,
        first_pass_yield_pct=fpy,
        overall_yield_pct=overall_yield,
        rework_rate_pct=rework_rate,
        scrap_rate_pct=scrap_rate,
        on_time_delivery_pct=otd,
        ndt_escape_count=results.missed_defects_escaped,
        ndt_false_alarms=results.false_alarm_rejections,
        bottleneck_station=bottleneck_key,
        bottleneck_station_name=bottleneck_disp,
        bottleneck_utilization_pct=bottleneck_util,
        system_avg_availability_pct=avg_sys_avail,
        system_avg_utilization_pct=avg_sys_util,
        station_kpis=station_kpis,
        total_energy_kwh=tot_energy,
        energy_per_conforming_part_kwh=energy_per_part,
    )
