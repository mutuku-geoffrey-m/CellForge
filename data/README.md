# CellForge Simulation Data & Synthetic Parameters

This directory contains the baseline industrial configuration dataset used by CellForge.

## Files

- `default_parameters.json`: Complete serialized baseline cell configuration, including workstation machine counts, cycle times, power ratings, capital expenditures, reliability parameters (MTBF/MTTR), NDT quality parameters, and economic unit rates.

## Synthetic Data Notice

All operational, equipment, and cost parameters in `default_parameters.json` are **synthetic engineering approximations** developed for academic and educational decision-support modeling. They represent plausible order-of-magnitude values for small-batch CNC machining and Laser Powder Bed Fusion (LPBF) additive manufacturing, but do not represent certified supplier quotes, real factory proprietary data, or audited commercial pricing.

## Workstation Parameter Summary

| Station Key | Workstation Name | Default Units | Mean Cycle (min) | Std Dev (min) | Power (kW) | CAPEX (USD) | MTBF (hr) | MTTR (hr) |
|---|---|---|---|---|---|---|---|---|
| `saw` | Raw Material Cutting (Bandsaw) | 1 | 8.0 | 1.2 | 4.5 | \$14,000 | 180.0 | 3.0 |
| `cnc_mill` | CNC Machining Center (Rough) | 2 | 32.0 | 3.5 | 18.0 | \$95,000 | 140.0 | 5.0 |
| `deburr` | Deburring & Surface Preparation | 1 | 10.0 | 1.5 | 2.5 | \$8,500 | 300.0 | 1.5 |
| `lpbf` | Laser Powder Bed Fusion (Batch 4) | 1 | 380.0 | 15.0 | 7.5 | \$320,000 | 100.0 | 8.0 |
| `post_heat` | Support Removal & Vacuum Furnace | 1 | 45.0 | 5.0 | 12.0 | \$48,000 | 220.0 | 4.0 |
| `cnc_finish` | Precision CNC Finishing Mill | 1 | 18.0 | 2.0 | 14.0 | \$85,000 | 150.0 | 4.0 |
| `inspection` | Shared NDT Dye-Penetrant Booth | 1 | 12.0 | 1.8 | 1.8 | \$16,000 | 400.0 | 2.0 |
| `packaging` | Final Packaging & Dispatch | 1 | 6.0 | 0.8 | 1.0 | \$6,000 | 500.0 | 1.0 |
