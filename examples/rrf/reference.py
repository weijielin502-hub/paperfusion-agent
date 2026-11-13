"""Human-authored RRF implementation used ONLY by the explicit replay fixture."""
import math


def scores(rankings, k=60):
    if isinstance(k, bool) or not isinstance(k, (int, float)) or not math.isfinite(k) or k <= 0:
        raise ValueError("k must be a finite positive number")
    result = {}
    for ranking in rankings:
        seen = set()
        for rank, doc in enumerate(ranking, start=1):
            if doc in seen:
                continue
            seen.add(doc)
            result[doc] = result.get(doc, 0.0) + 1.0 / (k + rank)
    return result


def fuse(rankings, k=60, limit=None):
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
        raise ValueError("limit must be a non-negative integer or None")
    values = scores(rankings, k)
    documents = sorted(values, key=lambda doc: (-values[doc], doc))
    return documents if limit is None else documents[:limit]
