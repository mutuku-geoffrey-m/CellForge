"""Configuration models and default parameters for CellForge manufacturing lab.

Defines dataclasses for workstation specifications, process routing,
quality/NDT inspection, economics, and discrete-event simulation controls.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass
class StationConfig:
    """Configuration for an individual manufacturing workstation.

    Attributes:
        name: Unique identifier for the station.
        display_name: Human-readable workstation title.
        machine_count: Number of identical parallel machines installed.
        cycle_time_mean_min: Expected operational cycle time per unit/batch in minutes.
        cycle_time_std_min: Standard deviation of cycle time in minutes (stochastic variation).
        power_kw: Rated electrical power demand in kilowatts during active processing.
        idle_power_kw: Base electrical power demand in kilowatts while idle.
        capital_cost_usd: Total equipment purchase/installation capital expenditure (CAPEX).
        useful_life_hours: Accounting depreciation horizon in operational hours.
        labor_ratio: Fractional operator allocation required per machine (e.g., 0.5 = 1 tech runs 2 machines).
        mtbf_hours: Mean Time Between Failures in operating hours (reliability).
        mttr_hours: Mean Time To Repair in hours (maintainability).
    """

    name: str
    display_name: str
    machine_count: int
    cycle_time_mean_min: float
    cycle_time_std_min: float
    power_kw: float
    idle_power_kw: float
    capital_cost_usd: float
    useful_life_hours: float = 20000.0
    labor_ratio: float = 0.5
    mtbf_hours: float = 120.0
    mttr_hours: float = 4.0

    def hourly_amortized_capital_cost(self) -> float:
        """Calculate hourly capital depreciation cost per machine ($/hr)."""
        if self.useful_life_hours <= 0:
            return 0.0
        return self.capital_cost_usd / self.useful_life_hours


@dataclass
class AdditiveBatchConfig:
    """Specific parameters for Laser Powder Bed Fusion (LPBF) batch builds.

    LPBF machines process multiple components simultaneously on a common build plate.
    The build duration consists of a fixed pre-heating, inert gas purging, recoating baseline
    plus exposure time proportional to part count.

    Attributes:
        build_plate_capacity: Maximum number of brackets that fit on one build substrate.
        chamber_prep_time_min: Fixed setup, preheating, and inert gas purging duration (minutes).
        per_part_exposure_min: Incremental laser scan and recoat time added per bracket (minutes).
        cooldown_time_min: Chamber cooling time before substrate extraction (minutes).
        powder_loss_ratio: Weight fraction of metal powder non-recyclable after sifting (support/re-melt loss).
    """

    build_plate_capacity: int = 4
    chamber_prep_time_min: float = 45.0
    per_part_exposure_min: float = 75.0
    cooldown_time_min: float = 60.0
    powder_loss_ratio: float = 0.15

    def total_batch_time_min(self, parts_in_batch: int) -> float:
        """Calculate total build cycle time for a given batch size in minutes."""
        count = max(1, min(parts_in_batch, self.build_plate_capacity))
        return (
            self.chamber_prep_time_min
            + (count * self.per_part_exposure_min)
            + self.cooldown_time_min
        )


@dataclass
class QualityInspectionConfig:
    """Non-Destructive Testing (NDT) surface inspection parameters.

    Models a dye-penetrant surface inspection (PT/FPI) stage.
    Inspection is probabilistic: defects are detected according to sensitivity,
    while false indications occur based on specificity.

    Attributes:
        inspection_time_mean_min: Mean time to clean, apply penetrant, dwell, develop, and inspect.
        inspection_time_std_min: Process time standard deviation in minutes.
        sensitivity: Probability of Detection (True Positive Rate) = P(Flagged | Defective).
        specificity: True Negative Rate = P(Accepted | Conforming).
                     False Positive Rate (false alarm) = 1.0 - specificity.
        rework_success_rate: Probability that a reworkable defect is cleared upon rework.
        consumable_cost_per_part_usd: Penetrant, emulsifier, developer, and cleaning solvent cost.
        rework_cycle_time_min: Additional bench rework/finishing duration before re-inspection.
        max_rework_cycles: Maximum allowed rework attempts (strictly 1 to prevent endless cycling).
    """

    inspection_time_mean_min: float = 12.0
    inspection_time_std_min: float = 2.0
    sensitivity: float = 0.94
    specificity: float = 0.97
    rework_success_rate: float = 0.80
    consumable_cost_per_part_usd: float = 4.50
    rework_cycle_time_min: float = 20.0
    max_rework_cycles: int = 1


@dataclass
class EconomicsConfig:
    """Unit economics, labor rates, energy tariffs, and material pricing (synthetic USD).

    Attributes:
        labor_rate_usd_per_hour: Fully burdened manufacturing technician wage ($/hr).
        electricity_rate_usd_per_kwh: Industrial electric power tariff ($/kWh).
        facility_overhead_usd_per_hour: Fixed shop floor overhead allocation per operating hour ($/hr).
        raw_material_conventional_usd: Cost of extruded aluminum 6061-T6 billet per bracket ($/unit).
        raw_material_additive_usd: Cost of AlSi10Mg spherical gas-atomized powder per bracket ($/unit).
        packaging_material_usd: Foam cushioning, protective bag, carton box, and barcode label ($/unit).
        rework_labor_rate_usd_per_hour: Technician rate for manual deburr/re-machining ($/hr).
        target_sale_price_usd: Baseline target market selling price for customer delivery ($/unit).
    """

    labor_rate_usd_per_hour: float = 38.00
    electricity_rate_usd_per_kwh: float = 0.14
    facility_overhead_usd_per_hour: float = 45.00
    raw_material_conventional_usd: float = 18.50
    raw_material_additive_usd: float = 42.00
    packaging_material_usd: float = 3.20
    rework_labor_rate_usd_per_hour: float = 42.00
    target_sale_price_usd: float = 185.00


@dataclass
class RouteConfig:
    """Process characteristics for a specific manufacturing route.

    Attributes:
        route_id: 'conventional' or 'additive'.
        display_name: Formatted route name.
        defect_probability: Intrinsic physical defect probability (surface tear, porosity, dimension).
        raw_material_cost_usd: Direct material cost per part.
        stations: Ordered sequence of workstation identifiers visited.
    """

    route_id: Literal["conventional", "additive"]
    display_name: str
    defect_probability: float
    raw_material_cost_usd: float
    stations: list[str]


@dataclass
class SimulationConfig:
    """Master simulation runtime parameters and production targets.

    Attributes:
        simulation_horizon_hours: Total operating window in hours (e.g. 160 hrs = 4 weeks single shift).
        target_demand_units: Required quantity of conforming mounting brackets to deliver.
        route_allocation_ratio: Fraction of production allocated to Route A (Conventional).
                                (1.0 - route_allocation_ratio) is routed to Route B (Additive).
        interarrival_mean_min: Mean job launch spacing in minutes.
        random_seed: Pseudorandom seed for repeatable stochastic runs.
        warm_up_hours: Optional initial warm-up period excluded from steady-state statistics.
        shift_duration_hours: Nominal shift duration (default 8.0 hours).
        delivery_deadline_hours: Customer contractual deadline in hours.
        arrival_mode: 'scheduled_batch' (fixed planned releases) or 'poisson' (stochastic arrivals).
    """

    simulation_horizon_hours: float = 160.0
    target_demand_units: int = 120
    route_allocation_ratio: float = 0.70
    interarrival_mean_min: float = 35.0
    random_seed: int = 42
    warm_up_hours: float = 0.0
    shift_duration_hours: float = 8.0
    delivery_deadline_hours: float = 160.0
    arrival_mode: Literal["scheduled_batch", "poisson"] = "scheduled_batch"


@dataclass
class CellConfig:
    """Complete manufacturing cell specification encompassing all equipment and parameters."""

    stations: dict[str, StationConfig] = field(default_factory=dict)
    additive_batch: AdditiveBatchConfig = field(default_factory=AdditiveBatchConfig)
    quality: QualityInspectionConfig = field(default_factory=QualityInspectionConfig)
    economics: EconomicsConfig = field(default_factory=EconomicsConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)

    def get_route_conventional(self) -> RouteConfig:
        """Construct conventional manufacturing route definition."""
        return RouteConfig(
            route_id="conventional",
            display_name="Route A: Conventional Subtractive (Bandsaw -> CNC Mill -> Deburr)",
            defect_probability=0.035,
            raw_material_cost_usd=self.economics.raw_material_conventional_usd,
            stations=["saw", "cnc_mill", "deburr", "inspection", "packaging"],
        )

    def get_route_additive(self) -> RouteConfig:
        """Construct metal additive manufacturing route definition."""
        return RouteConfig(
            route_id="additive",
            display_name="Route B: Metal Additive (LPBF -> Support/Heat -> CNC Finish)",
            defect_probability=0.075,
            raw_material_cost_usd=self.economics.raw_material_additive_usd,
            stations=["lpbf", "post_heat", "cnc_finish", "inspection", "packaging"],
        )

    def total_installed_capital_cost(self) -> float:
        """Calculate total capital expenditure for all installed equipment."""
        return sum(st.capital_cost_usd * st.machine_count for st in self.stations.values())

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration to a nested dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CellConfig:
        """Reconstruct configuration from a dictionary."""
        stations_dict = {}
        for name, st_data in data.get("stations", {}).items():
            stations_dict[name] = StationConfig(**st_data)

        additive_batch = AdditiveBatchConfig(**data.get("additive_batch", {}))
        quality = QualityInspectionConfig(**data.get("quality", {}))
        economics = EconomicsConfig(**data.get("economics", {}))
        simulation = SimulationConfig(**data.get("simulation", {}))

        return cls(
            stations=stations_dict,
            additive_batch=additive_batch,
            quality=quality,
            economics=economics,
            simulation=simulation,
        )

    def save_to_json(self, file_path: str | Path) -> None:
        """Save configuration to a JSON file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_json(cls, file_path: str | Path) -> CellConfig:
        """Load configuration from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


def default_cell_config() -> CellConfig:
    """Generate industrial default configuration for the CellForge mounting bracket cell.

    Machine parameters represent typical small-batch CNC and LPBF job shop equipment:
    - Bandsaw: Heavy-duty horizontal mitering bandsaw ($14,000)
    - CNC Mill: 3-Axis Vertical Machining Center ($95,000)
    - Deburring: Vibratory finishing & manual prep bench ($8,500)
    - LPBF Machine: Industrial metal powder-bed fusion printer ($320,000)
    - Post-Heat/Furnace: Atmosphere vacuum furnace & support removal station ($48,000)
    - CNC Finish: High-precision 3-axis finishing mill ($85,000)
    - Inspection: NDT dye-penetrant wash & UV darkroom inspection booth ($16,000)
    - Packaging: Packing, tagging, and strapping station ($6,000)
    """
    stations = {
        # Conventional Route Stations
        "saw": StationConfig(
            name="saw",
            display_name="Raw Material Cutting (Bandsaw)",
            machine_count=1,
            cycle_time_mean_min=8.0,
            cycle_time_std_min=1.2,
            power_kw=4.5,
            idle_power_kw=0.4,
            capital_cost_usd=14000.0,
            useful_life_hours=20000.0,
            labor_ratio=0.3,
            mtbf_hours=180.0,
            mttr_hours=3.0,
        ),
        "cnc_mill": StationConfig(
            name="cnc_mill",
            display_name="CNC Machining Center (Rough & Semi-Finish)",
            machine_count=2,
            cycle_time_mean_min=32.0,
            cycle_time_std_min=3.5,
            power_kw=18.0,
            idle_power_kw=1.8,
            capital_cost_usd=95000.0,
            useful_life_hours=25000.0,
            labor_ratio=0.5,
            mtbf_hours=140.0,
            mttr_hours=5.0,
        ),
        "deburr": StationConfig(
            name="deburr",
            display_name="Deburring & Surface Preparation",
            machine_count=1,
            cycle_time_mean_min=10.0,
            cycle_time_std_min=1.5,
            power_kw=2.5,
            idle_power_kw=0.2,
            capital_cost_usd=8500.0,
            useful_life_hours=15000.0,
            labor_ratio=1.0,
            mtbf_hours=300.0,
            mttr_hours=1.5,
        ),
        # Additive Route Stations
        "lpbf": StationConfig(
            name="lpbf",
            display_name="Laser Powder Bed Fusion (Metal 3D Printer)",
            machine_count=1,
            cycle_time_mean_min=380.0,  # Batch cycle time for 4 brackets
            cycle_time_std_min=15.0,
            power_kw=7.5,
            idle_power_kw=1.2,
            capital_cost_usd=320000.0,
            useful_life_hours=20000.0,
            labor_ratio=0.25,
            mtbf_hours=100.0,
            mttr_hours=8.0,
        ),
        "post_heat": StationConfig(
            name="post_heat",
            display_name="Support Removal & Stress-Relief Furnace",
            machine_count=1,
            cycle_time_mean_min=45.0,
            cycle_time_std_min=5.0,
            power_kw=12.0,
            idle_power_kw=0.8,
            capital_cost_usd=48000.0,
            useful_life_hours=20000.0,
            labor_ratio=0.5,
            mtbf_hours=220.0,
            mttr_hours=4.0,
        ),
        "cnc_finish": StationConfig(
            name="cnc_finish",
            display_name="CNC Precision Finishing Mill",
            machine_count=1,
            cycle_time_mean_min=18.0,
            cycle_time_std_min=2.0,
            power_kw=14.0,
            idle_power_kw=1.5,
            capital_cost_usd=85000.0,
            useful_life_hours=25000.0,
            labor_ratio=0.5,
            mtbf_hours=150.0,
            mttr_hours=4.0,
        ),
        # Shared Downstream Stations
        "inspection": StationConfig(
            name="inspection",
            display_name="Quality Inspection (Dye-Penetrant NDT)",
            machine_count=1,
            cycle_time_mean_min=12.0,
            cycle_time_std_min=1.8,
            power_kw=1.8,
            idle_power_kw=0.3,
            capital_cost_usd=16000.0,
            useful_life_hours=15000.0,
            labor_ratio=1.0,
            mtbf_hours=400.0,
            mttr_hours=2.0,
        ),
        "packaging": StationConfig(
            name="packaging",
            display_name="Final Packaging & Dispatch",
            machine_count=1,
            cycle_time_mean_min=6.0,
            cycle_time_std_min=0.8,
            power_kw=1.0,
            idle_power_kw=0.1,
            capital_cost_usd=6000.0,
            useful_life_hours=15000.0,
            labor_ratio=1.0,
            mtbf_hours=500.0,
            mttr_hours=1.0,
        ),
    }

    return CellConfig(
        stations=stations,
        additive_batch=AdditiveBatchConfig(
            build_plate_capacity=4,
            chamber_prep_time_min=45.0,
            per_part_exposure_min=75.0,  # 4 parts => 45 + 300 + 60 = 405 min
            cooldown_time_min=60.0,
            powder_loss_ratio=0.15,
        ),
        quality=QualityInspectionConfig(
            inspection_time_mean_min=12.0,
            inspection_time_std_min=1.8,
            sensitivity=0.94,
            specificity=0.97,
            rework_success_rate=0.80,
            consumable_cost_per_part_usd=4.50,
            rework_cycle_time_min=20.0,
            max_rework_cycles=1,
        ),
        economics=EconomicsConfig(
            labor_rate_usd_per_hour=38.00,
            electricity_rate_usd_per_kwh=0.14,
            facility_overhead_usd_per_hour=45.00,
            raw_material_conventional_usd=18.50,
            raw_material_additive_usd=42.00,
            packaging_material_usd=3.20,
            rework_labor_rate_usd_per_hour=42.00,
            target_sale_price_usd=185.00,
        ),
        simulation=SimulationConfig(
            simulation_horizon_hours=160.0,
            target_demand_units=120,
            route_allocation_ratio=0.70,
            interarrival_mean_min=35.0,
            random_seed=42,
            warm_up_hours=0.0,
            shift_duration_hours=8.0,
            delivery_deadline_hours=160.0,
            arrival_mode="scheduled_batch",
        ),
    )
