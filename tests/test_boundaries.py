import sys
import pytest
from paperfusion.storage import safe_path
from paperfusion.execution import Executor, run_process
from paperfusion.contracts import Plan


@pytest.mark.parametrize("name", ["../outside.py", "a/../../outside.py", "C:/outside.py",
                                  "C:\\outside.py", "C:outside.py", "a\\..\\outside.py",
                                  "\\\\server\\share\\file.py", "/outside.py"])
def test_path_escape_rejected(tmp_path, name):
    with pytest.raises(ValueError):
        safe_path(tmp_path, name)


def test_process_failure_preserves_output(tmp_path):
    result = run_process([sys.executable, "-c", "print('specific diagnostic'); raise SystemExit(7)"],
                         tmp_path, 10, tmp_path / "failure.log")
    assert result["returncode"] == 7 and not result["passed"]
    assert "specific diagnostic" in result["output"]


def test_process_timeout_is_not_success(tmp_path):
    result = run_process([sys.executable, "-c", "import time; time.sleep(30)"],
                         tmp_path, 1, tmp_path / "timeout.log")
    assert result["timed_out"] and not result["passed"]


def test_container_receives_no_credentials_and_readonly_inputs(tmp_path):
    command = Executor().command(tmp_path / "work", tmp_path / "checks", "test-container")
    assert "--network=none" in command and "--read-only" in command
    assert "--pids-limit=64" in command and "--cap-drop=ALL" in command
    mounts = [command[i+1] for i, arg in enumerate(command) if arg == "--mount"]
    assert len(mounts) == 2 and all("readonly" in m for m in mounts)
    assert not any("API_KEY" in c or "docker.sock" in c for c in command)


def test_plan_dependency_order_enforced():
    with pytest.raises(ValueError, match="dependencies"):
        Plan.model_validate({"summary": "x", "tasks": [{"id": "a", "title": "a", "files": ["a.py"],
                            "depends_on": ["b"], "specification": "x", "acceptance": ["x"]}]})
