"""Process contracts and credential-free execution of generated code."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .storage import atomic_text


class ToolFailure(RuntimeError):
    pass


def clean_env(extra=None):
    names = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "COMSPEC")
    env = {key: os.environ[key] for key in names if key in os.environ}
    env.update({"PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    env.update(extra or {})
    return env


def run_process(argv: list[str], cwd: Path, timeout: int, log: Path, env=None) -> dict:
    log.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    kwargs = {"start_new_session": True} if os.name != "nt" else {
        "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP
    }
    with log.open("w", encoding="utf-8") as output:
        try:
            proc = subprocess.Popen(argv, cwd=cwd, env=env or clean_env(), stdout=output,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kwargs)
        except OSError as exc:
            raise ToolFailure(f"Cannot start {Path(argv[0]).name}: {exc}") from exc
        timed_out = False
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                               capture_output=True, timeout=15)
            else:
                os.killpg(proc.pid, signal.SIGKILL)
            proc.kill()
            code = proc.wait(timeout=10)
    with log.open("rb") as output:
        output.seek(max(0, log.stat().st_size - 24000))
        tail = output.read().decode("utf-8", errors="replace")
    return {"returncode": code, "timed_out": timed_out, "seconds": round(time.monotonic()-started, 3),
            "output": tail, "log": str(log), "passed": code == 0 and not timed_out}


class Executor:
    def __init__(self, mode="docker", timeout=60, image="paperfusion-runner:0.2"):
        self.mode, self.timeout, self.image = mode, timeout, image

    def command(self, workspace: Path, acceptance: Path, container: str) -> list[str]:
        return ["docker", "run", "--rm", "--name", container, "--network=none", "--read-only",
                "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user", "65534:65534",
                "--cpus=1", "--memory=256m", "--memory-swap=256m", "--pids-limit=64",
                "--log-driver=none", "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m",
                "--mount", f"type=bind,source={workspace.resolve()},target=/workspace,readonly",
                "--mount", f"type=bind,source={acceptance.resolve()},target=/acceptance,readonly",
                "--workdir", "/workspace", "--env", "PYTHONPATH=/workspace",
                "--env", "PYTHONDONTWRITEBYTECODE=1", self.image, "python", "-u", "/acceptance/verify.py"]

    def verify(self, workspace: Path, acceptance: Path, log: Path) -> dict:
        if not (acceptance / "verify.py").is_file():
            raise ToolFailure("Acceptance directory must contain a controller-owned verify.py")
        name = "paperfusion-" + uuid.uuid4().hex[:12]
        if self.mode == "docker":
            argv = self.command(workspace, acceptance, name)
            env = clean_env({k: os.environ[k] for k in ("DOCKER_HOST", "DOCKER_CONFIG", "DOCKER_CONTEXT")
                             if k in os.environ})
        else:
            argv = [sys.executable, "-u", str((acceptance / "verify.py").resolve())]
            env = clean_env({"PYTHONPATH": str(workspace.resolve())})
        try:
            result = run_process(argv, workspace, self.timeout, log, env)
        finally:
            if self.mode == "docker":
                subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=20, env=env)
        result["executor"] = self.mode
        if self.mode == "docker" and result["returncode"] in (125, 126, 127):
            raise ToolFailure("Docker infrastructure failure; see " + str(log))
        atomic_text(log.with_suffix(".command.txt"), "\n".join(argv))
        return result
