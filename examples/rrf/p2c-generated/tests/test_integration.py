## tests/test_integration.py
"""Integration tests for ``search_app.SearchApp.search_results``.

These tests pin the caller-facing integration contract from ``config.yaml``:

* ``integration.entry_point = search_app.search_results``
* ``integration.schema = ordered_list_of_document_ids``
* ``integration.delegate_to = fusion.fuse``
* ``fusion.k = 60``
* ``fusion.rank_start = 1``
* ``input_handling.order = descending_score``
* ``input_handling.tie_break = ascending_document_id``
* ``input_handling.missing_document_contribution = 0.0``
* ``input_handling.dedupe_within_list = first_position``
* ``input_handling.renumber_positions_after_dedupe = false``
* ``validation.error_type = ValueError``
* ``evaluation.datasets = synthetic_rankings``
* ``evaluation.score_tolerance = 1.0e-12``
* ``evaluation.random_seed = null``

The module contains only deterministic synthetic fixtures. It does not
reproduce the original paper's TREC/LETOR experiments, does not use external
datasets, and does not import MAP/NDCG or any retrieval metric.
"""

import inspect
import math
from typing import Any, Dict, List, Set

import pytest

import fusion
import search_app
from search_app import SearchApp

# ---------------------------------------------------------------------------
# Configuration constants (mirrors of ``config.yaml`` — never invented here).
# ---------------------------------------------------------------------------

K: int = 60  # config.yaml -> fusion.k
SCORE_TOL: float = 1.0e-12  # config.yaml -> evaluation.score_tolerance


# ---------------------------------------------------------------------------
# Synthetic fixtures. All document IDs are strings and all scores are
# deterministic. Hand-computed expected orders are stored beside the fixtures.
# ---------------------------------------------------------------------------

FIXTURES: Dict[str, List[List[str]]] = {
    "empty_outer": [],
    "empty_inner": [[], []],
    "single_list": [["A", "B", "C"]],
    "overlapping": [["A", "B", "C"], ["B", "C", "A"]],
    "truncated": [["A"], ["B", "A"]],
    "different_lengths_tie": [["A", "B"], ["C"]],
    "dup_within": [["A", "B", "A", "C"]],
    "dup_across": [["A", "B"], ["B", "A"]],
    "tie_single_docs": [["A"], ["B"]],
    "lexical_tie": [["doc-2"], ["doc-10"]],
}

EXPECTED_ORDER: Dict[str, List[str]] = {
    "empty_outer": [],
    "empty_inner": [],
    "single_list": ["A", "B", "C"],
    "overlapping": ["B", "A", "C"],
    "truncated": ["A", "B"],
    "different_lengths_tie": ["A", "C", "B"],
    "dup_within": ["A", "B", "C"],
    "dup_across": ["A", "B"],
    "tie_single_docs": ["A", "B"],
    "lexical_tie": ["doc-10", "doc-2"],
}


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _fresh(rankings: List[List[str]]) -> List[List[str]]:
    """Return a fresh copy of a rankings fixture.

    Args:
        rankings: Synthetic ranked lists of string document IDs.

    Returns:
        A new list of new inner lists, suitable for single-pass consumers that
        may mutate or exhaust their input.
    """
    return [list(inner) for inner in rankings]


def _documents(rankings: List[List[str]]) -> Set[str]:
    """Return the set of all document IDs appearing in a rankings fixture.

    Args:
        rankings: Synthetic ranked lists of string document IDs.

    Returns:
        The union of document IDs across all inner rankings.
    """
    return {doc for inner in rankings for doc in inner}


def _app() -> SearchApp:
    """Return a default-constructed ``SearchApp``.

    Returns:
        A new integration wrapper using the module-level fusion implementation.
    """
    return SearchApp()


def _assert_schema(
    result: Any,
    rankings: List[List[str]],
) -> None:
    """Assert the caller-facing result schema.

    The integration schema is an ordered list of string document IDs, with no
    duplicate IDs and no documents outside the input union.

    Args:
        result: Value returned by ``SearchApp.search_results``.
        rankings: The exact input rankings used to produce ``result``.
    """
    assert isinstance(result, list)
    assert all(isinstance(doc, str) for doc in result)
    assert len(result) == len(set(result))
    assert set(result).issubset(_documents(rankings))


