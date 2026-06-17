from spatialscope.utils.run_index import compare_run_summaries


def test_compare_run_summaries_reports_deltas_and_notes():
    left = {
        "run_id": "a",
        "mode": "advanced",
        "dataset_hash": "same",
        "plan_source": "llm",
        "llm_enabled": True,
        "complete": True,
        "figures": 8,
        "tables": 4,
        "trace_steps": 12,
        "status_success": 10,
        "status_failed": 1,
        "status_repaired": 1,
        "warnings": 2,
        "errors": 1,
        "repairs": 1,
    }
    right = {
        "run_id": "b",
        "mode": "quick",
        "dataset_hash": "same",
        "plan_source": "rule_based",
        "llm_enabled": False,
        "complete": True,
        "figures": 5,
        "tables": 2,
        "trace_steps": 8,
        "status_success": 8,
        "status_failed": 0,
        "status_repaired": 0,
        "warnings": 0,
        "errors": 0,
        "repairs": 0,
    }
    comparison = compare_run_summaries(left, right)
    assert comparison["same_dataset"] is True
    assert comparison["left_run_id"] == "a"
    assert comparison["right_run_id"] == "b"
    rows = {row["Metric"]: row for row in comparison["rows"]}
    assert rows["Figures"]["Delta A-B"] == 3
    assert rows["Errors"]["Delta A-B"] == 1
    assert any("repair" in note.lower() for note in comparison["notes"])
