import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import PatientProfile, User
from assessment.models import DoctorNote, LifestyleProfile, Recommendation, RiskFlag, WellnessScore
from consultations.models import Consultation, Message


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def doctor_user(db):
    return User.objects.create_user(
        username="dr_house", password="StrongPass123", role=User.Role.DOCTOR
    )


@pytest.fixture
def other_doctor(db):
    return User.objects.create_user(
        username="dr_wilson", password="StrongPass123", role=User.Role.DOCTOR
    )


@pytest.fixture
def patient_user(db):
    user = User.objects.create_user(
        username="patient1", password="StrongPass123", role=User.Role.PATIENT
    )
    PatientProfile.objects.create(
        user=user,
        full_name="Amit Kumar",
        age=34,
        sex="male",
        height_cm=170,
        weight_kg=70,
        preferred_language="hi",
        consent_given_at=timezone.now(),
    )
    return user


@pytest.fixture
def consultation(db, patient_user):
    return Consultation.objects.create(
        patient=patient_user,
        language="hi",
        status=Consultation.Status.COMPLETED,
        chief_complaint_english="Fatigue for 2 weeks.",
    )


@pytest.fixture
def profile(db, consultation):
    return LifestyleProfile.objects.create(
        consultation=consultation,
        sleep_hours=5.0,
        exercise_days_per_week=0,
        diet_pattern="frequent_fast_food",
        water_litres_per_day=1.0,
        stress_level="high",
        sitting_hours_per_day=9.0,
        smoking_status="none",
        alcohol_frequency="occasional",
        evidence={"sleep": {"quote": "I sleep about 5 hours", "confidence": 0.9}},
    )


@pytest.mark.django_db
class TestDoctorPermissions:
    def _urls(self, consultation_id):
        return [
            ("get", reverse("doctor-consultation-list")),
            ("get", reverse("doctor-consultation-detail", args=[consultation_id])),
            ("patch", reverse("doctor-consultation-lifestyle", args=[consultation_id])),
            ("post", reverse("doctor-consultation-notes", args=[consultation_id])),
            ("post", reverse("doctor-consultation-review", args=[consultation_id])),
        ]

    def test_unauthenticated_forbidden(self, api_client, consultation):
        for method, url in self._urls(consultation.id):
            response = getattr(api_client, method)(url)
            assert response.status_code == 401, url

    def test_patient_forbidden(self, api_client, patient_user, consultation):
        api_client.force_authenticate(user=patient_user)
        for method, url in self._urls(consultation.id):
            response = getattr(api_client, method)(url)
            assert response.status_code == 403, url

    def test_doctor_allowed(self, api_client, doctor_user, consultation):
        api_client.force_authenticate(user=doctor_user)
        response = api_client.get(reverse("doctor-consultation-list"))
        assert response.status_code == 200
        response = api_client.get(reverse("doctor-consultation-detail", args=[consultation.id]))
        assert response.status_code == 200

    def test_any_doctor_sees_any_patient_single_clinic_demo(
        self, api_client, other_doctor, consultation
    ):
        api_client.force_authenticate(user=other_doctor)
        response = api_client.get(reverse("doctor-consultation-detail", args=[consultation.id]))
        assert response.status_code == 200


