"""
Shared slot definitions and status/clarification bookkeeping for the conversation
engine (extractor, questioner, orchestrator).

Per-slot engine state (extraction evidence, clarification attempts, skip state) is
stored in LifestyleProfile.evidence, keyed by slot name, since the model has no
dedicated columns for it:

    evidence[slot] = {
        "quote": str,                  # patient's own words backing the accepted value
        "confidence": float,           # extractor's confidence in the accepted value
        "assumption": str | None,      # any unit assumption made while normalising
        "needs_clarification": bool,   # set when a low-confidence/ambiguous answer was seen
        "clarification_count": int,    # how many clarifying questions have been asked
        "skipped": bool,               # clarification budget exhausted; gave up on this slot
    }
"""

SLOT_ORDER = [
    "sleep",
    "exercise",
    "diet",
    "water",
    "stress",
    "sitting",
    "smoking",
    "alcohol",
]

# All LifestyleProfile fields a slot can write to.
SLOT_FIELDS = {
    "sleep": ["sleep_hours"],
    "exercise": ["exercise_days_per_week", "exercise_minutes_per_session"],
    "diet": ["diet_pattern"],
    "water": ["water_litres_per_day"],
    "stress": ["stress_level"],
    "sitting": ["sitting_hours_per_day"],
    "smoking": ["smoking_status", "cigarettes_per_day"],
    "alcohol": ["alcohol_frequency"],
}

# The field whose presence determines whether a slot counts as "filled".
SLOT_PRIMARY_FIELD = {
    "sleep": "sleep_hours",
    "exercise": "exercise_days_per_week",
    "diet": "diet_pattern",
    "water": "water_litres_per_day",
    "stress": "stress_level",
    "sitting": "sitting_hours_per_day",
    "smoking": "smoking_status",
    "alcohol": "alcohol_frequency",
}

MAX_CLARIFICATIONS_PER_SLOT = 1


def get_meta(profile, slot) -> dict:
    return (profile.evidence or {}).get(slot, {})


def set_meta(profile, slot, **updates) -> dict:
    evidence = dict(profile.evidence or {})
    meta = dict(evidence.get(slot, {}))
    meta.update(updates)
    evidence[slot] = meta
    profile.evidence = evidence
    return meta


def is_filled(profile, slot) -> bool:
    value = getattr(profile, SLOT_PRIMARY_FIELD[slot])
    return value is not None and value != ""


def status_of(profile, slot) -> str:
    if get_meta(profile, slot).get("skipped"):
        return "skipped"
    if is_filled(profile, slot):
        return "filled"
    return "pending"


def slot_status_map(profile) -> dict:
    return {slot: status_of(profile, slot) for slot in SLOT_ORDER}


def all_resolved(profile) -> bool:
    return all(status_of(profile, slot) != "pending" for slot in SLOT_ORDER)


def finalize_clarifications(profile) -> None:
    """Mark any pending slot whose clarification budget is exhausted as skipped.

    Call once per turn, right after applying an extraction and before checking
    whether the questionnaire is fully resolved, so that check and the
    questioner's own slot search always see consistent state.
    """
    changed = False
    for slot in SLOT_ORDER:
        if status_of(profile, slot) != "pending":
            continue
        meta = get_meta(profile, slot)
        if (
            meta.get("needs_clarification")
            and meta.get("clarification_count", 0) >= MAX_CLARIFICATIONS_PER_SLOT
        ):
            set_meta(profile, slot, skipped=True)
            changed = True
    if changed:
        profile.save(update_fields=["evidence"])


def first_clarification_target(profile):
    for slot in SLOT_ORDER:
        if status_of(profile, slot) != "pending":
            continue
        meta = get_meta(profile, slot)
        if (
            meta.get("needs_clarification")
            and meta.get("clarification_count", 0) < MAX_CLARIFICATIONS_PER_SLOT
        ):
            return slot
    return None


def first_pending_target(profile):
    for slot in SLOT_ORDER:
        if status_of(profile, slot) == "pending":
            return slot
    return None
