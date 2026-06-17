from cli import main


def test_cli_llm_check_json_without_key(monkeypatch, capsys):
    monkeypatch.setattr("cli._load_dotenv_quietly", lambda: None)
    monkeypatch.delenv("SPATIALSCOPE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("SPATIALSCOPE_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    code = main(["llm-check", "--json"])
    output = capsys.readouterr().out
    assert code == 0
    assert '"provider": "disabled"' in output
    assert "rule_based" in output
