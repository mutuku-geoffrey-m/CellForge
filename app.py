"""CellForge: Industrial Manufacturing Operations Workstation (IMOW).

Interactive decision-support laboratory comparing conventional CNC subtractive machining
and laser powder-bed fusion (LPBF) additive manufacturing routes for custom industrial brackets.
Designed to industrial engineering terminal standards (Public Sans + JetBrains Mono, flat surfaces, zero neons).
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Ensure src/ is on sys.path regardless of execution directory
CURRENT_DIR = Path(__file__).resolve().parent
SRC_DIR = CURRENT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cellforge.config import default_cell_config
from cellforge.economics import EconomicsEngine
from cellforge.metrics import calculate_metrics
from cellforge.optimization import CapacityOptimizer
from cellforge.scenarios import ScenarioManager
from cellforge.simulation import SimulationEngine
from cellforge.validation import validate_config, verify_simulation_results

# =============================================================================
# Streamlit Application Configuration & Data-Terminal Workstation Styling
# =============================================================================

st.set_page_config(
    page_title="CellForge // Industrial Operations Workstation",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS: Data-Terminal Design System (taste-skill + awesome-design-md + web-design-guidelines)
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Public+Sans:wght@400;500;600;700&display=swap');

    /* Color Tokens: data-terminal dark palette */
    :root {
        --ground: #171719;
        --surface: #131217;
        --raised: #212023;
        --border: #222224;
        --rule: #1b1a1f;
        --control: #2a2a2e;
        --control-border: #3a3a3e;
        --text: #ffffff;
        --muted: #8a8c92;
        --accent: #4a8ad6;
        --positive: #44a282;
        --negative: #e5566f;
        --warning: #d9a441;
    }

    /* Global Application Root */
    .stApp {
        background-color: var(--ground);
        color: #dedee0;
        font-family: 'Public Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Zero Gradients, Zero Box Shadows */
    *, *::before, *::after {
        box-shadow: none !important;
    }

    /* Header Bar */
    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #111113;
        border-right: 1px solid var(--border);
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] li {
        font-size: 0.80rem;
        color: var(--muted);
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.86rem;
        letter-spacing: 0.05em;
        color: var(--text);
        text-transform: uppercase;
    }

    /* Workstation Header Bar */
    .workstation-header {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 14px 18px;
        margin-bottom: 16px;
    }
    .workstation-title {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.10rem;
        font-weight: 700;
        color: var(--text);
        letter-spacing: 0.05em;
    }
    .workstation-subtitle {
        font-size: 0.78rem;
        color: var(--muted);
        margin-top: 3px;
        line-height: 1.4;
    }
    .workstation-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 8px;
    }
    .chip {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.70rem;
        font-weight: 600;
        padding: 2px 7px;
        border-radius: 3px;
        border: 1px solid var(--border);
        background: var(--raised);
        color: var(--muted);
        letter-spacing: 0.04em;
    }
    .chip-accent {
        border-color: #3568a3;
        color: #6ba6ed;
        background: #17212e;
    }
    .chip-success {
        border-color: #347e65;
        color: #5fc39c;
        background: #15241f;
    }
    .chip-warning {
        border-color: #b8882e;
        color: #e6b758;
        background: #252014;
    }

    /* Flat High-Density KPI Cards (Typography Driven) */
    .imow-kpi-card {
        background-color: var(--surface);
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 12px 14px;
        margin-bottom: 10px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 94px;
    }
    .imow-kpi-label {
        font-family: 'Public Sans', sans-serif;
        font-size: 0.70rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--muted);
    }
    .imow-kpi-value {
        font-family: 'JetBrains Mono', monospace;
        font-variant-numeric: tabular-nums;
        font-size: 1.50rem;
        font-weight: 700;
        color: var(--text);
        letter-spacing: -0.02em;
        line-height: 1.15;
        margin-top: 4px;
    }
    .imow-kpi-sub {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        color: var(--muted);
        margin-top: 4px;
    }

    /* Industrial Panel Containers */
    .imow-panel {
        background-color: var(--surface);
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 14px 16px;
        margin-bottom: 12px;
    }
    .imow-panel-header {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.80rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        color: #e2e2e4;
        text-transform: uppercase;
        margin-bottom: 8px;
        border-bottom: 1px solid var(--border);
        padding-bottom: 6px;
    }

    /* Custom Streamlit Tabs Override */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 1px solid var(--border);
        background-color: transparent;
        padding-bottom: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: var(--surface);
        border: 1px solid var(--border);
        border-radius: 3px;
        padding: 6px 14px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.76rem;
        font-weight: 500;
        color: var(--muted);
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: var(--raised);
        color: var(--text);
        border-color: #3a3a3e;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: var(--raised);
        border-color: var(--accent);
        color: var(--text);
        font-weight: 600;
        border-bottom: 2px solid var(--accent);
    }

    /* Buttons */
    div.stButton > button {
        background-color: var(--raised) !important;
        color: var(--text) !important;
        border: 1px solid var(--control-border) !important;
        border-radius: 3px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.76rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.03em !important;
        padding: 6px 14px !important;
    }
    div.stButton > button:hover {
        background-color: #2a2a2e !important;
        border-color: var(--accent) !important;
        color: #6ba6ed !important;
    }
    div.stButton > button[kind="primary"] {
        background-color: #3568a3 !important;
        border-color: var(--accent) !important;
        color: #ffffff !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #285489 !important;
        border-color: #5593e0 !important;
        color: #ffffff !important;
    }

    /* Inputs, Sliders & Tables */
    .stNumberInput input, .stTextInput input {
        background-color: var(--ground) !important;
        border: 1px solid var(--border) !important;
        color: var(--text) !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.80rem !important;
        border-radius: 3px !important;
    }
    .stNumberInput input:focus, .stTextInput input:focus {
        border-color: var(--accent) !important;
        outline: none !important;
    }

    /* Sliders */
    .stSlider [data-baseweb="slider"] {
        margin-top: 4px;
    }
    .stSlider [role="slider"] {
        background-color: var(--accent) !important;
        border: 2px solid var(--surface) !important;
    }
    .stSlider div[data-testid="stThumbValue"] {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        color: var(--muted);
    }

    /* Expanders */
    [data-testid="stExpander"] {
        background-color: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 4px !important;
    }
    [data-testid="stExpander"] details summary {
        background-color: var(--raised) !important;
        border-radius: 3px !important;
        padding: 7px 12px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        color: #dedee0 !important;
        letter-spacing: 0.04em !important;
    }
    [data-testid="stExpander"] details summary:hover {
        color: var(--accent) !important;
    }

    /* Data Tables */
    div[data-testid="stTable"] table {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem;
        background-color: var(--surface);
        border: 1px solid var(--border);
        color: #dedee0;
    }
    div[data-testid="stTable"] th {
        background-color: var(--raised);
        color: var(--muted);
        font-weight: 600;
        border-bottom: 1px solid var(--border);
        text-transform: uppercase;
        font-size: 0.70rem;
        letter-spacing: 0.05em;
    }
    div[data-testid="stTable"] td {
        border-bottom: 1px solid var(--rule);
    }
    .stDataFrame {
        border: 1px solid var(--border);
        border-radius: 4px;
    }

    /* Status Annunciator Alerts */
    [data-testid="stAlert"] {
        background-color: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 4px !important;
        color: #dedee0 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.78rem !important;
    }
    [data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
        color: #dedee0 !important;
        font-size: 0.78rem !important;
    }

    /* Download Buttons */
    .stDownloadButton > button {
        background-color: var(--raised) !important;
        color: var(--text) !important;
        border: 1px solid var(--control-border) !important;
        border-radius: 3px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.76rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.03em !important;
        padding: 6px 14px !important;
    }
    .stDownloadButton > button:hover {
        background-color: #2a2a2e !important;
        border-color: var(--accent) !important;
        color: #6ba6ed !important;
    }

    /* Hairline Scrollbars */
    ::-webkit-scrollbar {
        width: 5px;
        height: 5px;
    }
    ::-webkit-scrollbar-track {
        background: var(--ground);
    }
    ::-webkit-scrollbar-thumb {
        background: #2a2a2e;
        border-radius: 2px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #3a3a3e;
    }

    /* Focus Rings & Accessibility */
    button:focus-visible, input:focus-visible, select:focus-visible {
        outline: 2px solid var(--accent) !important;
        outline-offset: 1px !important;
    }

    /* Code Blocks */
    code {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem;
        background-color: var(--raised);
        color: #6ba6ed;
        padding: 2px 5px;
        border-radius: 3px;
        border: 1px solid var(--border);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def style_chart(fig: go.Figure, height: int = 340, title: str | None = None) -> go.Figure:
    """Apply consistent industrial workstation dark styling to a Plotly figure."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#131217",
        plot_bgcolor="#131217",
        font={
            "family": "JetBrains Mono, Public Sans, -apple-system, sans-serif",
            "color": "#8a8c92",
            "size": 11,
        },
        title={
            "text": title if title else (fig.layout.title.text if fig.layout.title else ""),
            "font": {
                "family": "JetBrains Mono, monospace",
                "size": 12,
                "color": "#ffffff",
            },
            "x": 0.01,
            "xanchor": "left",
        },
        height=height,
        margin={"l": 40, "r": 20, "t": 40, "b": 40},
        xaxis={
            "gridcolor": "#222224",
            "zerolinecolor": "#3a3a3e",
            "linecolor": "#3a3a3e",
            "tickfont": {"size": 10, "color": "#8a8c92"},
        },
        yaxis={
            "gridcolor": "#222224",
            "zerolinecolor": "#3a3a3e",
            "linecolor": "#3a3a3e",
            "tickfont": {"size": 10, "color": "#8a8c92"},
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1.0,
            "font": {"size": 10, "color": "#bdbdc0"},
        },
    )
    return fig


