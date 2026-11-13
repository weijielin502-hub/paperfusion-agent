"""Portable, escaped HTML evidence report with no external assets."""
from __future__ import annotations
import html
import json
import os
from pathlib import Path
from .storage import atomic_text, read_json


def esc(value):
    return html.escape(str(value))


def render_report(root: Path):
    state = read_json(root / "state.json") if (root / "state.json").exists() else {}
    settings = read_json(root / "settings.json")
    plan = state.get("plan", {"tasks": [], "summary": "Waiting for planning"})
    cards, events, tokens, calls, input_tokens, output_tokens = [], [], 0, 0, 0, 0
    for step in sorted((root / "steps").glob("*")) if (root / "steps").exists() else []:
        result = read_json(step / "result.json")["result"] if (step / "result.json").exists() else {}
        trace = read_json(step / "trace.json") if (step / "trace.json").exists() else {}
        usage = trace.get("usage", {})
        calls += usage.get("model_calls", 0)
        input_tokens += usage.get("input_tokens", 0)
        output_tokens += usage.get("output_tokens", 0)
        tokens = input_tokens + output_tokens
        events.extend(trace.get("events", []))
        verdict = result.get("verdict", "plan" if "tasks" in result else "incomplete")
        content = esc(json.dumps(result or trace, ensure_ascii=False, indent=2))
        cards.append(f'<details class="step"><summary><span>{esc(step.name)}</span>'
                     f'<b class="badge">{esc(verdict)}</b></summary><p>{esc(result.get("summary", ""))}</p>'
                     f'<pre>{content}</pre><a href="steps/{esc(step.name)}/trace.json">Tool trace ↗</a></details>')
    checks = []
    for path in sorted((root / "checks").glob("*.json")) if (root / "checks").exists() else []:
        item = read_json(path)
        checks.append(f'<details class="step"><summary><span>{esc(path.stem)}</span><b class="badge">'
                      f'{"PASS" if item["passed"] else "FAIL"}</b></summary><pre>{esc(item["output"])}</pre></details>')
    evaluation = read_json(root / "evaluation.json") if (root / "evaluation.json").exists() else {}
    metrics = None
    for line in evaluation.get("output", "").splitlines():
        if line.startswith("METRICS_JSON="):
            try:
                metrics = json.loads(line.split("=", 1)[1])
            except ValueError:
                pass
    metric_html = '<p class="muted">No final experiment result recorded yet.</p>'
    if metrics:
        rows = []
        for row in metrics.get("queries", []):
            a, b = row["first_retriever_ndcg3"], row["rrf_ndcg3"]
            rows.append(f'<tr><td>Query {row["query"]+1}</td><td>{a:.4f}</td><td>{b:.4f}</td>'
                        f'<td class="delta">{b-a:+.4f}</td></tr>')
        metric_html = '<table><tr><th>Synthetic query</th><th>Original retriever</th><th>RRF</th><th>Δ nDCG@3</th></tr>' + ''.join(rows) + '</table>'
        metric_html += '<p class="muted">Four synthetic queries. This measures method integration, not the paper’s TREC/LETOR benchmark. Improvement is not guaranteed.</p>'
    diff = (root / "changes.diff").read_text(encoding="utf-8") if (root / "changes.diff").exists() else "No final diff yet."
    label = "LIVE MODEL RUN" if settings["mode"] == "live" else "SCRIPTED REPLAY · NO MODEL CALLS"
    try:
        in_price = float(os.environ["PAPERFUSION_INPUT_USD_PER_MILLION"])
        out_price = float(os.environ["PAPERFUSION_OUTPUT_USD_PER_MILLION"])
        cost_label = f"Estimated model cost: ${(input_tokens * in_price + output_tokens * out_price) / 1_000_000:.4f} (configured rates)."
    except (KeyError, ValueError):
        cost_label = "USD cost unknown: provider rates were not configured."
    status = state.get("status", "not_started")
    tasks = ''.join(f'<li><strong>{esc(t["title"])}</strong><span>{esc(t["strategy"])} · {esc(", ".join(t["files"]))}</span></li>' for t in plan["tasks"])
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PaperFusion · Run evidence</title><style>
:root{{--ink:#142438;--muted:#617080;--line:#dce3e8;--paper:#f4f6f8;--accent:#b84c28;--teal:#16756b}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 system-ui,sans-serif}}header{{background:var(--ink);color:#fff;padding:44px max(6vw,24px)}}.wordmark{{letter-spacing:.2em;font-size:12px;color:#a4c4ce}}h1{{font-size:clamp(32px,5vw,56px);line-height:1.1;letter-spacing:-.04em;margin:18px 0}}header p{{max-width:800px;color:#c5d3dc}}.tag{{font-size:11px;letter-spacing:.12em;border:1px solid #567084;padding:5px 10px;border-radius:20px}}main{{max-width:1180px;margin:auto;padding:28px 24px 60px}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:-2px}}.stat,section{{background:white;border:1px solid var(--line);border-radius:12px;padding:22px}}.stat strong{{display:block;font-size:24px;overflow-wrap:anywhere}}.stat span,.muted{{color:var(--muted);font-size:13px}}section{{margin-top:22px}}h2{{font-size:20px;margin:0 0 14px}}.eyebrow{{color:var(--accent);font-size:11px;letter-spacing:.12em;font-weight:700}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}.step{{border-top:1px solid var(--line);padding:13px 0}}summary{{cursor:pointer;display:flex;justify-content:space-between;gap:10px;align-items:center}}.badge{{font-size:11px;font-weight:600;padding:3px 9px;background:#eaf3f0;border-radius:20px;color:var(--teal)}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 ui-monospace,monospace;background:#f1f4f6;padding:16px;border-radius:6px;max-height:420px;overflow:auto}}a{{color:var(--teal)}}table{{width:100%;border-collapse:collapse;text-align:left}}th,td{{padding:12px;border-bottom:1px solid var(--line)}}th{{font-size:12px;color:var(--muted)}}.delta{{font-family:monospace}}ul{{padding-left:20px}}li{{margin:12px 0}}li span{{display:block;color:var(--muted);font-size:12px}}.flow{{font-family:monospace;line-height:2;color:var(--teal)}}footer{{margin-top:24px;color:var(--muted);font-size:12px}}@media(max-width:750px){{.stats{{grid-template-columns:1fr 1fr}}.grid{{grid-template-columns:1fr}}section{{padding:16px}}table{{font-size:12px}}th,td{{padding:8px}}}}
</style></head><body><header><div class="wordmark">PAPERFUSION / ENGINEERING EVIDENCE</div><h1>From paper to working code.</h1><p>{esc(settings['goal'])}</p><span class="tag">{label}</span></header><main>
<div class="stats"><div class="stat"><span>Run status</span><strong>{esc(status)}</strong></div><div class="stat"><span>Model calls</span><strong>{calls}</strong></div><div class="stat"><span>Reported tokens</span><strong>{tokens:,}</strong></div><div class="stat"><span>Execution environment</span><strong>{esc(settings['executor'])}</strong></div></div>
<section><div class="eyebrow">01 / DELIVERY CONTRACT</div><h2>{esc(plan['summary'])}</h2><div class="flow">Paper → Plan → Implement → Test → Review → Align → Evaluate</div><ul>{tasks}</ul><p class="muted">Model: {esc(settings['model'] or 'none')} · Review gates: {'disabled for ablation' if settings.get('baseline') else 'enabled'} · {esc(cost_label)}</p></section>
<div class="grid"><section><div class="eyebrow">02 / AGENT DECISIONS</div><h2>Inspect every role</h2>{''.join(cards)}</section><section><div class="eyebrow">03 / EXECUTED CHECKS</div><h2>Failures remain visible</h2>{''.join(checks) or '<p>No checks recorded yet.</p>'}</section></div>
<section><div class="eyebrow">04 / EXPERIMENT</div><h2>Measured outcomes</h2>{metric_html}</section>
<section><div class="eyebrow">05 / CODE DELIVERY</div><h2>The actual change</h2><details><summary>Open unified diff</summary><pre>{esc(diff)}</pre></details></section>
<footer>PaperFusion · Persistent LangGraph workflow · Read-only review roles · Controller-owned acceptance checks.<br>Replay traces are scripted fixtures. Live model reviews are judgments, not proof of benchmark reproduction.</footer></main></body></html>'''
    atomic_text(root / "report.html", page)
    return root / "report.html"
