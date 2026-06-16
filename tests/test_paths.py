from spatialscope.utils.paths import ensure_run_dirs, write_json, write_yaml_simple


def test_run_dirs_and_writers(tmp_path):
    dirs = ensure_run_dirs(tmp_path, "run_001")
    assert dirs["run_dir"].exists()
    assert dirs["figures_dir"].exists()
    write_json(dirs["run_dir"] / "x.json", {"ok": True})
    write_yaml_simple(dirs["run_dir"] / "x.yaml", {"mode": "quick"})
    assert (dirs["run_dir"] / "x.json").exists()
    assert (dirs["run_dir"] / "x.yaml").exists()

