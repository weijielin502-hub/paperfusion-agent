"""Runtime compatibility for vendored Paper2Code's OpenAI-only cost table.

The upstream source stays byte-for-byte intact. Token usage is logged without
inventing a price for a model the original cost table does not recognize.
"""
import json
import os
from pathlib import Path

if os.environ.get("PAPERFUSION_P2C_COMPAT") == "1":
    import utils

    def print_log_cost(response_json, model_name, stage, output_dir, accumulated_cost):
        usage = response_json.get("usage") or {}
        entry = {"stage": stage, "model": model_name,
                 "prompt_tokens": usage.get("prompt_tokens"),
                 "completion_tokens": usage.get("completion_tokens"),
                 "price_status": "unknown; no fabricated USD estimate"}
        target = Path(output_dir) / "usage.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print("[PaperFusion usage]", entry)
        return accumulated_cost

    utils.print_log_cost = print_log_cost
