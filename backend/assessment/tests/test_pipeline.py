import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from assessment import pipeline
from assessment.models import RiskFlag, Symptom, WellnessScore
from consultations.models import Message


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_run_analysis_creates_score_and_flags(consultation, sample_patient_profile):
    pipeline.run_analysis(consultation)

    score = WellnessScore.objects.get(consultation=consultation)
    assert score.total == 34
    assert score.band == "Poor"
    assert len(score.breakdown) == 8

    flag_codes = set(
        RiskFlag.objects.filter(consultation=consultation).values_list("code", flat=True)
    )
    assert flag_codes == {
        "poor_sleep",
        "sedentary_lifestyle",
        "high_stress",
        "unhealthy_diet",
        "low_water_intake",
        "obesity_risk",
        "hypertension_risk",
    }


@pytest.mark.django_db
def test_run_analysis_withholds_score_below_min_filled_slots(consultation, profile):
    """Only 2 of 8 slots filled (both favourable) - previously this rescaled
    to a misleadingly high score (see assessment.pipeline.MIN_FILLED_SLOTS);
    now no WellnessScore is produced at all."""
    profile.smoking_status = "none"
    profile.alcohol_frequency = "none"
    profile.save()

    pipeline.run_analysis(consultation)

    assert not WellnessScore.objects.filter(consultation=consultation).exists()


@pytest.mark.django_db
def test_run_analysis_produces_score_at_exactly_min_filled_slots(consultation, profile):
    profile.smoking_status = "none"
    profile.alcohol_frequency = "none"
    profile.diet_pattern = "balanced"
    profile.stress_level = "low"
    profile.save()

    pipeline.run_analysis(consultation)

    assert WellnessScore.objects.filter(consultation=consultation).exists()


@pytest.mark.django_db
def test_run_analysis_removes_stale_score_when_profile_drops_below_minimum(
    consultation, sample_patient_profile
):
    """A doctor override can reduce the effective filled-slot count (e.g.
    clearing a field) - re-running analysis must withdraw a previously-valid
    score rather than leave a stale one in place."""
    pipeline.run_analysis(consultation)
    assert WellnessScore.objects.filter(consultation=consultation).exists()

    sample_patient_profile.doctor_overrides = {
        "sleep_hours": None,
        "exercise_days_per_week": None,
        "diet_pattern": None,
        "stress_level": None,
        "sitting_hours_per_day": None,
    }
    sample_patient_profile.save()

    pipeline.run_analysis(consultation)

    assert not WellnessScore.objects.filter(consultation=consultation).exists()


@pytest.mark.django_db
def test_run_analysis_is_idempotent(consultation, sample_patient_profile):
    pipeline.run_analysis(consultation)
    pipeline.run_analysis(consultation)

    assert WellnessScore.objects.filter(consultation=consultation).count() == 1
    flags = RiskFlag.objects.filter(consultation=consultation)
    assert flags.count() == 7
    # No duplicate (code, consultation) pairs.
    assert len(set(flags.values_list("code", flat=True))) == 7


@pytest.mark.django_db
def test_run_analysis_regenerates_after_profile_change(consultation, sample_patient_profile):
    pipeline.run_analysis(consultation)
    assert WellnessScore.objects.get(consultation=consultation).total == 34
    assert "poor_sleep" in set(
        RiskFlag.objects.filter(consultation=consultation).values_list("code", flat=True)
    )

    sample_patient_profile.doctor_overrides = {
        "sleep_hours": 8.0,
        "exercise_days_per_week": 5,
        "exercise_minutes_per_session": 40,
        "diet_pattern": "balanced",
        "stress_level": "low",
        "sitting_hours_per_day": 5.0,
        "water_litres_per_day": 2.5,
    }
    sample_patient_profile.save()

    pipeline.run_analysis(consultation)

    score = WellnessScore.objects.get(consultation=consultation)
    assert score.total > 34
    remaining_codes = set(
        RiskFlag.objects.filter(consultation=consultation).values_list("code", flat=True)
    )
    assert "poor_sleep" not in remaining_codes


@pytest.mark.django_db
def test_run_analysis_syncs_new_symptoms_without_duplicating_llm_ones(
    consultation, sample_patient_profile
):
    Symptom.objects.create(
        consultation=consultation,
        name="headache",
        duration_text="2 weeks",
        severity="mild",
        source=Symptom.Source.LLM,
    )
    Message.objects.create(
        consultation=consultation,
        sender=Message.Sender.PATIENT,
        text_original="I have a severe headache and a fever.",
        text_english="I have a severe headache and a fever.",
        language="en",
    )

    pipeline.run_analysis(consultation)

    symptoms = Symptom.objects.filter(consultation=consultation)
    names_by_source = {s.source: s.name.lower() for s in symptoms}
    # The LLM's "headache" was not duplicated by scispaCy's "headache" entity
    # (case-insensitive lemma match), but "fever" is new and gets added.
    assert symptoms.filter(source=Symptom.Source.LLM, name="headache").count() == 1
    assert symptoms.filter(source=Symptom.Source.SCISPACY, name__icontains="headache").count() == 0
    assert symptoms.filter(source=Symptom.Source.SCISPACY, name__icontains="fever").exists()

    # Re-running does not duplicate the scispaCy-sourced rows.
    count_after_first_run = symptoms.count()
    pipeline.run_analysis(consultation)
    assert Symptom.objects.filter(consultation=consultation).count() == count_after_first_run


@pytest.mark.django_db
class TestReanalyseEndpoint:
    def test_doctor_can_reanalyse(self, api_client, doctor_user, consultation, sample_patient_profile):
        api_client.force_authenticate(user=doctor_user)
        response = api_client.post(reverse("consultation-reanalyse", args=[consultation.id]))
        assert response.status_code == 200
        assert WellnessScore.objects.filter(consultation=consultation).exists()

    def test_patient_cannot_reanalyse(self, api_client, patient_user, consultation, sample_patient_profile):
        api_client.force_authenticate(user=patient_user)
        response = api_client.post(reverse("consultation-reanalyse", args=[consultation.id]))
        assert response.status_code == 403

    def test_unauthenticated_cannot_reanalyse(self, api_client, consultation):
        response = api_client.post(reverse("consultation-reanalyse", args=[consultation.id]))
        assert response.status_code == 401
