"""
Builds the clinical summary PDF for a consultation. WeasyPrint itself is
imported lazily inside render_consultation_pdf() - it needs native libraries
(Pango/cairo/gobject) that aren't installed everywhere (notably this
project's Windows dev environment), so importing it at module load time
would break Django startup wherever those aren't present. See the README for
the apt packages needed on the Ubuntu deploy target.
"""

from pathlib import Path

from django.template.loader import render_to_string
from django.utils import timezone

from assessment import risk_rules
from assessment.engine import slots as slots_engine
from consultations.models import Consultation

FONTS_DIR = Path(__file__).resolve().parent / "static" / "fonts"

FACTOR_LABELS = {
    "sleep": "Sleep",
    "exercise": "Exercise",
    "diet": "Diet",
    "water": "Water",
    "stress": "Stress",
    "sitting": "Sitting",
    "smoking": "Smoking",
    "alcohol": "Alcohol",
}

FACTOR_UNITS = {
    "sleep": "hrs/day",
    "exercise": "min/week",
    "water": "L/day",
    "sitting": "hrs/day",
}


def _sub_score_label(factor, value, sub_score):
    if sub_score is None:
        return "Not reported"
    if factor == "water" and value is not None and value > risk_rules.HIGH_WATER_LITRES_CUTOFF:
        return "Above recommended - for doctor review"
    if sub_score >= 0.8:
        return "Good"
    if sub_score >= 0.6:
        return "Fair"
    if sub_score >= 0.4:
        return "Needs attention"
    return "Poor"


def _format_value(factor, value):
    if value is None:
        return "Not reported"
    unit = FACTOR_UNITS.get(factor)
    if unit:
        return f"{value} {unit}"
    return str(value).replace("_", " ").title()


def _lifestyle_rows(wellness_score):
    if not wellness_score or not wellness_score.breakdown:
        return []
    rows = []
    for item in wellness_score.breakdown:
        factor = item.get("factor")
        rows.append(
            {
                "label": FACTOR_LABELS.get(factor, str(factor).title()),
                "value": _format_value(factor, item.get("value")),
                "assessment": _sub_score_label(factor, item.get("value"), item.get("sub_score")),
                "weight": item.get("weight"),
                "points": item.get("points"),
            }
        )
    return rows


def _unanswered_slot_labels(consultation):
    profile = getattr(consultation, "lifestyle_profile", None)
    if not profile:
        return [FACTOR_LABELS[slot] for slot in slots_engine.SLOT_ORDER]
    status_map = slots_engine.slot_status_map(profile)
    return [
        FACTOR_LABELS[slot]
        for slot in slots_engine.SLOT_ORDER
        if status_map.get(slot) != "filled"
    ]


def build_report_context(consultation):
    patient = consultation.patient
    patient_profile = getattr(patient, "patient_profile", None)
    bmi = risk_rules.compute_bmi(patient_profile) if patient_profile else None

    wellness_score = getattr(consultation, "wellness_score", None)
    is_complete = consultation.status in (
        Consultation.Status.COMPLETED,
        Consultation.Status.REVIEWED,
    )
    is_escalated = consultation.status == Consultation.Status.ESCALATED

    return {
        "consultation": consultation,
        "patient": patient,
        "patient_profile": patient_profile,
        "bmi": bmi,
        "lifestyle_rows": _lifestyle_rows(wellness_score),
        "symptoms": list(consultation.symptoms.all()),
        "wellness_score": wellness_score,
        # Only meaningful once the assessment stopped without ever computing a
        # score at all (vs. genuinely not having filled 4+ slots) - see
        # assessment.pipeline.MIN_FILLED_SLOTS.
        "score_withheld_insufficient_data": is_complete and wellness_score is None,
        "risk_flags": list(consultation.risk_flags.all()),
        "recommendations": list(consultation.recommendations.order_by("order")),
        "is_complete": is_complete,
        "is_escalated": is_escalated,
        "unanswered_slots": _unanswered_slot_labels(consultation) if not is_complete else [],
        "doctor_notes": list(consultation.doctor_notes.select_related("doctor").all()),
        "generated_at": timezone.now(),
        "fonts_dir_uri": FONTS_DIR.resolve().as_uri(),
    }


def render_consultation_pdf(consultation) -> bytes:
    from weasyprint import HTML  # lazy - see module docstring

    context = build_report_context(consultation)
    html_string = render_to_string("reports/consultation_report.html", context)
    return HTML(string=html_string).write_pdf()
