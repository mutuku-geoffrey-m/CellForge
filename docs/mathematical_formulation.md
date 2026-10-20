# Mathematical Formulation & Analytical Models

## 1. Deterministic Capacity Planning Formulation (MILP)

The strategic capacity planning problem is formulated as a Mixed-Integer Linear Program (MILP), solved using `scipy.optimize.milp` via the HiGHS branch-and-cut engine.

### Sets and Indices
- $s \in \mathcal{S}$: Manufacturing workstations, $\mathcal{S} = \{\text{saw}, \text{cnc\_mill}, \text{deburr}, \text{lpbf}, \text{post\_heat}, \text{cnc\_finish}, \text{inspection}, \text{packaging}\}$.
- $r \in \mathcal{R}$: Production routes, $\mathcal{R} = \{\text{conv}, \text{add}\}$.

### Decision Variables
- $m_s \in \mathbb{Z}_{\ge 0}$: Number of parallel machines installed at workstation $s \in \mathcal{S}$.
- $x_{\text{conv}} \in \mathbb{Z}_{\ge 0}$: Number of bracket blanks launched on Route A (Conventional).
- $x_{\text{add}} \in \mathbb{Z}_{\ge 0}$: Number of bracket blanks launched on Route B (Additive).

### Parameters
- $D_{\text{target}}$: Minimum conforming parts required for delivery.
- $T_{\text{horizon}}$: Total operational horizon in hours (e.g. $160\,\text{hr}$).
- $B_{\text{budget}}$: Total capital equipment investment budget in USD.
- $\text{CAPEX}_s$: Capital purchase and commissioning cost for 1 machine at station $s$.
- $L_s$: Accounting depreciation life of station $s$ in operational hours (default $15,000\text{--}25,000\,\text{hr}$).
- $c_{\text{var}, r}$: Expected marginal variable cost per part on route $r$ (materials, labor, energy, consumables).
- $\tau_{s, r}$: Effective processing time required at station $s$ per part routed through $r$ (hours).
- $A_s$: Expected machine availability factor:
  $$A_s = \frac{\text{MTBF}_s}{\text{MTBF}_s + \text{MTTR}_s}$$
- $\eta_{\text{target}}$: Target planned utilization ceiling (default $0.85 = 85\%$) to mitigate queueing congestion.
- $Y_r$: Expected overall conforming yield along route $r$, factoring in first-pass acceptance and rework recovery:
  $$Y_r = (1 - p_{\text{def}, r}) + p_{\text{def}, r} \cdot \text{Sensitivity} \cdot p_{\text{rework\_succ}}$$

### Objective Function
Minimize total relevant manufacturing cost over the planning horizon:
$$\min_{m_s, x_r} \quad Z = \sum_{s \in \mathcal{S}} \left( \frac{\text{CAPEX}_s}{L_s} \cdot T_{\text{horizon}} \right) m_s + c_{\text{var}, \text{conv}} \cdot x_{\text{conv}} + c_{\text{var}, \text{add}} \cdot x_{\text{add}}$$

### Constraints

1. **Demand Satisfaction**:
   $$Y_{\text{conv}} \cdot x_{\text{conv}} + Y_{\text{add}} \cdot x_{\text{add}} \ge D_{\text{target}}$$

2. **Workstation Capacity Limits ($\forall s \in \mathcal{S}$)**:
   $$\tau_{s, \text{conv}} \cdot x_{\text{conv}} + \tau_{s, \text{add}} \cdot x_{\text{add}} \le m_s \cdot T_{\text{horizon}} \cdot A_s \cdot \eta_{\text{target}}$$

3. **Capital Budget Limit**:
   $$\sum_{s \in \mathcal{S}} \text{CAPEX}_s \cdot m_s \le B_{\text{budget}}$$

4. **Machine Bounds & Shared Station Mandate**:
   $$m_s \ge 1 \quad \forall s \in \{\text{inspection}, \text{packaging}\}$$
   $$m_{\min, s} \le m_s \le m_{\max, s} \quad \forall s \in \mathcal{S}$$

5. **Route-Equipment Coupling (Big-M Formulation)**:
   $$x_{\text{conv}} \le M \cdot m_s \quad \forall s \in \{\text{saw}, \text{cnc\_mill}, \text{deburr}\}$$
   $$x_{\text{add}} \le M \cdot m_s \quad \forall s \in \{\text{lpbf}, \text{post\_heat}, \text{cnc\_finish}\}$$
   Where $M = 500$ (an upper bound on total batch production).

---

