import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import PatientProfile, User
from assessment.engine.extractor import ExtractionResult, SlotEvidence, SymptomExtraction
from assessment.engine import orchestrator, slots
from assessment.models import LifestyleProfile, RiskFlag, Symptom
from consultations.models import Consultation


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def patient_user(db):
    user = User.objects.create_user(
        username="patient1", password="StrongPass123", role=User.Role.PATIENT
    )
    PatientProfile.objects.create(
        user=user,
        full_name="Patient One",
        preferred_language="en",
        consent_given_at=timezone.now(),
    )
    return user


@pytest.fixture
def hindi_patient_user(db):
    user = User.objects.create_user(
        username="patient_hi", password="StrongPass123", role=User.Role.PATIENT
    )
    PatientProfile.objects.create(
        user=user,
        full_name="Hindi Patient",
        preferred_language="hi",
        consent_given_at=timezone.now(),
    )
    return user


def _send_text(api_client, consultation_id, text):
    url = reverse("consultation-text-message", args=[consultation_id])
    return api_client.post(url, {"text": text}, format="json")


@pytest.mark.django_db
def test_happy_path_full_conversation(api_client, patient_user, monkeypatch):
    """Reproduces the sample patient: fatigue for 2 weeks, mild headaches, no
    fever; sleeps 5 hours; no exercise; frequent fast food; 1 litre of water a
    day; high stress; does not smoke; drinks occasionally; sits about 9 hours."""
    api_client.force_authenticate(user=patient_user)
    consultation = Consultation.objects.create(patient=patient_user, language="en")

    def mock_chat_json(*args, **kwargs):
        return mock_chat_json.result

    monkeypatch.setattr("core.services.groq_client.chat_json", mock_chat_json)

    turns = [
        (
            "I've had fatigue for 2 weeks and mild headaches, no fever.",
            ExtractionResult(
                chief_complaint_english="Fatigue for 2 weeks with mild headaches, no fever.",
                symptoms=[
                    SymptomExtraction(name="fatigue", duration_text="2 weeks", severity="moderate"),
                    SymptomExtraction(name="headache", duration_text="2 weeks", severity="mild"),
                ],
            ),
        ),
        (
            "I sleep about 5 hours a night.",
            ExtractionResult(
                sleep_hours=5.0,
                evidence={"sleep": SlotEvidence(quote="I sleep about 5 hours a night", confidence=0.95)},
            ),
        ),
        (
            "I don't exercise at all.",
            ExtractionResult(
                exercise_days_per_week=0,
                evidence={"exercise": SlotEvidence(quote="I don't exercise at all", confidence=0.9)},
            ),
        ),
        (
            "I eat fast food frequently.",
            ExtractionResult(
                diet_pattern="frequent_fast_food",
                evidence={"diet": SlotEvidence(quote="I eat fast food frequently", confidence=0.9)},
            ),
        ),
        (
            "About 1 litre of water a day.",
            ExtractionResult(
                water_litres_per_day=1.0,
                evidence={"water": SlotEvidence(quote="About 1 litre of water a day", confidence=0.9)},
            ),
        ),
        (
            "My stress is high because of work.",
            ExtractionResult(
                stress_level="high",
                evidence={"stress": SlotEvidence(quote="My stress is high", confidence=0.9)},
            ),
        ),
        (
            "I sit for about 9 hours a day at my desk.",
            ExtractionResult(
                sitting_hours_per_day=9.0,
                evidence={"sitting": SlotEvidence(quote="I sit for about 9 hours a day", confidence=0.9)},
            ),
        ),
        (
            "I don't smoke.",
            ExtractionResult(
                smoking_status="none",
                evidence={"smoking": SlotEvidence(quote="I don't smoke", confidence=0.95)},
            ),
        ),
        (
            "I drink occasionally, maybe at social events.",
            ExtractionResult(
                alcohol_frequency="occasional",
                evidence={"alcohol": SlotEvidence(quote="I drink occasionally", confidence=0.9)},
            ),
        ),
    ]

    expected_next_slot_target = [
        "sleep",
        "exercise",
        "diet",
        "water",
        "stress",
        "sitting",
        "smoking",
        "alcohol",
        None,  # closing message after the last slot
    ]

    for (text, extraction_result), expected_slot in zip(turns, expected_next_slot_target):
        mock_chat_json.result = extraction_result
        response = _send_text(api_client, consultation.id, text)
        assert response.status_code == 201, response.data
        ai_message = response.data["ai_message"]
        assert ai_message["slot_target"] == expected_slot

    consultation.refresh_from_db()
    assert consultation.status == Consultation.Status.COMPLETED
    assert consultation.completed_at is not None
    assert consultation.chief_complaint_english == "Fatigue for 2 weeks with mild headaches, no fever."
    assert consultation.turn_count == 9

    profile = consultation.lifestyle_profile
    assert profile.sleep_hours == 5.0
    assert profile.exercise_days_per_week == 0
    assert profile.diet_pattern == "frequent_fast_food"
    assert profile.water_litres_per_day == 1.0
    assert profile.stress_level == "high"
    assert profile.sitting_hours_per_day == 9.0
    assert profile.smoking_status == "none"
    assert profile.alcohol_frequency == "occasional"

    assert slots.all_resolved(profile)
    assert set(slots.slot_status_map(profile).values()) == {"filled"}

    # "fatigue" and "headache" come from the LLM extraction turn; "fever" is
    # added by Phase 4's scispaCy pass (run_analysis, called on completion) -
    # it tags the noun phrase in "no fever" too, since NER doesn't parse
    # negation.
    symptom_names = {
        name.lower()
        for name in Symptom.objects.filter(consultation=consultation).values_list(
            "name", flat=True
        )
    }
    assert {"fatigue", "headache"} <= symptom_names
    assert Symptom.objects.get(consultation=consultation, source="llm", name="fatigue")
    assert Symptom.objects.get(consultation=consultation, source="llm", name="headache")


