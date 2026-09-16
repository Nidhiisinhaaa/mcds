import pytest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import PatientProfile, User
from assessment.models import LifestyleProfile, Recommendation, RiskFlag, WellnessScore
from consultations.models import Consultation
from reports.pdf import build_report_context

FAKE_PDF_BYTES = b"%PDF-1.4 fake pdf content"


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
        user=user, full_name="Amit Kumar", preferred_language="hi", consent_given_at=timezone.now()
    )
    return user


@pytest.fixture
def other_patient(db):
    user = User.objects.create_user(
        username="patient2", password="StrongPass123", role=User.Role.PATIENT
    )
    PatientProfile.objects.create(
        user=user, full_name="Other Patient", preferred_language="en", consent_given_at=timezone.now()
    )
    return user


@pytest.fixture
def consultation(db, patient_user):
    return Consultation.objects.create(
        patient=patient_user, language="hi", status=Consultation.Status.COMPLETED
    )


@pytest.mark.django_db
class TestConsultationReportPDF:
    """render_consultation_pdf() is mocked in every test here - it needs
    WeasyPrint's native Pango/cairo/GObject libraries, which this project's
    Windows dev environment doesn't have (see README's apt-packages note).
    Mocking keeps these tests - permissions, status codes, content-type -
    portable to any machine, while the real renderer is exercised for real
    wherever those native libs are installed (the Ubuntu deploy target)."""

    def test_doctor_can_download_pdf(self, api_client, doctor_user, consultation, monkeypatch):
        monkeypatch.setattr(
            "reports.views.render_consultation_pdf", lambda c: FAKE_PDF_BYTES
        )
        api_client.force_authenticate(user=doctor_user)
        url = reverse("consultation-report-pdf", args=[consultation.id])
        response = api_client.get(url)

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert response.content == FAKE_PDF_BYTES

    def test_owning_patient_can_download_pdf(self, api_client, patient_user, consultation, monkeypatch):
        monkeypatch.setattr(
            "reports.views.render_consultation_pdf", lambda c: FAKE_PDF_BYTES
        )
        api_client.force_authenticate(user=patient_user)
        url = reverse("consultation-report-pdf", args=[consultation.id])
        response = api_client.get(url)

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_other_patient_forbidden(self, api_client, other_patient, consultation, monkeypatch):
        monkeypatch.setattr(
            "reports.views.render_consultation_pdf", lambda c: FAKE_PDF_BYTES
        )
        api_client.force_authenticate(user=other_patient)
        url = reverse("consultation-report-pdf", args=[consultation.id])
        response = api_client.get(url)
        assert response.status_code == 403

    def test_unauthenticated_forbidden(self, api_client, consultation):
        url = reverse("consultation-report-pdf", args=[consultation.id])
        response = api_client.get(url)
        assert response.status_code == 401

    def test_render_failure_returns_502(self, api_client, doctor_user, consultation, monkeypatch):
        def boom(c):
            raise RuntimeError("weasyprint exploded")

        monkeypatch.setattr("reports.views.render_consultation_pdf", boom)
        api_client.force_authenticate(user=doctor_user)
        url = reverse("consultation-report-pdf", args=[consultation.id])
        response = api_client.get(url)
        assert response.status_code == 502


def _render(consultation):
    """Renders the actual report template via the real context builder,
    without needing WeasyPrint (which only kicks in at the final
    HTML -> PDF step, not at HTML templating) - so these tests exercise the
    real template on any machine, including this Windows dev box."""
    return render_to_string("reports/consultation_report.html", build_report_context(consultation))


@pytest.mark.django_db
class TestIncompleteReportBanner:
    def test_completed_consultation_has_no_banner(self, patient_user):
        consultation = Consultation.objects.create(
            patient=patient_user, language="en", status=Consultation.Status.COMPLETED
        )
        html = _render(consultation)
        assert "Incomplete assessment" not in html

    def test_in_progress_consultation_shows_banner_with_unanswered_slots(self, patient_user):
        consultation = Consultation.objects.create(
            patient=patient_user, language="en", status=Consultation.Status.IN_PROGRESS
        )
        LifestyleProfile.objects.create(consultation=consultation, sleep_hours=7.0)

        html = _render(consultation)
        assert "Incomplete assessment" in html
        assert "still in progress" in html
        assert "Unanswered:" in html
        assert "Water" in html
        assert "Diet" in html
        assert "stopped early" not in html  # that wording is escalation-only

    def test_escalated_consultation_shows_escalation_wording_everywhere(self, patient_user):
        consultation = Consultation.objects.create(
            patient=patient_user, language="en", status=Consultation.Status.ESCALATED
        )
        RiskFlag.objects.create(
            consultation=consultation,
            code="chest_pain",
            label="Chest pain",
            severity="high",
            reason='Detected from patient message: "chest pain"',
        )

        html = _render(consultation)
        assert "Incomplete assessment" in html
        assert "stopped early" in html
        # The recommendations section must explain *why* there are none,
        # not read like a bare failure ("No recommendations generated.").
        assert "No lifestyle recommendations were generated." in html
        assert "No recommendations generated." not in html

    def test_completed_with_insufficient_data_message(self, patient_user):
        consultation = Consultation.objects.create(
            patient=patient_user, language="en", status=Consultation.Status.COMPLETED
        )
        LifestyleProfile.objects.create(
            consultation=consultation, smoking_status="none", alcohol_frequency="none"
        )
        # No WellnessScore row at all - see assessment.pipeline.MIN_FILLED_SLOTS.

        html = _render(consultation)
        assert "Not scored - insufficient responses." in html
        assert "Incomplete assessment" not in html  # the consultation itself IS complete


@pytest.mark.django_db
class TestWaterExcessLabel:
    def test_excess_water_labelled_for_doctor_review(self, patient_user):
        consultation = Consultation.objects.create(
            patient=patient_user, language="en", status=Consultation.Status.COMPLETED
        )
        LifestyleProfile.objects.create(consultation=consultation, water_litres_per_day=5.0)
        WellnessScore.objects.create(
            consultation=consultation,
            total=50,
            band="Fair",
            breakdown=[
                {
                    "factor": "water",
                    "value": 5.0,
                    "sub_score": 0.5,
                    "weight": 5,
                    "points": 2.5,
                    "reason": "Drinks 5.0 litres of water a day (sub-score 0.5).",
                }
            ],
        )

        html = _render(consultation)
        assert "Above recommended - for doctor review" in html


@pytest.mark.django_db
class TestPatientLanguageRecommendations:
    def test_shown_alongside_english_for_non_english_consultation(self, patient_user):
        consultation = Consultation.objects.create(
            patient=patient_user, language="hi", status=Consultation.Status.COMPLETED
        )
        Recommendation.objects.create(
            consultation=consultation,
            category="sleep",
            text_english="Sleep 7-8 hours a night.",
            text_patient_language="raat mein 7-8 ghante soyein.",
            sources=["general guidance"],
            order=0,
        )

        html = _render(consultation)
        assert "Sleep 7-8 hours a night." in html
        assert "raat mein 7-8 ghante soyein." in html

    def test_not_shown_for_english_consultation(self, other_patient):
        consultation = Consultation.objects.create(
            patient=other_patient, language="en", status=Consultation.Status.COMPLETED
        )
        Recommendation.objects.create(
            consultation=consultation,
            category="sleep",
            text_english="Sleep 7-8 hours a night.",
            text_patient_language="Sleep 7-8 hours a night.",
            sources=["general guidance"],
            order=0,
        )

        html = _render(consultation)
        assert html.count("Sleep 7-8 hours a night.") == 1
