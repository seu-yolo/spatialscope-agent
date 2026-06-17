from spatialscope.utils.quality import build_quality_report


def test_quality_report_passes_clean_run():
    quality = build_quality_report(
        {
            "run_id": "run",
            "dataset_hash": "abc",
            "dataset_summary": {"n_obs": 10, "n_vars": 20},
            "approved_plan": [{"id": "qc", "tool": "run_qc", "params": {}}],
            "plan_source": "rule_based",
            "execution_trace": [{"status": "success", "tool": "run_qc"}],
            "generated_figures": [{"path": "fig.png"}],
            "generated_tables": [{"path": "table.csv"}],
            "warnings": [],
            "errors": [],
            "repair_log": [],
            "final_answer": "done",
            "environment": {"python": "3.11"},
            "parameters": {"mode": "quick"},
        }
    )
    assert quality["overall_status"] == "pass"
    assert quality["score"] == 100
    assert quality["status_counts"]["fail"] == 0


def test_quality_report_warns_on_repaired_failure():
    quality = build_quality_report(
        {
            "run_id": "run",
            "dataset_hash": "abc",
            "dataset_summary": {"n_obs": 10, "n_vars": 20},
            "approved_plan": [{"id": "spatial", "tool": "plot_spatial", "params": {}}],
            "plan_source": "user_edited",
            "execution_trace": [
                {"status": "failed", "tool": "plot_spatial"},
                {"status": "repaired", "tool": "plot_spatial"},
            ],
            "generated_figures": [],
            "generated_tables": [],
            "warnings": ["repaired"],
            "errors": ["missing key"],
            "repair_log": [{"tool": "plot_spatial"}],
            "final_answer": "done",
            "environment": {"python": "3.11"},
            "parameters": {"mode": "quick"},
        }
    )
    assert quality["overall_status"] in {"warn", "fail"}
    assert any(gate["name"] == "Execution trace" and gate["status"] == "warn" for gate in quality["gates"])
    assert any(gate["name"] == "Error review" and gate["status"] == "warn" for gate in quality["gates"])
