import io
import json

import pytest
from pydantic import BaseModel

from core.services import groq_client


class EchoSchema(BaseModel):
    message: str = "default"
    confidence: float = 0.0


@pytest.mark.django_db
class TestGroqClientMock:
    """All assertions here run with GROQ_MOCK=1 - forced for every test run
    by config/test_settings.py, regardless of backend/.env - so no network
    calls are made."""

    def test_transcribe_returns_text_and_language(self):
        result = groq_client.transcribe(io.BytesIO(b"fake-audio"), language_hint="hi")
        assert isinstance(result["text"], str) and result["text"]
        assert isinstance(result["language"], str) and result["language"]

    def test_translate_audio_to_english_returns_text(self):
        result = groq_client.translate_audio_to_english(io.BytesIO(b"fake-audio"))
        assert isinstance(result, str) and result

    def test_translate_text_same_language_is_noop(self):
        assert groq_client.translate_text("hello", "en", "en") == "hello"

    def test_translate_text_different_language(self):
        result = groq_client.translate_text("mujhe sar dard hai", "hi", "en")
        assert "mujhe sar dard hai" in result
        assert "en" in result

    def test_chat_text_returns_string(self):
        result = groq_client.chat_text("You are a helpful assistant.", [])
        assert isinstance(result, str) and result

    def test_chat_json_validates_against_schema(self):
        result = groq_client.chat_json(
            "system prompt", [{"role": "user", "content": "hi"}], EchoSchema
        )
        assert isinstance(result, EchoSchema)
        assert result.message == "default"


