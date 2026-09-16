"""
Deterministic lifestyle risk-flag rules, evaluated from a LifestyleProfile
(plus the patient's height/weight for BMI). No LLM involved. See
docs/scoring.md for the plain-language writeup. Composite flags are always
phrased as "possible risk, for doctor review" - never a diagnosis.

profile.doctor_overrides takes precedence over extracted values, same as in
scoring.py.
"""

from assessment import scoring

# Asian-Indian BMI cutoffs (lower than the WHO global cutoffs of 25/30),
# configurable here.
BMI_OVERWEIGHT_CUTOFF = 23.0
BMI_OBESE_CUTOFF = 25.0

SEDENTARY_WEEKLY_EXERCISE_MINUTES_CUTOFF = 75
SEDENTARY_SITTING_HOURS_CUTOFF = 8
POOR_SLEEP_HOURS_CUTOFF = 6
LOW_WATER_LITRES_CUTOFF = 1.5
# Shared with scoring.py's excess-water sub-score band, so the "unusually
# high" flag and the reduced score fire together, not at different levels.
HIGH_WATER_LITRES_CUTOFF = scoring.HIGH_WATER_LITRES_CUTOFF
UNHEALTHY_DIET_PATTERNS = {"frequent_fast_food", "high_sugar", "irregular"}
TOBACCO_STATUSES = {"occasional", "daily"}
ALCOHOL_RISK_FREQUENCIES = {"weekly", "daily"}
HYPERTENSION_RISK_FACTOR_COUNT = 2

RISK_LABELS = {
    "poor_sleep": "Poor sleep",
    "sedentary_lifestyle": "Sedentary lifestyle",
    "high_stress": "High stress",
    "unhealthy_diet": "Unhealthy diet",
    "low_water_intake": "Low water intake",
    "excess_water_intake": "Unusually high water intake",
    "tobacco_use": "Tobacco use",
    "alcohol_risk": "Alcohol risk",
    "overweight": "Overweight (BMI)",
    "obese": "Obese (BMI)",
    "obesity_risk": "Possible obesity risk",
    "hypertension_risk": "Possible hypertension risk",
}


def _flag(code, severity, reason):
    return {"code": code, "label": RISK_LABELS[code], "severity": severity, "reason": reason}


def _effective_value(profile, field_name):
    overrides = profile.doctor_overrides or {}
    if field_name in overrides:
        return overrides[field_name]
    return getattr(profile, field_name)


def compute_bmi(patient_profile):
    """Returns BMI rounded to 1 decimal, or None if height/weight are unavailable."""
    if not patient_profile:
        return None
    height_cm = patient_profile.height_cm
    weight_kg = patient_profile.weight_kg
    if not height_cm or not weight_kg or height_cm <= 0:
        return None
    height_m = height_cm / 100
    return round(weight_kg / (height_m**2), 1)


