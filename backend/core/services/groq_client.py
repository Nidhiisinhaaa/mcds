"""
Single entry point for every Groq API call (chat, speech-to-text, translation).

The frontend never calls Groq directly; everything routes through this module so
retries, timeouts, mocking and logging behave consistently everywhere.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import List, Optional, Type, TypeVar

from django.conf import settings
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("core.groq")

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

REQUEST_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 2
BACKOFF_BASE_SECONDS = 1.0

# whisper-large-v3-turbo does not support the /audio/translations endpoint on
# Groq — only whisper-large-v3 does — so translation uses GROQ_TRANSLATE_MODEL
# (default "whisper-large-v3"), configured separately from GROQ_STT_MODEL.

# Model capability tables. Keep these current with
# https://console.groq.com/docs/reasoning and https://console.groq.com/docs/structured-outputs
# — reasoning/structured-output params are rejected by the API on models that
# don't support them, so every call site must check before sending them.

# Supports `reasoning_effort` (low/medium/high, etc).
REASONING_EFFORT_MODELS = {
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
}

# Supports `reasoning_format` (hidden/raw/parsed). Mutually exclusive with
# `include_reasoning`.
REASONING_FORMAT_MODELS = {
    "qwen/qwen3.8-27b",
}

# Supports reasoning but not `reasoning_format` (GPT-OSS keeps reasoning in a
# separate `message.reasoning` field by default) — use `include_reasoning=False`
# instead to get the same "hidden" effect without an unsupported-param error.
INCLUDE_REASONING_FALLBACK_MODELS = REASONING_EFFORT_MODELS - REASONING_FORMAT_MODELS

# Supports response_format={"type": "json_schema", ...} (structured outputs).
JSON_SCHEMA_MODELS = {
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-safeguard-20b",
    "qwen/qwen3.8-27b",
}

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class GroqServiceError(Exception):
    """Raised when a Groq call fails after retries, or a JSON response never
    validates against the expected schema. Callers should catch this and
    fail gracefully (e.g. flag the consultation for manual review)."""


def _load_fixture(name):
    with open(FIXTURES_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_client():
    from groq import Groq

    return Groq(api_key=settings.GROQ_API_KEY, timeout=REQUEST_TIMEOUT_SECONDS)


def _reasoning_kwargs(model: str) -> dict:
    """Build the reasoning kwargs for a chat completion, gated on what the
    configured model actually supports so switching models never sends a
    param the API will reject."""
    kwargs = {}
    if model in REASONING_EFFORT_MODELS and settings.GROQ_REASONING_EFFORT:
        kwargs["reasoning_effort"] = settings.GROQ_REASONING_EFFORT

    if model in REASONING_FORMAT_MODELS and settings.GROQ_REASONING_FORMAT:
        kwargs["reasoning_format"] = settings.GROQ_REASONING_FORMAT
    elif model in INCLUDE_REASONING_FALLBACK_MODELS:
        # reasoning_format and include_reasoning are mutually exclusive; this
        # model only supports the latter.
        kwargs["include_reasoning"] = False

    return kwargs


def _response_format_for(schema: Type[BaseModel], model: str) -> dict:
    """Structured outputs (json_schema) on supported models; best-effort
    json_object everywhere else."""
    if model in JSON_SCHEMA_MODELS:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": schema.model_json_schema(),
            },
        }
    return {"type": "json_object"}


_WHITESPACE_RUN_RE = re.compile(r"\s+")


def _normalize_generated_text(text: str) -> str:
    """Clean up LLM-generated patient-facing text for display.

    Collapses every run of Unicode whitespace - including U+00A0 (non-breaking
    space) and other Unicode space variants models sometimes emit, which
    Python's `\\s` already matches - down to a single regular space, and
    trims the ends. Only whitespace characters are touched: smart quotes,
    apostrophes, and non-Latin scripts (Hindi, Tamil, etc.) pass through
    completely unchanged.
    """
    if not text:
        return text
    return _WHITESPACE_RUN_RE.sub(" ", text).strip()


_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _balanced_span_from(text: str, start: int) -> Optional[str]:
    """Return the substring from `start` to its matching closing brace,
    treating braces inside quoted strings as ordinary characters (per JSON
    string escaping rules), or None if it never balances back to depth 0."""
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _extract_json_object(raw_content: str) -> str:
    """Recover a JSON object from a chat response that may be wrapped in
    markdown code fences and/or preceded or followed by prose (e.g. leaked
    reasoning text, which may itself mention stray '{' / '}' characters).

    Tries each '{' in turn as a candidate start, taking the first one whose
    balanced span actually parses as JSON; falls back to the original text
    if none does, so json.loads can raise a clear error upstream.
    """
    text = raw_content.strip()

    fence_match = _CODE_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    search_from = 0
    while True:
        start = text.find("{", search_from)
        if start == -1:
            break
        candidate = _balanced_span_from(text, start)
        if candidate is not None:
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        search_from = start + 1

    start = text.find("{")
    return text[start:] if start != -1 else text


def _retryable_call(operation, func, *args, **kwargs):
    """Run func with up to MAX_RETRIES retries (exponential backoff) on 429s
    and 5xx errors. Logs latency; never logs request payloads."""
    from groq import APITimeoutError, InternalServerError, RateLimitError

    retryable_errors = (RateLimitError, InternalServerError, APITimeoutError)

    attempt = 0
    while True:
        started = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            usage = getattr(result, "usage", None)
            logger.info(
                "groq.call_succeeded",
                extra={
                    "operation": operation,
                    "latency_ms": latency_ms,
                    "attempt": attempt + 1,
                    "prompt_tokens": getattr(usage, "prompt_tokens", None),
                    "completion_tokens": getattr(usage, "completion_tokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None),
                },
            )
            return result
        except retryable_errors as exc:
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            attempt += 1
            logger.warning(
                "groq.call_retryable_error",
                extra={
                    "operation": operation,
                    "latency_ms": latency_ms,
                    "attempt": attempt,
                    "error": type(exc).__name__,
                },
            )
            if attempt > MAX_RETRIES:
                raise GroqServiceError(
                    f"{operation} failed after {attempt} attempts: {exc}"
                ) from exc
            time.sleep(BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            logger.error(
                "groq.call_failed",
                extra={"operation": operation, "latency_ms": latency_ms, "error": type(exc).__name__},
            )
            raise GroqServiceError(f"{operation} failed: {exc}") from exc


def _prepare_upload_file(file):
    """Adapt a Django UploadedFile (or any file-like object) into the
    (filename, content, content_type) tuple the Groq SDK requires for audio
    uploads. It rejects Django's UploadedFile passed directly — despite being
    file-like, it's not bytes, an io.IOBase instance, PathLike, or a tuple —
    and Groq infers the audio format from the filename's extension, so a
    correct filename matters as much as the type.
    """
    filename = getattr(file, "name", None) or "audio.webm"
    content_type = getattr(file, "content_type", None) or "application/octet-stream"
    content_type = content_type.split(";")[0].strip()  # drop e.g. ";codecs=opus"

    if hasattr(file, "seek"):
        try:
            file.seek(0)
        except Exception:
            pass
    content = file.read() if hasattr(file, "read") else file

    return (filename, content, content_type)


def transcribe(file, language_hint: Optional[str] = None) -> dict:
    """Speech-to-text in the original (patient) language.

    Returns {"text": str, "language": str}.
    """
    if settings.GROQ_MOCK:
        logger.info("groq.transcribe_mock", extra={"language_hint": language_hint})
        return _load_fixture("transcribe.json")

    client = _get_client()
    response = _retryable_call(
        "transcribe",
        client.audio.transcriptions.create,
        model=settings.GROQ_STT_MODEL,
        file=_prepare_upload_file(file),
        language=language_hint or None,
        response_format="verbose_json",
        temperature=0,
    )
    return {
        "text": response.text,
        "language": getattr(response, "language", language_hint) or "",
    }


def translate_audio_to_english(file) -> str:
    """Speech-to-English-text in one step via Groq's audio translations endpoint."""
    if settings.GROQ_MOCK:
        logger.info("groq.translate_audio_mock")
        return _load_fixture("translate_audio.json")["text"]

    client = _get_client()
    response = _retryable_call(
        "translate_audio_to_english",
        client.audio.translations.create,
        model=settings.GROQ_TRANSLATE_MODEL,
        file=_prepare_upload_file(file),
        response_format="json",
        temperature=0,
    )
    return _normalize_generated_text(response.text)