class TestPrepareUploadFile:
    """The Groq SDK rejects Django's UploadedFile passed directly (it's not
    bytes, io.IOBase, PathLike, or a tuple, despite being file-like) - this
    adapter must always hand back a (filename, content, content_type) tuple."""

    def test_converts_django_uploaded_file_to_tuple(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        upload = SimpleUploadedFile(
            "recording.webm", b"fake-audio-bytes", content_type="audio/webm;codecs=opus"
        )
        filename, content, content_type = groq_client._prepare_upload_file(upload)
        assert filename == "recording.webm"
        assert content == b"fake-audio-bytes"
        assert content_type == "audio/webm"  # ";codecs=opus" stripped

    def test_defaults_when_name_and_content_type_are_absent(self):
        filename, content, content_type = groq_client._prepare_upload_file(io.BytesIO(b"x"))
        assert filename == "audio.webm"
        assert content == b"x"
        assert content_type == "application/octet-stream"

    def test_rewinds_before_reading(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        upload = SimpleUploadedFile("clip.wav", b"0123456789", content_type="audio/wav")
        upload.read()  # simulate a prior read leaving the pointer at EOF
        _filename, content, _content_type = groq_client._prepare_upload_file(upload)
        assert content == b"0123456789"


@pytest.mark.django_db
def test_transcribe_sends_a_proper_tuple_not_the_raw_django_file(monkeypatch, settings):
    """Regression test for the actual bug: transcribe() used to pass the raw
    Django UploadedFile straight through to the Groq SDK, which raises
    RuntimeError since it isn't bytes/io.IOBase/PathLike/tuple."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    settings.GROQ_MOCK = False
    upload = SimpleUploadedFile(
        "recording.webm", b"fake-audio-bytes", content_type="audio/webm;codecs=opus"
    )

    captured = {}

    class FakeTranscription:
        text = "hello"
        language = "en"

    class FakeTranscriptions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return FakeTranscription()

    class FakeAudio:
        transcriptions = FakeTranscriptions()

    class FakeClient:
        audio = FakeAudio()

    monkeypatch.setattr(groq_client, "_get_client", lambda: FakeClient())

    result = groq_client.transcribe(upload, language_hint="hi")

    assert result == {"text": "hello", "language": "en"}
    file_arg = captured["file"]
    assert isinstance(file_arg, tuple)
    assert file_arg == ("recording.webm", b"fake-audio-bytes", "audio/webm")


class TestNormalizeGeneratedText:
    """Model output sometimes contains U+00A0 (non-breaking space) and other
    Unicode space variants that render badly for patients. Normalisation must
    collapse those without touching quotes, apostrophes, or non-Latin script.

    Every non-ASCII character below is written as a \\uXXXX escape (rather
    than a literal character) so the exact codepoints under test are
    unambiguous in the source.
    """

    def test_non_breaking_space_becomes_regular_space(self):
        text = "Thank\u00a0you for\u00a0sharing that."
        assert groq_client._normalize_generated_text(text) == "Thank you for sharing that."

    def test_other_unicode_space_variants_collapse(self):
        # U+2003 EM SPACE, U+3000 IDEOGRAPHIC SPACE
        text = "one\u2003two\u3000three four"
        assert groq_client._normalize_generated_text(text) == "one two three four"

    def test_repeated_and_newline_whitespace_collapses(self):
        text = "Line one.\n\n  Line   two.\t\tLine three."
        assert (
            groq_client._normalize_generated_text(text) == "Line one. Line two. Line three."
        )

    def test_leading_and_trailing_whitespace_trimmed(self):
        assert groq_client._normalize_generated_text("  \u00a0 hello  \n") == "hello"

    def test_smart_quotes_and_apostrophes_preserved(self):
        # U+2019 right single quote, U+201C/U+201D double quotes, U+2014 em dash.
        text = "It\u2019s \u201cfine\u201d, thanks \u2014 really."
        assert groq_client._normalize_generated_text(text) == text

    def test_hindi_text_untouched_except_whitespace(self):
        # "mujhe sir dard hai" (I have a headache) with a stray NBSP where a
        # normal space belongs.
        text = "\u092e\u0941\u091d\u0947\u00a0\u0938\u093f\u0930 \u0926\u0930\u094d\u0926 \u0939\u0948"
        expected = "\u092e\u0941\u091d\u0947 \u0938\u093f\u0930 \u0926\u0930\u094d\u0926 \u0939\u0948"
        assert groq_client._normalize_generated_text(text) == expected

    def test_tamil_text_untouched_except_whitespace(self):
        # "enakku thalaivali ulladhu" (I have a headache) with doubled
        # whitespace to collapse.
        text = "\u0b8e\u0ba9\u0b95\u0bcd\u0b95\u0bc1  \u0ba4\u0bb2\u0bc8\u0bb5\u0bb2\u0bbf \u0b89\u0bb3\u0bcd\u0bb3\u0ba4\u0bc1"
        expected = "\u0b8e\u0ba9\u0b95\u0bcd\u0b95\u0bc1 \u0ba4\u0bb2\u0bc8\u0bb5\u0bb2\u0bbf \u0b89\u0bb3\u0bcd\u0bb3\u0ba4\u0bc1"
        assert groq_client._normalize_generated_text(text) == expected

    def test_empty_string_is_noop(self):
        assert groq_client._normalize_generated_text("") == ""

    def test_chat_text_output_is_normalized(self, monkeypatch, settings):
        settings.GROQ_MOCK = True
        monkeypatch.setattr(
            groq_client,
            "_load_fixture",
            lambda name: {"text": "Hello\u00a0there,   friend."},
        )
        result = groq_client.chat_text("system", [])
        assert result == "Hello there, friend."


class TestExtractJsonObject:
    """Reasoning models (e.g. openai/gpt-oss-120b) can leak chain-of-thought
    prose, sometimes wrapped in markdown fences, around the actual JSON
    payload. _extract_json_object must recover the JSON regardless."""

    def test_json_wrapped_in_reasoning_prose_and_code_fence(self):
        raw = (
            "Let me think through this step by step. The patient said they "
            "sleep about 5 hours, so sleep_hours should be 5.0.\n\n"
            "```json\n"
            '{"message": "ok", "confidence": 0.9}\n'
            "```\n\n"
            "That looks right."
        )
        extracted = groq_client._extract_json_object(raw)
        assert json.loads(extracted) == {"message": "ok", "confidence": 0.9}

    def test_json_wrapped_in_prose_without_fences(self):
        raw = 'Reasoning: the answer is clear. {"message": "ok", "confidence": 0.7} Done.'
        extracted = groq_client._extract_json_object(raw)
        assert json.loads(extracted) == {"message": "ok", "confidence": 0.7}

    def test_nested_braces_and_braces_inside_strings_are_not_confused(self):
        raw = (
            'Some preamble with a { stray brace.\n'
            '{"message": "value with a } brace and a nested {\\"x\\": 1}", "confidence": 0.5}\n'
            "trailing text { too"
        )
        extracted = groq_client._extract_json_object(raw)
        parsed = json.loads(extracted)
        assert parsed["confidence"] == 0.5
        assert "brace" in parsed["message"]

    def test_plain_json_with_no_prose_is_unaffected(self):
        raw = '{"message": "ok", "confidence": 1.0}'
        assert groq_client._extract_json_object(raw) == raw


@pytest.mark.django_db
def test_chat_json_parses_response_wrapped_in_reasoning_prose(monkeypatch, settings):
    """End-to-end: even with GROQ_MOCK off, a reasoning model's response that
    wraps the JSON object in leaked chain-of-thought prose still validates."""

    class FakeMessage:
        content = (
            "Thinking about the best answer... I believe the following JSON "
            "captures it correctly:\n"
            "```json\n"
            '{"message": "hidden-reasoning-safe", "confidence": 0.8}\n'
            "```"
        )

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]
        usage = None

    class FakeCompletions:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    settings.GROQ_MOCK = False
    settings.GROQ_CHAT_MODEL = "openai/gpt-oss-120b"
    monkeypatch.setattr(groq_client, "_get_client", lambda: FakeClient())

    result = groq_client.chat_json("system prompt", [{"role": "user", "content": "hi"}], EchoSchema)
    assert result.message == "hidden-reasoning-safe"
    assert result.confidence == 0.8
