"""
Semantic retrieval over the ingested guidelines. Never raises - if the
ChromaDB collection doesn't exist yet (no ingest has been run) or a query
fails for any reason, logs a warning once and returns an empty list so
callers (assessment/recommender.py) can fall back cleanly.
"""

import logging

from knowledge import chroma

logger = logging.getLogger("knowledge.retriever")

_warned_missing_collection = False

# Chroma always returns its k nearest neighbours, even when none of them are
# actually relevant (e.g. a sparse or partial knowledge base where only some
# guideline topics have been ingested) - there's no built-in relevance floor.
# Chroma's default distance space is squared L2 on the (roughly unit-norm)
# MiniLM embeddings, which empirically runs ~0.7 for genuinely on-topic
# matches in this project's guideline text vs ~1.6-2.0 for unrelated text.
# Chunks past this cutoff are treated the same as "nothing retrieved".
MAX_RELEVANT_DISTANCE = 1.3


def retrieve(query: str, k: int = 4, topic: str = None, age_group=None) -> list:
    """Returns up to k relevant chunks: [{"id", "text", "metadata": {file, page, topic, age_group}, "distance"}, ...].

    age_group: one age-group string (e.g. "adults"), or a list of acceptable
    ones (e.g. ["children", "adolescents"] for a patient under 18). Chunks
    tagged "unknown" always match too, regardless of what's asked for -
    ingest couldn't confidently tell what age group they're about, so they're
    treated as generally applicable rather than excluded.
    """
    global _warned_missing_collection

    try:
        collection = chroma.get_existing_collection()
    except Exception:
        logger.exception(
            "retriever.chroma_unavailable - unexpected error accessing chromadb "
            "(not the normal 'no ingest run yet' case) - RAG retrieval is degraded",
            extra={"query": query, "topic": topic},
        )
        return []

    if collection is None:
        if not _warned_missing_collection:
            logger.warning(
                "retriever.collection_missing - has ingest_guidelines been run?",
                extra={"collection": chroma.COLLECTION_NAME},
            )
            _warned_missing_collection = True
        return []

    clauses = []
    if topic:
        clauses.append({"topic": topic})
    if age_group:
        accepted = list(age_group) if isinstance(age_group, (list, tuple, set)) else [age_group]
        accepted = accepted + ["unknown"]
        clauses.append({"age_group": {"$in": accepted}})

    if not clauses:
        where = None
    elif len(clauses) == 1:
        where = clauses[0]
    else:
        where = {"$and": clauses}

    try:
        result = collection.query(query_texts=[query], n_results=k, where=where)
    except Exception:
        logger.exception("retriever.query_failed", extra={"query": query, "topic": topic})
        return []

    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    ids = (result.get("ids") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    if not documents:
        logger.warning("retriever.empty_result", extra={"query": query, "topic": topic})
        return []

    chunks = [
        {
            "id": ids[i] if i < len(ids) else None,
            "text": documents[i],
            "metadata": metadatas[i] if i < len(metadatas) else {},
            "distance": distances[i] if i < len(distances) else None,
        }
        for i in range(len(documents))
    ]
    relevant = [
        c for c in chunks if c["distance"] is None or c["distance"] <= MAX_RELEVANT_DISTANCE
    ]

    if not relevant:
        logger.warning("retriever.no_relevant_chunks", extra={"query": query, "topic": topic})

    return relevant
