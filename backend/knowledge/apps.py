from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'knowledge'

    def ready(self):
        # Log at startup, once, whether RAG retrieval will use real grpc or
        # the Windows Application Control workaround - see grpc_compat.py.
        from knowledge.grpc_compat import ensure_chromadb_importable

        ensure_chromadb_importable()