def render_kpi(label: str, value: str, subtext: str, badge: str | None = None) -> str:
    """Render a flat, high-density industrial data-terminal KPI card."""
    badge_html = f"<span class='chip'>{badge}</span>" if badge else ""
    return f"""
    <div class="imow-kpi-card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span class="imow-kpi-label">{label}</span>
            {badge_html}
        </div>
        <div class="imow-kpi-value">{value}</div>
        <div class="imow-kpi-sub">{subtext}</div>
    </div>
    """


# =============================================================================
# Session State Caching & Model Execution Helpers
# =============================================================================

if "base_config" not in st.session_state:
    st.session_state.base_config = default_cell_config()

if "baseline_results" not in st.session_state:
    engine = SimulationEngine(st.session_state.base_config)
    res = engine.run()
    metrics = calculate_metrics(res)
    finances = EconomicsEngine(st.session_state.base_config).calculate_finances(res, metrics)
    st.session_state.baseline_results = res
    st.session_state.baseline_metrics = metrics
    st.session_state.baseline_finances = finances

if "custom_results" not in st.session_state:
    st.session_state.custom_results = None
    st.session_state.custom_metrics = None
    st.session_state.custom_finances = None

if "opt_result" not in st.session_state:
    st.session_state.opt_result = None

# =============================================================================
# Application Sidebar: Workstation Global Parameters & Presets
# =============================================================================

with st.sidebar:
    st.markdown("### CELLFORGE // CONTROLS")
    st.caption("Industrial Discrete-Event Simulation & Capacity Optimization")
    st.markdown("---")

    st.markdown("**Operational Presets**")
    p_col1, p_col2 = st.columns(2)
    with p_col1:
        if st.button("Balanced Hybrid", use_container_width=True):
            st.session_state.base_config.simulation.route_allocation_ratio = 0.60
            st.session_state.base_config.simulation.target_demand_units = 120
            st.rerun()
        if st.button("Pure Subtractive", use_container_width=True):
            st.session_state.base_config.simulation.route_allocation_ratio = 1.00
            st.session_state.base_config.simulation.target_demand_units = 120
            st.rerun()
    with p_col2:
        if st.button("Pure Additive", use_container_width=True):
            st.session_state.base_config.simulation.route_allocation_ratio = 0.00
            st.session_state.base_config.simulation.target_demand_units = 120
            st.rerun()
        if st.button("Demand Surge", use_container_width=True):
            st.session_state.base_config.simulation.route_allocation_ratio = 0.50
            st.session_state.base_config.simulation.target_demand_units = 250
            st.rerun()

    st.markdown("---")
    st.markdown("**Global Simulation Controls**")
    horizon_hours = st.slider(
        "Simulation Horizon (Hours)",
        min_value=40.0,
        max_value=320.0,
        value=float(st.session_state.base_config.simulation.simulation_horizon_hours),
        step=20.0,
        help="Simulated operational window (160 hours = 4 work weeks of single 8h shifts).",
    )
    target_demand = st.number_input(
        "Target Contract Demand (Units)",
        min_value=20,
        max_value=500,
        value=int(st.session_state.base_config.simulation.target_demand_units),
        step=10,
        help="Contractual production volume of conforming brackets.",
    )
    route_ratio = st.slider(
        "Route A (Conventional CNC) Ratio",
        min_value=0.0,
        max_value=1.0,
        value=float(st.session_state.base_config.simulation.route_allocation_ratio),
        step=0.05,
        help="Fraction of parts routed to CNC Subtractive (remainder to LPBF Additive).",
    )
    seed = st.number_input(
        "Monte Carlo Seed (Reproducibility)",
        min_value=1,
        max_value=99999,
        value=int(st.session_state.base_config.simulation.random_seed),
        step=1,
    )

    st.markdown("---")
    st.markdown(
        """
        **Workstation Routing Architecture:**
        - **Target Workpiece**: Industrial Mounting Bracket
        - **Route A**: Saw -> CNC Milling -> Deburr
        - **Route B**: LPBF (Batch 4) -> Heat Treat -> CNC Finish
        - **Shared**: Dye-Penetrant NDT & Packaging
        """
    )
    st.caption("CellForge Decision-Support Laboratory | MIT License")

