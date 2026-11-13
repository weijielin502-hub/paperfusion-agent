## tests/test_fusion.py
"""Unit tests for the Reciprocal Rank Fusion implementation in ``fusion.py``.

These tests pin the paper method (Cormack, Clarke & Buettcher, SIGIR 2009):

    RRF(d) = sum over input lists of 1 / (k + rank(d))

with ranks starting at one, ``k`` fixed to 60, equal weighting across lists,
missing documents contributing zero, within-list duplicates contributing only
at first occurrence (without renumbering subsequent positions), fused ordering
by descending score, and ascending string document ID as the tie-breaker.

All assertions reference the project configuration in ``config.yaml``:

* ``fusion.k = 60``, ``fusion.rank_start = 1``
* ``input_handling``: zero for missing docs, first-position dedupe within list,
  no renumber after dedupe, ascending ID tie-break, descending score order
* ``validation``: bool rejection for ``k`` / ``limit``; finite positive
  numeric ``k``; ``None`` or nonnegative non-bool integer ``limit``;
  ``ValueError`` on failure
* ``evaluation.score_tolerance = 1e-12`` (applied via ``math.isclose``)
* ``evaluation.datasets = synthetic_rankings`` and
  ``evaluation.external_datasets = none`` — everything here is deterministic
  and synthetic, with no external datasets, training, or randomness.
"""

import math
from typing import Any, Dict, Iterable, List, Union

import pytest

from fusion import RRFEngine, fuse, scores

# ---------------------------------------------------------------------------
# Configuration constants (mirrors of ``config.yaml`` — never invented here).
# ---------------------------------------------------------------------------

PAPER_K: int = 60                                    # config.fusion.k
RANK_START: int = 1                                  # config.fusion.rank_start
SCORE_REL_TOL: float = 1.0e-12                       # evaluation.score_tolerance
SCORE_ABS_TOL: float = 1.0e-12                       # evaluation.score_tolerance


# ---------------------------------------------------------------------------
# Assertion helpers.
# ---------------------------------------------------------------------------


def _assert_close(actual: float, expected: float) -> None:
    """Assert that two floats are equal within the configured tolerance.

    Args:
        actual: The value produced by the implementation.
        expected: The analytically-derived reference value.
    """
    assert math.isclose(
        actual, expected, rel_tol=SCORE_REL_TOL, abs_tol=SCORE_ABS_TOL
    ), f"{actual!r} is not close to {expected!r}"


def _assert_scores_equal(
    actual: Dict[str, float], expected: Dict[str, float]
) -> None:
    """Assert two score maps share keys and are element-wise close.

    Args:
        actual: The score map produced by the implementation.
        expected: The analytically-derived reference score map.
    """
    assert set(actual) == set(expected), (
        f"Document sets differ: {set(actual)!r} vs {set(expected)!r}"
    )
    for key in expected:
        _assert_close(actual[key], expected[key])


def _reference_scores(
    rankings: Iterable[List[str]],
    k: Union[int, float] = PAPER_K,
) -> Dict[str, float]:
    """Independent reference implementation of RRF score accumulation.

    This helper mirrors the contract specification directly: enumerate every
    list with positions starting at :data:`RANK_START`, track a per-list
    ``seen`` set for first-occurrence dedupe, and accumulate
    ``1 / (k + position)``. It is used *only* as a cross-check for larger
    synthetic fixtures whose values would otherwise be tedious to spell out;
    the hand-checkable reference cases in this suite use literal arithmetic
    expressions directly, so the helper itself is verified independently.

    Args:
        rankings: Iterable of ranked lists of string document IDs.
        k: Rank constant (paper value: 60).

    Returns:
        Mapping from document ID to accumulated RRF score.
    """
    totals: Dict[str, float] = {}
    for ranked_list in rankings:
        seen = set()
        for position, doc_id in enumerate(ranked_list, start=RANK_START):
            if doc_id in seen:
                continue
            seen.add(doc_id)
            totals[doc_id] = totals.get(doc_id, 0.0) + 1.0 / (k + position)
    return totals


# ---------------------------------------------------------------------------
# The unit-test suite.
# ---------------------------------------------------------------------------


