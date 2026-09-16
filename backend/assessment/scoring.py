"""
Lifestyle Wellness Score: 8 weighted lifestyle factors, each scored 0-1 from
the patient's LifestyleProfile, combined into a 0-100 total. Deterministic
Python only - no LLM involved. See docs/scoring.md for the plain-language
writeup of everything in this file.

profile.doctor_overrides takes precedence over the extracted field values: if
a field name is a key in doctor_overrides (even mapped to None, meaning the
doctor cleared it), that value is used instead of the LLM-extracted one.
"""

WEIGHTS = {
    "sleep": 15,
    "exercise": 15,
    "diet": 15,
    "stress": 15,
    "smoking": 15,
    "alcohol": 10,
    "sitting": 10,
    "water": 5,
}
assert sum(WEIGHTS.values()) == 100

# Ordered highest threshold first; a total qualifies for the first band whose
# threshold it meets or exceeds.
BANDS = [
    (80, "Good"),
    (60, "Fair"),
    (40, "Needs attention"),
    (0, "Poor"),
]

DIET_SUB_SCORES = {
    "balanced": 1.0,
    "mixed": 0.6,
    "irregular": 0.4,
    "frequent_fast_food": 0.2,
    "high_sugar": 0.2,
}

STRESS_SUB_SCORES = {
    "low": 1.0,
    "moderate": 0.5,
    "high": 0.0,
}

SMOKING_SUB_SCORES = {
    "none": 1.0,
    "occasional": 0.3,
    "daily": 0.0,
}

ALCOHOL_SUB_SCORES = {
    "none": 1.0,
    "occasional": 0.7,
    "weekly": 0.4,
    "daily": 0.0,
}


def _sleep_sub_score(hours: float) -> float:
    if 7 <= hours <= 9:
        return 1.0
    if (6 <= hours < 7) or (9 < hours <= 10):
        return 0.6
    if 5 <= hours < 6:
        return 0.3
    return 0.0  # hours < 5 or hours > 10


def _exercise_sub_score(weekly_minutes: float) -> float:
    # Deliberately open-ended at the top, unlike water below: there's no
    # widely-accepted acute-harm threshold for "too much exercise" in general
    # lifestyle screening (WHO guidance describes diminishing returns, not
    # danger), so inventing a downturn cutoff here wouldn't be backed by
    # anything - it would just be a guess dressed up as a scoring rule.
    if weekly_minutes >= 150:
        return 1.0
    if 75 <= weekly_minutes < 150:
        return 0.6
    if 1 <= weekly_minutes < 75:
        return 0.3
    return 0.0  # weekly_minutes == 0


def _sitting_sub_score(hours: float) -> float:
    if hours < 6:
        return 1.0
    if 6 <= hours <= 8:
        return 0.6
    if 8 < hours <= 10:
        return 0.3
    return 0.0  # hours > 10


HIGH_WATER_LITRES_CUTOFF = 4.0


def _water_sub_score(litres: float) -> float:
    # Unlike exercise above, excess water intake has a real, well-known acute
    # risk (hyponatremia / water intoxication), so this band is deliberately
    # NOT left open-ended above the brief's 2-3.5L optimal range - drinking
    # more is not indefinitely "fine", let alone better.
    if litres > HIGH_WATER_LITRES_CUTOFF:
        return 0.5
    if litres >= 2:
        return 1.0
    if 1.5 <= litres < 2:
        return 0.6
    if 1 <= litres < 1.5:
        return 0.3
    return 0.0  # litres < 1


def _effective_value(profile, field_name):
    overrides = profile.doctor_overrides or {}
    if field_name in overrides:
        return overrides[field_name]
    return getattr(profile, field_name)


def _reason_for(factor, value, sub_score):
    if factor == "sleep":
        return f"Sleeps {value} hours a night (sub-score {sub_score})."
    if factor == "exercise":
        return f"About {value} minutes of exercise a week (sub-score {sub_score})."
    if factor == "diet":
        return f"Diet pattern reported as {value.replace('_', ' ')} (sub-score {sub_score})."
    if factor == "stress":
        return f"Day-to-day stress level reported as {value} (sub-score {sub_score})."
    if factor == "smoking":
        return f"Smoking status reported as {value} (sub-score {sub_score})."
    if factor == "alcohol":
        return f"Alcohol frequency reported as {value} (sub-score {sub_score})."
    if factor == "sitting":
        return f"Sits {value} hours a day (sub-score {sub_score})."
    if factor == "water":
        return f"Drinks {value} litres of water a day (sub-score {sub_score})."
    return f"{factor}: {value} (sub-score {sub_score})."


