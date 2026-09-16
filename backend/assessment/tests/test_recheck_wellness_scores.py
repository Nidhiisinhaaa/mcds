import pytest
from django.core.management import call_command

from assessment.models import WellnessScore


@pytest.mark.django_db
def test_clears_stale_score_below_min_filled_slots(consultation, profile, capsys):
    """Simulates a WellnessScore written before MIN_FILLED_SLOTS existed:
    only 2/8 slots filled (both favourable), but a score was still saved -
    exactly the "Bye" -> 100 "Good" bug this command cleans up."""
    profile.smoking_status = "none"
    profile.alcohol_frequency = "none"
    profile.save()
    WellnessScore.objects.create(consultation=consultation, total=100, band="Good", breakdown=[])

    call_command("recheck_wellness_scores")

    assert not WellnessScore.objects.filter(consultation=consultation).exists()
    output = capsys.readouterr().out
    assert f"consultation #{consultation.id}" in output
    assert "Cleared 1 stale WellnessScore row(s), kept 0" in output


@pytest.mark.django_db
def test_keeps_score_at_or_above_min_filled_slots(consultation, sample_patient_profile):
    WellnessScore.objects.create(consultation=consultation, total=34, band="Poor", breakdown=[])

    call_command("recheck_wellness_scores")

    assert WellnessScore.objects.filter(consultation=consultation).exists()


@pytest.mark.django_db
def test_clears_score_with_no_lifestyle_profile_at_all(consultation):
    """LifestyleProfile deleted/missing entirely -> 0 filled slots, cleared
    the same as any other under-filled case."""
    WellnessScore.objects.create(consultation=consultation, total=50, band="Fair", breakdown=[])

    call_command("recheck_wellness_scores")

    assert not WellnessScore.objects.filter(consultation=consultation).exists()


@pytest.mark.django_db
def test_dry_run_reports_without_deleting(consultation, profile, capsys):
    profile.smoking_status = "none"
    profile.save()
    WellnessScore.objects.create(consultation=consultation, total=100, band="Good", breakdown=[])

    call_command("recheck_wellness_scores", "--dry-run")

    assert WellnessScore.objects.filter(consultation=consultation).exists()
    output = capsys.readouterr().out
    assert "Would clear" in output
    assert "Would clear 1 stale WellnessScore row(s), kept 0" in output


@pytest.mark.django_db
def test_reports_mixed_cleared_and_kept_counts(consultation, profile, capsys):
    from accounts.models import User
    from assessment.models import LifestyleProfile
    from consultations.models import Consultation

    profile.smoking_status = "none"
    profile.save()
    WellnessScore.objects.create(consultation=consultation, total=100, band="Good", breakdown=[])

    other_patient = User.objects.create_user(
        username="patient_ok", password="StrongPass123", role=User.Role.PATIENT
    )
    other_consultation = Consultation.objects.create(patient=other_patient, language="en")
    LifestyleProfile.objects.create(
        consultation=other_consultation,
        sleep_hours=8.0,
        exercise_days_per_week=5,
        exercise_minutes_per_session=40,
        diet_pattern="balanced",
        stress_level="low",
    )
    WellnessScore.objects.create(consultation=other_consultation, total=90, band="Good", breakdown=[])

    call_command("recheck_wellness_scores")

    assert not WellnessScore.objects.filter(consultation=consultation).exists()
    assert WellnessScore.objects.filter(consultation=other_consultation).exists()
    output = capsys.readouterr().out
    assert "Cleared 1 stale WellnessScore row(s), kept 1" in output
