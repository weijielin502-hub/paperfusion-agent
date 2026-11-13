import json
import pytest
from p2c_tools import p2c_wrapper as p2c
from paperfusion.execution import ToolFailure


def trajectory(tmp_path, files):
    data = [{"role": "assistant", "content": "overview"}, {"role": "assistant", "content": "{}"},
            {"role": "assistant", "content": json.dumps({"Task list": files})}]
    (tmp_path / "planning_trajectories.json").write_text(json.dumps(data), encoding="utf-8")


def test_p2c_nonzero_exit_propagates(tmp_path, monkeypatch):
    monkeypatch.setattr(p2c, "run_process", lambda *a, **k: {"passed": False, "returncode": 9,
                        "timed_out": False, "log": "failure.log"})
    with pytest.raises(ToolFailure, match="exit=9"):
        p2c._run_python_script("1_planning.py", {"paper_name": "test", "output_dir": tmp_path})


def test_missing_success_artifact_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(p2c, "_run_python_script", lambda *a, **k: {"passed": True})
    with pytest.raises(ToolFailure, match="artifact missing"):
        p2c.run_planning("test", "model", "paper.json", tmp_path)


def test_generated_paths_validated_before_coding(tmp_path):
    trajectory(tmp_path, ["../../escape.py"])
    with pytest.raises(ValueError):
        p2c.run_coding("test", "model", "paper.json", tmp_path, tmp_path / "repo")


def test_coding_copies_config_and_checks_all_files(tmp_path, monkeypatch):
    trajectory(tmp_path, ["config.yaml", "model.py"])
    (tmp_path / "planning_config.yaml").write_text("k: 60", encoding="utf-8")
    monkeypatch.setattr(p2c, "_run_python_script", lambda *a, **k: {"passed": True})
    with pytest.raises(ToolFailure, match="model.py"):
        p2c.run_coding("test", "model", "paper.json", tmp_path, tmp_path / "repo")
    assert (tmp_path / "repo/config.yaml").read_text() == "k: 60"


def test_analyzer_prepares_nested_artifact_directories(tmp_path, monkeypatch):
    trajectory(tmp_path, ["tests/test_fusion.py"])
    monkeypatch.setattr(p2c, "_run_python_script", lambda *a, **k: {"passed": True})
    with pytest.raises(ToolFailure, match="simple_analysis_response"):
        p2c.run_analyzing("test", "model", "paper.json", tmp_path)
    assert (tmp_path / "analyzing_artifacts/tests").is_dir()


def test_debug_adapter_rejects_patch_outside_planned_files(tmp_path, monkeypatch):
    from types import SimpleNamespace
    trajectory(tmp_path, ["model.py"])
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "model.py").write_text("x = 1\n", encoding="utf-8")
    error = tmp_path / "error.txt"
    error.write_text("AssertionError", encoding="utf-8")
    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_:
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            "patches": [{"path": "../outside.py", "search": "x", "replace": "y"}]
        })))]))))
    monkeypatch.setattr("openai.OpenAI", lambda **_: fake)
    with pytest.raises(ToolFailure, match="planned file"):
        p2c.run_debugging("paper", "model", repo, output_dir=tmp_path, error_file_name=error)
    assert (repo / "model.py").read_text(encoding="utf-8") == "x = 1\n"