class _RecordingFusionAPI:
    """Minimal injected ``FusionAPI`` used to verify dependency injection.

    The wrapper delegates to the real ``fusion.fuse`` while recording the
    arguments passed by ``SearchApp.search_results``.
    """

    def __init__(self) -> None:
        """Initialize an empty call log."""
        self.calls: List[Any] = []

    def fuse(
        self,
        rankings: List[List[str]],
        k: int = K,
        limit: Any = None,
    ) -> List[str]:
        """Delegate to ``fusion.fuse`` and record the invocation.

        Args:
            rankings: Ranked lists of string document IDs.
            k: Rank constant forwarded to ``fusion.fuse``.
            limit: Optional result limit forwarded to ``fusion.fuse``.

        Returns:
            Fused document IDs ordered by descending score, with ascending
            document ID as the tie-breaker.
        """
        self.calls.append((k, limit))
        return fusion.fuse(rankings, k=k, limit=limit)


# ---------------------------------------------------------------------------
# Signature and schema preservation.
# ---------------------------------------------------------------------------


def test_signature_and_return_schema() -> None:
    """``SearchApp.search_results`` preserves its caller-facing signature."""
    signature = inspect.signature(SearchApp.search_results)
    parameters = signature.parameters

    assert list(parameters) == ["self", "rankings", "limit"]
    assert parameters["rankings"].default is inspect.Parameter.empty
    assert parameters["limit"].default is None

    app = _app()
    positional = app.search_results([["A", "B"]])
    keyword = app.search_results(rankings=[["A", "B"]], limit=None)

    assert positional == keyword
    assert isinstance(positional, list)
    assert all(isinstance(doc, str) for doc in positional)

    # ``limit`` remains a positional-or-keyword argument.
    assert app.search_results([["A", "B", "C"]], 1) == ["A"]


def test_bound_method_signature() -> None:
    """The bound method exposes only ``rankings`` and ``limit``."""
    signature = inspect.signature(_app().search_results)

    assert list(signature.parameters) == ["rankings", "limit"]
    assert signature.parameters["limit"].default is None


def test_module_level_function_signature() -> None:
    """The module-level compatibility shim has the documented signature."""
    signature = inspect.signature(search_app.search_results)
    parameters = signature.parameters

    assert list(parameters) == ["rankings", "limit"]
    assert parameters["rankings"].default is inspect.Parameter.empty
    assert parameters["limit"].default is None


@pytest.mark.parametrize("fixture_id", list(FIXTURES))
def test_return_schema_types(fixture_id: str) -> None:
    """Every fixture returns ``list[str]`` with no duplicate document IDs."""
    rankings = FIXTURES[fixture_id]
    result = _app().search_results(_fresh(rankings))

    _assert_schema(result, rankings)


def test_construction_variants() -> None:
    """Default construction and injected fusion APIs produce the same result."""
    rankings = [["A", "B", "C"], ["B", "C", "A"]]
    expected = EXPECTED_ORDER["overlapping"]

    default_app = _app()
    default_result = default_app.search_results(_fresh(rankings))
    assert default_result == expected

    # Repeating default construction is deterministic and schema-compatible.
    assert _app().search_results(_fresh(rankings)) == default_result

    # Dependency injection delegates with the configured paper value k=60.
    recording_api = _RecordingFusionAPI()
    injected_app = SearchApp(fusion_api=recording_api)
    injected_result = injected_app.search_results(_fresh(rankings))

    assert injected_result == default_result
    assert recording_api.calls == [(K, None)]


# ---------------------------------------------------------------------------
# Empty and basic inputs.
# ---------------------------------------------------------------------------


def test_empty_outer_rankings() -> None:
    """An empty outer iterable returns an empty list without raising."""
    app = _app()

    assert app.search_results([]) == []
    assert app.search_results([], limit=None) == []
    assert app.search_results([], limit=0) == []


def test_empty_inner_rankings() -> None:
    """Empty inner rankings are accepted and produce an empty result."""
    app = _app()

    assert app.search_results([[], []]) == []
    assert app.search_results([[]]) == []
    assert app.search_results([[["A"]][0], []]) == ["A"]


