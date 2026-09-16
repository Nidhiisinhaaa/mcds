"""
Shared ChromaDB setup for the guideline knowledge base. Persistent, local,
using Chroma's default ONNX (all-MiniLM-L6-v2) embedding function - no torch,
no sentence-transformers, per CLAUDE.md.
"""

import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger("knowledge.chroma")

CHROMA_DIR = Path(getattr(settings, "BASE_DIR", Path(__file__).resolve().parent.parent)) / "chroma_db"
COLLECTION_NAME = "guidelines"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

_client = None


def get_client():
    global _client
    if _client is None:
        from knowledge.grpc_compat import ensure_chromadb_importable

        ensure_chromadb_importable()
        import chromadb

        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def get_embedding_function():
    from chromadb.utils import embedding_functions

    return embedding_functions.DefaultEmbeddingFunction()


def get_or_create_collection():
    return get_client().get_or_create_collection(
        COLLECTION_NAME, embedding_function=get_embedding_function()
    )


def get_existing_collection():
    """Returns the collection, or None if it doesn't exist yet (e.g. no
    ingest has ever been run). Only swallows chromadb's own NotFoundError -
    any other exception (a real chromadb/grpc failure the stub in
    grpc_compat.py doesn't cover, a corrupt DB, etc.) propagates, so it's
    never mistaken for "no ingest has been run yet"."""
    from chromadb.errors import NotFoundError

    try:
        return get_client().get_collection(
            COLLECTION_NAME, embedding_function=get_embedding_function()
        )
    except NotFoundError:
        return None
