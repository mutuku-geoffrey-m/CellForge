# Brag Plan: CellForge Manufacturing Lab

## What is this app?
CellForge is an open-source manufacturing decision-support platform combining discrete-event simulation (SimPy), Mixed-Integer Linear Programming (SciPy MILP), and engineering economics to optimize capacity and routing between conventional CNC machining and metal additive manufacturing (LPBF).

## The angle
Engineering rigor over marketing buzz. Most factory models rely on static spreadsheets that ignore machine breakdowns and queue congestion, or expensive proprietary black boxes. CellForge solves this transparently with real operations research, dynamic physics, and empirical benchmarking.

## Hook (first 2-3 seconds)
"Conventional CNC or Metal 3D Printing?" A high-stakes capital allocation question backed by dual technical cards comparing Aluminum 6061-T6 Billet vs. AlSi10Mg Spherical Powder.

## Key moments (the middle)
- The Engine: SciPy MILP integer solver coupled to SimPy discrete-event queueing simulation with MTBF/MTTR unreliability.
- The Discovery: High additive allocation explodes WIP (+31 units) due to 6.75-hour batch cycles.
- The Solution: MILP-optimized configuration slashes unit cost from $169.93 to $135.92, cuts lead time by 70%, and saves $95,000 in equipment CAPEX.

## Outro / punchline
"CellForge: Simulation, Optimization & Engineering Economics for Small-Batch Manufacturing." MIT Licensed, 22 verified automated tests, zero external dependencies.

## User flow worth showing
1. Order Ingestion & Routing Split (Conventional vs. Additive)
2. Stochastic Production Run (Queue congestion, NDT dye penetrant inspection, rework loops)
3. Strategic Optimization & Economic Crossover (CAPEX savings, payback acceleration, unit cost breakdown)

## Tone
- Preset: polished
- Creative direction: serious executive engineering showcase
- Interpretation: Restrained, elegant motion, high-contrast dark slate styling, precise numbers, zero emojis, confidence through clarity.

## Format: landscape — 1920x1080
## Duration: 25.0 seconds

## Visual identity (from the project)
- Background: #0a0f1d (Deep Navy / Industrial Slate)
- Surface Cards: #131d31 with #22324f borders
- Accent Blue: #0284c7 (Route A / CNC)
- Accent Purple: #9333ea (Route B / Additive)
- Accent Green: #10b981 (Optimal / Yield)
- Accent Amber: #f59e0b (Inspection / Quality)
- Text Primary: #f8fafc
- Text Secondary: #94a3b8
- Display font: Inter, system-ui, -apple-system, sans-serif
- Body font: Inter, system-ui, -apple-system, sans-serif

## Share copy (draft)
CellForge combines discrete-event simulation (SimPy) and integer optimization (SciPy MILP) to answer a fundamental manufacturing question: CNC machining or Metal 3D Printing? Open-source, verified with 22 automated stress tests, and built with Python.

## Audio direction
- Role: Warm, focused, modern corporate electronic bed.
- Music: `music.mp3` (business moves track, volume normalized at 0.35, gentle fade out at 23.5s).
- SFX posture: Subtle interface clicks on card entries and status badges.
- Restraint rule: No harsh booms, no video game sounds, no distracting audio cues.

## Storyboard

### Scene 1 — The Strategic Dilemma — 0.0s to 4.5s (4.5s)
- Hook typography: "Conventional CNC vs. Metal 3D Printing"
- Question: "How do you allocate $650,000 in equipment under machine breakdowns and quality scrap?"
- Two parallel route cards slide in:
  - Route A: Subtractive CNC Machining (6061-T6 Billet, $15.50/pc)
  - Route B: Metal Additive LPBF (AlSi10Mg Powder, $38.20/pc)
- Transitions: Soft crossfade.

### Scene 2 — The Dual Architecture — 4.5s to 11.0s (6.5s)
- Title: "CellForge: Hybrid Simulation & Optimization Engine"
- 3 core technical cards arrive sequentially:
  - 1. Deterministic Capacity Planning: Exact SciPy MILP Branch-and-Bound
  - 2. Stochastic Discrete-Event Simulation: SimPy Queues, MTBF/MTTR Failures, LPBF Batching
  - 3. Shared Quality & NDT Loop: Dye-Penetrant Inspection (TPR 94%), Closed-Loop Rework & Scrap
- Visual: Connected bus lines linking mathematical planning with stochastic factory physics.

### Scene 3 — The Empirical Benchmark — 11.0s to 18.5s (7.5s)
- Title: "160-Hour Production Campaign: Real Benchmark Data"
- Side-by-side performance cards with verified empirical results:
  - Baseline Cell: $169.93 / part | 238 min lead time | 28.5 yr payback
  - Additive-Centric: $220.23 / part | 2,078 min lead time (WIP bottleneck!)
  - MILP-Optimized: $135.92 / part | 71 min lead time | 6.3 yr payback
- Key Callout Pills:
  - "-20% Unit Cost"
  - "-70% Lead Time"
  - "$95,000 CAPEX Saved"
  - "100% On-Time Delivery"

### Scene 4 — Open Engineering Rigor & Outro — 18.5s to 25.0s (6.5s)
- Title: "CellForge Manufacturing Lab"
- Tagline: "Simulation, optimization, and engineering economics for small-batch manufacturing."
- Deliverable Badges:
  - [22 Automated Pytest & Heavy Stress Tests]
  - [Parametric OpenSCAD Mechanical CAD Model]
  - [Interactive Streamlit Decision-Support Dashboard]
  - [MIT Licensed | 100% Open Source | Python 3.11]
- Final Logo & GitHub Repository Call-to-Action.