def test_single_list_passthrough() -> None:
    """A single distinct ranking preserves its order under RRF."""
    assert _app().search_results([["A", "B", "C"]]) == ["A", "B", "C"]


def test_overlapping_matches_reference() -> None:
    """The paper-style overlapping example fuses to B, A, C."""
    rankings = [["A", "B", "C"], ["B", "C", "A"]]

    assert _app().search_results(_fresh(rankings)) == ["B", "A", "C"]


def test_truncated_rankings() -> None:
    """Missing documents contribute zero and do not raise."""
    rankings = [["A"], ["B", "A"]]

    assert _app().search_results(_fresh(rankings)) == ["A", "B"]


# ---------------------------------------------------------------------------
# Project input-handling adaptations.
# ---------------------------------------------------------------------------


def test_duplicate_within_list() -> None:
    """Only the first occurrence in a list contributes; positions are not renumbered."""
    rankings = [["A", "B", "A", "C"]]

    assert _app().search_results(_fresh(rankings)) == ["A", "B", "C"]

    score_map = fusion.scores(_fresh(rankings), k=K)
    assert math.isclose(
        score_map["A"], 1.0 / (K + 1), rel_tol=SCORE_TOL, abs_tol=SCORE_TOL
    )
    assert math.isclose(
        score_map["B"], 1.0 / (K + 2), rel_tol=SCORE_TOL, abs_tol=SCORE_TOL
    )
    # ``C`` remains at its original position 4, i.e. 1/(60+4), not 1/(60+3).
    assert math.isclose(
        score_map["C"], 1.0 / (K + 4), rel_tol=SCORE_TOL, abs_tol=SCORE_TOL
    )


def test_duplicate_across_lists() -> None:
    """Repeated IDs across lists sum normally and ties use ascending ID."""
    rankings = [["A", "B"], ["B", "A"]]

    assert _app().search_results(_fresh(rankings)) == ["A", "B"]

    score_map = fusion.scores(_fresh(rankings), k=K)
    expected = 1.0 / (K + 1) + 1.0 / (K + 2)

    assert math.isclose(
        score_map["A"], expected, rel_tol=SCORE_TOL, abs_tol=SCORE_TOL
    )
    assert math.isclose(
        score_map["B"], expected, rel_tol=SCORE_TOL, abs_tol=SCORE_TOL
    )


def test_tie_break_ascending_id() -> None:
    """Exact score ties are broken by ascending lexicographic document ID."""
    app = _app()

    assert app.search_results([["A"], ["B"]]) == ["A", "B"]
    assert app.search_results([["A", "B"], ["C"]]) == ["A", "C", "B"]
    # Pure string ordering: "doc-10" < "doc-2".
    assert app.search_results([["doc-2"], ["doc-10"]]) == ["doc-10", "doc-2"]


# ---------------------------------------------------------------------------
# ``limit`` propagation.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "limit,expected",
    [
        (None, ["B", "A", "C"]),
        (0, []),
        (1, ["B"]),
        (2, ["B", "A"]),
        (3, ["B", "A", "C"]),
        (10, ["B", "A", "C"]),
    ],
)
def test_limit_propagation(limit: Any, expected: List[str]) -> None:
    """``limit`` is forwarded unchanged and applied after sorting."""
    rankings = [["A", "B", "C"], ["B", "C", "A"]]

    result = _app().search_results(_fresh(rankings), limit=limit)
    expected_fusion = fusion.fuse(_fresh(rankings), k=K, limit=limit)

    assert result == expected
    assert result == expected_fusion


@pytest.mark.parametrize("fixture_id", list(FIXTURES))
def test_limit_prefix_property(fixture_id: str) -> None:
    """A limited result is always a prefix of the full fused order."""
    rankings = FIXTURES[fixture_id]
    app = _app()

    full = app.search_results(_fresh(rankings), limit=None)
    limits = {0, 1, 2, len(full), len(full) + 3}

    for limit in limits:
        limited = app.search_results(_fresh(rankings), limit=limit)
        assert limited == full[:limit]


