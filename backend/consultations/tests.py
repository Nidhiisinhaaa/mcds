import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import PatientProfile, User
from consultations.models import Consultation


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def doctor_user(db):
    return User.objects.create_user(
        username="dr_house", password="StrongPass123", role=User.Role.DOCTOR
    )


@pytest.fixture
def patient_user(db):
    user = User.objects.create_user(
        username="patient1", password="StrongPass123", role=User.Role.PATIENT
    )
    PatientProfile.objects.create(
        user=user,
        full_name="Patient One",
        preferred_language="hi",
        consent_given_at=timezone.now(),
    )
    return user


@pytest.fixture
def unconsented_patient(db):
    user = User.objects.create_user(
        username="patient2", password="StrongPass123", role=User.Role.PATIENT
    )
    PatientProfile.objects.create(user=user, full_name="Patient Two", preferred_language="en")
    return user


@pytest.fixture
def other_patient(db):
    user = User.objects.create_user(
        username="patient3", password="StrongPass123", role=User.Role.PATIENT
    )
    PatientProfile.objects.create(
        user=user,
        full_name="Patient Three",
        preferred_language="en",
        consent_given_at=timezone.now(),
    )
    return user


@pytest.fixture
def consultation(db, patient_user):
    return Consultation.objects.create(patient=patient_user, language="hi")


@pytest.mark.django_db
class TestConsultationCreate:
    def test_create_requires_consent(self, api_client, unconsented_patient):
        api_client.force_authenticate(user=unconsented_patient)
        response = api_client.post(reverse("consultation-list-create"), {}, format="json")
        assert response.status_code == 403
        assert "consent" in str(response.data).lower()

    def test_create_defaults_language_to_profile(self, api_client, patient_user):
        api_client.force_authenticate(user=patient_user)
        response = api_client.post(reverse("consultation-list-create"), {}, format="json")
        assert response.status_code == 201
        assert response.data["language"] == "hi"
        assert response.data["status"] == "in_progress"

    def test_create_language_override(self, api_client, patient_user):
        api_client.force_authenticate(user=patient_user)
        response = api_client.post(
            reverse("consultation-list-create"), {"language": "ta"}, format="json"
        )
        assert response.status_code == 201
        assert response.data["language"] == "ta"

    def test_doctor_cannot_create_consultation(self, api_client, doctor_user):
        api_client.force_authenticate(user=doctor_user)
        response = api_client.post(reverse("consultation-list-create"), {}, format="json")
        assert response.status_code == 403

    def test_unauthenticated_cannot_create(self, api_client):
        response = api_client.post(reverse("consultation-list-create"), {}, format="json")
        assert response.status_code == 401


@pytest.mark.django_db
class TestConsultationListAndDetail:
    def test_list_returns_only_own_consultations(
        self, api_client, patient_user, other_patient, consultation
    ):
        Consultation.objects.create(patient=other_patient, language="en")

        api_client.force_authenticate(user=patient_user)
        response = api_client.get(reverse("consultation-list-create"))
        assert response.status_code == 200
        ids = [c["id"] for c in response.data["results"]]
        assert ids == [consultation.id]

    def test_detail_includes_messages(self, api_client, patient_user, consultation):
        consultation.messages.create(
            sender="patient", text_original="hi", text_english="hi", language="hi"
        )
        api_client.force_authenticate(user=patient_user)
        response = api_client.get(reverse("consultation-detail", args=[consultation.id]))
        assert response.status_code == 200
        assert len(response.data["messages"]) == 1

    def test_wrong_owner_gets_404(self, api_client, other_patient, consultation):
        api_client.force_authenticate(user=other_patient)
        response = api_client.get(reverse("consultation-detail", args=[consultation.id]))
        assert response.status_code == 404

    def test_detail_wellness_score_and_recommendations_null_when_absent(
        self, api_client, patient_user, consultation
    ):
        api_client.force_authenticate(user=patient_user)
        response = api_client.get(reverse("consultation-detail", args=[consultation.id]))
        assert response.status_code == 200
        assert response.data["wellness_score"] is None
        assert response.data["recommendations"] == []

    def test_detail_includes_wellness_score_and_recommendations_in_order(
        self, api_client, patient_user, consultation
    ):
        from assessment.models import Recommendation, WellnessScore

        WellnessScore.objects.create(
            consultation=consultation, total=72, band="Fair", breakdown=[{"factor": "sleep"}]
        )
        Recommendation.objects.create(
            consultation=consultation,
            category="water",
            text_english="Drink more water.",
            text_patient_language="Drink more water.",
            sources=["general guidance"],
            order=1,
        )
        Recommendation.objects.create(
            consultation=consultation,
            category="sleep",
            text_english="Sleep 7-8 hours.",
            text_patient_language="Sleep 7-8 hours.",
            sources=["general guidance"],
            order=0,
        )

        api_client.force_authenticate(user=patient_user)
        response = api_client.get(reverse("consultation-detail", args=[consultation.id]))
        assert response.status_code == 200
        assert response.data["wellness_score"] == {
            "total": 72,
            "band": "Fair",
            "breakdown": [{"factor": "sleep"}],
        }
        categories = [r["category"] for r in response.data["recommendations"]]
        assert categories == ["sleep", "water"]  # ordered by `order`, not creation time
        assert "text_english" not in response.data["recommendations"][0]


