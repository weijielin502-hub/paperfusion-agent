## fusion.py
"""Reciprocal Rank Fusion implementation.

This module implements Reciprocal Rank Fusion (RRF) as described by
Cormack, Clarke, and Buettcher (SIGIR 2009). Each document receives the sum of
``1 / (k + rank)`` across all input rankings, where ranking positions start at
one. Missing documents contribute zero by omission, duplicate document IDs
within a single ranking contribute only at their first position, and final
ordering is by descending score with ascending document ID as the tie-breaker.

Only the Python standard library is used at runtime.
"""

import math
from typing import Dict, Iterable, List, Optional, Union

__all__ = ["RRFEngine", "scores", "fuse"]


def scores(
    rankings: Iterable[List[str]],
    k: Union[int, float] = 60,
) -> Dict[str, float]:
    """Compute reciprocal rank fusion scores for the supplied rankings.

    Args:
        rankings: An iterable of ranked lists of string document IDs. Each inner
            list is ordered best-to-worst. The outer iterable may be single-pass.
        k: Rank constant used in the RRF formula. Must be a finite positive
            ``int`` or ``float`` and not a ``bool``. The paper fixes ``k=60``.

    Returns:
        A dictionary mapping each document that appears at least once to its
        accumulated RRF score.

    Raises:
        ValueError: If ``k`` is invalid.
    """
    return RRFEngine(k=k).scores(rankings)


def fuse(
    rankings: Iterable[List[str]],
    k: Union[int, float] = 60,
    limit: Optional[int] = None,
) -> List[str]:
    """Fuse ranked lists and return document IDs in descending score order.

    Args:
        rankings: An iterable of ranked lists of string document IDs. Each inner
            list is ordered best-to-worst. The outer iterable may be single-pass.
        k: Rank constant used in the RRF formula. Must be a finite positive
            ``int`` or ``float`` and not a ``bool``. The paper fixes ``k=60``.
        limit: Maximum number of fused document IDs to return. Must be ``None``
            or a nonnegative ``int`` and not a ``bool``. If ``None``, all fused
            documents are returned. If ``0``, an empty list is returned.

    Returns:
        A list of document IDs ordered by descending fused score, with ascending
        document ID as the tie-breaker.

    Raises:
        ValueError: If ``k`` or ``limit`` is invalid.
    """
    return RRFEngine(k=k).fuse(rankings, limit=limit)


class RRFEngine:
    """Engine implementing Reciprocal Rank Fusion."""

    def __init__(self, k: Union[int, float] = 60) -> None:
        """Initialize the RRF engine.

        Args:
            k: Rank constant used in the RRF formula. Stored here and validated
                before rankings are consumed.
        """
        self.k: Union[int, float] = k

    def scores(self, rankings: Iterable[List[str]]) -> Dict[str, float]:
        """Compute RRF scores for the supplied rankings.

        Args:
            rankings: An iterable of ranked lists of string document IDs.

        Returns:
            A dictionary mapping documents to their accumulated RRF scores.

        Raises:
            ValueError: If ``self.k`` is invalid.
        """
        validated_k = self._validate_k(self.k)
        return self._accumulate(rankings, validated_k)

    def fuse(
        self,
        rankings: Iterable[List[str]],
        limit: Optional[int] = None,
    ) -> List[str]:
        """Fuse rankings and return document IDs in descending score order.

        Args:
            rankings: An iterable of ranked lists of string document IDs.
            limit: Maximum number of returned documents. Must be ``None`` or a
                nonnegative ``int`` and not a ``bool``.

        Returns:
            A list of document IDs ordered by descending fused score, with
            ascending document ID as the tie-breaker.

        Raises:
            ValueError: If ``self.k`` or ``limit`` is invalid.
        """
        validated_limit = self._validate_limit(limit)
        score_dict = self.scores(rankings)
        ordered = self._sort(score_dict)
        if validated_limit is None:
            return ordered
        return ordered[:validated_limit]

    def _validate_k(self, k: Union[int, float]) -> float:
        """Validate and normalize the RRF rank constant.

        Args:
            k: Candidate rank constant.

        Returns:
            The validated rank constant as a ``float``.

        Raises:
            ValueError: If ``k`` is a ``bool``, non-numeric, non-finite, or not
                positive.
        """
        if isinstance(k, bool):
            raise ValueError("k must be a finite positive int or float, not bool")
        if not isinstance(k, (int, float)):
            raise ValueError("k must be a finite positive int or float")
        try:
            finite = math.isfinite(k)
        except (OverflowError, TypeError) as exc:
            raise ValueError("k must be a finite positive int or float") from exc
        if not finite:
            raise ValueError("k must be finite")
        if k <= 0:
            raise ValueError("k must be positive")
        return float(k)

    def _validate_limit(self, limit: Optional[int]) -> Optional[int]:
        """Validate the result limit.

        Args:
            limit: Candidate result limit. ``None`` means no limit.

        Returns:
            The validated limit, or ``None``.

        Raises:
            ValueError: If ``limit`` is a ``bool``, not an ``int``, or negative.
        """
        if limit is None:
            return None
        if isinstance(limit, bool):
            raise ValueError("limit must be None or a nonnegative int, not bool")
        if not isinstance(limit, int):
            raise ValueError("limit must be None or a nonnegative int")
        if limit < 0:
            raise ValueError("limit must be nonnegative")
        return limit

    def _accumulate(
        self,
        rankings: Iterable[List[str]],
        k: float,
    ) -> Dict[str, float]:
        """Accumulate RRF contributions across all ranked lists.

        Args:
            rankings: An iterable of ranked lists of string document IDs. This
                iterable is consumed exactly once.
            k: Validated rank constant.

        Returns:
            A dictionary mapping documents to accumulated scores.
        """
        accumulated: Dict[str, float] = {}
        for ranked_list in rankings:
            seen = set()
            for position, doc_id in enumerate(ranked_list, start=1):
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                accumulated[doc_id] = (
                    accumulated.get(doc_id, 0.0) + 1.0 / (k + position)
                )
        return accumulated

    def _sort(self, scores: Dict[str, float]) -> List[str]:
        """Sort documents by descending score and ascending document ID.

        Args:
            scores: Mapping from document ID to fused score.

        Returns:
            Document IDs ordered by descending score, with ascending document ID
            as the exact-tie breaker.
        """
        return [
            doc_id
            for doc_id, _ in sorted(
                scores.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
