"""
Medical NER over patient messages: DISEASE entities become Symptom rows,
deduplicated against whatever the LLM already extracted during the
conversation (assessment.engine.extractor).

Compatibility check (Phase 4, done on this project's Python 3.10.11 venv):
scispaCy 0.6.2 declares `spacy<3.9.0,>=3.7.0`. The en_ner_bc5cdr_md 0.5.4
model package additionally pins `spacy<3.8.0,>=3.7.4`, which resolved cleanly
to spacy==3.7.5 (down from the 3.8.16 that a bare `pip install spacy` would
give you) with no build failures — nmslib-metabrainz ships a prebuilt Windows
wheel for Python 3.10, so nothing needs a C++ toolchain. Loading the model
and running it against a sample sentence correctly tagged "fatigue",
"headaches", and "fever" as DISEASE entities. So this module uses scispaCy
directly; the spaCy en_core_web_sm + EntityRuler fallback described in the
brief was not needed and is not implemented here.
"""

import logging
import threading

logger = logging.getLogger("assessment.nlp")

DISEASE_LABEL = "DISEASE"

_nlp_lock = threading.Lock()
_nlp_singleton = None


def _get_nlp():
    """Lazily load the scispaCy pipeline once per process."""
    global _nlp_singleton
    if _nlp_singleton is None:
        with _nlp_lock:
            if _nlp_singleton is None:
                import en_ner_bc5cdr_md

                logger.info("nlp.loading_model", extra={"model": "en_ner_bc5cdr_md"})
                _nlp_singleton = en_ner_bc5cdr_md.load()
    return _nlp_singleton


def _lemma_key(text: str) -> str:
    """Case-insensitive, lemmatized key used to match a scispaCy entity
    against an already-recorded symptom name (e.g. "Headaches" / "headache"
    should collide)."""
    text = (text or "").strip()
    if not text:
        return ""
    doc = _get_nlp()(text)
    lemmas = [
        token.lemma_.lower() for token in doc if not token.is_punct and not token.is_space
    ]
    return " ".join(lemmas) or text.lower()


def extract_disease_entities(text: str) -> list:
    """Run NER on a piece of English text; return unique DISEASE entity
    surface strings (original casing/wording, in first-seen order)."""
    text = (text or "").strip()
    if not text:
        return []

    doc = _get_nlp()(text)
    seen = set()
    entities = []
    for ent in doc.ents:
        if ent.label_ != DISEASE_LABEL:
            continue
        surface = ent.text.strip()
        key = surface.lower()
        if surface and key not in seen:
            seen.add(key)
            entities.append(surface)
    return entities


def sync_symptoms_from_messages(consultation) -> list:
    """Run NER over every patient message's English text and create Symptom
    rows (source=scispacy) for DISEASE entities not already covered - by
    lemma match - by an existing Symptom (however it was sourced). Returns
    the list of newly created Symptom rows."""
    from assessment.models import Symptom
    from consultations.models import Message

    existing_names = consultation.symptoms.values_list("name", flat=True)
    seen_keys = {_lemma_key(name) for name in existing_names}

    patient_texts = consultation.messages.filter(
        sender=Message.Sender.PATIENT
    ).values_list("text_english", flat=True)

    created = []
    for text in patient_texts:
        for entity_text in extract_disease_entities(text):
            key = _lemma_key(entity_text)
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            created.append(
                Symptom.objects.create(
                    consultation=consultation,
                    name=entity_text,
                    duration_text="",
                    severity=Symptom.Severity.UNKNOWN,
                    source=Symptom.Source.SCISPACY,
                )
            )

    return created
