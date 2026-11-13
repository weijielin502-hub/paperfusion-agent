"""Existing search application: initially return the first retriever's ranking."""


def fuse(rankings, k=60, limit=None):
    documents = list(rankings[0]) if rankings else []
    return documents if limit is None else documents[:limit]


def scores(rankings, k=60):
    return {doc: 1.0 for doc in fuse(rankings, k)}
