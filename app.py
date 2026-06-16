from __future__ import annotations

from pathlib import Path

import streamlit as st

from spatialscope.agent.graph import run_agent


st.set_page_config(page_title="SpatialScope Agent", page_icon="◌", layout="wide")

st.title("SpatialScope Agent")
st.caption("From spatial transcriptomics data to traceable scientific insight.")

if "run_state" not in st.session_state:
    st.session_state.run_state = None

start_tab, analyze_tab, explore_tab, report_tab = st.tabs(["Start", "Analyze", "Explore", "Report"])

with start_tab:
    st.subheader("Start")
    st.write("Upload an `.h5ad` file, describe your analysis goal, and choose a run mode.")
    uploaded = st.file_uploader("Spatial AnnData file", type=["h5ad"])
    default_data = st.text_input("Or use local data path", value="data/demo_tiny.h5ad")
    query = st.text_area(
        "Natural-language task",
        value="Run quick spatial analysis and plot GeneA, GeneB, GeneC.",
        height=100,
    )
    mode = st.radio("Run mode", ["quick", "standard", "advanced"], horizontal=True)
    outdir = st.text_input("Output directory", value="outputs/runs")

    data_path = default_data
    if uploaded is not None:
        upload_dir = Path("outputs/tmp/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved = upload_dir / uploaded.name
        saved.write_bytes(uploaded.getbuffer())
        data_path = str(saved)
        st.success(f"Uploaded file saved to {saved}")

    if st.button("Generate plan and run workflow", type="primary"):
        with st.spinner("SpatialScope Agent is running..."):
            st.session_state.run_state = run_agent(data_path=data_path, query=query, mode=mode, outdir=outdir)
        st.success("Run complete.")

with analyze_tab:
    st.subheader("Analyze")
    state = st.session_state.run_state
    if not state:
        st.info("Run a workflow from the Start tab first.")
    else:
        st.metric("Run ID", state.get("run_id"))
        st.metric("Mode", state.get("mode"))
        st.write("Plan Preview")
        st.json(state.get("approved_plan", []))
        st.write("Agent Trace")
        st.dataframe(state.get("execution_trace", []), use_container_width=True)
        if state.get("warnings"):
            st.warning("\n".join(map(str, state.get("warnings", []))))
        if state.get("errors"):
            st.error("\n".join(map(str, state.get("errors", []))))

with explore_tab:
    st.subheader("Explore")
    state = st.session_state.run_state
    if not state:
        st.info("Run a workflow from the Start tab first.")
    else:
        st.write("Dataset summary")
        st.json(state.get("dataset_summary", {}))
        st.write("Figures")
        for fig in state.get("generated_figures", []):
            path = fig.get("path")
            st.markdown(f"**{fig.get('title', Path(str(path)).name)}**")
            if path and Path(path).exists():
                st.image(path, caption=fig.get("caption"), use_container_width=True)
            else:
                st.caption(fig.get("caption", ""))
        st.write("Tables")
        for table in state.get("generated_tables", []):
            path = table.get("path")
            st.markdown(f"- `{path}` - {table.get('title', '')}")

with report_tab:
    st.subheader("Report")
    state = st.session_state.run_state
    if not state:
        st.info("Run a workflow from the Start tab first.")
    else:
        st.write(state.get("final_answer"))
        report_path = state.get("report_path")
        if report_path and Path(str(report_path)).exists():
            report_bytes = Path(str(report_path)).read_bytes()
            st.download_button("Download HTML report", report_bytes, file_name="spatialscope_report.html")
            st.markdown(f"Report path: `{report_path}`")
        trace_path = Path(str(state.get("run_dir"))) / "agent_trace.json"
        if trace_path.exists():
            st.download_button("Download agent_trace.json", trace_path.read_bytes(), file_name="agent_trace.json")
        metadata_path = Path(str(state.get("run_dir"))) / "run_metadata.json"
        if metadata_path.exists():
            st.download_button("Download run_metadata.json", metadata_path.read_bytes(), file_name="run_metadata.json")

