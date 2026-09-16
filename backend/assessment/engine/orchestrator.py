"""
Drives one turn of the lifestyle assessment conversation. Conversation state
lives entirely in the database (LifestyleProfile fields + evidence, Consultation
status/turn_count) - never in the LLM.
"""

import logging

from django.db import transaction
from django.utils import timezone

from assessment import pipeline
from assessment.engine import extractor, questioner, red_flags, slots
from assessment.models import LifestyleProfile, Symptom
from consultations.models import Message
from core.services import groq_client

logger = logging.getLogger("assessment.engine.orchestrator")

TURN_CAP = 16

_CLOSING_INSTRUCTION = (
    "Write a short, warm closing message in exactly two short sentences: thank the patient "
    "for answering the lifestyle questions, and tell them their answers and a wellness "
    "summary are now ready for their doctor to review. Do not mention any upcoming visit, "
    "appointment, or seeing them in person - the consultation is happening right now. Do not "
    "give any medical advice, reassurance, or diagnosis."
)


def handle_patient_message(consultation, message) -> Message:
    """Process one patient message and return the resulting AI Message."""
    with transaction.atomic():
        keyword_codes = red_flags.keyword_scan(message.text_english or message.text_original)
        if keyword_codes:
            return red_flags.trigger(consultation, keyword_codes, message)

        extraction = extractor.extract(consultation, message)

        extraction_codes = red_flags.filter_known_codes(extraction.red_flags)
        if extraction_codes:
            return red_flags.trigger(consultation, extraction_codes, message)

        profile = _apply_extraction(consultation, extraction, message)
        slots.finalize_clarifications(profile)

        if slots.all_resolved(profile) or consultation.turn_count >= TURN_CAP:
            return _close_consultation(consultation)

        return _ask_next_question(consultation)


def get_slot_status(consultation) -> dict:
    profile, _ = LifestyleProfile.objects.get_or_create(consultation=consultation)
    return slots.slot_status_map(profile)


def _is_first_patient_turn(consultation, message) -> bool:
    return not consultation.messages.filter(
        sender=Message.Sender.PATIENT, created_at__lt=message.created_at
    ).exists()


def _apply_extraction(consultation, extraction, message):
    profile, _ = LifestyleProfile.objects.get_or_create(consultation=consultation)

    if _is_first_patient_turn(consultation, message):
        chief_complaint_english = extraction.chief_complaint_english or message.text_english
        consultation.chief_complaint_original = message.text_original
        consultation.chief_complaint_english = chief_complaint_english
        consultation.save(update_fields=["chief_complaint_original", "chief_complaint_english"])

    for slot in slots.SLOT_ORDER:
        field_names = slots.SLOT_FIELDS[slot]
        has_any_value = any(getattr(extraction, field_name) is not None for field_name in field_names)

        if has_any_value:
            for field_name in field_names:
                value = getattr(extraction, field_name)
                if value is not None:
                    setattr(profile, field_name, value)
            evidence_entry = extraction.evidence.get(slot)
            slots.set_meta(
                profile,
                slot,
                quote=evidence_entry.quote if evidence_entry else "",
                confidence=evidence_entry.confidence if evidence_entry else 1.0,
                assumption=evidence_entry.assumption if evidence_entry else None,
                needs_clarification=False,
            )
        elif extraction.needs_clarification == slot:
            slots.set_meta(profile, slot, needs_clarification=True)

    profile.save()

    for symptom in extraction.symptoms:
        Symptom.objects.create(
            consultation=consultation,
            name=symptom.name,
            duration_text=symptom.duration_text,
            severity=symptom.severity,
            source=Symptom.Source.LLM,
        )

    return profile


def _ask_next_question(consultation) -> Message:
    question = questioner.next_question(consultation)
    if question is None:
        # Nothing left to ask despite not being fully resolved (shouldn't normally
        # happen) - close out rather than leave the patient without a reply.
        return _close_consultation(consultation)

    return Message.objects.create(
        consultation=consultation,
        sender=Message.Sender.AI,
        text_original=question["text_patient_language"],
        text_english=question["text_english"],
        language=consultation.language,
        slot_target=question["slot_target"],
    )


def _close_consultation(consultation) -> Message:
    text_english = groq_client.chat_text(
        "You are a warm, non-judgemental clinical intake assistant.",
        [{"role": "user", "content": _CLOSING_INSTRUCTION}],
        temperature=0.4,
    )
    text_patient_language = groq_client.translate_text(text_english, "en", consultation.language)

    ai_message = Message.objects.create(
        consultation=consultation,
        sender=Message.Sender.AI,
        text_original=text_patient_language,
        text_english=text_english,
        language=consultation.language,
    )

    consultation.status = consultation.Status.COMPLETED
    consultation.completed_at = timezone.now()
    consultation.save(update_fields=["status", "completed_at"])

    pipeline.run_analysis(consultation)

    return ai_message