# Update base config parameters if modified in sidebar
st.session_state.base_config.simulation.simulation_horizon_hours = horizon_hours
st.session_state.base_config.simulation.target_demand_units = target_demand
st.session_state.base_config.simulation.route_allocation_ratio = route_ratio
st.session_state.base_config.simulation.random_seed = seed

# =============================================================================
# Workstation Top Telemetry Header
# =============================================================================

st.markdown(
    """
    <div class="workstation-header">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">
            <div>
                <div class="workstation-title">CELLFORGE // INDUSTRIAL OPERATIONS WORKSTATION</div>
                <div class="workstation-subtitle">Flexible Manufacturing Operations · AlSi10Mg LPBF Additive vs 6061-T6 CNC Subtractive Decision Support</div>
            </div>
            <div class="workstation-chips">
                <span class="chip chip-accent">[ENGINE: SIMPY 4.1]</span>
                <span class="chip chip-accent">[SOLVER: SCIPY MILP]</span>
                <span class="chip chip-success">[STATUS: OPERATIONAL]</span>
                <span class="chip">[ROUTING: DUAL-PATH CNC/LPBF]</span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# Main Workstation Tabs
# =============================================================================

tab_overview, tab_sim, tab_opt, tab_econ, tab_scenarios, tab_notes = st.tabs(
    [
        "01 // CELL TELEMETRY & MASS BALANCE",
        "02 // SIMULATION STUDIO & FLEET TUNING",
        "03 // CAPACITY OPTIMIZATION (MILP)",
        "04 // ECONOMICS & QUALITY (NDT)",
        "05 // BENCHMARK SCENARIO MATRIX",
        "06 // MATHEMATICAL FORMULATIONS",
    ]
)

# =============================================================================
# TAB 1: CELL TELEMETRY & MASS BALANCE
# =============================================================================

with tab_overview:
    bm = st.session_state.baseline_metrics
    bf = st.session_state.baseline_finances

    # Headline Factory Telemetry Strip (5-Column Flat KPI Cards)
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.markdown(
            render_kpi(
                "Conforming Output",
                f"{bm.conforming_parts} <span style='font-size: 0.90rem; color: #8a8c92;'>UNITS</span>",
                f"Overall Yield: {bm.overall_yield_pct:.1f}%",
                f"STARTED: {bm.parts_started}",
            ),
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            render_kpi(
                "Throughput Rate",
                f"{bm.throughput_per_hour:.2f} <span style='font-size: 0.90rem; color: #8a8c92;'>/ HR</span>",
                f"Shift Rate: {bm.throughput_per_shift:.1f} / 8h",
                "FLOW",
            ),
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            render_kpi(
                "Mean Lead Time",
                f"{bm.mean_lead_time_min / 60.0:.1f} <span style='font-size: 0.90rem; color: #8a8c92;'>HRS</span>",
                f"Median: {bm.median_lead_time_min / 60.0:.1f} hrs",
                "CYCLE",
            ),
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            render_kpi(
                "Unit Manufacturing Cost",
                f"${bf.cost_per_conforming_part_usd:.2f}",
                f"Amortized Cap: ${bf.cost_breakdown.capital_amortized_usd:,.0f}",
                "UNIT COST",
            ),
            unsafe_allow_html=True,
        )
    with k5:
        b_name = bm.bottleneck_station_name.split("(")[0].strip()
        st.markdown(
            render_kpi(
                "Critical Bottleneck",
                b_name.upper(),
                f"Station Util: {bm.bottleneck_utilization_pct:.1f}%",
                "BINDING",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)

    # Material Flow Network & Workstation Specifications
    c_sankey, c_routing = st.columns([3, 2])

    with c_sankey:
        labels = [
            "Raw Stock Release",  # 0
            "Route A: Bandsaw Cut",  # 1
            "Route A: CNC Machining",  # 2
            "Route A: Deburr & Prep",  # 3
            "Route B: LPBF Build (Batch)",  # 4
            "Route B: Stress Relief",  # 5
            "Route B: CNC Finishing",  # 6
            "Shared NDT Inspection",  # 7
            "Rework Bench",  # 8
            "Final Packaging",  # 9
            "Conforming Finished Goods",  # 10
            "Scrapped Material",  # 11
        ]

        total_started = bm.parts_started
        conv_s = int(total_started * route_ratio)
        add_s = total_started - conv_s
        first_pass = bm.parts_started * (bm.first_pass_yield_pct / 100.0)
        rework_vol = bm.rework_rate_pct / 100.0 * total_started
        rework_ok = rework_vol * 0.8
        scrap_vol = bm.scrapped_parts
        conforming_vol = bm.conforming_parts

        fig_sankey = go.Figure(
            data=[
                go.Sankey(
                    node={
                        "pad": 14,
                        "thickness": 16,
                        "line": {"color": "#222224", "width": 1},
                        "label": labels,
                        "color": [
                            "#4a4a4e",  # 0: Raw Stock
                            "#4a8ad6",  # 1: Bandsaw Cut (Route A)
                            "#3568a3",  # 2: CNC Machining (Route A)
                            "#284f7d",  # 3: Deburr & Prep (Route A)
                            "#8a8c92",  # 4: LPBF Build (Route B)
                            "#717379",  # 5: Stress Relief (Route B)
                            "#595a5f",  # 6: CNC Finishing (Route B)
                            "#d9a441",  # 7: Shared NDT Inspection
                            "#b8882e",  # 8: Rework Bench
                            "#347e65",  # 9: Final Packaging
                            "#44a282",  # 10: Conforming Finished Goods
                            "#e5566f",  # 11: Scrapped Material
                        ],
                    },
                    link={
                        "source": [0, 0, 1, 2, 0, 4, 5, 3, 6, 7, 7, 8, 8, 9],
                        "target": [1, 4, 2, 3, 4, 5, 6, 7, 7, 9, 8, 7, 11, 10],
                        "value": [
                            conv_s,
                            add_s,
                            conv_s,
                            conv_s,
                            add_s,
                            add_s,
                            add_s,
                            conv_s,
                            add_s,
                            max(1, first_pass),
                            max(1, rework_vol),
                            max(1, rework_ok),
                            max(1, scrap_vol),
                            conforming_vol,
                        ],
                        "color": "rgba(74, 138, 214, 0.16)",
                    },
                )
            ]
        )
        style_chart(fig_sankey, height=360, title="MATERIAL MASS BALANCE & QUALITY ROUTING NETWORK")
        st.plotly_chart(fig_sankey, use_container_width=True)

    with c_routing:
        st.markdown(
            """
            <div class="imow-panel">
                <div class="imow-panel-header">MANUFACTURING PROCESS & ROUTING SPECIFICATIONS</div>
                <div style="font-size: 0.80rem; line-height: 1.5; color: #8a8c92;">
                    <p><strong style="color: #4a8ad6;">[ROUTE A: CNC SUBTRACTIVE]</strong><br>
                    Raw 6061-T6 aluminum extrusion billet cut on horizontal bandsaw, roughed & contoured on 3-axis CNC vertical milling center, vibratory deburred.</p>
                    <p><strong style="color: #ffffff;">[ROUTE B: LPBF METAL ADDITIVE]</strong><br>
                    AlSi10Mg spherical gas-atomized metal powder melted via Laser Powder Bed Fusion in 4-bracket batches, vacuum stress-relieved, finish CNC machined for precision datum interfaces.</p>
                    <p><strong style="color: #d9a441;">[SHARED QUALITY STATION: NDT]</strong><br>
                    Liquid Penetrant Surface Testing (PT) per ASTM E1417. Flagged defects undergo 1 rework cycle at finishing bench; repeat failures scrapped.</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# =============================================================================
# TAB 2: SIMULATION STUDIO & FLEET TUNING
# =============================================================================

with tab_sim:
    st.markdown(
        """
        <div style="margin-bottom: 12px; font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: #8a8c92;">
            DISCRETE-EVENT SIMULATION WORKBENCH // SIMPY 4.1 ENGINE
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Station Parameter Controls
    with st.expander("WORKSTATION FLEET PARAMETERS & MACHINE ALLOCATIONS", expanded=True):
        custom_cfg = copy.deepcopy(st.session_state.base_config)

        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            st.markdown("**[ROUTE A] Bandsaw Cut**")
            m_saw = st.number_input(
                "Bandsaw Count", 1, 4, custom_cfg.stations["saw"].machine_count, key="ws_saw"
            )
            t_saw = st.number_input(
                "Cycle Time (min)",
                2.0,
                30.0,
                float(custom_cfg.stations["saw"].cycle_time_mean_min),
                1.0,
                key="ws_tsaw",
            )
            custom_cfg.stations["saw"].machine_count = m_saw
            custom_cfg.stations["saw"].cycle_time_mean_min = t_saw

        with sc2:
            st.markdown("**[ROUTE A] CNC Machining**")
            m_cnc = st.number_input(
                "CNC Mills Count", 1, 6, custom_cfg.stations["cnc_mill"].machine_count, key="ws_cnc"
            )
            t_cnc = st.number_input(
                "Cycle Time (min)",
                10.0,
                90.0,
                float(custom_cfg.stations["cnc_mill"].cycle_time_mean_min),
                2.0,
                key="ws_tcnc",
            )
            custom_cfg.stations["cnc_mill"].machine_count = m_cnc
            custom_cfg.stations["cnc_mill"].cycle_time_mean_min = t_cnc

        with sc3:
            st.markdown("**[ROUTE A] Deburr & Prep**")
            m_deb = st.number_input(
                "Deburr Benches", 1, 4, custom_cfg.stations["deburr"].machine_count, key="ws_deb"
            )
            t_deb = st.number_input(
                "Cycle Time (min)",
                2.0,
                30.0,
                float(custom_cfg.stations["deburr"].cycle_time_mean_min),
                1.0,
                key="ws_tdeb",
            )
            custom_cfg.stations["deburr"].machine_count = m_deb
            custom_cfg.stations["deburr"].cycle_time_mean_min = t_deb

        with sc4:
            st.markdown("**[SHARED] NDT Inspection**")
            m_insp = st.number_input(
                "Inspection Booths",
                1,
                4,
                custom_cfg.stations["inspection"].machine_count,
                key="ws_insp",
            )
            t_insp = st.number_input(
                "Cycle Time (min)",
                3.0,
                45.0,
                float(custom_cfg.stations["inspection"].cycle_time_mean_min),
                1.0,
                key="ws_tinsp",
            )
            custom_cfg.stations["inspection"].machine_count = m_insp
            custom_cfg.stations["inspection"].cycle_time_mean_min = t_insp

        sc5, sc6, sc7, sc8 = st.columns(4)
        with sc5:
            st.markdown("**[ROUTE B] LPBF 3D Printer**")
            m_lpbf = st.number_input(
                "Printers Count", 1, 4, custom_cfg.stations["lpbf"].machine_count, key="ws_lpbf"
            )
            batch_cap = st.number_input(
                "Brackets / Plate",
                1,
                8,
                custom_cfg.additive_batch.build_plate_capacity,
                key="ws_bcap",
            )
            custom_cfg.stations["lpbf"].machine_count = m_lpbf
            custom_cfg.additive_batch.build_plate_capacity = batch_cap

        with sc6:
            st.markdown("**[ROUTE B] Stress Relief**")
            m_post = st.number_input(
                "Furnaces Count",
                1,
                4,
                custom_cfg.stations["post_heat"].machine_count,
                key="ws_post",
            )
            t_post = st.number_input(
                "Cycle Time (min)",
                10.0,
                120.0,
                float(custom_cfg.stations["post_heat"].cycle_time_mean_min),
                5.0,
                key="ws_tpost",
            )
            custom_cfg.stations["post_heat"].machine_count = m_post
            custom_cfg.stations["post_heat"].cycle_time_mean_min = t_post

        with sc7:
            st.markdown("**[ROUTE B] CNC Finishing**")
            m_fin = st.number_input(
                "Finish Mills",
                1,
                4,
                custom_cfg.stations["cnc_finish"].machine_count,
                key="ws_fin",
            )
            t_fin = st.number_input(
                "Cycle Time (min)",
                5.0,
                60.0,
                float(custom_cfg.stations["cnc_finish"].cycle_time_mean_min),
                2.0,
                key="ws_tfin",
            )
            custom_cfg.stations["cnc_finish"].machine_count = m_fin
            custom_cfg.stations["cnc_finish"].cycle_time_mean_min = t_fin

        with sc8:
            st.markdown("**[SHARED] Packaging Station**")
            m_pack = st.number_input(
                "Packaging Benches",
                1,
                4,
                custom_cfg.stations["packaging"].machine_count,
                key="ws_pack",
            )
            t_pack = st.number_input(
                "Cycle Time (min)",
                1.0,
                20.0,
                float(custom_cfg.stations["packaging"].cycle_time_mean_min),
                1.0,
                key="ws_tpack",
            )
            custom_cfg.stations["packaging"].machine_count = m_pack
            custom_cfg.stations["packaging"].cycle_time_mean_min = t_pack

    col_btn, _ = st.columns([1, 4])
    with col_btn:
        run_btn = st.button("EXECUTE SIMULATION [SIMPY]", type="primary", use_container_width=True)

    if run_btn:
        valid, errs = validate_config(custom_cfg)
        if not valid:
            st.error(f"[CONFIG ERROR] Invalid parameters: {', '.join(errs)}")
        else:
            with st.spinner("Executing SimPy discrete-event simulation..."):
                engine = SimulationEngine(custom_cfg)
                res = engine.run()
                metrics = calculate_metrics(res)
                finances = EconomicsEngine(custom_cfg).calculate_finances(res, metrics)

                v_rep = verify_simulation_results(res)
                if not v_rep.is_valid:
                    st.warning(f"[VERIFICATION NOTICE] {'; '.join(v_rep.errors)}")

                st.session_state.custom_results = res
                st.session_state.custom_metrics = metrics
                st.session_state.custom_finances = finances
                st.success("[COMPLETED] Simulation completed successfully.")

    # Active Results
    act_res = st.session_state.custom_results or st.session_state.baseline_results
    act_m = st.session_state.custom_metrics or st.session_state.baseline_metrics
    act_f = st.session_state.custom_finances or st.session_state.baseline_finances

    # KPI Strip
    rk1, rk2, rk3, rk4 = st.columns(4)
    with rk1:
        st.markdown(
            render_kpi(
                "Conforming Delivered",
                f"{act_m.conforming_parts} <span style='font-size: 0.90rem; color: #8a8c92;'>UNITS</span>",
                f"Started: {act_m.parts_started} | Scrapped: {act_m.scrapped_parts}",
                "OUTPUT",
            ),
            unsafe_allow_html=True,
        )
    with rk2:
        st.markdown(
            render_kpi(
                "Throughput Rate",
                f"{act_m.throughput_per_hour:.2f} <span style='font-size: 0.90rem; color: #8a8c92;'>/ HR</span>",
                f"Per Shift: {act_m.throughput_per_shift:.1f} units",
                "THROUGHPUT",
            ),
            unsafe_allow_html=True,
        )
    with rk3:
        st.markdown(
            render_kpi(
                "Mean Lead Time",
                f"{act_m.mean_lead_time_min / 60.0:.2f} <span style='font-size: 0.90rem; color: #8a8c92;'>HRS</span>",
                f"Queue Wait: {act_m.mean_wait_time_min / 60.0:.2f} hrs",
                "LEAD TIME",
            ),
            unsafe_allow_html=True,
        )
    with rk4:
        st.markdown(
            render_kpi(
                "Critical Bottleneck",
                act_m.bottleneck_station_name.split("(")[0].strip().upper(),
                f"Raw Util: {act_m.bottleneck_utilization_pct:.1f}%",
                "BINDING",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)

    # Workstation Utilization vs Availability & Lead Time Histogram
    ch_col1, ch_col2 = st.columns(2)

    with ch_col1:
        st_names = [s.display_name.split("(")[0].strip() for s in act_m.station_kpis.values()]
        utils = [s.raw_utilization_pct for s in act_m.station_kpis.values()]
        avails = [s.availability_pct for s in act_m.station_kpis.values()]

        fig_util = go.Figure()
        fig_util.add_trace(
            go.Bar(
                name="Raw Utilization (%)",
                x=st_names,
                y=utils,
                marker_color="#4a8ad6",
            )
        )
        fig_util.add_trace(
            go.Scatter(
                name="Machine Availability (%)",
                x=st_names,
                y=avails,
                mode="lines+markers",
                marker={"color": "#d9a441", "size": 6},
                line={"dash": "dash", "width": 1.5, "color": "#d9a441"},
            )
        )
        fig_util.update_layout(
            barmode="group",
            yaxis={"title": "Percentage (%)", "range": [0, 105]},
            xaxis={"tickangle": -25},
        )
        style_chart(fig_util, height=330, title="WORKSTATION UTILIZATION VS MACHINE AVAILABILITY")
        st.plotly_chart(fig_util, use_container_width=True)

    with ch_col2:
        conforming_parts = [p for p in act_res.part_records if p.status == "conforming"]
        if conforming_parts:
            lts_hours = [p.total_lead_time_min / 60.0 for p in conforming_parts]
            routes = [
                "Route A: Subtractive" if p.route == "conventional" else "Route B: Additive"
                for p in conforming_parts
            ]
            df_lt = pd.DataFrame({"LeadTimeHours": lts_hours, "Route": routes})

            fig_lt = px.histogram(
                df_lt,
                x="LeadTimeHours",
                color="Route",
                barmode="overlay",
                nbins=25,
                color_discrete_map={
                    "Route A: Subtractive": "#4a8ad6",
                    "Route B: Additive": "#8a8c92",
                },
            )
            fig_lt.update_layout(
                xaxis_title="Lead Time (Hours)",
                yaxis_title="Part Count",
            )
            style_chart(fig_lt, height=330, title="CONFORMING PART LEAD TIME DISTRIBUTION")
            st.plotly_chart(fig_lt, use_container_width=True)

    # Dynamic Work-in-Progress (WIP) Tracking
    if act_res.wip_history:
        wip_df = pd.DataFrame(
            [
                {
                    "Time_Hours": sn.time_min / 60.0,
                    "Total_WIP": sn.total_wip,
                    "Conventional_WIP": sn.conventional_wip,
                    "Additive_WIP": sn.additive_wip,
                }
                for sn in act_res.wip_history
            ]
        )
        fig_wip = px.line(
            wip_df,
            x="Time_Hours",
            y=["Total_WIP", "Conventional_WIP", "Additive_WIP"],
            color_discrete_map={
                "Total_WIP": "#ffffff",
                "Conventional_WIP": "#4a8ad6",
                "Additive_WIP": "#8a8c92",
            },
        )
        fig_wip.update_layout(
            xaxis_title="Simulated Time (Hours)",
            yaxis_title="Parts in System (WIP)",
        )
        style_chart(fig_wip, height=270, title="DYNAMIC WORK-IN-PROGRESS (WIP) TELEMETRY OVER TIME")
        st.plotly_chart(fig_wip, use_container_width=True)

    # Data Export Strip
    d1, d2 = st.columns(2)
    with d1:
        parts_data = [
            {
                "Part_ID": p.part_id,
                "Route": p.route,
                "Arrival_Min": round(p.arrival_time_min, 1),
                "Completion_Min": round(p.completion_time_min, 1),
                "Lead_Time_Min": round(p.total_lead_time_min, 1),
                "Wait_Time_Min": round(p.total_waiting_time_min, 1),
                "Processing_Time_Min": round(p.total_processing_time_min, 1),
                "Rework_Count": p.rework_count,
                "Status": p.status,
                "On_Time": p.on_time,
            }
            for p in act_res.part_records
        ]
        csv_bytes = pd.DataFrame(parts_data).to_csv(index=False).encode("utf-8")
        st.download_button(
            "DOWNLOAD PART EVENT LOGS (CSV)",
            data=csv_bytes,
            file_name="cellforge_part_records.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with d2:
        summary_dict = {
            "metrics": act_m.to_dict(),
            "finances": act_f.to_dict(),
        }
        json_bytes = json.dumps(summary_dict, indent=2).encode("utf-8")
        st.download_button(
            "DOWNLOAD SIMULATION KPI SUMMARY (JSON)",
            data=json_bytes,
            file_name="cellforge_simulation_summary.json",
            mime="application/json",
            use_container_width=True,
        )

# =============================================================================
# TAB 3: CAPACITY OPTIMIZATION (MILP)
# =============================================================================

with tab_opt:
    st.markdown(
        """
        <div style="margin-bottom: 12px; font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: #8a8c92;">
            MIXED-INTEGER LINEAR PROGRAMMING (MILP) CAPACITY OPTIMIZER // SCIPY.OPTIMIZE.MILP
        </div>
        """,
        unsafe_allow_html=True,
    )

    o_c1, o_c2 = st.columns(2)
    with o_c1:
        opt_demand = st.number_input(
            "Contract Demand Target (Conforming Brackets)",
            min_value=50,
            max_value=400,
            value=int(st.session_state.base_config.simulation.target_demand_units),
            step=10,
            key="opt_demand_input",
        )
    with o_c2:
        opt_budget = st.number_input(
            "Equipment Capital Budget (USD)",
            min_value=150000.0,
            max_value=1500000.0,
            value=650000.0,
            step=25000.0,
            key="opt_budget_input",
        )

    if st.button("SOLVE CAPACITY PLANNING MILP", type="primary"):
        with st.spinner("Executing branch-and-bound integer program..."):
            optimizer = CapacityOptimizer(st.session_state.base_config)
            opt_res = optimizer.optimize(
                target_demand=opt_demand,
                capital_budget_usd=opt_budget,
                horizon_hours=float(
                    st.session_state.base_config.simulation.simulation_horizon_hours
                ),
            )
            opt_res = optimizer.validate_in_simulation(opt_res)
            st.session_state.opt_result = opt_res

    if st.session_state.opt_result is not None:
        o = st.session_state.opt_result

        status_class = "chip-success" if o.success else "chip-warning"
        status_text = (
            "[OPTIMAL SOLUTION IDENTIFIED]" if o.success else "[INFEASIBLE CONSTRAINTS DETECTED]"
        )
        st.markdown(
            f"""
            <div style="margin-top: 10px; margin-bottom: 12px;">
                <span class="chip {status_class}" style="font-size: 0.80rem; padding: 4px 10px;">{status_text}</span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.80rem; color: #8a8c92; margin-left: 10px;">{o.status_message}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not o.success and o.infeasibility_reasons:
            for r in o.infeasibility_reasons:
                st.error(f"[CONSTRAINT VIOLATION] {r}")

        # Optimization Headline Strip
        oc1, oc2, oc3, oc4 = st.columns(4)
        with oc1:
            st.markdown(
                render_kpi(
                    "Equipment CAPEX",
                    f"${o.total_capital_expenditure_usd:,.0f}",
                    f"Budget: ${o.capital_budget_usd:,.0f}",
                    "CAPITAL",
                ),
                unsafe_allow_html=True,
            )
        with oc2:
            st.markdown(
                render_kpi(
                    "Objective Total Cost",
                    f"${o.objective_total_cost_usd:,.0f}",
                    f"Amortized Cap: ${o.amortized_capital_cost_usd:,.0f}",
                    "OBJECTIVE",
                ),
                unsafe_allow_html=True,
            )
        with oc3:
            st.markdown(
                render_kpi(
                    "Optimal Route Split",
                    f"{o.conventional_ratio * 100:.0f}% / {(1 - o.conventional_ratio) * 100:.0f}%",
                    "Conv CNC / Add LPBF",
                    "ROUTING",
                ),
                unsafe_allow_html=True,
            )
        with oc4:
            st.markdown(
                render_kpi(
                    "Simulated Output",
                    f"{o.simulated_conforming_output} <span style='font-size: 0.90rem; color: #8a8c92;'>UNITS</span>",
                    f"Target Contract: {o.target_demand}",
                    "VERIFIED",
                ),
                unsafe_allow_html=True,
            )

        st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)

        # Machine Allocation Table
        st.markdown("**RECOMMENDED WORKSTATION MACHINE ALLOCATION**")
        rec_data = []
        for k, count in o.recommended_machine_counts.items():
            st_cfg = st.session_state.base_config.stations[k]
            rec_data.append(
                {
                    "Station ID": k,
                    "Workstation Name": st_cfg.display_name,
                    "Recommended Count": count,
                    "Unit CAPEX": f"${st_cfg.capital_cost_usd:,.0f}",
                    "Total CAPEX": f"${st_cfg.capital_cost_usd * count:,.0f}",
                    "Deterministic Util (%)": f"{o.deterministic_utilizations.get(k, 0):.1f}%",
                }
            )
        st.table(pd.DataFrame(rec_data))

        # Stochastic Simulation Validation & Discrepancy Card
        st.markdown(
            f"""
            <div class="imow-panel">
                <div class="imow-panel-header">DETERMINISTIC PLANNING VS STOCHASTIC SIMULATION VALIDATION</div>
                <div style="font-size: 0.80rem; line-height: 1.5; color: #8a8c92;">
                    <p>Linear programming models deterministic flow rates assuming average processing times.
                    Evaluating the recommended machine fleet in the stochastic SimPy simulation introduces queuing delays,
                    LPBF batch accumulation latency, and machine breakdown interruptions.</p>
                    <p><strong style="color: #4a8ad6;">[KINGMAN QUEUEING ANALYSIS]</strong>: {o.stochastic_discrepancy_explanation}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        comp_df = pd.DataFrame(
            [
                {
                    "Metric Parameter": "Throughput Rate (parts/hr)",
                    "Deterministic MILP Prediction": f"{o.deterministic_expected_throughput:.2f}",
                    "Stochastic Simulation Result": f"{o.simulated_throughput_per_hour:.2f}",
                },
                {
                    "Metric Parameter": "Conforming Output (units)",
                    "Deterministic MILP Prediction": f"{o.target_demand} (Assumed Exact)",
                    "Stochastic Simulation Result": f"{o.simulated_conforming_output}",
                },
                {
                    "Metric Parameter": "Bottleneck Workstation",
                    "Deterministic MILP Prediction": "Binding planned utilization",
                    "Stochastic Simulation Result": f"{o.simulated_bottleneck}",
                },
            ]
        )
        st.table(comp_df)

# =============================================================================
# TAB 4: ECONOMICS & QUALITY (NDT)
# =============================================================================

with tab_econ:
    f_act = st.session_state.custom_finances or st.session_state.baseline_finances
    m_act = st.session_state.custom_metrics or st.session_state.baseline_metrics

    # Unit Cost & Payback Cards
    ec1, ec2, ec3, ec4 = st.columns(4)
    with ec1:
        st.markdown(
            render_kpi(
                "Cost / Conforming Part",
                f"${f_act.cost_per_conforming_part_usd:.2f}",
                "Total Relevant Manufacturing Cost",
                "UNIT COST",
            ),
            unsafe_allow_html=True,
        )
    with ec2:
        st.markdown(
            render_kpi(
                "Break-Even Volume",
                f"{f_act.break_even.break_even_units:.0f} <span style='font-size: 0.90rem; color: #8a8c92;'>UNITS</span>",
                f"Target Price: ${f_act.break_even.selling_price_per_unit_usd:.2f}",
                "BREAK-EVEN",
            ),
            unsafe_allow_html=True,
        )
    with ec3:
        st.markdown(
            render_kpi(
                "Capital Payback Period",
                f"{f_act.break_even.payback_period_years:.1f} <span style='font-size: 0.90rem; color: #8a8c92;'>YEARS</span>",
                f"Projected Annual ROI: {f_act.break_even.return_on_investment_pct:.1f}%",
                "PAYBACK",
            ),
            unsafe_allow_html=True,
        )
    with ec4:
        st.markdown(
            render_kpi(
                "First-Pass Yield",
                f"{m_act.first_pass_yield_pct:.1f}%",
                f"Rework: {m_act.rework_rate_pct:.1f}% | Scrap: {m_act.scrap_rate_pct:.1f}%",
                "QUALITY",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)

    # Manufacturing Cost Breakdown & Crossover Curve
    col_e1, col_e2 = st.columns(2)

    with col_e1:
        cb = f_act.cost_breakdown
        cost_labels = [
            "Amortized Equipment Capital",
            "Direct Materials",
            "Direct Manufacturing Labor",
            "Electrical Energy",
            "NDT Consumables",
            "Rework Labor",
            "Facility Overhead",
        ]
        cost_values = [
            cb.capital_amortized_usd,
            cb.material_usd,
            cb.labor_usd,
            cb.energy_usd,
            cb.inspection_consumables_usd,
            cb.rework_usd,
            cb.facility_overhead_usd,
        ]

        fig_pie = go.Figure(
            data=[
                go.Pie(
                    labels=cost_labels,
                    values=cost_values,
                    hole=0.48,
                    marker={
                        "colors": [
                            "#4a8ad6",  # Capital
                            "#3568a3",  # Materials
                            "#8a8c92",  # Labor
                            "#d9a441",  # Energy
                            "#b8882e",  # NDT
                            "#e5566f",  # Rework
                            "#4a4a4e",  # Overhead
                        ]
                    },
                )
            ]
        )
        style_chart(fig_pie, height=330, title="MANUFACTURING EXPENSE COST STRUCTURE")
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_e2:
        rc = f_act.route_comparison
        df_cross = pd.DataFrame(
            {
                "Volume": rc.volumes,
                "Conventional ($)": rc.conventional_unit_costs,
                "Additive LPBF ($)": rc.additive_unit_costs,
            }
        )

        fig_cross = go.Figure()
        fig_cross.add_trace(
            go.Scatter(
                x=df_cross["Volume"],
                y=df_cross["Conventional ($)"],
                name="Route A: Subtractive CNC",
                line={"color": "#4a8ad6", "width": 2.0},
            )
        )
        fig_cross.add_trace(
            go.Scatter(
                x=df_cross["Volume"],
                y=df_cross["Additive LPBF ($)"],
                name="Route B: Additive LPBF",
                line={"color": "#8a8c92", "width": 2.0},
            )
        )

        if rc.crossover_volume_units > 0:
            fig_cross.add_vline(
                x=rc.crossover_volume_units,
                line_dash="dash",
                line_color="#e5566f",
                annotation_text=f"Crossover: {rc.crossover_volume_units:.0f} units",
                annotation_font={"size": 10, "color": "#ffffff"},
            )

        fig_cross.update_layout(
            xaxis_title="Production Batch Volume (Units)",
            yaxis_title="Estimated Unit Cost ($ / Unit)",
        )
        style_chart(
            fig_cross, height=330, title="UNIT COST VS PRODUCTION VOLUME (ECONOMIC CROSSOVER)"
        )
        st.plotly_chart(fig_cross, use_container_width=True)

    # NDT Quality Testing Section
    st.markdown(
        """
        <div class="imow-panel">
            <div class="imow-panel-header">LIQUID PENETRANT SURFACE TESTING (ASTM E1417) QUALITY TELEMETRY</div>
            <div style="font-size: 0.80rem; line-height: 1.5; color: #8a8c92;">
                Statistical inspection modeled with imperfect sensitivity (True Positive Rate) and specificity (True Negative Rate).
                Quality escapes pose critical structural risks, while false indications drive rework bench overhead.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    qc1, qc2 = st.columns(2)
    with qc1:
        tp = m_act.parts_completed - m_act.first_pass_yield_pct
        fn = m_act.ndt_escape_count
        fp = m_act.ndt_false_alarms
        tn = m_act.conforming_parts - fn

        matrix_data = pd.DataFrame(
            [
                {
                    "Physical Condition": "Defective Workpiece",
                    "Flagged Defective (Positive)": f"{tp:.0f} [TRUE POSITIVE]",
                    "Cleared Conforming (Negative)": f"{fn} [QUALITY ESCAPE]",
                },
                {
                    "Physical Condition": "Conforming Workpiece",
                    "Flagged Defective (Positive)": f"{fp} [FALSE ALARM]",
                    "Cleared Conforming (Negative)": f"{tn} [TRUE NEGATIVE]",
                },
            ]
        )
        st.table(matrix_data)

    with qc2:
        st.markdown(
            """
            <div style="font-size: 0.80rem; line-height: 1.5; color: #8a8c92;">
                <p><strong style="color: #e5566f;">[QUALITY ESCAPE // TYPE II ERROR]</strong><br>
                Defects undetected by penetrant dwell/emulsification passing into dispatch. Structural bracket failure risk in industrial service.</p>
                <p><strong style="color: #d9a441;">[FALSE ALARM // TYPE I ERROR]</strong><br>
                Conforming parts falsely flagged due to surface roughness or solvent bleed-out, driving unneeded rework bench labor.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

# =============================================================================
# TAB 5: BENCHMARK SCENARIO MATRIX
# =============================================================================

with tab_scenarios:
    st.markdown(
        """
        <div style="margin-bottom: 12px; font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: #8a8c92;">
            MULTI-SCENARIO BENCHMARKING & SENSITIVITY SUITE
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("RUN BENCHMARK SCENARIO SUITE", type="primary"):
        with st.spinner("Executing multi-scenario benchmark battery..."):
            mgr = ScenarioManager(st.session_state.base_config)
            scenario_results = mgr.run_all_standard_scenarios()

            opt_run = mgr.run_optimization_scenario(
                target_demand=int(st.session_state.base_config.simulation.target_demand_units),
                capital_budget_usd=620000.0,
            )
            scenario_results["optimized"] = opt_run

            st.session_state.scenario_benchmark = scenario_results
            st.session_state.scenario_df = ScenarioManager.build_comparison_dataframe(
                scenario_results
            )
            st.success("[COMPLETED] Multi-scenario benchmark suite executed.")

    if "scenario_df" in st.session_state:
        df_scenarios = st.session_state.scenario_df
        st.dataframe(df_scenarios, use_container_width=True)

        sc1, sc2 = st.columns(2)
        with sc1:
            fig_th = px.bar(
                df_scenarios,
                x="Scenario Name",
                y="Throughput (units/hr)",
                color_discrete_sequence=["#4a8ad6"],
            )
            fig_th.update_layout(xaxis_title="")
            style_chart(fig_th, height=300, title="THROUGHPUT RATE COMPARISON ACROSS SCENARIOS")
            st.plotly_chart(fig_th, use_container_width=True)

        with sc2:
            fig_cost = px.bar(
                df_scenarios,
                x="Scenario Name",
                y="Cost / Conforming Part ($)",
                color_discrete_sequence=["#8a8c92"],
            )
            fig_cost.update_layout(xaxis_title="")
            style_chart(fig_cost, height=300, title="UNIT MANUFACTURING COST COMPARISON")
            st.plotly_chart(fig_cost, use_container_width=True)

        # Little's Law WIP Congestion vs Lead Time
        fig_scatter = px.scatter(
            df_scenarios,
            x="Time-Weighted WIP",
            y="Mean Lead Time (min)",
            size="Total CAPEX ($)",
            color="Scenario Name",
            text="Scenario ID",
            color_discrete_sequence=[
                "#4a8ad6",
                "#8a8c92",
                "#44a282",
                "#d9a441",
                "#e5566f",
                "#dedee0",
            ],
        )
        fig_scatter.update_traces(textposition="top center")
        style_chart(fig_scatter, height=340, title="LITTLE'S LAW CONGESTION: WIP VS MEAN LEAD TIME")
        st.plotly_chart(fig_scatter, use_container_width=True)

        csv_scen = df_scenarios.to_csv(index=False).encode("utf-8")
        st.download_button(
            "DOWNLOAD SCENARIO MATRIX (CSV)",
            data=csv_scen,
            file_name="cellforge_scenario_comparison.csv",
            mime="text/csv",
        )
    else:
        st.info(
            "Execute 'RUN BENCHMARK SCENARIO SUITE' to generate multi-scenario performance data."
        )

# =============================================================================
# TAB 6: MATHEMATICAL FORMULATIONS
# =============================================================================

with tab_notes:
    st.markdown(
        """
        <div style="margin-bottom: 12px; font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: #8a8c92;">
            MATHEMATICAL FORMULATIONS, DISCLOSURES & TECHNICAL LIMITATIONS
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("**1. Capacity Planning Mixed-Integer Linear Program (MILP)**")
    st.latex(
        r"""
        \min \quad Z = \sum_{s \in \mathcal{S}} \left( \frac{\text{CAPEX}_s}{L_s} \cdot T_{\text{horizon}} \right) m_s + c_{\text{var}, A} x_A + c_{\text{var}, B} x_B
        """
    )
    st.markdown("**Subject to:**")
    st.latex(
        r"""
        \begin{aligned}
        \text{Demand Satisfaction:} \quad & Y_A x_A + Y_B x_B \ge D_{\text{target}} \\
        \text{Workstation Capacity:} \quad & \tau_{s, A} x_A + \tau_{s, B} x_B \le m_s \cdot T_{\text{horizon}} \cdot A_s \cdot \eta_{\text{cap}} \quad \forall s \in \mathcal{S} \\
        \text{Capital Budget:} \quad & \sum_{s \in \mathcal{S}} \text{CAPEX}_s \cdot m_s \le B_{\text{budget}} \\
        \text{Integrality \& Bounds:} \quad & m_s \in \{m_{\min, s}, \dots, m_{\max, s}\}, \quad x_A, x_B \in \mathbb{Z}_{\ge 0}
        \end{aligned}
        """
    )

    st.markdown("---")

    st.markdown("**2. Operational Metrics & Manufacturing Formulations**")
    st.markdown(
        """
        - **Machine Availability ($A$)**:
          $$A = \\frac{\\text{Operating Time}}{\\text{Planned Time}} = \\frac{\\text{MTBF}}{\\text{MTBF} + \\text{MTTR}}$$
        - **Raw Workstation Utilization ($U_{\\text{raw}}$)**:
          $$U_{\\text{raw}} = \\frac{\\text{Total Busy Processing Time}}{m_s \\cdot T_{\\text{horizon}}}$$
        - **Overall Equipment Effectiveness (OEE)**:
          $$\\text{OEE} = \\text{Availability} \\times \\text{Performance} \\times \\text{Quality}$$
        - **Little's Law Queueing Formulation**:
          $$\\overline{\\text{WIP}} = \\text{Throughput Rate } (\\lambda) \\times \\text{Mean Lead Time } (W)$$
        - **Kingman's Heavy-Traffic Approximation for Station Waiting Time**:
          $$W_q \\approx \\left( \\frac{\\rho}{1 - \\rho} \\right) \\left( \\frac{c_a^2 + c_s^2}{2} \\right) \\tau$$
        """
    )

    st.markdown("---")

    st.markdown("**3. Assumptions, Educational Disclaimers & Licensing**")
    st.markdown(
        """
        1. **Educational Simulation**: CellForge models synthetic processing distributions, maintenance intervals, and cost rates. It is not an audited model of an AS9100 certified manufacturing facility.
        2. **Finite Production Horizon**: Production campaigns are modeled over finite horizon windows ($T_{\\text{horizon}} = 160\\,\\text{hrs}$) rather than infinite steady-state queuing.
        3. **NDT Procedure**: The penetrant inspection model is an educational probabilistic representation and cannot substitute for qualified ASTM E1417 or ISO 3452 Level II/III certified personnel.
        4. **Open-Source License**: CellForge is distributed under the MIT License.
        """
    )
