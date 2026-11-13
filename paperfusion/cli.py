from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from .contracts import RunSettings
from .workflow import ROOT, Workflow, create_run


def configure():
    load_dotenv(ROOT / ".env.local", override=False)
    if not os.getenv("OPENAI_API_KEY") and os.getenv("DEEPSEEK_API_KEY"):
        os.environ["OPENAI_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]
    os.environ.setdefault("OPENAI_BASE_URL", "https://api.deepseek.com")
    os.environ.setdefault("OPENAI_MODEL", "deepseek-flash")


def main():
    configure()
    parser = argparse.ArgumentParser(description="PaperFusion: integrate paper methods with execution evidence")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--output", required=True)
    run.add_argument("--mode", choices=["live", "replay"], default="live")
    run.add_argument("--executor", choices=["docker", "local-trusted"], default="docker")
    run.add_argument("--analysis", choices=["provided", "p2c"], default="provided")
    run.add_argument("--project", default=str(ROOT / "examples/rrf/project"))
    run.add_argument("--paper", default=str(ROOT / "examples/rrf/paper.json"))
    run.add_argument("--plan-file", help="Validated frozen plan; useful for controlled comparisons")
    run.add_argument("--acceptance", default=str(ROOT / "examples/rrf/acceptance"))
    run.add_argument("--goal", default="Integrate reciprocal rank fusion into the existing search application. "
                     "Preserve search_app.py and its public interface. Implement the supplied paper contract in fusion.py.")
    run.add_argument("--auto-approve", action="store_true")
    run.add_argument("--force-fuse", action="store_true", help="Replay fixture only: fail every repair attempt")
    run.add_argument("--without-reviews", action="store_true", help="Ablation: implement/test without Reviewer/Monitor")
    run.add_argument("--stop-after", choices=["analyze", "plan", "approve", "generate", "implement", "verify", "review"])
    run.add_argument("--max-attempts", type=int, default=3)
    resume = sub.add_parser("resume")
    resume.add_argument("run_dir")
    resume.add_argument("--approve", action="store_true")
    resume.add_argument("--retry", action="store_true")
    resume.add_argument("--stop", action="store_true")
    resume.add_argument("--feedback", default="")
    report = sub.add_parser("report")
    report.add_argument("run_dir")
    sub.add_parser("doctor")
    args = parser.parse_args()
    if args.command == "doctor":
        import shutil
        print(json.dumps({"key_configured": bool(os.getenv("OPENAI_API_KEY")),
                          "model": os.getenv("OPENAI_MODEL"), "docker_cli": bool(shutil.which("docker")),
                          "p2c_scripts_present": (ROOT / "paper2code/codes/3_coding.py").is_file()}, indent=2))
        return
    if args.command == "report":
        from .report import render_report
        print(render_report(Path(args.run_dir)))
        return
    if args.command == "run":
        if args.mode == "live" and not os.getenv("OPENAI_API_KEY"):
            parser.error("Set OPENAI_API_KEY or DEEPSEEK_API_KEY in .env.local")
        if args.mode == "live" and args.force_fuse:
            parser.error("--force-fuse is only for replay fixtures")
        settings = RunSettings(goal=args.goal, project=str(Path(args.project).resolve()),
                               paper=str(Path(args.paper).resolve()), acceptance=str(Path(args.acceptance).resolve()),
                               mode=args.mode, analysis=args.analysis, executor=args.executor,
                               model=os.environ["OPENAI_MODEL"] if args.mode == "live" else "",
                               auto_approve=args.auto_approve, force_fuse=args.force_fuse,
                               max_attempts=args.max_attempts, baseline=args.without_reviews)
        path = Path(args.output)
        create_run(path, settings, Path(args.plan_file) if args.plan_file else None)
        result = Workflow(path).execute(stop_after=args.stop_after)
    else:
        path = Path(args.run_dir)
        decision = True if args.approve else ({"action": "retry", "feedback": args.feedback} if args.retry
                                              else ({"action": "stop"} if args.stop else None))
        result = Workflow(path).execute(resume=True, decision=decision)
    print(json.dumps({"status": result.get("status"), "report": str(path.resolve() / "report.html")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
