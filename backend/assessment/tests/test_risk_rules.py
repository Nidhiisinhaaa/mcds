import pytest

from accounts.models import PatientProfile
from assessment.risk_rules import compute_bmi, evaluate


def _codes(flags):
    return {flag["code"] for flag in flags}


@pytest.mark.django_db
def test_sample_patient_expected_flags(sample_patient_profile, patient_user):
    """No height/weight recorded, so BMI-based flags can't fire directly, but
    obesity_risk still fires via its sedentary+unhealthy_diet clause."""
    flags = evaluate(sample_patient_profile, patient_user.patient_profile)
    assert _codes(flags) == {
        "poor_sleep",
        "sedentary_lifestyle",
        "high_stress",
        "unhealthy_diet",
        "low_water_intake",
        "obesity_risk",
        "hypertension_risk",
    }
    for flag in flags:
        assert flag["reason"]
        if flag["code"] in ("obesity_risk", "hypertension_risk"):
            assert "possible risk, for doctor review" in flag["reason"].lower()


@pytest.mark.django_db
def test_healthy_profile_has_no_flags(profile, patient_user):
    profile.sleep_hours = 8.0
    profile.exercise_days_per_week = 5
    profile.exercise_minutes_per_session = 40
    profile.diet_pattern = "balanced"
    profile.stress_level = "low"
    profile.smoking_status = "none"
    profile.alcohol_frequency = "none"
    profile.sitting_hours_per_day = 5.0
    profile.water_litres_per_day = 2.5
    profile.save()

    flags = evaluate(profile, patient_user.patient_profile)
    assert flags == []


@pytest.mark.django_db
class TestIndividualRules:
    def test_poor_sleep(self, profile, patient_user):
        profile.sleep_hours = 5.9
        profile.save()
        assert "poor_sleep" in _codes(evaluate(profile, patient_user.patient_profile))

        profile.sleep_hours = 6.0
        profile.save()
        assert "poor_sleep" not in _codes(evaluate(profile, patient_user.patient_profile))

    def test_sedentary_via_low_exercise(self, profile, patient_user):
        profile.exercise_days_per_week = 1
        profile.exercise_minutes_per_session = 10  # 10 min/wk < 75
        profile.save()
        assert "sedentary_lifestyle" in _codes(evaluate(profile, patient_user.patient_profile))

    def test_sedentary_via_long_sitting(self, profile, patient_user):
        profile.sitting_hours_per_day = 8.1
        profile.save()
        assert "sedentary_lifestyle" in _codes(evaluate(profile, patient_user.patient_profile))

        profile.sitting_hours_per_day = 8.0
        profile.save()
        assert "sedentary_lifestyle" not in _codes(evaluate(profile, patient_user.patient_profile))

    def test_high_stress(self, profile, patient_user):
        profile.stress_level = "moderate"
        profile.save()
        assert "high_stress" not in _codes(evaluate(profile, patient_user.patient_profile))

        profile.stress_level = "high"
        profile.save()
        assert "high_stress" in _codes(evaluate(profile, patient_user.patient_profile))

    @pytest.mark.parametrize("pattern", ["frequent_fast_food", "high_sugar", "irregular"])
    def test_unhealthy_diet(self, profile, patient_user, pattern):
        profile.diet_pattern = pattern
        profile.save()
        assert "unhealthy_diet" in _codes(evaluate(profile, patient_user.patient_profile))

    @pytest.mark.parametrize("pattern", ["balanced", "mixed"])
    def test_healthy_diet_not_flagged(self, profile, patient_user, pattern):
        profile.diet_pattern = pattern
        profile.save()
        assert "unhealthy_diet" not in _codes(evaluate(profile, patient_user.patient_profile))

    def test_low_water_intake(self, profile, patient_user):
        profile.water_litres_per_day = 1.49
        profile.save()
        assert "low_water_intake" in _codes(evaluate(profile, patient_user.patient_profile))

        profile.water_litres_per_day = 1.5
        profile.save()
        assert "low_water_intake" not in _codes(evaluate(profile, patient_user.patient_profile))

    def test_excess_water_intake(self, profile, patient_user):
        profile.water_litres_per_day = 4.0
        profile.save()
        assert "excess_water_intake" not in _codes(evaluate(profile, patient_user.patient_profile))

        profile.water_litres_per_day = 5.0
        profile.save()
        codes = _codes(evaluate(profile, patient_user.patient_profile))
        assert "excess_water_intake" in codes
        assert "low_water_intake" not in codes

    @pytest.mark.parametrize("status", ["occasional", "daily"])
    def test_tobacco_use(self, profile, patient_user, status):
        profile.smoking_status = status
        profile.save()
        assert "tobacco_use" in _codes(evaluate(profile, patient_user.patient_profile))

    def test_tobacco_not_flagged_when_none(self, profile, patient_user):
        profile.smoking_status = "none"
        profile.save()
        assert "tobacco_use" not in _codes(evaluate(profile, patient_user.patient_profile))

    @pytest.mark.parametrize("frequency", ["weekly", "daily"])
    def test_alcohol_risk(self, profile, patient_user, frequency):
        profile.alcohol_frequency = frequency
        profile.save()
        assert "alcohol_risk" in _codes(evaluate(profile, patient_user.patient_profile))

    @pytest.mark.parametrize("frequency", ["none", "occasional"])
    def test_alcohol_not_flagged(self, profile, patient_user, frequency):
        profile.alcohol_frequency = frequency
        profile.save()
        assert "alcohol_risk" not in _codes(evaluate(profile, patient_user.patient_profile))


