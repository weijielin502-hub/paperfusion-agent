"""Existing caller. The agent must preserve this integration contract."""
from fusion import fuse


def search_results(keyword_ids, semantic_ids, limit=5):
    return {"documents": fuse([keyword_ids, semantic_ids], limit=limit), "method": "fusion"}
