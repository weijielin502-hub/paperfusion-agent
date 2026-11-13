# Case: integrate Reciprocal Rank Fusion

**Starting program:** `project/search_app.py` calls `fusion.fuse`; `fusion.py` returned only the first retriever's list. The Agent applied RRF while preserving that interface.

**Paper evidence:** Section 1, page 1 of [Cormack et al. (2009)](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) defines `sum(1/(k+rank))` with `k=60`. One-based positions, truncated-list handling, duplicate behavior and deterministic ties are checked in controller-owned tests. The latter three are documented project adaptations.

**Actual live run:** [live-report.html](live-report.html) is a snapshot of a real `deepseek-flash` run. Planner chose one direct task, Implementer edited `fusion.py`, eight Docker acceptance tests passed, and Reviewer and Monitor approved. All four roles made model calls. The diff and machine-readable evidence are in `live-evidence/`.

**Measured result:** Across four hand-authored queries with relevance labels, RRF raised nDCG@3 on one, lowered it on two, and tied on one relative to the first retriever. This is too small for a general quality claim and does not replicate TREC or LETOR results.

**Replay:** The scripted fixture first shifts ranks to zero-based indexing. Acceptance checks reject this and the fixture repairs it on attempt two. This proves controller feedback and resume, with no model-generated repair.

**Controlled ablation:** The [no-review report](ablation-report.html) uses the exact plan saved by the full run and the same DeepSeek model, starting code and Docker acceptance checks. It omits Reviewer and Monitor. Both runs passed all eight tests and produced the same four synthetic-query metrics. The full run used 15 model calls (43,566 input and 6,038 output tokens); the ablation used 3 (8,242 input and 1,199 output tokens). The full run includes an additional planning call, while the ablation loads the frozen plan, so token totals include that difference. With this one easy task, the extra review did not improve the measured outcome; it produced inspectable alignment and quality judgments at higher cost. See [machine-readable comparison](comparison.json). No general performance claim follows from one task.