@pytest.mark.django_db
class TestBMI:
    def test_compute_bmi(self, patient_user):
        pp = patient_user.patient_profile
        pp.height_cm = 170
        pp.weight_kg = 70
        pp.save()
        # 70 / (1.70^2) = 24.22
        assert compute_bmi(pp) == pytest.approx(24.2, abs=0.05)

    def test_bmi_none_without_height_or_weight(self, patient_user):
        pp = patient_user.patient_profile
        pp.height_cm = 170
        pp.weight_kg = None
        pp.save()
        assert compute_bmi(pp) is None

    def test_bmi_none_when_no_patient_profile(self):
        assert compute_bmi(None) is None

    def test_overweight_edge_at_23(self, profile, patient_user):
        pp = patient_user.patient_profile
        pp.height_cm = 170
        pp.weight_kg = 66.5  # BMI = 23.0 exactly
        pp.save()
        codes = _codes(evaluate(profile, pp))
        assert "overweight" in codes
        assert "obese" not in codes

    def test_just_below_overweight_not_flagged(self, profile, patient_user):
        pp = patient_user.patient_profile
        pp.height_cm = 170
        pp.weight_kg = 66.0  # BMI = 22.8
        pp.save()
        codes = _codes(evaluate(profile, pp))
        assert "overweight" not in codes
        assert "obese" not in codes

    def test_obese_edge_at_25(self, profile, patient_user):
        pp = patient_user.patient_profile
        pp.height_cm = 170
        pp.weight_kg = 72.5  # BMI = 25.09
        pp.save()
        codes = _codes(evaluate(profile, pp))
        assert "obese" in codes
        assert "overweight" not in codes  # obese takes precedence, not both

    def test_obesity_risk_from_bmi_alone(self, profile, patient_user):
        pp = patient_user.patient_profile
        pp.height_cm = 170
        pp.weight_kg = 66.5  # BMI = 23.0
        pp.save()
        # No sedentary/unhealthy diet data at all.
        assert "obesity_risk" in _codes(evaluate(profile, pp))

    def test_hypertension_risk_needs_two_factors(self, profile, patient_user):
        pp = patient_user.patient_profile
        profile.stress_level = "high"
        profile.save()
        # Only one contributing factor (high_stress) -> should not fire yet.
        assert "hypertension_risk" not in _codes(evaluate(profile, pp))

        profile.smoking_status = "daily"
        profile.save()
        # Two contributing factors (high_stress, tobacco_use) -> fires.
        assert "hypertension_risk" in _codes(evaluate(profile, pp))


@pytest.mark.django_db
def test_doctor_override_changes_flags(sample_patient_profile, patient_user):
    baseline = _codes(evaluate(sample_patient_profile, patient_user.patient_profile))
    assert "poor_sleep" in baseline

    sample_patient_profile.doctor_overrides = {"sleep_hours": 8.0}
    sample_patient_profile.save()

    overridden = _codes(evaluate(sample_patient_profile, patient_user.patient_profile))
    assert "poor_sleep" not in overridden
