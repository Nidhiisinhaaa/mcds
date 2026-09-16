"""
Safety-net red-flag detection: symptoms that mean the questionnaire should stop
and the patient should be told to seek in-person care now.

Triggered by either the extractor's own red_flags output, or an independent
English keyword scan of the translated text (run first, before the extractor,
so an emergency is never gated behind LLM extraction succeeding).
"""

import re

from assessment.models import RiskFlag
from consultations.models import Message
from core.services import groq_client

RED_FLAG_LABELS = {
    "chest_pain": "Chest pain",
    "severe_breathlessness": "Severe breathlessness",
    "fainting": "Fainting or loss of consciousness",
    "stroke_signs": "Possible stroke signs (face droop, one-sided weakness, slurred speech)",
    "blood_in_vomit_or_stool": "Blood in vomit or stool",
    "self_harm_thoughts": "Thoughts of self-harm",
    "high_fever_with_stiff_neck": "High fever with a stiff neck",
}

_KEYWORD_PATTERNS = {
    "chest_pain": [
        r"chest pain",
        r"pain in (?:my|the) chest",
        r"chest (?:feels?|is) tight",
        r"chest tightness",
    ],
    "severe_breathlessness": [
        r"can'?t breathe",
        r"cannot breathe",
        r"difficulty breathing",
        r"severe(?:ly)? breathless",
        r"gasping for (?:air|breath)",
        r"struggling to breathe",
    ],
    "fainting": [
        r"fainted",
        r"fainting",
        r"passed out",
        r"blacked out",
        r"lost consciousness",
    ],
    "stroke_signs": [
        r"face (?:is )?droop",
        r"one[- ]sided weakness",
        r"one side of (?:my|the) (?:face|body)",
        r"slurred speech",
        r"can'?t move one side",
        r"weakness on one side",
    ],
    "blood_in_vomit_or_stool": [
        r"blood in (?:my |the )?vomit",
        r"vomit(?:ing)? blood",
        r"blood in (?:my |the )?stool",
        r"bloody stool",
        r"black(?:ish)? stool",
    ],
    "self_harm_thoughts": [
        r"kill myself",
        r"suicidal",
        r"self[- ]harm",
        r"end my life",
        r"hurt myself on purpose",
        r"don'?t want to live",
    ],
}

KNOWN_CODES = set(RED_FLAG_LABELS)


def keyword_scan(text_english: str) -> list:
    text_l = (text_english or "").lower()
    codes = []
    for code, patterns in _KEYWORD_PATTERNS.items():
        if any(re.search(p, text_l) for p in patterns):
            codes.append(code)
    if re.search(r"stiff neck", text_l) and re.search(r"fever", text_l):
        codes.append("high_fever_with_stiff_neck")
    return codes


def filter_known_codes(codes) -> list:
    seen = []
    for code in codes or []:
        if code in KNOWN_CODES and code not in seen:
            seen.append(code)
    return seen


_ESCALATION_INSTRUCTION = (
    "The patient just described symptoms that need urgent in-person medical attention: "
    "{labels}. Write one calm, clear message (2-3 sentences) telling them these symptoms "
    "need prompt in-person medical care and that they should contact their doctor or local "
    "emergency services now. Do not diagnose, do not speculate on causes, and do not ask any "
    "further questions."
)


def trigger(consultation, codes, message):
    """Record the risk flags, escalate the consultation, stop the questionnaire, and
    return a calm AI Message telling the patient to seek care now."""
    labels = [RED_FLAG_LABELS[code] for code in codes]

    for code, label in zip(codes, labels):
        RiskFlag.objects.get_or_create(
            consultation=consultation,
            code=code,
            defaults={
                "label": label,
                "severity": RiskFlag.Severity.HIGH,
                "reason": f'Detected from patient message: "{(message.text_english or "")[:300]}"',
            },
        )

    text_english = groq_client.chat_text(
        "You are a calm, clear clinical safety assistant.",
        [{"role": "user", "content": _ESCALATION_INSTRUCTION.format(labels=", ".join(labels))}],
        temperature=0.2,
    )
    text_patient_language = groq_client.translate_text(text_english, "en", consultation.language)

    ai_message = Message.objects.create(
        consultation=consultation,
        sender=Message.Sender.AI,
        text_original=text_patient_language,
        text_english=text_english,
        language=consultation.language,
    )

    consultation.status = consultation.Status.ESCALATED
    consultation.save(update_fields=["status"])

    return ai_message
