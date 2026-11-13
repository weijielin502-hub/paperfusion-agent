"""Durable task orchestration. Every model role is a bounded tool loop."""
from __future__ import annotations
import difflib
import sqlite3
from pathlib import Path
from typing import TypedDict
from filelock import FileLock
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from .agents import ModelAgent, ReplayAgent
from .contracts import AgentResult, Plan, RunSettings
from .execution import Executor, ToolFailure
from .storage import atomic_text, copy_source, digest, manifest, read_json, safe_path, verify_manifest, write_json

ROOT = Path(__file__).resolve().parent.parent


class State(TypedDict, total=False):
    plan: dict
    index: int
    attempt: int
    limit: int
    status: str
    feedback: list[str]
    verdict: str
    current_manifest: dict
    verification: dict
    history: list[dict]


def create_run(path: Path, settings: RunSettings, frozen_plan: Path | None = None):
    path = path.resolve()
    if path.exists():
        raise ValueError("Run directory already exists. Use resume or choose a new directory.")
    source = Path(settings.project).resolve()
    paper = Path(settings.paper).resolve()
    acceptance = Path(settings.acceptance).resolve()
    if not source.is_dir() or not paper.is_file() or not (acceptance / "verify.py").is_file():
        raise ValueError("Project, paper JSON and acceptance/verify.py must exist")
    if path.is_relative_to(source) or path.is_relative_to(acceptance):
        raise ValueError("Run directory must be outside project and acceptance inputs")
    paper_data = read_json(paper)
    path.mkdir(parents=True)
    copy_source(source, path / "workspace")
    copy_source(source, path / "original")
    copy_source(acceptance, path / "acceptance")
    write_json(path / "paper.json", paper_data)
    write_json(path / "settings.json", settings.model_dump())
    write_json(path / "inputs.json", {"original": manifest(path / "original"),
                                     "acceptance": manifest(path / "acceptance"),
                                     "paper": digest(paper_data)})
    if frozen_plan:
        plan = Plan.model_validate(read_json(Path(frozen_plan))).model_dump()
        for task in plan["tasks"]:
            for name in task["files"]:
                safe_path(path / "workspace", name)
        write_json(path / "frozen-plan.json", plan)