@pytest.mark.django_db
class TestConsultationState:
    def test_state_before_any_messages(self, api_client, patient_user, consultation):
        api_client.force_authenticate(user=patient_user)
        response = api_client.get(reverse("consultation-state", args=[consultation.id]))
        assert response.status_code == 200
        assert response.data["status"] == "in_progress"
        assert set(response.data["slot_status"].values()) == {"pending"}
        assert response.data["slot_status"]["sleep"] == "pending"

    def test_state_wrong_owner_404(self, api_client, other_patient, consultation):
        api_client.force_authenticate(user=other_patient)
        response = api_client.get(reverse("consultation-state", args=[consultation.id]))
        assert response.status_code == 404


@pytest.mark.django_db
class TestTextMessage:
    def test_post_text_translates_when_not_english(self, api_client, patient_user, consultation):
        api_client.force_authenticate(user=patient_user)
        url = reverse("consultation-text-message", args=[consultation.id])
        response = api_client.post(url, {"text": "mujhe sar dard hai"}, format="json")
        assert response.status_code == 201
        patient_message = response.data["patient_message"]
        assert patient_message["text_original"] == "mujhe sar dard hai"
        assert "mujhe sar dard hai" in patient_message["text_english"]
        assert response.data["ai_message"] is not None
        assert response.data["ai_message"]["sender"] == "ai"
        assert response.data["slot_status"]["sleep"] == "pending"
        assert response.data["status"] == "in_progress"

        consultation.refresh_from_db()
        assert consultation.turn_count == 1

    def test_post_text_english_consultation_no_translation_marker(
        self, api_client, other_patient
    ):
        consultation = Consultation.objects.create(patient=other_patient, language="en")
        api_client.force_authenticate(user=other_patient)
        url = reverse("consultation-text-message", args=[consultation.id])
        response = api_client.post(url, {"text": "I have a headache"}, format="json")
        assert response.status_code == 201
        assert response.data["patient_message"]["text_english"] == "I have a headache"

    def test_post_text_wrong_owner_404(self, api_client, other_patient, consultation):
        api_client.force_authenticate(user=other_patient)
        url = reverse("consultation-text-message", args=[consultation.id])
        response = api_client.post(url, {"text": "hi"}, format="json")
        assert response.status_code == 404

    def test_post_text_rejected_when_not_in_progress(self, api_client, patient_user, consultation):
        consultation.status = Consultation.Status.COMPLETED
        consultation.save(update_fields=["status"])
        api_client.force_authenticate(user=patient_user)
        url = reverse("consultation-text-message", args=[consultation.id])
        response = api_client.post(url, {"text": "hi"}, format="json")
        assert response.status_code == 400

    def test_post_text_blank_rejected(self, api_client, patient_user, consultation):
        api_client.force_authenticate(user=patient_user)
        url = reverse("consultation-text-message", args=[consultation.id])
        response = api_client.post(url, {"text": ""}, format="json")
        assert response.status_code == 400