@pytest.mark.django_db
def test_clarification_cap_skips_after_one_reattempt(api_client, patient_user, monkeypatch):
    api_client.force_authenticate(user=patient_user)
    consultation = Consultation.objects.create(patient=patient_user, language="en")

    def mock_chat_json(*args, **kwargs):
        return mock_chat_json.result

    monkeypatch.setattr("core.services.groq_client.chat_json", mock_chat_json)

    # Turn 1: chief complaint, no slot data yet -> AI should ask about sleep.
    mock_chat_json.result = ExtractionResult(chief_complaint_english="Feeling unwell.")
    response = _send_text(api_client, consultation.id, "I've not been feeling well.")
    assert response.data["ai_message"]["slot_target"] == "sleep"

    # Turn 2: ambiguous sleep answer -> model flags needs_clarification, no value accepted.
    mock_chat_json.result = ExtractionResult(needs_clarification="sleep")
    response = _send_text(api_client, consultation.id, "Not really sure, it varies.")
    assert response.data["ai_message"]["slot_target"] == "sleep"
    assert response.data["slot_status"]["sleep"] == "pending"

    # Turn 3: still ambiguous -> clarification budget (1) is exhausted, slot is
    # skipped, and the conversation moves on to the next slot.
    mock_chat_json.result = ExtractionResult(needs_clarification="sleep")
    response = _send_text(api_client, consultation.id, "I honestly couldn't say.")
    assert response.data["ai_message"]["slot_target"] == "exercise"
    assert response.data["slot_status"]["sleep"] == "skipped"

    profile = LifestyleProfile.objects.get(consultation=consultation)
    assert profile.sleep_hours is None
    meta = slots.get_meta(profile, "sleep")
    assert meta["skipped"] is True
    assert meta["clarification_count"] == 1


@pytest.mark.django_db
def test_turn_cap_forces_completion(api_client, patient_user, monkeypatch):
    api_client.force_authenticate(user=patient_user)
    consultation = Consultation.objects.create(
        patient=patient_user, language="en", turn_count=15
    )

    monkeypatch.setattr(
        "core.services.groq_client.chat_json",
        lambda *args, **kwargs: ExtractionResult(),
    )

    response = _send_text(api_client, consultation.id, "Still not sure about most things.")
    assert response.status_code == 201
    assert response.data["ai_message"]["slot_target"] is None

    consultation.refresh_from_db()
    assert consultation.turn_count == 16
    assert consultation.status == Consultation.Status.COMPLETED


@pytest.mark.django_db
def test_red_flag_keyword_escalates_and_stops_questionnaire(api_client, patient_user):
    api_client.force_authenticate(user=patient_user)
    consultation = Consultation.objects.create(patient=patient_user, language="en")

    response = _send_text(
        api_client, consultation.id, "I have severe chest pain and I can't breathe."
    )
    assert response.status_code == 201
    assert response.data["ai_message"] is not None

    consultation.refresh_from_db()
    assert consultation.status == Consultation.Status.ESCALATED

    codes = set(RiskFlag.objects.filter(consultation=consultation).values_list("code", flat=True))
    assert "chest_pain" in codes
    assert all(
        rf.severity == RiskFlag.Severity.HIGH
        for rf in RiskFlag.objects.filter(consultation=consultation)
    )

    # Further lifestyle questions are disabled once escalated.
    follow_up = _send_text(api_client, consultation.id, "Never mind, I'm fine.")
    assert follow_up.status_code == 400


@pytest.mark.django_db
def test_hindi_conversation_translates_questions(api_client, hindi_patient_user, monkeypatch):
    api_client.force_authenticate(user=hindi_patient_user)
    consultation = Consultation.objects.create(patient=hindi_patient_user, language="hi")

    monkeypatch.setattr(
        "core.services.groq_client.chat_json",
        lambda *args, **kwargs: ExtractionResult(chief_complaint_english="Headache."),
    )

    response = _send_text(api_client, consultation.id, "mujhe sir dard hai")
    assert response.status_code == 201

    patient_message = response.data["patient_message"]
    assert patient_message["language"] == "hi"
    assert patient_message["text_original"] == "mujhe sir dard hai"
    assert patient_message["text_english"] == "[en] mujhe sir dard hai"

    ai_message = response.data["ai_message"]
    assert ai_message["language"] == "hi"
    assert ai_message["text_original"].startswith("[hi] ")
    assert ai_message["text_original"] != ai_message["text_english"]
    assert ai_message["slot_target"] == "sleep"
