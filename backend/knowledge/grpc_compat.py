"""
Windows Application Control blocks grpc's native cygrpc extension on some
deployments (this dev machine included). chromadb pulls grpc in
unconditionally via its OpenTelemetry tracing subsystem:
chromadb -> chromadb.auth.token_authn -> chromadb.telemetry.opentelemetry ->
opentelemetry's gRPC OTLP span exporter -> grpc -> grpc._cython.cygrpc.
That import chain has nothing to do with chromadb's actual embedded
PersistentClient operation - this project never configures a real OTLP
exporter, so the exporter class only needs to be *defined* at import time,
never actually used for networking.

ensure_chromadb_importable() tries a real `import grpc` first and only
installs a stub into sys.modules if that genuinely fails, so it never masks
a real chromadb failure - a machine where grpc imports fine (e.g. the Ubuntu
deploy target) always uses the real package. The stub itself satisfies
import-time attribute access (class definitions, enum-like constants) but
raises a loud RuntimeError if any stubbed callable is ever actually invoked,
so a genuine attempt to use grpc networking fails noisily instead of
behaving like a working no-op backend.
"""

import logging
import sys
import types

logger = logging.getLogger("knowledge.chroma")

_STUB_VERSION_MARKER = "0.0.0-stub"


class _AutoAttr(type):
    """Metaclass giving stub classes (StatusCode, Compression, ...) stable
    per-name sentinel attributes, e.g. StatusCode.CANCELLED, without having
    to enumerate the real grpc enum values by hand."""

    _cache = {}

    def __getattr__(cls, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        key = (cls, name)
        if key not in _AutoAttr._cache:
            _AutoAttr._cache[key] = object()
        return _AutoAttr._cache[key]


class _StatusCode(metaclass=_AutoAttr):
    pass


class _ChannelCredentials(metaclass=_AutoAttr):
    pass


class _Compression(metaclass=_AutoAttr):
    pass


class _StubRpcError(Exception):
    pass


def _refuse(*_args, **_kwargs):
    raise RuntimeError(
        "grpc is stubbed out on this machine (Windows Application Control "
        "blocks cygrpc.pyd) and this stub only covers chromadb's import-time "
        "needs, not real gRPC networking. Something just tried to actually "
        "use grpc, which means knowledge/grpc_compat.py's stub no longer "
        "covers what chromadb needs and must be extended - or the "
        "Application Control block needs to be lifted for a real fix."
    )


def _build_stub_module():
    module = types.ModuleType("grpc")
    module.__version__ = _STUB_VERSION_MARKER
    module.RpcError = _StubRpcError
    module.StatusCode = _StatusCode
    module.ChannelCredentials = _ChannelCredentials
    module.Compression = _Compression

    def _module_getattr(name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _refuse

    module.__getattr__ = _module_getattr
    return module


def ensure_chromadb_importable():
    """Make `import chromadb` possible even when the real grpc package can't
    load its native extension. Call this before the first `import chromadb`
    in a process. Idempotent, and logs which path was taken so the choice is
    visible rather than silent."""
    stub_installed = (
        "grpc" in sys.modules
        and getattr(sys.modules["grpc"], "__version__", None) == _STUB_VERSION_MARKER
    )
    if stub_installed:
        return

    try:
        import grpc  # noqa: F401

        logger.info("knowledge.chroma.grpc_available - using the real grpc package")
    except ImportError as exc:
        logger.warning(
            "knowledge.chroma.grpc_stubbed - real grpc import failed (%s); "
            "installing a stub so chromadb can still import. RAG retrieval "
            "does not need real gRPC networking, only grpc's import-time "
            "definitions, so this is safe - but any genuine attempt to use "
            "grpc networking will now raise loudly instead of silently "
            "no-opping.",
            exc,
        )
        sys.modules["grpc"] = _build_stub_module()