def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """Plain-text translation via the chat model. Returns only the translation."""
    if source_lang == target_lang:
        return text

    if settings.GROQ_MOCK:
        logger.info(
            "groq.translate_text_mock",
            extra={"source_lang": source_lang, "target_lang": target_lang, "text_length": len(text)},
        )
        template = _load_fixture("translate_text.json")["template"]
        return _normalize_generated_text(
            template.format(text=text, target_lang=target_lang, source_lang=source_lang)
        )

    system = (
        f"You are a precise medical translator. Translate the user's message from "
        f"{source_lang} to {target_lang}. Preserve clinical meaning exactly. "
        f"Reply with only the translation, no notes or quotation marks."
    )
    client = _get_client()
    response = _retryable_call(
        "translate_text",
        client.chat.completions.create,
        model=settings.GROQ_CHAT_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        temperature=0,
        **_reasoning_kwargs(settings.GROQ_CHAT_MODEL),
    )
    return _normalize_generated_text(response.choices[0].message.content.strip())


class _TranslatedBatch(BaseModel):
    translations: List[str] = []


def translate_batch(texts: list, source_lang: str, target_lang: str) -> list:
    """Translate several short texts in a single call, preserving order and
    count. Falls back to padding/truncating (with a logged warning) if the
    model ever returns the wrong number of translations, rather than raising."""
    if not texts:
        return []
    if source_lang == target_lang:
        return list(texts)

    if settings.GROQ_MOCK:
        logger.info(
            "groq.translate_batch_mock",
            extra={"count": len(texts), "source_lang": source_lang, "target_lang": target_lang},
        )
        template = _load_fixture("translate_text.json")["template"]
        return [
            _normalize_generated_text(
                template.format(text=text, target_lang=target_lang, source_lang=source_lang)
            )
            for text in texts
        ]

    system = (
        f"You are a precise medical translator. Translate every string in the given JSON "
        f"array from {source_lang} to {target_lang}, preserving clinical meaning exactly. "
        f"Return exactly {len(texts)} translations, in the same order, as a JSON object "
        f'{{"translations": [...]}}.'
    )
    user_content = json.dumps({"texts": list(texts)})

    result = chat_json(
        system, [{"role": "user", "content": user_content}], _TranslatedBatch, temperature=0
    )
    translations = [_normalize_generated_text(t) for t in result.translations]

    if len(translations) != len(texts):
        logger.warning(
            "groq.translate_batch_count_mismatch",
            extra={"expected": len(texts), "got": len(translations)},
        )
        if len(translations) < len(texts):
            translations = translations + list(texts[len(translations) :])
        else:
            translations = translations[: len(texts)]

    return translations


