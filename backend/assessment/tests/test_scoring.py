import pytest

from assessment.scoring import compute_wellness_score


@pytest.mark.django_db
def test_sample_patient_exact_score(sample_patient_profile):
    """Working (see docs/scoring.md for the full table):

    sleep    5h                 -> sub 0.3 * weight 15 = 4.5
    exercise 0 days -> 0 min/wk -> sub 0.0 * weight 15 = 0.0
    diet     frequent_fast_food -> sub 0.2 * weight 15 = 3.0
    stress   high               -> sub 0.0 * weight 15 = 0.0
    smoking  none               -> sub 1.0 * weight 15 = 15.0
    alcohol  occasional         -> sub 0.7 * weight 10 = 7.0
    sitting  9h                 -> sub 0.3 * weight 10 = 3.0
    water    1L                 -> sub 0.3 * weight 5  = 1.5

    total = 4.5 + 0 + 3.0 + 0 + 15.0 + 7.0 + 3.0 + 1.5 = 34.0 -> Poor (<40)
    """
    result = compute_wellness_score(sample_patient_profile)
    assert result["total"] == 34
    assert result["band"] == "Poor"
    assert len(result["breakdown"]) == 8
    assert all(item["reason"] != "not reported" for item in result["breakdown"])


@pytest.mark.django_db
def test_missing_slot_is_excluded_and_rescaled(profile):
    """All slots filled except sitting (weight 10) -> everyone else's weight
    is rescaled by 100/90, and sitting shows up as "not reported"."""
    profile.sleep_hours = 8.0  # sub 1.0, weight 15 -> 15/90*100 = 16.666...
    profile.exercise_days_per_week = 5
    profile.exercise_minutes_per_session = 40  # 200 min/wk, sub 1.0
    profile.diet_pattern = "balanced"  # sub 1.0
    profile.stress_level = "low"  # sub 1.0
    profile.smoking_status = "none"  # sub 1.0
    profile.alcohol_frequency = "none"  # sub 1.0
    profile.water_litres_per_day = 2.5  # sub 1.0
    # sitting_hours_per_day left as None (not reported)
    profile.save()

    result = compute_wellness_score(profile)

    sitting_entry = next(item for item in result["breakdown"] if item["factor"] == "sitting")
    assert sitting_entry["reason"] == "not reported"
    assert sitting_entry["weight"] == 0
    assert sitting_entry["value"] is None
    assert sitting_entry["sub_score"] is None

    # Every other sub-score is 1.0, so with rescaling the total should still
    # be 100 (rescaled weights still sum to 100, all multiplied by 1.0).
    assert result["total"] == 100
    assert result["band"] == "Good"

    included = [item for item in result["breakdown"] if item["factor"] != "sitting"]
    assert sum(item["weight"] for item in included) == pytest.approx(100, abs=0.1)


@pytest.mark.django_db
def test_all_slots_missing_gives_zero(profile):
    result = compute_wellness_score(profile)
    assert result["total"] == 0
    assert result["band"] == "Poor"
    assert all(item["reason"] == "not reported" for item in result["breakdown"])


@pytest.mark.django_db
def test_doctor_override_changes_score(sample_patient_profile):
    baseline = compute_wellness_score(sample_patient_profile)
    assert baseline["total"] == 34

    # Doctor corrects the extracted sleep value from 5h to 8h.
    sample_patient_profile.doctor_overrides = {"sleep_hours": 8.0}
    sample_patient_profile.save()

    overridden = compute_wellness_score(sample_patient_profile)
    sleep_entry = next(item for item in overridden["breakdown"] if item["factor"] == "sleep")
    assert sleep_entry["value"] == 8.0
    assert sleep_entry["sub_score"] == 1.0
    # sleep points go from 4.5 to 15.0, a +10.5 swing: 34 + 10.5 = 44.5,
    # which Python's round-half-to-even rounds down to 44.
    assert overridden["total"] == 44


@pytest.mark.django_db
class TestSleepSubScoreBands:
    @pytest.mark.parametrize(
        "hours,expected_sub_score",
        [
            (7.0, 1.0),
            (8.0, 1.0),
            (9.0, 1.0),
            (6.0, 0.6),
            (6.9, 0.6),
            (9.5, 0.6),
            (10.0, 0.6),
            (5.0, 0.3),
            (5.9, 0.3),
            (4.9, 0.0),
            (10.1, 0.0),
        ],
    )
    def test_sleep_band(self, profile, hours, expected_sub_score):
        profile.sleep_hours = hours
        profile.save()
        result = compute_wellness_score(profile)
        entry = next(item for item in result["breakdown"] if item["factor"] == "sleep")
        assert entry["sub_score"] == pytest.approx(expected_sub_score)


