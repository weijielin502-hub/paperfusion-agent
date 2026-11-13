# Repository guide for coding agents

PaperFusion 0.2 uses Python, LangGraph, LangChain model tools and a read-only Docker acceptance runner. See `README.md` and `docs/ARCHITECTURE.md` before changing the workflow. The original OpenCode POC configuration and prompts are preserved under `legacy/` for provenance; they are not the current runtime.

- Keep `paper2code/` vendor source unchanged. Fix integration behavior in `p2c_tools/`.
- Do not read, print, commit or transmit `.env.local`. It contains a user-owned API key.
- Write model-generated application code only inside a run workspace and only in the frozen task's allowed files.
- Keep acceptance checks controller-owned and separate from the generated source mount.
- Record failed calls and tests; do not relabel a scripted replay as a model run or synthetic metrics as paper benchmark reproduction.
- Run `pytest` and `ruff` after workflow changes. Docker replay is the integration gate.
