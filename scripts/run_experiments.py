"""Reproducible benchmark experiment runner for CellForge.

Executes:
1. Baseline balanced scenario (120 units, 70/30 conv/add split)
2. Additive-centric scenario (80% metal LPBF allocation)
3. High-demand surge scenario (+50% demand stress test)
4. Quality stress scenario (high defect rate & degraded rework)
5. Mixed-Integer Linear Programming (MILP) capacity optimization
6. Stochastic simulation validation of the recommended configuration

Exports real calculated results to:
- outputs/sample_scenario_comparison.csv
- outputs/experiment_summary.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add src to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cellforge.config import default_cell_config
from cellforge.scenarios import ScenarioManager


def main():
    print("=" * 70)
    print("CellForge: Running Reproducible Manufacturing Lab Experiments")
    print("=" * 70)

    base_cfg = default_cell_config()
    mgr = ScenarioManager(base_cfg)

    print("\n[1/5] Executing standard benchmark scenarios...")
    scenario_results = mgr.run_all_standard_scenarios()
    for s_id, s_run in scenario_results.items():
        print(
            f"  -> Finished: {s_run.scenario_name} (Conforming: {s_run.metrics.conforming_parts} parts)"
        )

    print("\n[2/5] Formulating and solving Capacity Planning MILP...")
    target_demand = 140
    budget_usd = 650000.0
    print(f"  -> Target Demand: {target_demand} conforming brackets")
    print(f"  -> Equipment Budget: ${budget_usd:,.0f}")

    opt_run = mgr.run_optimization_scenario(
        target_demand=target_demand, capital_budget_usd=budget_usd
    )
    scenario_results["optimized"] = opt_run
    print(f"  -> Finished: {opt_run.scenario_name}")
    print(f"     Recommended CAPEX: ${opt_run.finances.total_installed_capex_usd:,.0f}")
    print(f"     Simulated Conforming Output: {opt_run.metrics.conforming_parts} parts")

    print("\n[3/5] Compiling side-by-side scenario comparison table...")
    df_comparison = ScenarioManager.build_comparison_dataframe(scenario_results)
    print(
        df_comparison[
            [
                "Scenario Name",
                "Conforming Parts",
                "Throughput (units/hr)",
                "Mean Lead Time (min)",
                "Cost / Conforming Part ($)",
            ]
        ]
    )

    # Ensure outputs directory exists
    outputs_dir = REPO_ROOT / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    csv_path = outputs_dir / "sample_scenario_comparison.csv"
    df_comparison.to_csv(csv_path, index=False)
    print(f"\n[4/5] Saved comparison table to: {csv_path}")

    # Generate JSON summary
    summary = {
        "metadata": {
            "project": "CellForge",
            "version": "0.1.0",
            "simulation_horizon_hours": base_cfg.simulation.simulation_horizon_hours,
            "random_seed": base_cfg.simulation.random_seed,
        },
        "scenarios": {},
    }

    for s_id, s_run in scenario_results.items():
        summary["scenarios"][s_id] = {
            "name": s_run.scenario_name,
            "description": s_run.description,
            "metrics": s_run.metrics.to_dict(),
            "finances": s_run.finances.to_dict(),
        }

    json_path = outputs_dir / "experiment_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[5/5] Saved structured summary to: {json_path}")

    print("\n" + "=" * 70)
    print("Experiments completed successfully! All output files generated from real runs.")
    print("=" * 70)


if __name__ == "__main__":
    main()