def _band_for(total: int) -> str:
    for threshold, band in BANDS:
        if total >= threshold:
            return band
    return BANDS[-1][1]


def compute_wellness_score(profile) -> dict:
    breakdown = []
    included = []  # (factor, weight, sub_score)

    sleep_hours = _effective_value(profile, "sleep_hours")
    if sleep_hours is None:
        breakdown.append(_not_reported("sleep"))
    else:
        sub_score = _sleep_sub_score(sleep_hours)
        included.append(("sleep", WEIGHTS["sleep"], sub_score, sleep_hours))

    exercise_days = _effective_value(profile, "exercise_days_per_week")
    exercise_minutes = _effective_value(profile, "exercise_minutes_per_session")
    if exercise_days is None or (exercise_days > 0 and exercise_minutes is None):
        breakdown.append(_not_reported("exercise"))
    else:
        weekly_minutes = exercise_days * (exercise_minutes or 0)
        sub_score = _exercise_sub_score(weekly_minutes)
        included.append(("exercise", WEIGHTS["exercise"], sub_score, weekly_minutes))

    diet_pattern = _effective_value(profile, "diet_pattern")
    if diet_pattern is None:
        breakdown.append(_not_reported("diet"))
    else:
        sub_score = DIET_SUB_SCORES[diet_pattern]
        included.append(("diet", WEIGHTS["diet"], sub_score, diet_pattern))

    stress_level = _effective_value(profile, "stress_level")
    if stress_level is None:
        breakdown.append(_not_reported("stress"))
    else:
        sub_score = STRESS_SUB_SCORES[stress_level]
        included.append(("stress", WEIGHTS["stress"], sub_score, stress_level))

    smoking_status = _effective_value(profile, "smoking_status")
    if smoking_status is None:
        breakdown.append(_not_reported("smoking"))
    else:
        sub_score = SMOKING_SUB_SCORES[smoking_status]
        included.append(("smoking", WEIGHTS["smoking"], sub_score, smoking_status))

    alcohol_frequency = _effective_value(profile, "alcohol_frequency")
    if alcohol_frequency is None:
        breakdown.append(_not_reported("alcohol"))
    else:
        sub_score = ALCOHOL_SUB_SCORES[alcohol_frequency]
        included.append(("alcohol", WEIGHTS["alcohol"], sub_score, alcohol_frequency))

    sitting_hours = _effective_value(profile, "sitting_hours_per_day")
    if sitting_hours is None:
        breakdown.append(_not_reported("sitting"))
    else:
        sub_score = _sitting_sub_score(sitting_hours)
        included.append(("sitting", WEIGHTS["sitting"], sub_score, sitting_hours))

    water_litres = _effective_value(profile, "water_litres_per_day")
    if water_litres is None:
        breakdown.append(_not_reported("water"))
    else:
        sub_score = _water_sub_score(water_litres)
        included.append(("water", WEIGHTS["water"], sub_score, water_litres))

    included_weight_total = sum(weight for _, weight, _, _ in included)
    rescale = 100 / included_weight_total if included_weight_total else 0

    raw_total = 0.0
    for factor, weight, sub_score, value in included:
        rescaled_weight = weight * rescale
        points = sub_score * rescaled_weight
        raw_total += points
        breakdown.append(
            {
                "factor": factor,
                "value": value,
                "sub_score": sub_score,
                "weight": round(rescaled_weight, 2),
                "points": round(points, 2),
                "reason": _reason_for(factor, value, sub_score),
            }
        )

    total = round(raw_total)
    band = _band_for(total)

    # Keep breakdown in the canonical slot order regardless of insertion order.
    order = {f: i for i, f in enumerate(WEIGHTS)}
    breakdown.sort(key=lambda item: order[item["factor"]])

    return {"total": total, "band": band, "breakdown": breakdown}


def _not_reported(factor):
    return {
        "factor": factor,
        "value": None,
        "sub_score": None,
        "weight": 0,
        "points": None,
        "reason": "not reported",
    }
