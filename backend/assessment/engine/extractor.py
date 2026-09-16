"""
Turns the patient's latest English message (plus recent conversation context and
current slot state) into structured lifestyle data via the Groq chat model, then
cross-checks any numbers against regex_numbers.py.
"""

import logging
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from assessment.engine import regex_numbers, slots
from assessment.models import LifestyleProfile
from consultations.models import Message
from core.services import groq_client

logger = logging.getLogger("assessment.engine.extractor")

RECENT_TURNS_WINDOW = 12
MIN_CONFIDENCE = 0.6

# Must mirror assessment.engine.slots.SLOT_ORDER.
SlotName = Literal[
    "sleep", "exercise", "diet", "water", "stress", "sitting", "smoking", "alcohol"
]

RED_FLAG_CODE = Literal[
    "chest_pain",
    "severe_breathlessness",
    "fainting",
    "stroke_signs",
    "blood_in_vomit_or_stool",
    "self_harm_thoughts",
    "high_fever_with_stiff_neck",
]


class SlotEvidence(BaseModel):
    quote: str = ""
    confidence: float = 0.0
    assumption: Optional[str] = None


class SymptomExtraction(BaseModel):
    name: str
    duration_text: str = ""
    severity: Literal["mild", "moderate", "severe", "unknown"] = "unknown"


class ExtractionResult(BaseModel):
    sleep_hours: Optional[float] = None
    exercise_days_per_week: Optional[int] = None
    exercise_minutes_per_session: Optional[int] = None
    smoking_status: Optional[Literal["none", "occasional", "daily"]] = None
    cigarettes_per_day: Optional[int] = None
    alcohol_frequency: Optional[Literal["none", "occasional", "weekly", "daily"]] = None
    diet_pattern: Optional[
        Literal["balanced", "mixed", "frequent_fast_food", "high_sugar", "irregular"]
    ] = None
    water_litres_per_day: Optional[float] = None
    stress_level: Optional[Literal["low", "moderate", "high"]] = None
    sitting_hours_per_day: Optional[float] = None

    evidence: Dict[str, SlotEvidence] = Field(default_factory=dict)
    symptoms: List[SymptomExtraction] = Field(default_factory=list)
    chief_complaint_english: Optional[str] = None
    red_flags: List[RED_FLAG_CODE] = Field(default_factory=list)
    needs_clarification: Optional[SlotName] = None


SYSTEM_PROMPT = """You are a clinical intake extraction assistant. You read a patient's \
message (already translated to English) plus recent conversation context, and extract ONLY \
what the patient explicitly said. Never infer or guess a value they did not state.

Use these exact choices:
- smoking_status: none | occasional | daily
- alcohol_frequency: none | occasional | weekly | daily
- diet_pattern: balanced | mixed | frequent_fast_food | high_sugar | irregular
- stress_level: low | moderate | high

Normalise ranges to their midpoint (e.g. "7-8 hours" -> 7.5). Convert glasses of water to \
litres assuming 250 ml per glass, and record that assumption in the evidence entry's \
"assumption" field. Convert phrasing like "twice a week, 30 minutes" into a day count and a \
minutes count.

For every field you fill in, add an evidence entry keyed by its slot name (sleep, exercise, \
diet, water, stress, sitting, smoking, alcohol) containing the patient's own words as "quote" \
and your confidence from 0 to 1. If an answer is ambiguous, contradictory, or you are not \
confident, do NOT fill the field — instead set needs_clarification to that slot's name.

Current known slot values (do not ask about or restate already-known slots): {slot_state}

Also extract, only when clearly present:
- symptoms: name, how long (duration_text), severity (mild/moderate/severe/unknown).
- chief_complaint_english: only if this message is the patient's first description of why \
they came in.
- red_flags: any of chest_pain, severe_breathlessness, fainting, stroke_signs, \
blood_in_vomit_or_stool, self_harm_thoughts, high_fever_with_stiff_neck that are clearly \
present.
"""

NUMERIC_CROSS_CHECK_FIELDS = {
    "sleep_hours": regex_numbers.extract_hours,
    "sitting_hours_per_day": regex_numbers.extract_hours,
    "water_litres_per_day": regex_numbers.extract_litres,
    "exercise_days_per_week": regex_numbers.extract_days_per_week,
    "exercise_minutes_per_session": regex_numbers.extract_minutes,
    "cigarettes_per_day": regex_numbers.extract_cigarettes_per_day,
}


def _recent_turns(consultation):
    recent = list(consultation.messages.order_by("-created_at")[:RECENT_TURNS_WINDOW])
    recent.reverse()
    role_by_sender = {Message.Sender.PATIENT: "user", Message.Sender.AI: "assistant"}
    return [
        {"role": role_by_sender[m.sender], "content": m.text_english or m.text_original}
        for m in recent
        if (m.text_english or m.text_original)
    ]


def _slot_state_summary(profile) -> dict:
    return {slot: getattr(profile, slots.SLOT_PRIMARY_FIELD[slot]) for slot in slots.SLOT_ORDER}


def _cross_check_numeric_fields(result: ExtractionResult, text_english: str) -> ExtractionResult:
    for field_name, regex_func in NUMERIC_CROSS_CHECK_FIELDS.items():
        llm_value = getattr(result, field_name)
        if llm_value is None:
            continue
        regex_value = regex_func(text_english)
        if regex_value is None:
            continue

        llm_float = float(llm_value)
        regex_float = float(regex_value)
        if llm_float == 0:
            continue

        diff_ratio = abs(regex_float - llm_float) / abs(llm_float)
        if diff_ratio > 0.2:
            logger.warning(
                "extractor.regex_conflict",
                extra={
                    "field": field_name,
                    "llm_value": llm_float,
                    "regex_value": regex_float,
                    "diff_ratio": round(diff_ratio, 3),
                },
            )
            cast = int if isinstance(llm_value, int) else float
            setattr(result, field_name, cast(regex_value))
    return result


def _apply_confidence_threshold(result: ExtractionResult) -> ExtractionResult:
    """Only accept a slot's value if its evidence confidence is >= MIN_CONFIDENCE;
    otherwise blank the value out and flag the slot for clarification."""
    needs_clarification = result.needs_clarification
    for slot in slots.SLOT_ORDER:
        field_names = slots.SLOT_FIELDS[slot]
        has_value = any(getattr(result, field_name) is not None for field_name in field_names)
        if not has_value:
            continue

        evidence_entry = result.evidence.get(slot)
        confidence = evidence_entry.confidence if evidence_entry else 0.0
        if confidence < MIN_CONFIDENCE:
            for field_name in field_names:
                setattr(result, field_name, None)
            if needs_clarification is None:
                needs_clarification = slot

    result.needs_clarification = needs_clarification
    return result


def extract(consultation, latest_patient_message) -> ExtractionResult:
    profile, _ = LifestyleProfile.objects.get_or_create(consultation=consultation)

    system = SYSTEM_PROMPT.format(slot_state=_slot_state_summary(profile))
    messages = _recent_turns(consultation)

    result = groq_client.chat_json(system, messages, ExtractionResult, temperature=0)
    result = _cross_check_numeric_fields(
        result, latest_patient_message.text_english or latest_patient_message.text_original or ""
    )
    result = _apply_confidence_threshold(result)
    return result