@pytest.mark.django_db
class TestDoctorConsultationList:
    def test_escalated_pinned_first_then_completed_newest_first(
        self, api_client, doctor_user, patient_user
    ):
        old_completed = Consultation.objects.create(
            patient=patient_user, language="en", status=Consultation.Status.COMPLETED
        )
        new_completed = Consultation.objects.create(
            patient=patient_user, language="en", status=Consultation.Status.COMPLETED
        )
        in_progress = Consultation.objects.create(
            patient=patient_user, language="en", status=Consultation.Status.IN_PROGRESS
        )
        escalated = Consultation.objects.create(
            patient=patient_user, language="en", status=Consultation.Status.ESCALATED
        )
        reviewed = Consultation.objects.create(
            patient=patient_user, language="en", status=Consultation.Status.REVIEWED
        )

        # started_at is auto_now_add - force an explicit order independent of creation time.
        Consultation.objects.filter(pk=old_completed.pk).update(
            started_at=timezone.now() - timezone.timedelta(days=2)
        )
        Consultation.objects.filter(pk=new_completed.pk).update(
            started_at=timezone.now() - timezone.timedelta(days=1)
        )

        api_client.force_authenticate(user=doctor_user)
        response = api_client.get(reverse("doctor-consultation-list"))
        assert response.status_code == 200
        ids = [row["id"] for row in response.data["results"]]

        assert ids == [
            escalated.id,
            new_completed.id,
            old_completed.id,
            in_progress.id,
            reviewed.id,
        ]

    def test_status_filter(self, api_client, doctor_user, patient_user):
        Consultation.objects.create(
            patient=patient_user, language="en", status=Consultation.Status.COMPLETED
        )
        escalated = Consultation.objects.create(
            patient=patient_user, language="en", status=Consultation.Status.ESCALATED
        )

        api_client.force_authenticate(user=doctor_user)
        response = api_client.get(reverse("doctor-consultation-list"), {"status": "escalated"})
        ids = [row["id"] for row in response.data["results"]]
        assert ids == [escalated.id]

    def test_search_by_chief_complaint(self, api_client, doctor_user, consultation):
        api_client.force_authenticate(user=doctor_user)
        response = api_client.get(reverse("doctor-consultation-list"), {"q": "Fatigue"})
        ids = [row["id"] for row in response.data["results"]]
        assert consultation.id in ids

    def test_search_by_patient_name(self, api_client, doctor_user, consultation):
        api_client.force_authenticate(user=doctor_user)
        response = api_client.get(reverse("doctor-consultation-list"), {"q": "Amit"})
        ids = [row["id"] for row in response.data["results"]]
        assert consultation.id in ids

    def test_queue_row_shape(self, api_client, doctor_user, consultation, profile):
        WellnessScore.objects.create(consultation=consultation, total=34, band="Poor", breakdown=[])
        RiskFlag.objects.create(
            consultation=consultation, code="poor_sleep", label="Poor sleep", severity="medium", reason="x"
        )

        api_client.force_authenticate(user=doctor_user)
        response = api_client.get(reverse("doctor-consultation-list"))
        row = next(r for r in response.data["results"] if r["id"] == consultation.id)
        assert row["patient_name"] == "Amit Kumar"
        assert row["patient_age"] == 34
        assert row["language"] == "hi"
        assert row["chief_complaint_english"] == "Fatigue for 2 weeks."
        assert row["wellness_total"] == 34
        assert row["wellness_band"] == "Poor"
        assert row["flag_count"] == 1
        assert row["status"] == "completed"

    def test_queue_row_null_score_for_completed_insufficient_data(
        self, api_client, doctor_user, patient_user
    ):
        """A completed consultation with no WellnessScore row (insufficient
        data - see assessment.pipeline.MIN_FILLED_SLOTS) must serialize a
        null score, not error or fall back to some default."""
        consultation = Consultation.objects.create(
            patient=patient_user, language="en", status=Consultation.Status.COMPLETED
        )

        api_client.force_authenticate(user=doctor_user)
        response = api_client.get(reverse("doctor-consultation-list"))
        row = next(r for r in response.data["results"] if r["id"] == consultation.id)
        assert row["wellness_total"] is None
        assert row["wellness_band"] is None
        assert row["status"] == "completed"


@pytest.mark.django_db
class TestDoctorConsultationDetail:
    def test_full_detail_shape(self, api_client, doctor_user, consultation, profile):
        Message.objects.create(
            consultation=consultation,
            sender=Message.Sender.PATIENT,
            text_original="mujhe thakaan hai",
            text_english="I am tired",
            language="hi",
        )
        WellnessScore.objects.create(consultation=consultation, total=34, band="Poor", breakdown=[])
        RiskFlag.objects.create(
            consultation=consultation, code="poor_sleep", label="Poor sleep", severity="medium", reason="Reported 5 hours."
        )
        Recommendation.objects.create(
            consultation=consultation,
            category="sleep",
            text_english="Sleep 7-8 hours.",
            text_patient_language="7-8 ghante soyein.",
            sources=["general guidance"],
            order=0,
        )
        DoctorNote.objects.create(consultation=consultation, doctor=doctor_user, text="Looks stable.")

        api_client.force_authenticate(user=doctor_user)
        response = api_client.get(reverse("doctor-consultation-detail", args=[consultation.id]))
        assert response.status_code == 200
        data = response.data

        assert data["patient_profile"]["full_name"] == "Amit Kumar"
        assert data["patient_profile"]["bmi"] == pytest.approx(24.2, abs=0.1)
        assert len(data["messages"]) == 1
        assert data["messages"][0]["text_english"] == "I am tired"
        assert data["lifestyle_profile"]["sleep_hours"] == 5.0
        assert data["lifestyle_profile"]["evidence"]["sleep"]["quote"] == "I sleep about 5 hours"
        assert data["slot_status"] == {
            "sleep": "filled",
            "exercise": "filled",
            "diet": "filled",
            "water": "filled",
            "stress": "filled",
            "sitting": "filled",
            "smoking": "filled",
            "alcohol": "filled",
        }
        assert data["wellness_score"]["total"] == 34
        assert data["risk_flags"][0]["code"] == "poor_sleep"
        assert data["recommendations"][0]["text_english"] == "Sleep 7-8 hours."
        assert data["recommendations"][0]["sources"] == ["general guidance"]
        assert data["doctor_notes"][0]["text"] == "Looks stable."
        assert data["doctor_notes"][0]["doctor_username"] == "dr_house"

    def test_slot_status_distinguishes_skipped_from_pending(
        self, api_client, doctor_user, consultation
    ):
        sparse_profile = LifestyleProfile.objects.create(
            consultation=consultation,
            sleep_hours=7.0,  # filled
            evidence={
                # diet was asked, patient's answer was never confident enough,
                # clarification budget exhausted -> skipped.
                "diet": {"needs_clarification": True, "clarification_count": 1, "skipped": True},
                # water was flagged for clarification but hasn't exhausted
                # its budget yet -> still pending, not skipped.
                "water": {"needs_clarification": True, "clarification_count": 0},
            },
        )

        api_client.force_authenticate(user=doctor_user)
        response = api_client.get(reverse("doctor-consultation-detail", args=[consultation.id]))
        slot_status = response.data["slot_status"]

        assert slot_status["sleep"] == "filled"
        assert slot_status["diet"] == "skipped"
        assert slot_status["water"] == "pending"
        assert slot_status["stress"] == "pending"  # never touched at all