@pytest.mark.django_db
class TestAudioMessage:
    def _audio_file(self, name="note.webm", size=1024, content_type="audio/webm"):
        return SimpleUploadedFile(name, b"a" * size, content_type=content_type)

    def test_post_audio_success(self, api_client, patient_user, consultation):
        api_client.force_authenticate(user=patient_user)
        url = reverse("consultation-audio-message", args=[consultation.id])
        response = api_client.post(
            url, {"audio": self._audio_file()}, format="multipart"
        )
        assert response.status_code == 201
        patient_message = response.data["patient_message"]
        assert patient_message["text_original"]
        assert patient_message["text_english"]
        assert patient_message["audio"]
        assert response.data["ai_message"] is not None
        assert response.data["ai_message"]["sender"] == "ai"

        consultation.refresh_from_db()
        assert consultation.turn_count == 1
        assert consultation.messages.count() == 2

    def test_post_audio_unsupported_format_rejected(self, api_client, patient_user, consultation):
        api_client.force_authenticate(user=patient_user)
        url = reverse("consultation-audio-message", args=[consultation.id])
        response = api_client.post(
            url,
            {"audio": self._audio_file(name="note.txt", content_type="text/plain")},
            format="multipart",
        )
        assert response.status_code == 400

    def test_post_audio_oversize_rejected(self, api_client, patient_user, consultation):
        api_client.force_authenticate(user=patient_user)
        url = reverse("consultation-audio-message", args=[consultation.id])
        oversize = 20 * 1024 * 1024 + 1
        response = api_client.post(
            url,
            {"audio": self._audio_file(size=oversize)},
            format="multipart",
        )
        assert response.status_code == 400

    def test_post_audio_wrong_owner_404(self, api_client, other_patient, consultation):
        api_client.force_authenticate(user=other_patient)
        url = reverse("consultation-audio-message", args=[consultation.id])
        response = api_client.post(url, {"audio": self._audio_file()}, format="multipart")
        assert response.status_code == 404

    def test_post_audio_rejected_when_not_in_progress(
        self, api_client, patient_user, consultation
    ):
        consultation.status = Consultation.Status.ESCALATED
        consultation.save(update_fields=["status"])
        api_client.force_authenticate(user=patient_user)
        url = reverse("consultation-audio-message", args=[consultation.id])
        response = api_client.post(url, {"audio": self._audio_file()}, format="multipart")
        assert response.status_code == 400


@pytest.mark.django_db
class TestGroqFailureHandling:
    """A Groq upstream failure must never surface as a bare 500 - the view
    should catch GroqServiceError and return a controlled 502 instead."""

    def _audio_file(self):
        return SimpleUploadedFile("note.webm", b"fake-audio-bytes", content_type="audio/webm")

    def test_audio_endpoint_returns_502_when_transcribe_fails(
        self, api_client, patient_user, consultation, monkeypatch
    ):
        from core.services.groq_client import GroqServiceError

        def failing_transcribe(*args, **kwargs):
            raise GroqServiceError("upstream boom")

        monkeypatch.setattr("consultations.views.groq_client.transcribe", failing_transcribe)

        api_client.force_authenticate(user=patient_user)
        url = reverse("consultation-audio-message", args=[consultation.id])
        response = api_client.post(url, {"audio": self._audio_file()}, format="multipart")

        assert response.status_code == 502
        assert response.data["detail"]
        # No half-saved message from the failed turn.
        assert consultation.messages.count() == 0

    def test_audio_endpoint_returns_502_when_translate_fails(
        self, api_client, patient_user, consultation, monkeypatch
    ):
        from core.services.groq_client import GroqServiceError

        def failing_translate(*args, **kwargs):
            raise GroqServiceError("upstream boom")

        # consultation fixture's patient_user has preferred_language "hi", so
        # translate_text is actually reached (not skipped as English).
        monkeypatch.setattr("consultations.views.groq_client.translate_text", failing_translate)

        api_client.force_authenticate(user=patient_user)
        url = reverse("consultation-audio-message", args=[consultation.id])
        response = api_client.post(url, {"audio": self._audio_file()}, format="multipart")

        assert response.status_code == 502
        assert response.data["detail"]
        assert consultation.messages.count() == 0

    def test_text_endpoint_returns_502_on_groq_failure(
        self, api_client, patient_user, consultation, monkeypatch
    ):
        from core.services.groq_client import GroqServiceError

        def failing_translate(*args, **kwargs):
            raise GroqServiceError("upstream boom")

        monkeypatch.setattr("consultations.views.groq_client.translate_text", failing_translate)

        api_client.force_authenticate(user=patient_user)
        url = reverse("consultation-text-message", args=[consultation.id])
        response = api_client.post(url, {"text": "hello"}, format="json")

        assert response.status_code == 502
        assert response.data["detail"]
        assert consultation.messages.count() == 0
