from spatialscope.tools.registry import list_tool_contracts
from spatialscope.utils.agent_audit import build_agent_audit


def test_agent_audit_passes_traceable_contract_bound_run():
    state = {
        "run_id": "run",
        "approved_plan": [
            {"tool": "run_qc", "params": {}, "rationale": "QC"},
            {"tool": "plot_umap", "params": {"color": "leiden"}, "rationale": "UMAP"},
        ],
        "tool_contracts": list_tool_contracts(),
        "execution_trace": [
            {"node": "inspect_dataset", "tool": "load_h5ad", "status": "success"},
            {"node": "execute_tool", "tool": "run_qc", "status": "success"},
            {"node": "execute_tool", "tool": "plot_umap", "status": "success"},
        ],
        "generated_figures": [{"path": "figures/umap.png"}],
        "generated_tables": [{"path": "tables/qc.csv"}],
        "repair_log": [],
        "final_answer": "The run completed with evidence-linked outputs.",
        "_adata": "private object should not appear in public state",
    }

    audit = build_agent_audit(state)

    assert audit["overall_status"] == "pass"
    assert audit["score"] == 100
    assert audit["planned_tools"] == ["run_qc", "plot_umap"]
    assert audit["executed_tools"] == ["run_qc", "plot_umap"]
    assert audit["unknown_plan_tools"] == []
    assert all(check["status"] == "pass" for check in audit["checks"])


def test_agent_audit_flags_unknown_and_unexecuted_plan():
    state = {
        "run_id": "run",
        "approved_plan": [{"tool": "not_a_tool", "params": {}, "rationale": "bad"}],
        "tool_contracts": [],
        "execution_trace": [],
        "generated_figures": [],
        "generated_tables": [],
        "repair_log": [],
        "final_answer": "",
    }

    audit = build_agent_audit(state)

    assert audit["overall_status"] == "fail"
    assert "not_a_tool" in audit["unknown_plan_tools"]
    statuses = {check["name"]: check["status"] for check in audit["checks"]}
    assert statuses["Plan contract alignment"] == "fail"
    assert statuses["Plan execution coverage"] == "fail"
    assert statuses["Trace registry discipline"] == "fail"
