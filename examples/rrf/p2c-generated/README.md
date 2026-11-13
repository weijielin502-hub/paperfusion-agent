# Reciprocal Rank Fusion (RRF) Reproduction

Reproduction of **Reciprocal Rank Fusion** from Cormack, Clarke & Büttcher,
*"Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning
Methods"* (SIGIR 2009), plus the project's explicit input-handling adaptations
and its integration at `search_app.search_results`.

> **Scope note (must read).** The supplied material is a maintainer-written
> method note plus an implementation contract — **not** the full paper. This
> project therefore reproduces the **method and its integration on synthetic
> rankings only**. It does **not** reproduce the paper's TREC / LETOR datasets,
> qrels, baselines, or reported MAP / NDCG scores, because those artifacts are
> not available in the supplied material.

---

## 1. What this project does and does not do

| | |
|---|---|
| **Reproduces** | The RRF score formula `RRF(d) = Σ 1/(k + rank_r(d))`, the paper's fixed `k = 60`, ranks starting at 1, equal weighting across lists, descending-score output, and ascending-document-ID tie-breaking. |
| **Reproduces (project adaptations)** | Truncated rankings, missing documents contributing `0.0`, within-list duplicate IDs counting only at their first position **without renumbering** later positions, and lexicographic tie-breaking. |
| **Integrates** | `search_app.search_results(rankings, limit=None) -> list[str]`, preserving the caller-facing signature and return schema. |
| **Evaluates** | Deterministic synthetic rankings with pass/fail unit tests, exact order matching, and a bounded numeric tolerance of `1e-12`. |
| **Does NOT do** | No training. No learning rate, batch size, epoch count, or optimizer. No external datasets. No network access. No randomness. No retrieval metrics (MAP / NDCG / etc.). No tuning of `k`. |

---

## 2. The method

For every document `d`:
