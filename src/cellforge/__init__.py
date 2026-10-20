"""CellForge: Simulation, optimization, and engineering economics for small-batch manufacturing.

A comprehensive discrete-event simulation, mixed-integer linear programming (MILP)
capacity planning, and engineering economics lab for comparing conventional subtractive
and additive metal manufacturing routes.
"""

from cellforge.config import CellConfig, SimulationConfig, default_cell_config
from cellforge.economics import EconomicsEngine, FinancialSummary
from cellforge.metrics import PerformanceMetrics, calculate_metrics
from cellforge.optimization import CapacityOptimizer, OptimizationResult
from cellforge.scenarios import ScenarioManager, get_standard_scenarios
from cellforge.simulation import SimulationEngine, SimulationResults

__version__ = "0.1.0"
__all__ = [
    "CapacityOptimizer",
    "CellConfig",
    "EconomicsEngine",
    "FinancialSummary",
    "OptimizationResult",
    "PerformanceMetrics",
    "ScenarioManager",
    "SimulationConfig",
    "SimulationEngine",
    "SimulationResults",
    "calculate_metrics",
    "default_cell_config",
    "get_standard_scenarios",
]