def chat_text(system: str, messages: list, temperature: float = 0.0) -> str:
    """Free-form chat completion, returns the assistant's text reply."""
    if settings.GROQ_MOCK:
        logger.info("groq.chat_text_mock", extra={"message_count": len(messages)})
        return _normalize_generated_text(_load_fixture("chat_text.json")["text"])

    client = _get_client()
    response = _retryable_call(
        "chat_text",
        client.chat.completions.create,
        model=settings.GROQ_CHAT_MODEL,
        messages=[{"role": "system", "content": system}, *messages],
        temperature=temperature,
        **_reasoning_kwargs(settings.GROQ_CHAT_MODEL),
    )
    return _normalize_generated_text(response.choices[0].message.content.strip())


def _mock_schema_instance(schema: Type[SchemaT]) -> SchemaT:
    """Build a schema instance for GROQ_MOCK: prefer a fixture file named after
    the schema (fixtures/chat_json/<SchemaName>.json); otherwise fall back to
    the schema's own field defaults."""
    fixture_path = FIXTURES_DIR / "chat_json" / f"{schema.__name__}.json"
    if fixture_path.exists():
        with open(fixture_path, "r", encoding="utf-8") as f:
            return schema(**json.load(f))
    return schema()


def chat_json(
    system: str,
    messages: list,
    schema: Type[SchemaT],
    temperature: float = 0.0,
) -> SchemaT:
    """JSON-mode chat completion, validated against a pydantic schema.

    On validation failure, retries once with the validation error appended to
    the conversation, then raises GroqServiceError.
    """
    if settings.GROQ_MOCK:
        logger.info(
            "groq.chat_json_mock", extra={"schema": schema.__name__, "message_count": len(messages)}
        )
        return _mock_schema_instance(schema)

    client = _get_client()
    model = settings.GROQ_CHAT_MODEL
    schema_hint = (
        f"Respond with ONLY a JSON object matching this schema: "
        f"{json.dumps(schema.model_json_schema())}"
    )
    conversation = [
        {"role": "system", "content": f"{system}\n\n{schema_hint}"},
        *messages,
    ]

    for attempt in range(2):
        response = _retryable_call(
            "chat_json",
            client.chat.completions.create,
            model=model,
            messages=conversation,
            temperature=temperature,
            response_format=_response_format_for(schema, model),
            **_reasoning_kwargs(model),
        )
        raw_content = response.choices[0].message.content
        try:
            data = json.loads(_extract_json_object(raw_content))
            return schema(**data)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            logger.warning(
                "groq.chat_json_validation_failed",
                extra={"schema": schema.__name__, "attempt": attempt + 1, "error": str(exc)},
            )
            conversation.append({"role": "assistant", "content": raw_content})
            conversation.append(
                {
                    "role": "user",
                    "content": (
                        "That response was not valid JSON matching the schema. "
                        f"Validation error: {exc}. Reply again with only corrected JSON."
                    ),
                }
            )

    raise GroqServiceError(
        f"chat_json: response never validated against {schema.__name__} after retry"
    )