## 2. Stochastic Dynamics & Kingman's Queueing Approximation

While the MILP planning model uses deterministic mean flow rates, the discrete-event SimPy simulation captures variance in processing times, batch staging, and machine failure events.

In single-server and multi-server queueing systems ($G/G/m$), the mean waiting time in queue $W_q$ is approximated by **Kingman's Heavy-Traffic Formula**:
$$W_q \approx \left( \frac{\rho^{\sqrt{2(m+1)}-1}}{1 - \rho} \right) \cdot \left( \frac{c_a^2 + c_s^2}{2} \right) \cdot \tau$$

Where:
- $\rho = \frac{\lambda \tau}{m}$ is the server traffic intensity (utilization).
- $c_a = \frac{\sigma_a}{\mu_a}$ is the coefficient of variation of part inter-arrival times.
- $c_s = \frac{\sigma_s}{\mu_s}$ is the coefficient of variation of machine cycle times.
- $\tau$ is mean processing time.

### Discrepancy Insight
As planned utilization $\rho \to 1.0$, the factor $\frac{\rho}{1 - \rho} \to \infty$, causing non-linear queue explosion and extended lead times. This explains why the stochastic simulation exhibits lower effective throughput and higher WIP than the ideal linear programming model predicts.

---

## 3. Work-in-Progress & Little's Law

In steady-state manufacturing systems, the average work-in-progress ($\overline{\text{WIP}}$), throughput ($\lambda$), and mean flow lead time ($W$) satisfy **Little's Law**:
$$\overline{\text{WIP}} = \lambda \cdot W$$

In CellForge, time-weighted average WIP is computed by integrating the continuous state step-function across simulation events:
$$\overline{\text{WIP}}_{\text{time-weighted}} = \frac{1}{T_{\text{horizon}}} \int_0^{T_{\text{horizon}}} N_{\text{WIP}}(t) \, dt = \frac{1}{T_{\text{horizon}}} \sum_{k=1}^{K-1} N_k \cdot (t_{k+1} - t_k)$$

CellForge validates model consistency by computing the relative Little's Law discrepancy percentage:
$$\epsilon_{\text{Little}} = \frac{\left| \overline{\text{WIP}}_{\text{time-weighted}} - (\lambda \cdot W) \right|}{\overline{\text{WIP}}_{\text{time-weighted}}} \times 100\%$$

---

## 4. Overall Equipment Effectiveness (OEE)

Workstation operational productivity is tracked using standard industrial OEE:
$$\text{OEE} = \text{Availability} \times \text{Performance} \times \text{Quality}$$

Where:
- **Availability ($A$)**:
  $$A = \frac{\text{Operating Time}}{\text{Planned Production Time}} = \frac{m_s \cdot T_{\text{horizon}} - T_{\text{downtime}}}{m_s \cdot T_{\text{horizon}}}$$
- **Performance ($P$)**:
  $$P = \frac{\text{Ideal Cycle Time} \times \text{Total Units Processed}}{\text{Operating Time}}$$
- **Quality ($Q$)**:
  $$Q = \frac{\text{Conforming Units Processed}}{\text{Total Units Processed}}$$

---

## 5. Economic Crossover & Break-Even Analysis

### Route Economic Crossover
Conventional subtractive manufacturing incurs higher upfront tooling, CAD/CAM setup, and fixture fabrication costs ($F_{\text{conv}} \approx \$1,800$), but lower marginal cost per bracket ($v_{\text{conv}}$).
Metal additive manufacturing incurs minimal tooling setup ($F_{\text{add}} \approx \$450$), but higher marginal material (metal powder) and machine hourly depreciation rates ($v_{\text{add}}$).

The analytical economic crossover volume $N_{\text{crossover}}$ is the batch quantity at which total manufacturing costs are identical:
$$F_{\text{conv}} + N_{\text{crossover}} \cdot v_{\text{conv}} = F_{\text{add}} + N_{\text{crossover}} \cdot v_{\text{add}}$$

Solving for $N_{\text{crossover}}$:
$$N_{\text{crossover}} = \frac{F_{\text{conv}} - F_{\text{add}}}{v_{\text{add}} - v_{\text{conv}}}$$

### Investment Payback Period
$$\text{Payback Period (Years)} = \frac{\sum_{s} \text{CAPEX}_s \cdot m_s}{\text{Annual Net Cash Flow}}$$
Where $\text{Annual Net Cash Flow} = (\text{Annual Conforming Volume} \times P_{\text{sale}}) - \text{Annual Operating Costs}$.