class TestFusion:
    """Contract tests for ``fusion.scores`` / ``fusion.fuse`` / ``RRFEngine``."""

    # -----------------------------------------------------------------------
    # Score correctness (paper formula, k=60 by default).
    # -----------------------------------------------------------------------

    def test_score_formula(self) -> None:
        """Overlapping rankings produce the 1/(k+rank) sums per the paper."""
        rankings = [["A", "B", "C"], ["B", "C", "A"]]
        expected = {
            "A": 1.0 / (PAPER_K + 1) + 1.0 / (PAPER_K + 3),
            "B": 1.0 / (PAPER_K + 2) + 1.0 / (PAPER_K + 1),
            "C": 1.0 / (PAPER_K + 3) + 1.0 / (PAPER_K + 2),
        }
        _assert_scores_equal(scores(rankings), expected)
        # B > A > C by construction; no ties here.
        assert fuse(rankings) == ["B", "A", "C"]

    def test_score_formula_single_list(self) -> None:
        """A single ranking fuses to itself (identity when IDs are unique)."""
        rankings = [["doc-1", "doc-2", "doc-3"]]
        result = scores(rankings)
        _assert_close(result["doc-1"], 1.0 / (PAPER_K + 1))
        _assert_close(result["doc-2"], 1.0 / (PAPER_K + 2))
        _assert_close(result["doc-3"], 1.0 / (PAPER_K + 3))
        assert fuse(rankings) == ["doc-1", "doc-2", "doc-3"]

    def test_score_formula_k_override(self) -> None:
        """The ``k`` parameter is threaded through the formula, not hard-coded."""
        rankings = [["A", "B"]]
        result = scores(rankings, k=1)
        _assert_close(result["A"], 1.0 / (1 + 1))  # 1/2
        _assert_close(result["B"], 1.0 / (1 + 2))  # 1/3
        assert fuse(rankings, k=1) == ["A", "B"]

    def test_scores_returns_all_documents(self) -> None:
        """``scores`` returns exactly the documents that appeared, no extras."""
        rankings = [["A", "B", "A", "C"], ["D"]]
        result = scores(rankings)
        assert set(result) == {"A", "B", "C", "D"}
        _assert_close(result["A"], 1.0 / (PAPER_K + 1))
        _assert_close(result["B"], 1.0 / (PAPER_K + 2))
        # Position preserved after the duplicate skip within list one.
        _assert_close(result["C"], 1.0 / (PAPER_K + 4))
        _assert_close(result["D"], 1.0 / (PAPER_K + 1))
        for value in result.values():
            assert isinstance(value, float)
            assert value > 0.0

    # -----------------------------------------------------------------------
    # Duplicate handling.
    # -----------------------------------------------------------------------

    def test_duplicate_within_list(self) -> None:
        """Within a list, only the first occurrence contributes; no renumber.

        In ``["A", "B", "A", "C"]`` the trailing ``A`` is skipped but the
        original position 4 is retained for ``C`` (i.e. ``C = 1/64``, not the
        common bug ``C = 1/63``).
        """
        rankings = [["A", "B", "A", "C"]]
        expected = {
            "A": 1.0 / (PAPER_K + 1),
            "B": 1.0 / (PAPER_K + 2),
            "C": 1.0 / (PAPER_K + 4),  # NOT 1/(60+3)
        }
        _assert_scores_equal(scores(rankings), expected)
        assert fuse(rankings) == ["A", "B", "C"]

    def test_duplicate_adjacent(self) -> None:
        """Repeated identical IDs collapse to their single first occurrence."""
        rankings = [["A", "A", "A"]]
        _assert_close(scores(rankings)["A"], 1.0 / (PAPER_K + 1))
        assert fuse(rankings) == ["A"]

    def test_duplicate_across_lists_sum(self) -> None:
        """Across lists, contributions for the same document accumulate."""
        rankings = [["A", "B"], ["A", "C"]]
        result = scores(rankings)
        _assert_close(
            result["A"],
            1.0 / (PAPER_K + 1) + 1.0 / (PAPER_K + 1),
        )
        _assert_close(result["B"], 1.0 / (PAPER_K + 2))
        _assert_close(result["C"], 1.0 / (PAPER_K + 2))
        # B and C tie; ascending ID decides, so B before C.
        assert fuse(rankings) == ["A", "B", "C"]

    # -----------------------------------------------------------------------
    # Missing documents and truncated rankings.
    # -----------------------------------------------------------------------

    def test_missing_documents(self) -> None:
        """A document absent from a list contributes zero for that list."""
        rankings = [["A", "B"], ["B"]]
        result = scores(rankings)
        _assert_close(result["A"], 1.0 / (PAPER_K + 1))
        _assert_close(
            result["B"],
            1.0 / (PAPER_K + 2) + 1.0 / (PAPER_K + 1),
        )
        assert fuse(rankings) == ["B", "A"]

    def test_truncated_rankings_varied_lengths(self) -> None:
        """Lists of different lengths (a truncated ranking) fuse correctly."""
        rankings = [["A", "B", "C"], ["A", "C"]]
        result = scores(rankings)
        _assert_close(
            result["A"],
            1.0 / (PAPER_K + 1) + 1.0 / (PAPER_K + 1),
        )
        _assert_close(result["B"], 1.0 / (PAPER_K + 2))
        _assert_close(
            result["C"],
            1.0 / (PAPER_K + 3) + 1.0 / (PAPER_K + 2),
        )
        assert fuse(rankings) == ["A", "C", "B"]

    # -----------------------------------------------------------------------
    # Tie-breaking (ascending document ID).
    # -----------------------------------------------------------------------

    def test_tie_break(self) -> None:
        """Exact-score ties are broken by ascending document ID."""
        rankings = [["A"], ["B"]]
        result = scores(rankings)
        _assert_close(result["A"], 1.0 / (PAPER_K + 1))
        _assert_close(result["B"], 1.0 / (PAPER_K + 1))
        assert fuse(rankings) == ["A", "B"]

    def test_tie_break_three_way(self) -> None:
        """Three-way tie resolves to lexicographically ascending IDs."""
        rankings = [["A"], ["B"], ["C"]]
        assert fuse(rankings) == ["A", "B", "C"]

    def test_tie_break_ignores_input_order(self) -> None:
        """Tie-breaking ignores the outer-list order for equal scores."""
        rankings = [["C"], ["A"], ["B"]]
        assert fuse(rankings) == ["A", "B", "C"]

    def test_tie_break_mixed_with_strict_order(self) -> None:
        """A strict winner is placed first; the A/C tie uses ascending ID."""
        rankings = [["A", "B", "C"], ["C", "B", "A"]]
        # A = C = 1/61 + 1/63 (tied), B = 2/62 (strictly greater than A/C).
        assert fuse(rankings) == ["A", "C", "B"]

    # -----------------------------------------------------------------------
    # Empty inputs.
    # -----------------------------------------------------------------------

    def test_empty_rankings(self) -> None:
        """Empty outer iterables and empty inner lists are accepted silently."""
        assert scores([]) == {}
        assert fuse([]) == []
        assert scores([[], []]) == {}
        assert fuse([[], []]) == []
        assert scores([[]]) == {}

        # An empty inner list must not perturb a non-empty sibling.
        rankings = [["A"], []]
        _assert_close(scores(rankings)["A"], 1.0 / (PAPER_K + 1))
        assert fuse(rankings) == ["A"]

    # -----------------------------------------------------------------------
    # ``k`` typing and equivalence.
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("k", [1, 60, 60.0, 0.5, 1.0e-6, 1.0e9])
    def test_valid_k_values(self, k: Union[int, float]) -> None:
        """Every positive finite int/float ``k`` is accepted and applied."""
        result = scores([["A"]], k=k)
        _assert_close(result["A"], 1.0 / (k + 1))

    def test_k_int_equals_float(self) -> None:
        """``k=60`` and ``k=60.0`` are equivalent (``int`` vs ``float``)."""
        rankings = [["A", "B"]]
        _assert_scores_equal(
            scores(rankings, k=60), scores(rankings, k=60.0)
        )
        assert fuse(rankings, k=60) == fuse(rankings, k=60.0)

    # -----------------------------------------------------------------------
    # ``limit`` behavior.
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize(
        "limit,expected",
        [
            (None, ["A", "B", "C"]),
            (0, []),
            (1, ["A"]),
            (2, ["A", "B"]),
            (3, ["A", "B", "C"]),
            (100, ["A", "B", "C"]),
        ],
    )
    def test_limit(self, limit, expected: List[str]) -> None:
        """``limit`` truncates *after* sorting; ``None``/oversize keep all."""
        out = fuse([["A", "B", "C"]], limit=limit)
        assert isinstance(out, list)
        assert out == expected

    def test_limit_applied_after_sort(self) -> None:
        """``limit`` is applied to the fused order, not the insertion order."""
        rankings = [["A", "B", "C"], ["C", "B", "A"]]
        # Full fused order is ["A", "C", "B"]; limit=2 must keep A and C,
        # not the insertion-order prefix ["A", "B"].
        assert fuse(rankings) == ["A", "C", "B"]
        assert fuse(rankings, limit=2) == ["A", "C"]

    @pytest.mark.parametrize("limit", [None, 0, 1, 5, 100])
    def test_valid_limit_values_accepted(self, limit) -> None:
        """Valid ``limit`` values (including 0) return a list without raising."""
        out = fuse([["A", "B"]], limit=limit)
        assert isinstance(out, list)

    # -----------------------------------------------------------------------
    # Validation (only the exception type is required; message text is not).
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize(
        "kind,bad_value",
        [
            ("k", True),
            ("k", False),
            ("k", 0),
            ("k", 0.0),
            ("k", -1),
            ("k", -1.0),
            ("k", -0.5),
            ("k", float("inf")),
            ("k", float("-inf")),
            ("k", float("nan")),
            ("k", "60"),
            ("k", None),
            ("k", [60]),
            ("k", (60,)),
            ("k", 3 + 0j),
            ("limit", True),
            ("limit", False),
            ("limit", -1),
            ("limit", -2),
            ("limit", 3.0),
            ("limit", -1.5),
            ("limit", "5"),
            ("limit", [1]),
            ("limit", 3 + 0j),
        ],
    )
    def test_validation(self, kind: str, bad_value: Any) -> None:
        """Invalid ``k`` / ``limit`` raise ``ValueError`` per ``config.yaml``."""
        if kind == "k":
            with pytest.raises(ValueError):
                scores([["A"]], k=bad_value)
        elif kind == "limit":
            with pytest.raises(ValueError):
                fuse([["A"]], limit=bad_value)
        else:  # pragma: no cover - defensive guard against fixture drift.
            pytest.fail(f"unknown validation kind: {kind!r}")

    def test_invalid_k_raises_before_consuming_rankings(self) -> None:
        """``k`` validation precedes consumption of the (possibly lazy) input."""
        consumed: List[bool] = []

        def gen():
            consumed.append(True)
            yield ["A"]

        with pytest.raises(ValueError):
            scores(gen(), k=0)
        assert consumed == []

    def test_invalid_limit_raises_before_consuming_rankings(self) -> None:
        """``limit`` validation also precedes consumption of the input."""
        consumed: List[bool] = []

        def gen():
            consumed.append(True)
            yield ["A"]

        with pytest.raises(ValueError):
            fuse(gen(), limit=-1)
        assert consumed == []

    # -----------------------------------------------------------------------
    # Non-mutation of inputs.
    # -----------------------------------------------------------------------

    def test_input_rankings_not_mutated(self) -> None:
        """Neither ``scores`` nor ``fuse`` mutate the caller's rankings."""
        rankings = [["A", "B", "A", "C"], ["B", "C"]]
        snapshot = [list(inner) for inner in rankings]
        scores(rankings)
        fuse(rankings)
        assert rankings == snapshot

    # -----------------------------------------------------------------------
    # Single-pass (generator) iterables.
    # -----------------------------------------------------------------------

    def test_scores_accepts_generator(self) -> None:
        """``scores`` consumes a generator exactly once and produces scores."""
        def gen():
            yield ["A", "B"]
            yield ["B", "C"]

        expected = {
            "A": 1.0 / (PAPER_K + 1),
            "B": 1.0 / (PAPER_K + 2) + 1.0 / (PAPER_K + 1),
            "C": 1.0 / (PAPER_K + 2),
        }
        _assert_scores_equal(scores(gen()), expected)

    def test_fuse_accepts_generator(self) -> None:
        """``fuse`` consumes a generator exactly once and returns the order."""
        def gen():
            yield ["A", "B"]
            yield ["B", "C"]

        # B has two contributions; A and C have one each at ranks 1 and 3.
        assert fuse(gen()) == ["B", "A", "C"]

    # -----------------------------------------------------------------------
    # Property / invariance checks (deterministic, no randomness).
    # -----------------------------------------------------------------------

    def test_outer_order_invariance(self) -> None:
        """Reordering the outer iterable leaves scores/order unchanged."""
        base = [["A", "B", "C"], ["B", "A"], ["A"]]
        permuted = [base[2], base[0], base[1]]
        _assert_scores_equal(scores(base), scores(permuted))
        assert fuse(base) == fuse(permuted)

    def test_add_empty_ranking_invariance(self) -> None:
        """Adding an empty ranking does not affect scores or fused order."""
        base = [["A", "B"], ["B", "C"]]
        augmented = base + [[]]
        _assert_scores_equal(scores(base), scores(augmented))
        assert fuse(base) == fuse(augmented)

    def test_fuse_output_consistency(self) -> None:
        """Fused output matches ``scores`` keys, with no duplicates."""
        rankings = [["A", "B", "C"], ["B", "C", "A"]]
        out = fuse(rankings)
        score_map = scores(rankings)
        assert set(out) == set(score_map)
        assert len(out) == len(set(out))

    def test_no_zero_or_negative_scores(self) -> None:
        """Because ``k > 0`` and ranks start at 1, all scores are positive."""
        for value in scores([["A"], ["B"], ["C"]]).values():
            assert value > 0.0

    def test_fuse_respects_limit_length(self) -> None:
        """``fuse`` length tracks ``limit`` but never exceeds the doc count."""
        rankings = [["A", "B", "C"], ["B"]]
        assert len(fuse(rankings, limit=2)) == 2
        assert len(fuse(rankings, limit=100)) == len(scores(rankings))
        assert len(fuse(rankings, limit=0)) == 0
        assert len(fuse(rankings, limit=None)) == len(scores(rankings))

    # -----------------------------------------------------------------------
    # ``RRFEngine`` interface (design-mandated class).
    # -----------------------------------------------------------------------

    def test_engine_matches_module(self) -> None:
        """``RRFEngine`` produces identical scores and order as module-level API."""
        rankings = [["A", "B"], ["B", "C"]]
        engine = RRFEngine(PAPER_K)
        _assert_scores_equal(engine.scores(rankings), scores(rankings))
        assert engine.fuse(rankings) == fuse(rankings)

    def test_engine_default_k(self) -> None:
        """``RRFEngine()`` defaults to the paper value ``k = 60``."""
        engine = RRFEngine()
        _assert_close(
            engine.scores([["A"]])["A"], 1.0 / (PAPER_K + 1)
        )

    @pytest.mark.parametrize(
        "bad_k",
        [True, False, 0, -1, float("inf"), float("nan"), "60", None],
    )
    def test_engine_invalid_k(self, bad_k: Any) -> None:
        """Invalid ``k`` surfaces via ``ValueError`` when scores are computed."""
        with pytest.raises(ValueError):
            RRFEngine(bad_k).scores([["A"]])

    @pytest.mark.parametrize(
        "bad_limit", [True, False, -1, -2, 3.0, -1.5, "5", [1]]
    )
    def test_engine_invalid_limit(self, bad_limit: Any) -> None:
        """Invalid ``limit`` surfaces via ``ValueError`` when fusing."""
        with pytest.raises(ValueError):
            RRFEngine(PAPER_K).fuse([["A"]], limit=bad_limit)

    # -----------------------------------------------------------------------
    # Reference-helper sanity (cheap insurance for the larger fixture test).
    # -----------------------------------------------------------------------

    def test_reference_helper_matches_hand_case(self) -> None:
        """``_reference_scores`` reproduces the hand-computed reference case."""
        rankings = [["A", "B", "C"], ["B", "C", "A"]]
        expected = {
            "A": 1.0 / (PAPER_K + 1) + 1.0 / (PAPER_K + 3),
            "B": 1.0 / (PAPER_K + 2) + 1.0 / (PAPER_K + 1),
            "C": 1.0 / (PAPER_K + 3) + 1.0 / (PAPER_K + 2),
        }
        _assert_scores_equal(_reference_scores(rankings), expected)

    def test_scores_matches_reference_on_larger_fixture(self) -> None:
        """Larger synthetic fixture matches the independently-derived reference."""
        rankings = [
            ["doc-1", "doc-2", "doc-3", "doc-4"],
            ["doc-4", "doc-2", "doc-5"],
            ["doc-1", "doc-5", "doc-3"],
        ]
        _assert_scores_equal(scores(rankings), _reference_scores(rankings))