@pytest.mark.django_db
class TestExerciseSubScoreBands:
    @pytest.mark.parametrize(
        "days,minutes,expected_sub_score",
        [
            (5, 30, 1.0),  # 150 min/wk
            (7, 30, 1.0),  # 210 min/wk
            (3, 25, 0.6),  # 75 min/wk
            (2, 38, 0.6),  # 76 min/wk
            (2, 37, 0.3),  # 74 min/wk - just below the 75 cutoff
            (1, 30, 0.3),  # 30 min/wk
            (0, None, 0.0),
        ],
    )
    def test_exercise_band(self, profile, days, minutes, expected_sub_score):
        profile.exercise_days_per_week = days
        profile.exercise_minutes_per_session = minutes
        profile.save()
        result = compute_wellness_score(profile)
        entry = next(item for item in result["breakdown"] if item["factor"] == "exercise")
        assert entry["sub_score"] == pytest.approx(expected_sub_score)

    def test_exercise_missing_minutes_when_days_positive_is_not_reported(self, profile):
        profile.exercise_days_per_week = 3
        profile.exercise_minutes_per_session = None
        profile.save()
        result = compute_wellness_score(profile)
        entry = next(item for item in result["breakdown"] if item["factor"] == "exercise")
        assert entry["reason"] == "not reported"


@pytest.mark.django_db
class TestSittingSubScoreBands:
    @pytest.mark.parametrize(
        "hours,expected_sub_score",
        [
            (5.9, 1.0),
            (6.0, 0.6),
            (8.0, 0.6),
            (8.1, 0.3),
            (10.0, 0.3),
            (10.1, 0.0),
        ],
    )
    def test_sitting_band(self, profile, hours, expected_sub_score):
        profile.sitting_hours_per_day = hours
        profile.save()
        result = compute_wellness_score(profile)
        entry = next(item for item in result["breakdown"] if item["factor"] == "sitting")
        assert entry["sub_score"] == pytest.approx(expected_sub_score)


@pytest.mark.django_db
class TestWaterSubScoreBands:
    @pytest.mark.parametrize(
        "litres,expected_sub_score",
        [
            (2.0, 1.0),
            (3.5, 1.0),
            (4.0, 1.0),  # at the excess cutoff, not yet over it
            (4.1, 0.5),  # just over - reduced, not left open-ended and "Good"
            (10.0, 0.5),
            (1.5, 0.6),
            (1.9, 0.6),
            (1.0, 0.3),
            (1.4, 0.3),
            (0.9, 0.0),
        ],
    )
    def test_water_band(self, profile, litres, expected_sub_score):
        profile.water_litres_per_day = litres
        profile.save()
        result = compute_wellness_score(profile)
        entry = next(item for item in result["breakdown"] if item["factor"] == "water")
        assert entry["sub_score"] == pytest.approx(expected_sub_score)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field,value,expected_sub_score",
    [
        ("diet_pattern", "balanced", 1.0),
        ("diet_pattern", "mixed", 0.6),
        ("diet_pattern", "irregular", 0.4),
        ("diet_pattern", "frequent_fast_food", 0.2),
        ("diet_pattern", "high_sugar", 0.2),
        ("stress_level", "low", 1.0),
        ("stress_level", "moderate", 0.5),
        ("stress_level", "high", 0.0),
        ("smoking_status", "none", 1.0),
        ("smoking_status", "occasional", 0.3),
        ("smoking_status", "daily", 0.0),
        ("alcohol_frequency", "none", 1.0),
        ("alcohol_frequency", "occasional", 0.7),
        ("alcohol_frequency", "weekly", 0.4),
        ("alcohol_frequency", "daily", 0.0),
    ],
)
def test_categorical_sub_scores(profile, field, value, expected_sub_score):
    setattr(profile, field, value)
    profile.save()
    result = compute_wellness_score(profile)
    factor = {
        "diet_pattern": "diet",
        "stress_level": "stress",
        "smoking_status": "smoking",
        "alcohol_frequency": "alcohol",
    }[field]
    entry = next(item for item in result["breakdown"] if item["factor"] == factor)
    assert entry["sub_score"] == pytest.approx(expected_sub_score)