class Workflow:
    def __init__(self, run_dir: Path):
        self.root = run_dir.resolve()
        self.settings = RunSettings.model_validate(read_json(self.root / "settings.json"))
        self.workspace = self.root / "workspace"
        self.paper = read_json(self.root / "paper.json")
        self.executor = Executor(self.settings.executor, self.settings.timeout_seconds)
        if self.settings.mode == "live":
            self.agent = ModelAgent(self.workspace, self.root / "acceptance", self.executor,
                                    self.settings.model, self.settings.max_tool_rounds)
        else:
            self.agent = ReplayAgent(self.workspace, ROOT / "examples" / "rrf", self.settings.force_fuse)

    def validate_inputs(self):
        saved = read_json(self.root / "inputs.json")
        verify_manifest(self.root / "original", saved["original"])
        verify_manifest(self.root / "acceptance", saved["acceptance"])
        if digest(self.paper) != saved["paper"]:
            raise ValueError("Paper changed after this run was created")

    def analyze(self, state):
        if self.settings.analysis == "p2c":
            from p2c_tools.p2c_wrapper import analyze_paper_full
            out = self.root / "p2c_analysis"
            receipt = out / "complete.json"
            key = digest({"paper": self.paper, "model": self.settings.model,
                          "vendor": manifest(ROOT / "paper2code" / "codes")})
            if receipt.exists():
                saved = read_json(receipt)
                if saved["key"] != key:
                    raise ValueError("P2C analysis cache does not match current inputs")
            else:
                analyze_paper_full("paper", self.settings.model, self.root / "paper.json", out)
                write_json(receipt, {"key": key})
        else:
            write_json(self.root / "analysis.json", {"origin": "provided evidence, not a P2C execution",
                                                      "paper": self.paper})
        return {"status": "planning", "index": 0, "attempt": 1, "limit": self.settings.max_attempts,
                "feedback": [], "history": [], "current_manifest": manifest(self.workspace)}

    def context(self, state):
        context = {"goal": self.settings.goal, "paper": self.paper, "feedback": state.get("feedback", []),
                   "attempt": state.get("attempt", 1), "verification": state.get("verification", {}),
                   "project_files": list(manifest(self.workspace)), "baseline": self.settings.baseline}
        if state.get("plan"):
            context["task"] = state["plan"]["tasks"][state["index"]]
        analysis = self.root / "p2c_analysis" / "analyzing_artifacts"
        if analysis.is_dir():
            context["p2c_analysis"] = {f.name: f.read_text(encoding="utf-8")[:16000]
                                       for f in sorted(analysis.glob("*.txt"))[:12]}
        generated = self.root / "generated" / "repo"
        if generated.is_dir():
            context["generated_reference"] = {name: safe_path(generated, name).read_text(encoding="utf-8")[:12000]
                                               for name in list(manifest(generated))[:12]}
        return context

    def role(self, name, state):
        key = f"{state.get('index', 0):02d}-{state.get('attempt', 1):02d}-{name}"
        folder = self.root / "steps" / key
        receipt = folder / "result.json"
        context = self.context(state)
        # Workspace changes are intentional during implementation, but no other role can write.
        identity = digest({"role": name, "task": context.get("task"), "goal": self.settings.goal,
                           "paper": self.paper, "feedback": state.get("feedback", []),
                           "input_manifest": state.get("current_manifest")})
        if receipt.exists():
            saved = read_json(receipt)
            if saved["identity"] != identity:
                raise ValueError("Role receipt does not match checkpoint inputs")
            verify_manifest(self.workspace, saved["manifest"])
            return saved["result"]
        folder.mkdir(parents=True, exist_ok=True)
        before = folder / "before.json"
        if name == "implementer":
            allowed = context["task"]["files"]
            if before.exists():
                # A process died mid-role. Restore exactly its writable files before replay.
                original = read_json(before)
                for rel, content in original.items():
                    target = safe_path(self.workspace, rel)
                    if content is None:
                        if target.exists():
                            target.unlink()
                    else:
                        atomic_text(target, content)
            else:
                verify_manifest(self.workspace, state["current_manifest"])
                write_json(before, {rel: safe_path(self.workspace, rel).read_text(encoding="utf-8")
                                   if safe_path(self.workspace, rel).exists() else None for rel in allowed})
        verify_manifest(self.workspace, state["current_manifest"])
        write_json(folder / "input.json", context)
        result = self.agent.run(name, context, folder)
        schema = Plan if name == "planner" else AgentResult
        result = schema.model_validate(result).model_dump()
        after = manifest(self.workspace)
        if name != "implementer" and after != state["current_manifest"]:
            raise ToolFailure("Read-only role changed workspace")
        write_json(receipt, {"identity": identity, "result": result, "manifest": after})
        return result

    def plan(self, state):
        frozen = self.root / "frozen-plan.json"
        if frozen.exists():
            plan = Plan.model_validate(read_json(frozen)).model_dump()
            write_json(self.root / "steps" / "00-01-planner" / "trace.json",
                       {"mode": "frozen_plan", "usage": {"model_calls": 0}, "events": []})
            write_json(self.root / "steps" / "00-01-planner" / "result.json",
                       {"identity": digest(plan), "result": plan, "manifest": manifest(self.workspace)})
        else:
            plan = self.role("planner", state)
        for task in plan["tasks"]:
            for name in task["files"]:
                safe_path(self.workspace, name)
            if task["strategy"] == "p2c" and self.settings.analysis != "p2c":
                raise ToolFailure("Planner selected P2C generation, but analysis mode is provided. "
                                  "Use --analysis p2c for this task or supply a direct plan.")
        write_json(self.root / "plan.json", plan)
        return {"plan": plan, "status": "awaiting_plan"}

    def approve(self, state):
        approved = self.settings.auto_approve or interrupt({"kind": "plan", "plan": state["plan"]})
        if approved is not True:
            return {"status": "cancelled"}
        write_json(self.root / "approval.json", {"approved": True, "automatic": self.settings.auto_approve,
                                                "plan_hash": digest(state["plan"])})
        return {"status": "running"}

    def generate(self, state):
        task = state["plan"]["tasks"][state["index"]]
        if task["strategy"] == "p2c":
            from p2c_tools.p2c_wrapper import run_coding
            out = self.root / "generated"
            receipt = out / "complete.json"
            identity = digest({"analysis": read_json(self.root / "p2c_analysis" / "complete.json"),
                               "model": self.settings.model})
            if receipt.exists():
                saved = read_json(receipt)
                if saved["identity"] != identity:
                    raise ValueError("Generated repository belongs to another paper/configuration")
                verify_manifest(out / "repo", saved["manifest"])
            else:
                run_coding("paper", self.settings.model, self.root / "paper.json",
                           self.root / "p2c_analysis", out / "repo")
                write_json(receipt, {"identity": identity, "manifest": manifest(out / "repo")})
        return {"status": "implementing"}

    def implement(self, state):
        result = self.role("implementer", state)
        return {"current_manifest": manifest(self.workspace), "status": "testing", "verdict": result["verdict"]}

    def verify(self, state):
        verify_manifest(self.workspace, state["current_manifest"])
        self.validate_inputs()
        log = self.root / "checks" / f"task-{state['index']}-attempt-{state['attempt']}.log"
        result = self.executor.verify(self.workspace, self.root / "acceptance", log)
        write_json(log.with_suffix(".json"), result)
        return {"verification": result, "verdict": "approved" if result["passed"] else "changes_required",
                "status": "reviewing", "feedback": [] if result["passed"] else [result["output"]]}

    def review(self, state):
        result = self.role("reviewer", state)
        return {"verdict": result["verdict"], "feedback": result["findings"] + [result["summary"]],
                "status": "monitoring"}

    def monitor(self, state):
        result = self.role("monitor", state)
        return {"verdict": result["verdict"], "feedback": result["findings"] + [result["summary"]]}

    def retry(self, state):
        history = state["history"] + [{"task": state["index"], "attempt": state["attempt"],
                                       "outcome": "repair_required", "feedback": state["feedback"]}]
        return {"attempt": state["attempt"] + 1, "history": history,
                "status": "paused" if state["attempt"] >= state["limit"] else "repairing"}

    def pause(self, state):
        decision = interrupt({"kind": "repair_budget", "task": state["plan"]["tasks"][state["index"]]["id"],
                              "failed_attempts": state["attempt"] - 1, "feedback": state["feedback"],
                              "options": ["retry", "stop"]})
        if isinstance(decision, dict) and decision.get("action") == "retry":
            extra = int(decision.get("additional_attempts", 1))
            if not 1 <= extra <= 3:
                raise ValueError("A recovery decision can grant 1–3 extra attempts")
            return {"limit": state["limit"] + extra, "status": "repairing",
                    "feedback": state["feedback"] + [str(decision.get("feedback", ""))]}
        return {"status": "stopped"}

    def advance(self, state):
        history = state["history"] + [{"task": state["index"], "attempt": state["attempt"], "outcome": "accepted"}]
        return {"index": state["index"] + 1, "attempt": 1, "limit": self.settings.max_attempts,
                "feedback": [], "history": history, "status": "running"}

    def finish(self, state):
        self.validate_inputs()
        verify_manifest(self.workspace, state["current_manifest"])
        result = self.executor.verify(self.workspace, self.root / "acceptance", self.root / "final-check.log")
        write_json(self.root / "evaluation.json", result)
        original = self.root / "original"
        diff = []
        for name in sorted(set(manifest(original)) | set(manifest(self.workspace))):
            old, new = safe_path(original, name), safe_path(self.workspace, name)
            old_text = old.read_text(encoding="utf-8").splitlines(True) if old.exists() else []
            new_text = new.read_text(encoding="utf-8").splitlines(True) if new.exists() else []
            diff.extend(difflib.unified_diff(old_text, new_text, fromfile="before/"+name, tofile="after/"+name))
        atomic_text(self.root / "changes.diff", "".join(diff))
        return {"status": "completed" if result["passed"] else "experiment_failed", "verification": result}

    def graph(self, saver):
        builder = StateGraph(State)
        for name in ("analyze", "plan", "approve", "generate", "implement", "verify", "review", "monitor",
                     "retry", "pause", "advance", "finish"):
            builder.add_node(name, getattr(self, name))
        builder.add_edge(START, "analyze")
        builder.add_edge("analyze", "plan")
        builder.add_edge("plan", "approve")
        builder.add_conditional_edges("approve", lambda s: "finish" if s["status"] == "cancelled" else "go",
                                      {"finish": END, "go": "generate"})
        builder.add_edge("generate", "implement")
        builder.add_edge("implement", "verify")
        builder.add_conditional_edges("verify", lambda s: "pass" if s["verification"]["passed"] else "fail",
                                      {"pass": "advance" if self.settings.baseline else "review", "fail": "retry"})
        builder.add_conditional_edges("review", lambda s: s["verdict"] == "approved",
                                      {True: "monitor", False: "retry"})
        builder.add_conditional_edges("monitor", lambda s: s["verdict"] == "approved",
                                      {True: "advance", False: "retry"})
        builder.add_conditional_edges("retry", lambda s: s["status"] == "paused",
                                      {True: "pause", False: "generate"})
        builder.add_conditional_edges("pause", lambda s: s["status"] == "stopped",
                                      {True: END, False: "generate"})
        builder.add_conditional_edges("advance", lambda s: s["index"] >= len(s["plan"]["tasks"]),
                                      {True: "finish", False: "generate"})
        builder.add_edge("finish", END)
        return builder.compile(checkpointer=saver)

    def execute(self, *, resume=False, decision=None, stop_after=None):
        self.validate_inputs()
        with FileLock(str(self.root / "run.lock"), timeout=0):
            with sqlite3.connect(self.root / "checkpoints.sqlite", check_same_thread=False) as connection:
                graph = self.graph(SqliteSaver(connection))
                config = {"configurable": {"thread_id": "run"}, "recursion_limit": 1000}
                old = graph.get_state(config)
                if resume:
                    if not old.values:
                        raise ValueError("No checkpoint exists to resume")
                    if not old.next:
                        return dict(old.values)
                    has_interrupt = any(t.interrupts for t in old.tasks)
                    if has_interrupt and decision is None:
                        return dict(old.values)
                    initial = Command(resume=decision) if has_interrupt else None
                else:
                    if old.values:
                        raise ValueError("Existing checkpoint: use resume")
                    initial = {}
                try:
                    for update in graph.stream(initial, config, stream_mode="updates", durability="sync"):
                        checkpoint = graph.get_state(config)
                        write_json(self.root / "state.json", dict(checkpoint.values))
                        names = [k for k in update if not k.startswith("__")]
                        if names:
                            print(" → ".join(names), flush=True)
                        if stop_after and stop_after in names:
                            break
                except Exception as exc:
                    write_json(self.root / "error.json", {"type": type(exc).__name__, "message": str(exc),
                                                          "recovery": "Fix infrastructure, then resume"})
                    raise
                finally:
                    checkpoint = graph.get_state(config)
                    final = dict(checkpoint.values)
                    write_json(self.root / "state.json", final)
                    from .report import render_report
                    render_report(self.root)
                return final
