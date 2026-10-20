"""CellForge: Manufacturing Simulation, Optimization, and Engineering Economics Lab.

Interactive Streamlit decision-support application comparing conventional CNC subtractive
and laser powder-bed fusion (LPBF) additive manufacturing routes for custom industrial brackets.
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
# Streamlit Application Configuration & Industrial Styling
# =============================================================================

st.set_page_config(
    page_title="CellForge | Manufacturing Simulation & Optimization Lab",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for refined industrial engineering aesthetic
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .metric-title {
        color: #495057;
        font-size: 0.82rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        color: #1a252f;
        font-size: 1.65rem;
        font-weight: 700;
        margin-top: 4px;
    }
    .metric-subtitle {
        color: #6c757d;
        font-size: 0.78rem;
        margin-top: 2px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 16px;
        font-weight: 600;
    }
    .badge-conv {
        background-color: #e3f2fd;
        color: #0d47a1;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-add {
        background-color: #f3e5f5;
        color: #4a148c;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# Session State Caching & Model Execution Helpers
# =============================================================================

if "base_config" not in st.session_state:
    st.session_state.base_config = default_cell_config()

if "baseline_results" not in st.session_state:
    # Run initial baseline simulation on launch
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
# Application Sidebar: Global Controls & Scenario Selection
# =============================================================================

with st.sidebar:
    st.title("CellForge")
    st.caption("Discrete-Event Simulation & Capacity Planning")
    st.markdown("---")

    st.subheader("Global Simulation Parameters")
    horizon_hours = st.slider(
        "Simulation Horizon (Hours)",
        min_value=40.0,
        max_value=320.0,
        value=float(st.session_state.base_config.simulation.simulation_horizon_hours),
        step=20.0,
        help="Simulated operational window (160 hours = 4 work weeks of single 8h shifts).",
    )
    target_demand = st.number_input(
        "Target Demand (Conforming Units)",
        min_value=20,
        max_value=500,
        value=int(st.session_state.base_config.simulation.target_demand_units),
        step=10,
        help="Contractual production quantity of acceptable mounting brackets.",
    )
    route_ratio = st.slider(
        "Route A (Conventional) Volume Ratio",
        min_value=0.0,
        max_value=1.0,
        value=float(st.session_state.base_config.simulation.route_allocation_ratio),
        step=0.05,
        help="Fraction routed to CNC Subtractive (remainder routed to LPBF Metal Additive).",
    )
    seed = st.number_input(
        "Random Seed (Reproducibility)",
        min_value=1,
        max_value=99999,
        value=int(st.session_state.base_config.simulation.random_seed),
        step=1,
    )

    st.markdown("---")
    st.markdown(
        """
        **System Specification:**
        - **Product**: Custom Industrial Mounting Bracket
        - **Route A**: Saw -> CNC Milling -> Deburr
        - **Route B**: LPBF (Batch 4) -> Heat Treat -> CNC Finish
        - **Shared**: Dye-Penetrant NDT & Packaging
        """
    )
    st.caption("Educational Prototype | Synthetic Engineering Parameters")

# Update base config parameters if modified in sidebar
st.session_state.base_config.simulation.simulation_horizon_hours = horizon_hours
st.session_state.base_config.simulation.target_demand_units = target_demand
st.session_state.base_config.simulation.route_allocation_ratio = route_ratio
st.session_state.base_config.simulation.random_seed = seed

# =============================================================================
# Main Application Tabs
# =============================================================================

tab_overview, tab_sim, tab_scenarios, tab_opt, tab_econ, tab_notes = st.tabs(
    [
        "Overview",
        "Simulation Lab",
        "Scenario Comparison",
        "Optimization Lab",
        "Economics & Quality",
        "Engineering Notes",
    ]
)

# =============================================================================
# TAB 1: OVERVIEW
# =============================================================================

with tab_overview:
    st.header("CellForge: Manufacturing Decision-Support System")
    st.markdown(
        """
        CellForge is an open-source manufacturing engineering laboratory designed to evaluate the trade-offs
        between **conventional subtractive machining** and **metal additive manufacturing (Laser Powder Bed Fusion)**
        for small-batch production of custom industrial mounting brackets.
        """
    )

    st.info(
        "**Core Engineering Question:** *Given a production target, equipment budget, manufacturing-route alternatives, "
        "machine reliability, and product-quality requirements, what production configuration can deliver the required "
        "number of acceptable parts at the lowest practical cost?*"
    )

    # Headline Baseline Metrics
    bm = st.session_state.baseline_metrics
    bf = st.session_state.baseline_finances

    st.subheader("Baseline Cell Performance (160 Operational Hours)")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(
            "Conforming Output",
            f"{bm.conforming_parts} units",
            f"{bm.overall_yield_pct:.1f}% Yield",
        )
    with col2:
        st.metric(
            "Throughput",
            f"{bm.throughput_per_hour:.2f} / hr",
            f"{bm.throughput_per_shift:.1f} / shift",
        )
    with col3:
        st.metric(
            "Mean Lead Time",
            f"{bm.mean_lead_time_min / 60.0:.1f} hrs",
            f"Median: {bm.median_lead_time_min / 60.0:.1f} h",
        )
    with col4:
        st.metric(
            "Unit Cost",
            f"${bf.cost_per_conforming_part_usd:.2f}",
            f"CAPEX: ${bf.total_installed_capex_usd:,.0f}",
        )
    with col5:
        st.metric(
            "Bottleneck",
            bm.bottleneck_station_name.split("(")[0],
            f"{bm.bottleneck_utilization_pct:.1f}% Util",
        )

    st.markdown("---")

    # Production Flow Architecture Diagram (Sankey / Mermaid)
    st.subheader("Manufacturing Process Flow & Quality Routing")
    col_flow1, col_flow2 = st.columns([3, 2])

    with col_flow1:
        # Plotly Sankey Diagram showing part flow through the cell
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
                        "pad": 15,
                        "thickness": 18,
                        "line": {"color": "black", "width": 0.5},
                        "label": labels,
                        "color": [
                            "#455a64",
                            "#1e88e5",
                            "#1976d2",
                            "#1565c0",
                            "#8e24aa",
                            "#7b1fa2",
                            "#6a1b9a",
                            "#f57c00",
                            "#fbc02d",
                            "#388e3c",
                            "#2e7d32",
                            "#d32f2f",
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
                    },
                )
            ]
        )
        fig_sankey.update_layout(
            title_text="Material Mass Flow & Rework Network",
            font_size=11,
            height=340,
            margin={"l": 10, "r": 10, "t": 35, "b": 10},
        )
        st.plotly_chart(fig_sankey, use_container_width=True)

    with col_flow2:
        st.markdown(
            """
            **Manufacturing Routing Rules:**
            1. **Route A (Subtractive)**: Extruded 6061-T6 aluminum billet is cut to length on a horizontal bandsaw, roughed and contoured on a 3-axis CNC vertical milling center, and deburred.
            2. **Route B (Additive)**: AlSi10Mg spherical metal powder is melted via Laser Powder Bed Fusion (LPBF) in batches of 4 brackets, undergoes vacuum stress-relief heat treatment, and precision CNC finishing for critical datum faces.
            3. **Shared NDT Inspection**: Fluorescent dye-penetrant surface inspection testing for flaws. Non-conforming parts undergo 1 rework cycle at the finishing bench, followed by re-inspection. Repeat failures are scrapped.
            4. **Dispatch**: Conforming brackets are cleaned, tagged, and packed.
            """
        )

    st.markdown("---")
    st.caption(
        "**Notice on Synthetic Modeling**: All machine costs, operational cycle times, and failure rates are synthetic engineering estimates developed for educational simulation."
    )

# =============================================================================
# TAB 2: SIMULATION LAB
# =============================================================================

with tab_sim:
    st.header("Workstation Configuration & Simulation Execution")
    st.markdown(
        "Adjust machine allocations, operational cycle times, and reliability parameters, then run the discrete-event simulation."
    )

    # Workstation Config Editor
    with st.expander("Workstation Configuration & Cycle Times", expanded=True):
        st_cols1 = st.columns(4)
        custom_cfg = copy.deepcopy(st.session_state.base_config)

        # Conventional stations
        with st_cols1[0]:
            st.markdown("**Route A: Bandsaw Cut**")
            m_saw = st.number_input(
                "Bandsaw Count",
                1,
                4,
                custom_cfg.stations["saw"].machine_count,
                key="sim_saw",
            )
            t_saw = st.number_input(
                "Mean Cycle (min)",
                2.0,
                30.0,
                float(custom_cfg.stations["saw"].cycle_time_mean_min),
                1.0,
                key="sim_tsaw",
            )
            custom_cfg.stations["saw"].machine_count = m_saw
            custom_cfg.stations["saw"].cycle_time_mean_min = t_saw

        with st_cols1[1]:
            st.markdown("**Route A: CNC Machining**")
            m_cnc = st.number_input(
                "CNC Mills Count",
                1,
                6,
                custom_cfg.stations["cnc_mill"].machine_count,
                key="sim_cnc",
            )
            t_cnc = st.number_input(
                "Mean Cycle (min)",
                10.0,
                90.0,
                float(custom_cfg.stations["cnc_mill"].cycle_time_mean_min),
                2.0,
                key="sim_tcnc",
            )
            custom_cfg.stations["cnc_mill"].machine_count = m_cnc
            custom_cfg.stations["cnc_mill"].cycle_time_mean_min = t_cnc

        with st_cols1[2]:
            st.markdown("**Route A: Deburr & Prep**")
            m_deb = st.number_input(
                "Deburr Benches",
                1,
                4,
                custom_cfg.stations["deburr"].machine_count,
                key="sim_deb",
            )
            t_deb = st.number_input(
                "Mean Cycle (min)",
                2.0,
                30.0,
                float(custom_cfg.stations["deburr"].cycle_time_mean_min),
                1.0,
                key="sim_tdeb",
            )
            custom_cfg.stations["deburr"].machine_count = m_deb
            custom_cfg.stations["deburr"].cycle_time_mean_min = t_deb

        with st_cols1[3]:
            st.markdown("**Shared: Inspection (NDT)**")
            m_insp = st.number_input(
                "Inspection Booths",
                1,
                4,
                custom_cfg.stations["inspection"].machine_count,
                key="sim_insp",
            )
            t_insp = st.number_input(
                "Mean Cycle (min)",
                3.0,
                45.0,
                float(custom_cfg.stations["inspection"].cycle_time_mean_min),
                1.0,
                key="sim_tinsp",
            )
            custom_cfg.stations["inspection"].machine_count = m_insp
            custom_cfg.stations["inspection"].cycle_time_mean_min = t_insp

        st_cols2 = st.columns(4)
        with st_cols2[0]:
            st.markdown("**Route B: LPBF 3D Printer**")
            m_lpbf = st.number_input(
                "LPBF Printers",
                1,
                4,
                custom_cfg.stations["lpbf"].machine_count,
                key="sim_lpbf",
            )
            batch_cap = st.number_input(
                "Brackets per Plate",
                1,
                8,
                custom_cfg.additive_batch.build_plate_capacity,
                key="sim_bcap",
            )
            custom_cfg.stations["lpbf"].machine_count = m_lpbf
            custom_cfg.additive_batch.build_plate_capacity = batch_cap

        with st_cols2[1]:
            st.markdown("**Route B: Heat & Support**")
            m_post = st.number_input(
                "Furnace Stations",
                1,
                4,
                custom_cfg.stations["post_heat"].machine_count,
                key="sim_post",
            )
            t_post = st.number_input(
                "Mean Cycle (min)",
                10.0,
                120.0,
                float(custom_cfg.stations["post_heat"].cycle_time_mean_min),
                5.0,
                key="sim_tpost",
            )
            custom_cfg.stations["post_heat"].machine_count = m_post
            custom_cfg.stations["post_heat"].cycle_time_mean_min = t_post

        with st_cols2[2]:
            st.markdown("**Route B: CNC Finishing**")
            m_fin = st.number_input(
                "Finish Mill Count",
                1,
                4,
                custom_cfg.stations["cnc_finish"].machine_count,
                key="sim_fin",
            )
            t_fin = st.number_input(
                "Mean Cycle (min)",
                5.0,
                60.0,
                float(custom_cfg.stations["cnc_finish"].cycle_time_mean_min),
                2.0,
                key="sim_tfin",
            )
            custom_cfg.stations["cnc_finish"].machine_count = m_fin
            custom_cfg.stations["cnc_finish"].cycle_time_mean_min = t_fin

        with st_cols2[3]:
            st.markdown("**Shared: Packaging**")
            m_pack = st.number_input(
                "Packaging Stations",
                1,
                4,
                custom_cfg.stations["packaging"].machine_count,
                key="sim_pack",
            )
            t_pack = st.number_input(
                "Mean Cycle (min)",
                1.0,
                20.0,
                float(custom_cfg.stations["packaging"].cycle_time_mean_min),
                1.0,
                key="sim_tpack",
            )
            custom_cfg.stations["packaging"].machine_count = m_pack
            custom_cfg.stations["packaging"].cycle_time_mean_min = t_pack

    # Run Simulation Trigger
    run_col1, run_col2 = st.columns([1, 4])
    with run_col1:
        run_btn = st.button("Execute Simulation", type="primary", use_container_width=True)

    if run_btn:
        # Validate configuration before running
        valid, errs = validate_config(custom_cfg)
        if not valid:
            st.error(f"Configuration Invalid: {', '.join(errs)}")
        else:
            with st.spinner("Running SimPy discrete-event simulation..."):
                engine = SimulationEngine(custom_cfg)
                res = engine.run()
                metrics = calculate_metrics(res)
                finances = EconomicsEngine(custom_cfg).calculate_finances(res, metrics)

                # Post-run verification
                v_rep = verify_simulation_results(res)
                if not v_rep.is_valid:
                    st.warning(f"Verification Notice: {'; '.join(v_rep.errors)}")

                st.session_state.custom_results = res
                st.session_state.custom_metrics = metrics
                st.session_state.custom_finances = finances
                st.success("Simulation completed successfully!")

    # Display active simulation results (or baseline if custom not run)
    active_res = st.session_state.custom_results or st.session_state.baseline_results
    active_m = st.session_state.custom_metrics or st.session_state.baseline_metrics
    active_f = st.session_state.custom_finances or st.session_state.baseline_finances

    st.subheader("Operational Results & Factory Performance")

    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    with kpi_col1:
        st.metric(
            "Conforming Delivered",
            f"{active_m.conforming_parts} parts",
            f"Started: {active_m.parts_started}",
        )
    with kpi_col2:
        st.metric(
            "Throughput Rate",
            f"{active_m.throughput_per_hour:.2f} / hr",
            f"{active_m.throughput_per_shift:.1f} / shift",
        )
    with kpi_col3:
        st.metric(
            "Mean Production Lead Time",
            f"{active_m.mean_lead_time_min / 60.0:.2f} hrs",
            f"Wait: {active_m.mean_wait_time_min / 60.0:.2f} hrs",
        )
    with kpi_col4:
        st.metric(
            "Workstation Bottleneck",
            active_m.bottleneck_station_name.split("(")[0],
            f"{active_m.bottleneck_utilization_pct:.1f}% Raw Util",
        )

    st.markdown("---")

    # Visualizations: Workstation Utilization & Queue Analysis
    c_chart1, c_chart2 = st.columns(2)

    with c_chart1:
        # Station Utilization vs Availability
        st_names = [s.display_name.split("(")[0] for s in active_m.station_kpis.values()]
        utils = [s.raw_utilization_pct for s in active_m.station_kpis.values()]
        avails = [s.availability_pct for s in active_m.station_kpis.values()]

        fig_util = go.Figure()
        fig_util.add_trace(
            go.Bar(name="Raw Utilization (%)", x=st_names, y=utils, marker_color="#1976d2")
        )
        fig_util.add_trace(
            go.Scatter(
                name="Availability (%)",
                x=st_names,
                y=avails,
                mode="lines+markers",
                marker={"color": "#d32f2f", "size": 8},
                line={"dash": "dash"},
            )
        )
        fig_util.update_layout(
            title="Workstation Utilization vs Machine Availability",
            yaxis={"title": "Percentage (%)", "range": [0, 105]},
            xaxis={"tickangle": -25},
            barmode="group",
            height=350,
            margin={"l": 40, "r": 20, "t": 40, "b": 60},
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        )
        st.plotly_chart(fig_util, use_container_width=True)

    with c_chart2:
        # Lead Time Distribution Histogram
        conforming_parts = [p for p in active_res.part_records if p.status == "conforming"]
        if conforming_parts:
            lts_hours = [p.total_lead_time_min / 60.0 for p in conforming_parts]
            routes = [p.route.capitalize() for p in conforming_parts]
            df_lt = pd.DataFrame({"LeadTimeHours": lts_hours, "Route": routes})

            fig_lt = px.histogram(
                df_lt,
                x="LeadTimeHours",
                color="Route",
                barmode="overlay",
                nbins=25,
                title="Conforming Part Lead Time Distribution (Hours)",
                color_discrete_map={"Conventional": "#1e88e5", "Additive": "#8e24aa"},
            )
            fig_lt.update_layout(
                xaxis_title="Total Lead Time (Hours)",
                yaxis_title="Part Count",
                height=350,
                margin={"l": 40, "r": 20, "t": 40, "b": 40},
            )
            st.plotly_chart(fig_lt, use_container_width=True)
        else:
            st.info("No completed conforming parts to plot lead time distribution.")

    # Time-Weighted WIP & Station Queues
    st.subheader("Dynamic Work-in-Progress (WIP) Tracking")
    if active_res.wip_history:
        wip_df = pd.DataFrame(
            [
                {
                    "Time_Hours": sn.time_min / 60.0,
                    "Total_WIP": sn.total_wip,
                    "Conventional_WIP": sn.conventional_wip,
                    "Additive_WIP": sn.additive_wip,
                }
                for sn in active_res.wip_history
            ]
        )
        fig_wip = px.line(
            wip_df,
            x="Time_Hours",
            y=["Total_WIP", "Conventional_WIP", "Additive_WIP"],
            title="System-Wide Work-in-Progress Over Time",
            color_discrete_map={
                "Total_WIP": "#263238",
                "Conventional_WIP": "#1e88e5",
                "Additive_WIP": "#8e24aa",
            },
        )
        fig_wip.update_layout(
            xaxis_title="Simulated Time (Hours)",
            yaxis_title="Parts in System (WIP)",
            height=280,
            margin={"l": 40, "r": 20, "t": 40, "b": 40},
        )
        st.plotly_chart(fig_wip, use_container_width=True)

    # Export Data
    st.subheader("Data Export")
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        # CSV Export of individual part records
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
            for p in active_res.part_records
        ]
        csv_bytes = pd.DataFrame(parts_data).to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Part-Level Event Logs (CSV)",
            data=csv_bytes,
            file_name="cellforge_part_records.csv",
            mime="text/csv",
        )

    with col_dl2:
        # JSON summary of all KPIs
        summary_dict = {
            "metrics": active_m.to_dict(),
            "finances": active_f.to_dict(),
        }
        json_bytes = json.dumps(summary_dict, indent=2).encode("utf-8")
        st.download_button(
            "Download Simulation KPI Summary (JSON)",
            data=json_bytes,
            file_name="cellforge_simulation_summary.json",
            mime="application/json",
        )

# =============================================================================
# TAB 3: SCENARIO COMPARISON
# =============================================================================

with tab_scenarios:
    st.header("Comparative Scenario Analysis")
    st.markdown(
        "Evaluate multi-scenario trade-offs across capital requirements, bottleneck shifts, "
        "flow lead times, and unit economics."
    )

    if st.button("Run Multi-Scenario Benchmark Suite"):
        with st.spinner("Executing standard benchmark scenarios..."):
            mgr = ScenarioManager(st.session_state.base_config)
            scenario_results = mgr.run_all_standard_scenarios()

            # Add optimized scenario
            opt_run = mgr.run_optimization_scenario(
                target_demand=int(st.session_state.base_config.simulation.target_demand_units),
                capital_budget_usd=620000.0,
            )
            scenario_results["optimized"] = opt_run

            st.session_state.scenario_benchmark = scenario_results
            st.session_state.scenario_df = ScenarioManager.build_comparison_dataframe(
                scenario_results
            )
            st.success("Benchmark suite completed!")

    if "scenario_df" in st.session_state:
        df_scenarios = st.session_state.scenario_df
        st.dataframe(df_scenarios, use_container_width=True)

        # Comparative Visualizations
        sc1, sc2 = st.columns(2)
        with sc1:
            fig_th = px.bar(
                df_scenarios,
                x="Scenario Name",
                y="Throughput (units/hr)",
                color="Scenario Name",
                title="Throughput Rate Comparison",
            )
            fig_th.update_layout(xaxis_title="", height=320, showlegend=False)
            st.plotly_chart(fig_th, use_container_width=True)

        with sc2:
            fig_cost = px.bar(
                df_scenarios,
                x="Scenario Name",
                y="Cost / Conforming Part ($)",
                color="Scenario Name",
                title="Unit Manufacturing Cost ($ / Conforming Part)",
            )
            fig_cost.update_layout(xaxis_title="", height=320, showlegend=False)
            st.plotly_chart(fig_cost, use_container_width=True)

        # Lead time vs WIP Tradeoff
        fig_scatter = px.scatter(
            df_scenarios,
            x="Time-Weighted WIP",
            y="Mean Lead Time (min)",
            size="Total CAPEX ($)",
            color="Scenario Name",
            text="Scenario ID",
            title="WIP Congestion vs Lead Time (Little's Law Trade-Off)",
        )
        fig_scatter.update_traces(textposition="top center")
        fig_scatter.update_layout(height=350)
        st.plotly_chart(fig_scatter, use_container_width=True)

        # Download comparison CSV
        csv_scen = df_scenarios.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Scenario Comparison Table (CSV)",
            data=csv_scen,
            file_name="cellforge_scenario_comparison.csv",
            mime="text/csv",
        )
    else:
        st.info(
            "Click 'Run Multi-Scenario Benchmark Suite' above to execute and compare all standard scenarios."
        )

# =============================================================================
# TAB 4: OPTIMIZATION LAB
# =============================================================================

with tab_opt:
    st.header("Operations Research & Capacity Optimization Lab")
    st.markdown(
        """
        Solve the deterministic capacity-planning problem using **Mixed-Integer Linear Programming (MILP)**
        via `scipy.optimize.milp`.
        CellForge determines the exact cost-optimal machine portfolio and route allocation to satisfy target demand
        subject to equipment budget, workstation capacity, and reliability constraints.
        """
    )

    opt_col1, opt_col2 = st.columns(2)
    with opt_col1:
        opt_demand = st.number_input(
            "Contract Demand Target (Conforming Units)",
            min_value=50,
            max_value=400,
            value=int(st.session_state.base_config.simulation.target_demand_units),
            step=10,
            key="opt_demand_in",
        )
    with opt_col2:
        opt_budget = st.number_input(
            "Capital Equipment Budget (USD)",
            min_value=150000.0,
            max_value=1500000.0,
            value=650000.0,
            step=25000.0,
            key="opt_budget_in",
        )

    if st.button("Solve Capacity Planning MILP", type="primary"):
        with st.spinner("Solving integer branch-and-bound optimization..."):
            optimizer = CapacityOptimizer(st.session_state.base_config)
            opt_res = optimizer.optimize(
                target_demand=opt_demand,
                capital_budget_usd=opt_budget,
                horizon_hours=float(
                    st.session_state.base_config.simulation.simulation_horizon_hours
                ),
            )
            # Run simulation validation of recommendation
            opt_res = optimizer.validate_in_simulation(opt_res)
            st.session_state.opt_result = opt_res

    if st.session_state.opt_result is not None:
        o = st.session_state.opt_result

        if o.success:
            st.success(f"[OPTIMAL] {o.status_message}")
        else:
            st.warning(f"[INFEASIBLE] {o.status_message}")
            if o.infeasibility_reasons:
                for r in o.infeasibility_reasons:
                    st.error(r)

        # High-level Optimization Output Cards
        oc1, oc2, oc3, oc4 = st.columns(4)
        with oc1:
            st.metric(
                "Total Equipment CAPEX",
                f"${o.total_capital_expenditure_usd:,.0f}",
                f"Budget: ${o.capital_budget_usd:,.0f}",
            )
        with oc2:
            st.metric(
                "Total Relevant Cost",
                f"${o.objective_total_cost_usd:,.0f}",
                f"Amortized Cap: ${o.amortized_capital_cost_usd:,.0f}",
            )
        with oc3:
            st.metric(
                "Route Allocation Split",
                f"{o.conventional_ratio * 100:.0f}% Conv / {(1 - o.conventional_ratio) * 100:.0f}% Add",
            )
        with oc4:
            st.metric(
                "Simulated Conforming Output",
                f"{o.simulated_conforming_output} units",
                f"Target: {o.target_demand}",
            )

        st.markdown("---")

        # Recommended Machine Counts Table
        st.subheader("Recommended Machine Resource Allocation")
        rec_data = []
        for k, count in o.recommended_machine_counts.items():
            st_cfg = st.session_state.base_config.stations[k]
            rec_data.append(
                {
                    "Station Key": k,
                    "Workstation Name": st_cfg.display_name,
                    "Recommended Machine Count": count,
                    "Unit CAPEX ($)": f"${st_cfg.capital_cost_usd:,.0f}",
                    "Subtotal CAPEX ($)": f"${st_cfg.capital_cost_usd * count:,.0f}",
                    "Planned Deterministic Util (%)": f"{o.deterministic_utilizations.get(k, 0):.1f}%",
                }
            )
        st.table(pd.DataFrame(rec_data))

        # Stochastic Simulation Validation & Discrepancy Analysis
        st.subheader("Deterministic Planning vs Stochastic Simulation Validation")
        st.markdown(
            """
            Linear programming models deterministic flow rates assuming average processing times.
            The recommended configuration was evaluated in the **stochastic SimPy discrete-event simulation**
            to capture queueing delays, LPBF batch accumulation latency, and machine breakdowns.
            """
        )

        st.info(f"**Discrepancy Analysis:** {o.stochastic_discrepancy_explanation}")

        # Comparison metrics
        comp_df = pd.DataFrame(
            [
                {
                    "Metric": "Throughput (parts/hr)",
                    "Deterministic MILP Prediction": f"{o.deterministic_expected_throughput:.2f}",
                    "Stochastic Simulation Result": f"{o.simulated_throughput_per_hour:.2f}",
                },
                {
                    "Metric": "Conforming Output",
                    "Deterministic MILP Prediction": f"{o.target_demand} (Assumed Exact)",
                    "Stochastic Simulation Result": f"{o.simulated_conforming_output}",
                },
                {
                    "Metric": "Bottleneck Workstation",
                    "Deterministic MILP Prediction": "Identified by binding utilization",
                    "Stochastic Simulation Result": f"{o.simulated_bottleneck}",
                },
            ]
        )
        st.table(comp_df)

# =============================================================================
# TAB 5: ECONOMICS & QUALITY
# =============================================================================

with tab_econ:
    st.header("Engineering Economics & Quality Analytics")
    st.markdown(
        "Examine manufacturing cost breakdown, unit economics, break-even production volume, "
        "and non-destructive testing (NDT) detection performance."
    )

    f_act = st.session_state.custom_finances or st.session_state.baseline_finances
    m_act = st.session_state.custom_metrics or st.session_state.baseline_metrics

    # Unit Cost & Payback Cards
    ec1, ec2, ec3, ec4 = st.columns(4)
    with ec1:
        st.metric(
            "Cost / Conforming Part",
            f"${f_act.cost_per_conforming_part_usd:.2f}",
            "Total Relevant Cost",
        )
    with ec2:
        st.metric(
            "Break-Even Volume",
            f"{f_act.break_even.break_even_units:.0f} units",
            f"Target Price: ${f_act.break_even.selling_price_per_unit_usd:.2f}",
        )
    with ec3:
        st.metric(
            "Capital Payback Period",
            f"{f_act.break_even.payback_period_years:.1f} years",
            f"Annual ROI: {f_act.break_even.return_on_investment_pct:.1f}%",
        )
    with ec4:
        st.metric(
            "First-Pass Yield",
            f"{m_act.first_pass_yield_pct:.1f}%",
            f"Rework: {m_act.rework_rate_pct:.1f}% | Scrap: {m_act.scrap_rate_pct:.1f}%",
        )

    st.markdown("---")

    # Cost Breakdown Donut & Economic Crossover
    col_e1, col_e2 = st.columns(2)

    with col_e1:
        st.subheader("Manufacturing Cost Structure")
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

        fig_pie = go.Figure(data=[go.Pie(labels=cost_labels, values=cost_values, hole=0.45)])
        fig_pie.update_layout(
            title="Relevant Manufacturing Expenses Breakdown",
            height=340,
            margin={"l": 20, "r": 20, "t": 40, "b": 20},
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_e2:
        st.subheader("Conventional vs Additive Cost-Volume Crossover")
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
                name="Route A: Conventional CNC",
                line={"color": "#1e88e5", "width": 2.5},
            )
        )
        fig_cross.add_trace(
            go.Scatter(
                x=df_cross["Volume"],
                y=df_cross["Additive LPBF ($)"],
                name="Route B: Metal Additive (LPBF)",
                line={"color": "#8e24aa", "width": 2.5},
            )
        )

        if rc.crossover_volume_units > 0:
            fig_cross.add_vline(
                x=rc.crossover_volume_units,
                line_dash="dash",
                line_color="#d32f2f",
                annotation_text=f"Crossover: {rc.crossover_volume_units:.0f} units",
            )

        fig_cross.update_layout(
            title="Unit Cost vs Batch Volume (Economic Crossover)",
            xaxis_title="Production Batch Volume (Units)",
            yaxis_title="Estimated Unit Cost ($ / Unit)",
            height=340,
            margin={"l": 40, "r": 20, "t": 40, "b": 40},
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        )
        st.plotly_chart(fig_cross, use_container_width=True)

    st.markdown("---")

    # Quality & NDT Section
    st.subheader("Non-Destructive Testing (NDT) Quality Performance")
    st.markdown(
        """
        The shared quality station models **Liquid Penetrant Surface Testing (PT)**.
        NDT is an imperfect statistical inspection process characterized by sensitivity (True Positive Rate)
        and specificity (True Negative Rate).
        """
    )

    qc1, qc2 = st.columns(2)
    with qc1:
        # Confusion matrix for NDT
        st.markdown("**Simulated Inspection Confusion Matrix**")
        tp = m_act.parts_completed - m_act.first_pass_yield_pct  # Flagged defects
        fn = m_act.ndt_escape_count
        fp = m_act.ndt_false_alarms
        tn = m_act.conforming_parts - fn

        matrix_data = pd.DataFrame(
            [
                {
                    "Actual State": "Physically Defective",
                    "Flagged (Positive)": f"{tp:.0f} (True Positive)",
                    "Cleared (Negative)": f"{fn} (Quality Escape / False Neg)",
                },
                {
                    "Actual State": "Physically Conforming",
                    "Flagged (Positive)": f"{fp} (False Alarm / False Pos)",
                    "Cleared (Negative)": f"{tn} (True Negative)",
                },
            ]
        )
        st.table(matrix_data)

    with qc2:
        st.markdown(
            """
            **Operational Consequences of NDT Imperfections:**
            - **Quality Escapes (Type II Error / False Negatives)**: Defective parts undetected by penetrant dwell/development that enter customer dispatch. Critical risk in load-bearing structural brackets.
            - **False Indications (Type I Error / False Positives)**: Conforming parts flagged as defective due to surface solvent residue, geometric high spots, or operator subjectivity, incurring unnecessary rework bench expenses.
            """
        )

# =============================================================================
# TAB 6: ENGINEERING NOTES
# =============================================================================

with tab_notes:
    st.header("Engineering Formulation, Assumptions, and References")

    st.subheader("1. Mathematical Formulation: Capacity Planning MILP")
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

    st.subheader("2. Key Performance Indicator (KPI) Definitions")
    st.markdown(
        """
        - **Machine Availability ($A$)**:
          $$A = \\frac{\\text{Operating Time}}{\\text{Planned Time}} = \\frac{\\text{MTBF}}{\\text{MTBF} + \\text{MTTR}}$$
        - **Workstation Utilization ($U_{\\text{raw}}$)**:
          $$U_{\\text{raw}} = \\frac{\\text{Busy Service Time}}{m_s \\cdot T_{\\text{horizon}}}$$
        - **Overall Equipment Effectiveness (OEE)**:
          $$\\text{OEE} = \\text{Availability} \\times \\text{Performance} \\times \\text{Quality}$$
          Where Performance $= \\frac{\\text{Ideal Cycle Time} \\times \\text{Parts Processed}}{\\text{Operating Time}}$, and Quality $= \\frac{\\text{Conforming Units}}{\\text{Total Units}}$.
        - **Little's Law Consistency**:
          $$\\overline{\\text{WIP}} = \\text{Throughput} (\\lambda) \\times \\text{Mean Lead Time} (W)$$
        """
    )

    st.markdown("---")

    st.subheader("3. Major Assumptions & Technical Limitations")
    st.markdown(
        """
        1. **Educational Simulation**: CellForge models synthetic processing distributions, maintenance intervals, and cost rates. It is not an audited model of a certified manufacturing plant.
        2. **Finite Production Horizon**: The model simulates finite production campaigns ($T_{\\text{horizon}} = 160\\,\\text{hrs}$) rather than infinite steady-state queuing.
        3. **NDT Procedure**: The dye-penetrant inspection model is an educational probabilistic representation and cannot substitute for qualified ASTM E1417 or ISO 3452 Level II/III personnel.
        4. **CAD Structural Verification**: The parametric OpenSCAD mounting bracket is a geometric design artifact and has not been certified through physical load proofing or finite element analysis (FEA).
        """
    )
