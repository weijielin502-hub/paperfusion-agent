## main.py
"""Demo entry point for the Reciprocal Rank Fusion reproduction.

Runs a small synthetic demonstration of Reciprocal Rank Fusion (Cormack,
Clarke & Buettcher, SIGIR 2009) using the project's ``search_app`` integration
and the ``fusion`` implementation. No external datasets, training, or TREC/LETOR
scoring are involved (see ``config.yaml`` evaluation scope).

Design relationships exercised here:

* ``Main --> SearchApp``   — via ``self.search_app.search_results(...)``.
* ``Main --> FusionAPI``   — via ``self.fusion_api.scores(...)``.
* ``SearchApp o-- FusionAPI`` — ``SearchApp`` delegates fusion calls to the
  injected ``FusionAPI`` instance.

The method itself (formula ``1 / (k + rank)``, first-position de-duplication,
missing-document zero contribution, descending score, ascending document-ID
tie-break, and validation) lives entirely in ``fusion.py``; this module must
not re-implement any of it.
"""

import json
from typing import Any, Dict, Iterable, List, Optional, Union

from fusion import fuse as rrf_fuse, scores as rrf_scores
from search_app import K, SearchApp

__all__ = ["Main"]


class _FusionAPIImpl:
    """Concrete FusionAPI adapter over the module-level fusion functions.

    Exposes the ``scores`` / ``fuse`` surface required by ``SearchApp`` (see
    ``search_app.FusionAPI``) while honoring a caller-supplied ``k``. Delegates
    every bit of RRF behavior — validation, first-occurrence de-duplication,
    missing-document zero contribution, ordering, and tie-breaking — to
    ``fusion`` so this module never duplicates fusion logic.
    """

    def fuse(
        self,
        rankings: Iterable[List[str]],
        k: Union[int, float] = K,
        limit: Optional[int] = None,
    ) -> List[str]:
        """Fuse ranked lists and return ordered document IDs."""
        return rrf_fuse(rankings, k=k, limit=limit)

    def scores(
        self,
        rankings: Iterable[List[str]],
        k: Union[int, float] = K,
    ) -> Dict[str, float]:
        """Return the RRF score map for the supplied rankings."""
        return rrf_scores(rankings, k=k)


class Main:
    """Entry point exercising RRF and its ``search_app`` integration surface."""

    def __init__(self) -> None:
        """Instantiate the demo's FusionAPI and SearchApp wiring."""
        self.fusion_api: _FusionAPIImpl = _FusionAPIImpl()
        self.search_app: SearchApp = SearchApp(fusion_api=self.fusion_api)

    def _sample_rankings(self) -> List[List[str]]:
        """Return deterministic synthetic rankings for the demonstration.

        The fixture is hand-constructed per ``config.yaml`` evaluation scope
        (``datasets: synthetic_rankings``, ``random_seed: null``). It contains
        overlapping documents, documents absent from some lists, and lists of
        differing lengths. Rankings are returned unchanged — first-occurrence
        de-duplication, missing-document handling, and tie-breaking are the
        responsibility of ``fusion.py``.
        """
        return [
            ["A", "B", "C"],
            ["B", "C", "D"],
            ["C", "A"],
        ]

    def run_demo(self) -> Dict[str, Any]:
        """Run the demo and return a dictionary describing the fusion.

        Uses the public integration entry point ``SearchApp.search_results``
        for the fused order (preserving the caller-facing ``list[str]``
        schema) and ``FusionAPI.scores`` for the RRF score map. Always uses
        ``k = 60`` (``config.yaml -> fusion.k``) and ``limit = None`` so the
        full fused order is shown.

        Returns:
            A dictionary with keys ``"rankings"`` (``list[list[str]]``),
            ``"fused_order"`` (``list[str]``), and ``"scores"``
            (``dict[str, float]``).
        """
        rankings: List[List[str]] = self._sample_rankings()

        fused_order: List[str] = self.search_app.search_results(
            rankings, limit=None
        )
        score_map: Dict[str, float] = self.fusion_api.scores(rankings, k=K)

        result: Dict[str, Any] = {
            "rankings": [list(r) for r in rankings],
            "fused_order": list(fused_order),
            "scores": dict(score_map),
        }

        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result


if __name__ == "__main__":
    Main().run_demo()
