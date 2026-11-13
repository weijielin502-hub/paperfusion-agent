"""Integration layer exposing Reciprocal Rank Fusion via ``search_results``.

This module preserves the caller-facing entry point
``search_app.search_results(rankings, limit=None) -> list[str]`` while
delegating all fusion work to :mod:`fusion` (the single source of truth for
Reciprocal Rank Fusion).

Scope and configuration anchors (see ``config.yaml``):

* ``integration.entry_point = search_app.search_results`` — the public
  callable preserved here.
* ``integration.schema = ordered_list_of_document_ids`` — the return type is
  exactly ``list[str]``; no wrapping, copying, or conversion.
* ``integration.delegate_to = fusion.fuse`` — all RRF behavior (formula,
  first-position de-duplication, missing-document zero contribution,
  descending-score order, ascending document-ID tie-break, ``limit``
  handling, and ``ValueError`` validation) is inherited from ``fusion.fuse``.
* ``fusion.k = 60`` — the paper's fixed rank constant, passed explicitly.
* ``evaluation.datasets = synthetic_rankings`` and
  ``evaluation.external_datasets = none`` — this layer does not reproduce the
  paper's TREC/LETOR results.

The module intentionally does **not**:

* re-implement RRF, re-validate ``k``, re-validate ``limit``, or re-sort;
* add required arguments, alter defaults, or change positional/keyword order;
* mutate the incoming ``rankings`` iterable;
* introduce new exception types — ``ValueError`` from :func:`fusion.fuse`
  propagates unchanged.

Only the Python standard library and the project's :mod:`fusion` module are
imported at runtime. ``pytest`` is a test-only dependency and is never imported
here.
"""

from typing import Iterable, List, Optional, Protocol, runtime_checkable

from fusion import fuse

__all__ = ["FusionAPI", "SearchApp", "search_results", "K"]

# config.yaml -> fusion.k  ("The study fixes k to 60.")
K: int = 60


@runtime_checkable
class FusionAPI(Protocol):
    """Structural interface for the fusion surface used by :class:`SearchApp`.

    Implementations must expose a ``fuse`` method with the same keyword
    arguments and return schema as :func:`fusion.fuse`
    (``integration.schema = ordered_list_of_document_ids``).
    """

    def fuse(
        self,
        rankings: Iterable[List[str]],
        k: float = 60,
        limit: Optional[int] = None,
    ) -> List[str]:
        """Fuse ranked lists and return ordered document IDs."""
        ...


class SearchApp:
    """Integration wrapper delegating fusion to :mod:`fusion`.

    The class holds no state beyond the optional injected fusion API. Repeated
    calls with equal inputs yield equal outputs and never mutate the input
    rankings.
    """

    def __init__(self, fusion_api: Optional[FusionAPI] = None) -> None:
        """Initialize the integration wrapper.

        Args:
            fusion_api: Optional dependency-injected fusion surface exposing
                ``fuse(rankings, k=..., limit=...)``. When ``None``, delegation
                falls back to the module-level :func:`fusion.fuse`.
        """
        self._fusion_api: Optional[FusionAPI] = fusion_api

    def search_results(
        self,
        rankings: Iterable[List[str]],
        limit: Optional[int] = None,
    ) -> List[str]:
        """Fuse ranked lists into a single ordered list of document IDs.

        This is the preserved public entry point. The ``rankings`` iterable is
        forwarded without materialization (single-pass iterables are allowed),
        and ``limit`` is forwarded unchanged — including ``None``, ``0``,
        negatives, floats, and booleans — so that :func:`fusion.fuse` owns all
        validation and raises ``ValueError`` per ``config.yaml -> validation``.

        Args:
            rankings: An iterable of ranked lists of string document IDs. Each
                inner list is ordered best-to-worst.
            limit: Maximum number of fused document IDs to return. Must be
                ``None`` or a nonnegative ``int`` and not a ``bool``. If
                ``None``, all fused documents are returned. If ``0``, an empty
                list is returned.

        Returns:
            Document IDs ordered by descending fused score, with ascending
            document ID as the tie-breaker (``list[str]``).

        Raises:
            ValueError: Propagated unchanged from :func:`fusion.fuse` when
                ``k`` or ``limit`` is invalid. The paper's ``k`` is fixed to
                ``K`` here, so in practice only invalid ``limit`` reaches this
                error path.
        """
        if self._fusion_api is not None:
            return self._fusion_api.fuse(rankings, k=K, limit=limit)
        return fuse(rankings, k=K, limit=limit)


_DEFAULT_APP: Optional[SearchApp] = None


def search_results(
    rankings: Iterable[List[str]],
    limit: Optional[int] = None,
) -> List[str]:
    """Module-level compatibility shim for ``search_app.search_results``.

    Preserves the caller-facing function entry point named in
    ``config.yaml -> integration.entry_point``. Semantics are identical to
    ``SearchApp().search_results(rankings, limit=limit)``; a shared stateless
    :class:`SearchApp` instance is reused across calls.

    Args:
        rankings: An iterable of ranked lists of string document IDs.
        limit: Maximum number of fused document IDs to return, or ``None``.

    Returns:
        Document IDs ordered by descending fused score, with ascending
        document ID as the tie-breaker (``list[str]``).

    Raises:
        ValueError: Propagated unchanged from :func:`fusion.fuse` when
            ``limit`` is invalid.
    """
    global _DEFAULT_APP
    if _DEFAULT_APP is None:
        _DEFAULT_APP = SearchApp()
    return _DEFAULT_APP.search_results(rankings, limit=limit)
