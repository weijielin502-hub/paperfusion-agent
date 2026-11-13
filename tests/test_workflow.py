import pytest
from paperfusion.contracts import RunSettings
from paperfusion.workflow import ROOT, Workflow, create_run
from paperfusion.storage import read_json


def make_run(tmp_path, **kwargs):
    example = ROOT / "examples/rrf"
    settings = RunSettings(goal="Integrate RRF", project=str(example / "project"),
                           paper=str(example / "paper.json"), acceptance=str(example / "acceptance"),
                           mode="replay", executor="local-trusted", auto_approve=True, **kwargs)
    run = tmp_path / "run"
    create_run(run, settings)
    return run


def test_real_acceptance_rejects_first_attempt_then_passes(tmp_path):
    run = make_run(tmp_path)
    result = Workflow(run).execute()
    assert result["status"] == "completed"
    checks = [read_json(p) for p in sorted((run / "checks").glob("*.json"))]
    assert [c["passed"] for c in checks] == [False, True]
    assert "METRICS_JSON=" in read_json(run / "evaluation.json")["output"]
    assert "SCRIPTED REPLAY" in (run / "report.html").read_text(encoding="utf-8")


def test_checkpoint_resume_does_not_redo_implementation(tmp_path):
    run = make_run(tmp_path)
    Workflow(run).execute(stop_after="implement")
    receipt = run / "steps/00-01-implementer/result.json"
    before = receipt.read_bytes()
    Workflow(run).execute(resume=True)
    assert receipt.read_bytes() == before
    assert read_json(run / "state.json")["status"] == "completed"


def test_fuse_persists_and_requires_explicit_decision(tmp_path):
    run = make_run(tmp_path, force_fuse=True)
    result = Workflow(run).execute()
    assert result["status"] == "paused"
    assert len(result["history"]) == 3
    assert Workflow(run).execute(resume=True)["status"] == "paused"
    assert Workflow(run).execute(resume=True, decision={"action": "stop"})["status"] == "stopped"


def test_changed_workspace_cannot_silently_resume(tmp_path):
    run = make_run(tmp_path)
    Workflow(run).execute(stop_after="implement")
    (run / "workspace/fusion.py").write_text("tampered = True", encoding="utf-8")
    with pytest.raises(ValueError, match="Workspace differs"):
        Workflow(run).execute(resume=True)


def test_acceptance_cannot_be_silently_changed(tmp_path):
    run = make_run(tmp_path)
    (run / "acceptance/verify.py").write_text("raise SystemExit(0)", encoding="utf-8")
    with pytest.raises(ValueError, match="Workspace differs"):
        Workflow(run).execute()


def test_nested_run_directory_rejected(tmp_path):
    settings = RunSettings(goal="test", project=str(tmp_path), paper=str(ROOT / "examples/rrf/paper.json"),
                           acceptance=str(ROOT / "examples/rrf/acceptance"), mode="replay", executor="local-trusted")
    with pytest.raises(ValueError, match="outside"):
        create_run(tmp_path / "run", settings)


def test_live_code_requires_isolation():
    with pytest.raises(ValueError, match="Docker"):
        RunSettings(goal="x", project="x", paper="x", acceptance="x", mode="live", executor="local-trusted")


def test_frozen_plan_is_used_without_model_planning(tmp_path):
    example = ROOT / "examples/rrf"
    settings = RunSettings(goal="Integrate RRF", project=str(example / "project"),
                           paper=str(example / "paper.json"), acceptance=str(example / "acceptance"),
                           mode="replay", executor="local-trusted", auto_approve=True)
    run = tmp_path / "frozen"
    create_run(run, settings, example / "plan.json")
    result = Workflow(run).execute()
    assert result["status"] == "completed"
    assert read_json(run / "steps/00-01-planner/trace.json")["usage"]["model_calls"] == 0


def test_reviewer_rejection_reenters_implementer(tmp_path, monkeypatch):
    run = make_run(tmp_path)
    workflow = Workflow(run)
    original = workflow.agent.run
    rejected = {"count": 0}

    def role_with_one_rejection(role, context, evidence_dir):
        if role == "reviewer" and rejected["count"] == 0:
            rejected["count"] += 1
            return {"verdict": "changes_required", "summary": "Need a clearer implementation",
                    "findings": ["Inspect fusion.py again"], "evidence": ["fusion.py"]}
        return original(role, context, evidence_dir)

    monkeypatch.setattr(workflow.agent, "run", role_with_one_rejection)
    result = workflow.execute()
    assert result["status"] == "completed"
    assert len(result["history"]) == 3  # test fail, review fail, accepted
    assert (run / "steps/00-03-implementer/result.json").exists()