# ---------------------------------------------------------------------------
# Delegation to ``fusion.fuse``.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture_id", list(FIXTURES))
@pytest.mark.parametrize("limit", [None, 0, 2, 10])
def test_delegates_to_fusion_fuse(fixture_id: str, limit: Any) -> None:
    """``search_results`` output equals ``fusion.fuse`` for identical inputs."""
    rankings = FIXTURES[fixture_id]

    integrated = _app().search_results(_fresh(rankings), limit=limit)
    direct = fusion.fuse(_fresh(rankings), k=K, limit=limit)

    assert integrated == direct


def test_module_level_function_delegates() -> None:
    """The module-level compatibility shim matches the method."""
    rankings = [["A", "B", "C"], ["B", "C", "A"]]

    assert (
        search_app.search_results(_fresh(rankings), limit=2)
        == SearchApp().search_results(_fresh(rankings), limit=2)
        == ["B", "A"]
    )


# ---------------------------------------------------------------------------
# Iterable behavior, non-mutation, and determinism.
# ---------------------------------------------------------------------------


def test_single_pass_iterable() -> None:
    """A single-pass generator input is consumed exactly once."""
    rankings = [["A", "B"], ["B", "C"]]

    def ranking_generator():
        for ranked_list in rankings:
            yield ranked_list

    expected = _app().search_results(_fresh(rankings))
    actual = _app().search_results(ranking_generator())

    assert actual == expected


def test_input_not_mutated() -> None:
    """The integration layer does not mutate caller-owned rankings."""
    rankings = [["A", "B", "A"], ["B"]]
    snapshot = _fresh(rankings)

    _app().search_results(rankings)

    assert rankings == snapshot


def test_determinism() -> None:
    """Repeated calls and outer-list permutations are deterministic."""
    rankings = [["A", "B", "C"], ["B", "C", "A"]]
    app = _app()

    first = app.search_results(_fresh(rankings))
    second = app.search_results(_fresh(rankings))
    assert first == second

    shuffled = [["B", "C", "A"], ["A", "B", "C"]]
    assert app.search_results(_fresh(shuffled)) == first


# ---------------------------------------------------------------------------
# Error paths.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_limit",
    [
        True,
        False,
        -1,
        -100,
        3.0,
        2.5,
        "2",
        [1],
        object(),
    ],
)
def test_invalid_limit_raises_value_error(bad_limit: Any) -> None:
    """Invalid limits raise ``ValueError`` and no other exception type."""
    with pytest.raises(ValueError):
        _app().search_results([["A"]], limit=bad_limit)


def test_invalid_limit_does_not_depend_on_input() -> None:
    """Invalid ``limit`` is rejected before rankings are consumed."""
    for rankings in ([], [[], []], [["A"]]):
        with pytest.raises(ValueError):
            _app().search_results(_fresh(rankings), limit=-1)

    consumed: List[bool] = []

    def ranking_generator():
        consumed.append(True)
        yield ["A"]

    with pytest.raises(ValueError):
        _app().search_results(ranking_generator(), limit=-1)

    assert consumed == []


def test_module_level_invalid_limit_raises_value_error() -> None:
    """The module-level shim propagates invalid-limit ``ValueError``."""
    with pytest.raises(ValueError):
        search_app.search_results([], limit=-1)


@pytest.mark.parametrize("fixture_id", list(FIXTURES))
@pytest.mark.parametrize("limit", [None, 0, 1, 10])
def test_no_unexpected_exceptions_on_valid_inputs(
    fixture_id: str,
    limit: Any,
) -> None:
    """Valid fixtures and limits complete without unexpected exceptions."""
    _app().search_results(_fresh(FIXTURES[fixture_id]), limit=limit)


# ---------------------------------------------------------------------------
# Consistency with ``fusion.scores``.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture_id", list(FIXTURES))
def test_result_documents_match_scores(fixture_id: str) -> None:
    """Fused document IDs match score-map keys and are in score order."""
    rankings = FIXTURES[fixture_id]

    result = _app().search_results(_fresh(rankings))
    score_map = fusion.scores(_fresh(rankings), k=K)

    assert set(result) == set(score_map)
    assert all(score_map[doc] > 0.0 for doc in result)

    for first, second in zip(result, result[1:]):
        assert score_map[first] + SCORE_TOL >= score_map[second]