def evaluate(profile, patient_profile) -> list:
    flags = []

    sleep_hours = _effective_value(profile, "sleep_hours")
    exercise_days = _effective_value(profile, "exercise_days_per_week")
    exercise_minutes = _effective_value(profile, "exercise_minutes_per_session")
    diet_pattern = _effective_value(profile, "diet_pattern")
    stress_level = _effective_value(profile, "stress_level")
    smoking_status = _effective_value(profile, "smoking_status")
    alcohol_frequency = _effective_value(profile, "alcohol_frequency")
    sitting_hours = _effective_value(profile, "sitting_hours_per_day")
    water_litres = _effective_value(profile, "water_litres_per_day")

    weekly_exercise_minutes = None
    if exercise_days is not None:
        weekly_exercise_minutes = exercise_days * (exercise_minutes or 0)

    # --- individual rules -------------------------------------------------

    poor_sleep = sleep_hours is not None and sleep_hours < POOR_SLEEP_HOURS_CUTOFF
    if poor_sleep:
        flags.append(
            _flag(
                "poor_sleep",
                "medium",
                f"Reports {sleep_hours} hours of sleep a night, below the "
                f"recommended minimum of {POOR_SLEEP_HOURS_CUTOFF} hours.",
            )
        )

    low_exercise = (
        weekly_exercise_minutes is not None
        and weekly_exercise_minutes < SEDENTARY_WEEKLY_EXERCISE_MINUTES_CUTOFF
    )
    long_sitting = sitting_hours is not None and sitting_hours > SEDENTARY_SITTING_HOURS_CUTOFF
    sedentary_lifestyle = low_exercise or long_sitting
    if sedentary_lifestyle:
        parts = []
        if low_exercise:
            parts.append(f"only {weekly_exercise_minutes} minutes of exercise a week")
        if long_sitting:
            parts.append(f"sitting {sitting_hours} hours a day")
        flags.append(
            _flag("sedentary_lifestyle", "medium", "Reports " + " and ".join(parts) + ".")
        )

    high_stress = stress_level == "high"
    if high_stress:
        flags.append(
            _flag("high_stress", "medium", "Reports a high day-to-day stress level.")
        )

    unhealthy_diet = diet_pattern in UNHEALTHY_DIET_PATTERNS
    if unhealthy_diet:
        flags.append(
            _flag(
                "unhealthy_diet",
                "medium",
                f"Reports a {diet_pattern.replace('_', ' ')} diet pattern.",
            )
        )

    low_water = water_litres is not None and water_litres < LOW_WATER_LITRES_CUTOFF
    if low_water:
        flags.append(
            _flag(
                "low_water_intake",
                "low",
                f"Reports drinking {water_litres} litres of water a day, below the "
                f"recommended {LOW_WATER_LITRES_CUTOFF} litres.",
            )
        )

    excess_water = water_litres is not None and water_litres > HIGH_WATER_LITRES_CUTOFF
    if excess_water:
        flags.append(
            _flag(
                "excess_water_intake",
                "low",
                f"Reports drinking {water_litres} litres of water a day, above the "
                f"{HIGH_WATER_LITRES_CUTOFF} litre level where excess intake becomes a "
                "possible risk (e.g. hyponatremia) - for doctor review.",
            )
        )

    tobacco_use = smoking_status in TOBACCO_STATUSES
    if tobacco_use:
        flags.append(
            _flag("tobacco_use", "high", f"Reports {smoking_status} smoking.")
        )

    alcohol_risk = alcohol_frequency in ALCOHOL_RISK_FREQUENCIES
    if alcohol_risk:
        flags.append(
            _flag(
                "alcohol_risk", "medium", f"Reports {alcohol_frequency} alcohol consumption."
            )
        )

    bmi = compute_bmi(patient_profile)
    bmi_overweight = bmi is not None and bmi >= BMI_OVERWEIGHT_CUTOFF
    bmi_obese = bmi is not None and bmi >= BMI_OBESE_CUTOFF
    if bmi_obese:
        flags.append(
            _flag(
                "obese",
                "medium",
                f"BMI of {bmi} is at or above the Asian-Indian obese cutoff of "
                f"{BMI_OBESE_CUTOFF}.",
            )
        )
    elif bmi_overweight:
        flags.append(
            _flag(
                "overweight",
                "low",
                f"BMI of {bmi} is at or above the Asian-Indian overweight cutoff of "
                f"{BMI_OVERWEIGHT_CUTOFF}.",
            )
        )

    # --- composite rules (always "possible risk, for doctor review") ------

    if bmi_overweight or (sedentary_lifestyle and unhealthy_diet):
        reasons = []
        if bmi_overweight:
            reasons.append(f"a BMI of {bmi}")
        if sedentary_lifestyle and unhealthy_diet:
            reasons.append("a sedentary lifestyle combined with an unhealthy diet")
        flags.append(
            _flag(
                "obesity_risk",
                "medium",
                "Possible risk, for doctor review: " + " and ".join(reasons) + ".",
            )
        )

    hypertension_contributors = {
        "high stress": high_stress,
        "a sedentary lifestyle": sedentary_lifestyle,
        "an unhealthy diet": unhealthy_diet,
        "tobacco use": tobacco_use,
        "alcohol use": alcohol_risk,
        f"a BMI at or above {BMI_OBESE_CUTOFF}": bmi_obese,
    }
    present = [label for label, is_present in hypertension_contributors.items() if is_present]
    if len(present) >= HYPERTENSION_RISK_FACTOR_COUNT:
        flags.append(
            _flag(
                "hypertension_risk",
                "high",
                "Possible risk, for doctor review, based on " + ", ".join(present) + ".",
            )
        )

    return flags
