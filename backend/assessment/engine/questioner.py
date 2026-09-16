"""
Picks the next slot to ask about and generates one short, warm question for it in
the patient's language.
"""

from assessment.engine import slots
from consultations.models import Message
from core.services import groq_client

SLOT_INTENTS = {
    "sleep": "how many hours they usually sleep per night",
    "exercise": "how many days a week they exercise and for roughly how long each time",
    "diet": (
        "what their typical diet is like - for example balanced, mixed, frequent fast "
        "food, high sugar, or irregular meals"
    ),
    "water": "roughly how much water they drink in a day",
    "stress": "how they would describe their day-to-day stress level (low, moderate, or high)",
    "sitting": "roughly how many hours a day they spend sitting",
    "smoking": "whether they smoke, and if so how often",
    "alcohol": "how often they drink alcohol",
}

_SYSTEM_PROMPT = (
    "You are a warm, non-judgemental clinical intake assistant collecting a lifestyle "
    "history before a doctor's review. Ask ONE short question in English, about ONLY the "
    "topic given below. Never give medical advice, reassurance, opinions, or a diagnosis. "
    "Keep it to one or two short sentences and never ask about more than one topic."
)


def _build_instruction(slot, is_clarification, is_first_ai_turn):
    parts = [f"Ask the patient {SLOT_INTENTS[slot]}."]
    if is_clarification:
        parts.append(
            "Their previous answer on this topic was unclear or incomplete, so briefly and "
            "kindly ask again, a little more specifically."
        )
    if is_first_ai_turn:
        parts.append(
            "This is your first reply after they described their main symptom: start with "
            "one brief, warm sentence acknowledging it and noting that a few lifestyle "
            "questions will help the doctor, then ask the question."
        )
    return " ".join(parts)


def _is_first_ai_turn(consultation) -> bool:
    return not consultation.messages.filter(sender=Message.Sender.AI).exists()


def next_question(consultation):
    from assessment.models import LifestyleProfile

    profile, _ = LifestyleProfile.objects.get_or_create(consultation=consultation)

    target_slot = slots.first_clarification_target(profile)
    is_clarification = target_slot is not None
    if target_slot is None:
        target_slot = slots.first_pending_target(profile)

    if target_slot is None:
        return None

    if is_clarification:
        meta = slots.get_meta(profile, target_slot)
        slots.set_meta(
            profile, target_slot, clarification_count=meta.get("clarification_count", 0) + 1
        )
        profile.save(update_fields=["evidence"])

    is_first_ai_turn = _is_first_ai_turn(consultation)
    instruction = _build_instruction(target_slot, is_clarification, is_first_ai_turn)

    text_english = groq_client.chat_text(
        _SYSTEM_PROMPT, [{"role": "user", "content": instruction}], temperature=0.4
    )
    text_patient_language = groq_client.translate_text(text_english, "en", consultation.language)

    return {
        "text_patient_language": text_patient_language,
        "text_english": text_english,
        "slot_target": target_slot,
    }
