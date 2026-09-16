import pytest

from assessment import nlp
from assessment.models import Symptom
from consultations.models import Message


def test_extract_disease_entities_finds_diseases():
    entities = nlp.extract_disease_entities(
        "The patient reports fatigue for 2 weeks, mild headaches, and no fever."
    )
    lowered = {e.lower() for e in entities}
    assert "fatigue" in lowered
    assert "headaches" in lowered
    assert "fever" in lowered


def test_extract_disease_entities_empty_text():
    assert nlp.extract_disease_entities("") == []
    assert nlp.extract_disease_entities(None) == []


def test_extract_disease_entities_deduplicates_within_text():
    entities = nlp.extract_disease_entities("My headache is worse than my headache yesterday.")
    lowered = [e.lower() for e in entities]
    assert lowered.count("headache") == 1


def test_lemma_key_matches_case_and_plural_variants():
    assert nlp._lemma_key("Headaches") == nlp._lemma_key("headache")
    assert nlp._lemma_key("FEVER") == nlp._lemma_key("fever")


@pytest.mark.django_db
def test_sync_symptoms_from_messages_creates_scispacy_rows(consultation):
    Message.objects.create(
        consultation=consultation,
        sender=Message.Sender.PATIENT,
        text_original="I have a bad cough and a headache.",
        text_english="I have a bad cough and a headache.",
        language="en",
    )

    created = nlp.sync_symptoms_from_messages(consultation)

    assert len(created) >= 1
    for symptom in created:
        assert symptom.source == Symptom.Source.SCISPACY
        assert symptom.consultation_id == consultation.id


@pytest.mark.django_db
def test_sync_symptoms_from_messages_dedupes_against_existing(consultation):
    Symptom.objects.create(
        consultation=consultation,
        name="cough",
        duration_text="",
        severity=Symptom.Severity.UNKNOWN,
        source=Symptom.Source.LLM,
    )
    Message.objects.create(
        consultation=consultation,
        sender=Message.Sender.PATIENT,
        text_original="I have a cough.",
        text_english="I have a cough.",
        language="en",
    )

    created = nlp.sync_symptoms_from_messages(consultation)

    assert all(s.name.lower() != "cough" for s in created)
    assert Symptom.objects.filter(consultation=consultation, name__iexact="cough").count() == 1
