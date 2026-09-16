import pytest
from django.utils import timezone

from accounts.models import PatientProfile, User
from assessment.models import LifestyleProfile
from consultations.models import Consultation


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
def doctor_user(db):
    return User.objects.create_user(
        username="dr_house", password="StrongPass123", role=User.Role.DOCTOR
    )


@pytest.fixture
def consultation(db, patient_user):
    return Consultation.objects.create(patient=patient_user, language="en")


@pytest.fixture
def profile(db, consultation):
    return LifestyleProfile.objects.create(consultation=consultation)


@pytest.fixture
def sample_patient_profile(profile):
    """The Phase 3 sample patient: fatigue for 2 weeks, mild headaches, no
    fever; sleeps 5 hours; no exercise; frequent fast food; 1 litre of water a
    day; high stress; does not smoke; drinks occasionally; sits ~9 hours."""
    profile.sleep_hours = 5.0
    profile.exercise_days_per_week = 0
    profile.exercise_minutes_per_session = None
    profile.diet_pattern = "frequent_fast_food"
    profile.water_litres_per_day = 1.0
    profile.stress_level = "high"
    profile.sitting_hours_per_day = 9.0
    profile.smoking_status = "none"
    profile.alcohol_frequency = "occasional"
    profile.save()
    return profile
