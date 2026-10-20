# Assumptions, Model Limitations, and Disclaimers

## 1. Educational Scope & Synthetic Data Notice

CellForge is an open-source educational and portfolio decision-support laboratory developed to illustrate principles of manufacturing systems design, discrete-event simulation, operations research, and engineering economics.

- **Synthetic Parameters**: All equipment purchase prices, labor wage rates, electricity tariffs, operational cycle times, defect rates, and reliability metrics ($\text{MTBF}/\text{MTTR}$) are **synthetic engineering approximations**.
- **No Physical Plant Validation**: This application is not calibrated to an operating commercial factory and must not be used as an audited basis for real equipment capital appropriation requests, binding supplier purchase orders, or legal contract bids.

---

## 2. Discrete-Event Simulation & Production Horizon

### Finite Campaign vs. Steady-State Warm-Up
- The simulation model default evaluates a **finite production campaign** ($T_{\text{horizon}} = 160\,\text{hours}$, representative of a 4-week single-shift contract) starting from an empty-and-idle cell state.
- **Warm-Up Policy**: Because job-shop contracts are discrete finite-horizon campaigns, transient start-up effects (initial pipe-filling) and ending work-in-progress drain are explicitly accounted for in the system mass balance. An optional warm-up filter is provided in configuration for steady-state queue analysis.
- **Arrival Scheduling**: Parts are released according to planned production schedules with stochastic release noise, rather than purely memoryless Poisson streams, reflecting standard ERP/MRP production releases.

---

## 3. Non-Destructive Testing (NDT) & Quality Limitations

> [!CAUTION]
> **Safety & Quality Certification Notice**:
> The quality inspection module models a simplified probabilistic representation of Liquid Penetrant Surface Testing (PT / FPI). It is **not** a qualified NDT inspection procedure and cannot replace certified inspection personnel or structural proof testing.

- **Standard Compliance**: The simulation does not implement qualified written procedures under **ASTM E1417** (*Standard Practice for Liquid Penetrant Testing*), **ISO 3452**, or **ASME Boiler and Pressure Vessel Code Section V**.
- **Inspector Qualification**: Real industrial NDT requires personnel certified to ASNT SNT-TC-1A, NAS 410, or EN ISO 9712 (Level II or Level III). CellForge applies generalized detection probabilities ($TPR$, $TNR$) and does not model optical visual acuity, ultraviolet illuminance thresholds ($>1000\,\mu\text{W/cm}^2$), penetrant dwell chemistry, or defect aspect-ratio thresholds.
- **Structural Integrity**: An accepted part in CellForge has passed simulated surface penetrant testing; it has **not** been certified free of subsurface defects (e.g., via radiographic computed tomography or ultrasonic testing).

---

## 4. Mechanical CAD Artifact Limitations

- **Parametric Geometry**: The provided OpenSCAD model (`cad/parametric_mounting_bracket.scad`) is a parametric constructive solid geometry artifact constructed to provide physical dimensions for process planning and cycle-time estimation.
- **No Structural Validation**: The mounting bracket has **not** been validated using Finite Element Analysis (FEA), fracture mechanics, or physical tensile/fatigue test bench experiments.
- **Export Validation**: Because the OpenSCAD headless CLI executable was not present in the automated build environment, export validation to binary STL was not executed automatically. The source file is authored to strict OpenSCAD CSG syntax.

---

## 5. Operations Research & Optimizer Discrepancy

- **Deterministic vs. Stochastic Modeling**: The Mixed-Integer Linear Program (MILP) solver in `cellforge.optimization` optimizes capacity against mean operational rates. It assumes deterministic linear flow.
- **Stochastic Congestion**: The SimPy simulation accounts for variance in machining durations, machine breakdowns, batch plate staging latency in LPBF, and queueing at the shared inspection booth. As predicted by Kingman's formula, realized stochastic throughput may be slightly lower than the deterministic MILP prediction when stations operate at high utilization.
- **No False Optimality Claims**: The MILP guarantees mathematical optimality **only** with respect to the deterministic linear programming formulation and its stated constraints, not for the complex stochastic queueing network.

---

## 6. Engineering Economics Assumptions

- **Straight-Line Depreciation**: Capital expenditures are amortized using standard straight-line hourly depreciation based on assumed useful operating hours ($15,000\text{--}25,000\,\text{hours}$).
- **Single Currency**: All financial figures are denominated in synthetic USD.
- **Taxation & Time Value of Money**: Tax depreciation shields, salvage scrap recovery value, inflation, and discounted cash flow / Net Present Value (NPV) discount rates are excluded to maintain transparency in direct unit manufacturing economics.
