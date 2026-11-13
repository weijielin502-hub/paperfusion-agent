#!/usr/bin/env python3
"""
P2C Wrapper — 封装 Paper2Code 脚本调用，提供统一的 Python 接口。
SDD 的 implementer subagent 可通过此模块间接调用 P2C，无需记忆 Shell 参数拼接细节。

用法:
  from p2c_tools.p2c_wrapper import run_planning, run_analyzing, run_coding, analyze_paper_full

  analyze_paper_full(paper_name="Transformer",
                     gpt_version="o3-mini",
                     pdf_json_path="examples/Transformer_cleaned.json",
                     output_dir="p2c_outputs/Transformer")
"""
import os
import subprocess
import sys
from pathlib import Path

P2C_ROOT = Path(__file__).resolve().parent.parent / "paper2code"
P2C_CODES = P2C_ROOT / "codes"


def _run_python_script(script_name, args_dict):
    script_path = P2C_CODES / script_name
    if not script_path.exists():
        raise FileNotFoundError("P2C script not found: " + str(script_path))

    cmd = [sys.executable, str(script_path)]
    for key, value in args_dict.items():
        cmd += ["--" + key, value]

    print("[P2C Wrapper] Running: " + " ".join(cmd))
    result = subprocess.run(cmd, capture_output=False, text=True, cwd=str(P2C_CODES.parent))
    return result


def run_planning(paper_name, gpt_version, pdf_json_path, output_dir):
    _run_python_script("1_planning.py", {
        "paper_name": paper_name,
        "gpt_version": gpt_version,
        "pdf_json_path": pdf_json_path,
        "output_dir": output_dir,
    })


def run_extract_config(paper_name, output_dir):
    _run_python_script("1.1_extract_config.py", {
        "paper_name": paper_name,
        "output_dir": output_dir,
    })


def run_analyzing(paper_name, gpt_version, pdf_json_path, output_dir):
    _run_python_script("2_analyzing.py", {
        "paper_name": paper_name,
        "gpt_version": gpt_version,
        "pdf_json_path": pdf_json_path,
        "output_dir": output_dir,
    })


def run_coding(paper_name, gpt_version, pdf_json_path, output_dir, output_repo_dir):
    _run_python_script("3_coding.py", {
        "paper_name": paper_name,
        "gpt_version": gpt_version,
        "pdf_json_path": pdf_json_path,
        "output_dir": output_dir,
        "output_repo_dir": output_repo_dir,
    })


def run_debugging(paper_name, gpt_version, output_repo_dir):
    _run_python_script("4_debugging.py", {
        "paper_name": paper_name,
        "gpt_version": gpt_version,
        "output_repo_dir": output_repo_dir,
    })


def analyze_paper_full(paper_name, gpt_version, pdf_json_path, output_dir):
    """一键运行 Planning + Config提取 + Analyzing"""
    os.makedirs(output_dir, exist_ok=True)

    print("[P2C Wrapper] === Phase 1: Planning ===")
    run_planning(paper_name, gpt_version, pdf_json_path, output_dir)

    print("[P2C Wrapper] === Phase 1.1: Extract Config ===")
    run_extract_config(paper_name, output_dir)

    print("[P2C Wrapper] === Phase 2: Analyzing ===")
    run_analyzing(paper_name, gpt_version, pdf_json_path, output_dir)

    return {
        "planning_dir": os.path.join(output_dir, "planning_artifacts"),
        "analyzing_dir": os.path.join(output_dir, "analyzing_artifacts"),
        "config_yaml": os.path.join(output_dir, "planning_config.yaml"),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="P2C Wrapper CLI")
    subparsers = parser.add_subparsers(dest="command")

    p_plan = subparsers.add_parser("plan", help="Run planning")
    p_plan.add_argument("--paper", required=True)
    p_plan.add_argument("--gpt", default="o3-mini")
    p_plan.add_argument("--json", required=True)
    p_plan.add_argument("--out", required=True)

    p_analyze = subparsers.add_parser("analyze", help="Run analyzing")
    p_analyze.add_argument("--paper", required=True)
    p_analyze.add_argument("--gpt", default="o3-mini")
    p_analyze.add_argument("--json", required=True)
    p_analyze.add_argument("--out", required=True)

    p_code = subparsers.add_parser("code", help="Run coding")
    p_code.add_argument("--paper", required=True)
    p_code.add_argument("--gpt", default="o3-mini")
    p_code.add_argument("--json", required=True)
    p_code.add_argument("--out", required=True)
    p_code.add_argument("--repo", required=True)

    p_full = subparsers.add_parser("full", help="Run planning + config + analyzing")
    p_full.add_argument("--paper", required=True)
    p_full.add_argument("--gpt", default="o3-mini")
    p_full.add_argument("--json", required=True)
    p_full.add_argument("--out", required=True)

    args = parser.parse_args()

    if args.command == "plan":
        run_planning(args.paper, args.gpt, args.json, args.out)
    elif args.command == "analyze":
        run_analyzing(args.paper, args.gpt, args.json, args.out)
    elif args.command == "code":
        run_coding(args.paper, args.gpt, args.json, args.out, args.repo)
    elif args.command == "full":
        analyze_paper_full(args.paper, args.gpt, args.json, args.out)
    else:
        parser.print_help()