@pytest.mark.django_db
class TestDoctorLifestyleOverride:
    def test_override_triggers_rescore(self, api_client, doctor_user, consultation, profile):
        from assessment import pipeline

        pipeline.rescore_only(consultation)
        baseline = WellnessScore.objects.get(consultation=consultation)
        assert baseline.total == 34
        assert "poor_sleep" in set(
            RiskFlag.objects.filter(consultation=consultation).values_list("code", flat=True)
        )

        api_client.force_authenticate(user=doctor_user)
        url = reverse("doctor-consultation-lifestyle", args=[consultation.id])
        response = api_client.patch(url, {"doctor_overrides": {"sleep_hours": 8.0}}, format="json")

        assert response.status_code == 200
        profile.refresh_from_db()
        assert profile.doctor_overrides == {"sleep_hours": 8.0}

        updated_score = WellnessScore.objects.get(consultation=consultation)
        assert updated_score.total > baseline.total
        assert "poor_sleep" not in set(
            RiskFlag.objects.filter(consultation=consultation).values_list("code", flat=True)
        )

    def test_override_merges_with_existing(self, api_client, doctor_user, consultation, profile):
        profile.doctor_overrides = {"stress_level": "low"}
        profile.save(update_fields=["doctor_overrides"])

        api_client.force_authenticate(user=doctor_user)
        url = reverse("doctor-consultation-lifestyle", args=[consultation.id])
        api_client.patch(url, {"doctor_overrides": {"sleep_hours": 8.0}}, format="json")

        profile.refresh_from_db()
        assert profile.doctor_overrides == {"stress_level": "low", "sleep_hours": 8.0}

    def test_unknown_field_rejected(self, api_client, doctor_user, consultation, profile):
        api_client.force_authenticate(user=doctor_user)
        url = reverse("doctor-consultation-lifestyle", args=[consultation.id])
        response = api_client.patch(url, {"doctor_overrides": {"not_a_field": 1}}, format="json")
        assert response.status_code == 400

    def test_missing_body_rejected(self, api_client, doctor_user, consultation, profile):
        api_client.force_authenticate(user=doctor_user)
        url = reverse("doctor-consultation-lifestyle", args=[consultation.id])
        response = api_client.patch(url, {}, format="json")
        assert response.status_code == 400


@pytest.mark.django_db
class TestDoctorNotes:
    def test_create_note(self, api_client, doctor_user, consultation):
        api_client.force_authenticate(user=doctor_user)
        url = reverse("doctor-consultation-notes", args=[consultation.id])
        response = api_client.post(url, {"text": "Discussed diet changes."}, format="json")
        assert response.status_code == 201
        note = DoctorNote.objects.get(consultation=consultation)
        assert note.doctor == doctor_user
        assert note.text == "Discussed diet changes."


@pytest.mark.django_db
class TestDoctorReview:
    def test_review_sets_doctor_reviewed_at_and_status(self, api_client, doctor_user, consultation):
        api_client.force_authenticate(user=doctor_user)
        url = reverse("doctor-consultation-review", args=[consultation.id])
        response = api_client.post(url)
        assert response.status_code == 200

        consultation.refresh_from_db()
        assert consultation.doctor == doctor_user
        assert consultation.reviewed_at is not None
        assert consultation.status == Consultation.Status.REVIEWED
