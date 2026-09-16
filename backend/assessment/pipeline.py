"""
Post-conversation analysis: NER -> wellness score -> risk flags ->
recommendations. Deterministic except for the NER step's model inference and
the recommender's LLM call (no LLM is involved in scoring or risk rules).

Idempotent: every derived row this pipeline owns (scispaCy-sourced Symptoms,
the WellnessScore, risk_rules-sourced RiskFlags, Recommendations) is deleted
and regenerated on each run, so calling it again (e.g. via the reanalyse
endpoint, or after a doctor edits LifestyleProfile.doctor_overrides) always
reflects current state.

Red-flag RiskFlags (created directly by assessment.engine.red_flags when the
conversation escalates) are deliberately left alone here - this pipeline only
owns the risk_rules-derived flags, so a reanalyse call on an escalated
consultation can't erase the record of why it was escalated.
"""

import logging

from django.db import transaction

from assessment import nlp, recommender, risk_rules, scoring
from assessment.models import LifestyleProfile, Recommendation, RiskFlag, Symptom, WellnessScore

logger = logging.getLogger("assessment.pipeline")

# Below this many filled slots (out of 8), a WellnessScore is not produced at
# all rather than rescaling a handful of answers up to fill the whole 0-100
# scale - e.g. two favourable answers alone can rescale to 100/100 "Good",
# which is a mathematically-correct but clinically misleading number for a
# consultation that's mostly unanswered.
MIN_FILLED_SLOTS = 4


def _rescore(consultation, profile):
    """Deterministic score + risk-flag recomputation - no LLM, no NLP. Shared
    by the full pipeline and the doctor's lifestyle-override endpoint, which
    only needs this part re-run (not a fresh NER pass or new recommendations)."""
    result = scoring.compute_wellness_score(profile)
    filled_slots = sum(1 for row in result["breakdown"] if row["sub_score"] is not None)

    if filled_slots < MIN_FILLED_SLOTS:
        WellnessScore.objects.filter(consultation=consultation).delete()
        logger.info(
            "pipeline.score_withheld_insufficient_data",
            extra={"consultation_id": consultation.id, "filled_slots": filled_slots},
        )
    else:
        WellnessScore.objects.update_or_create(
            consultation=consultation,
            defaults={
                "total": result["total"],
                "band": result["band"],
                "breakdown": result["breakdown"],
            },
        )

    RiskFlag.objects.filter(consultation=consultation, code__in=risk_rules.RISK_LABELS).delete()
    patient_profile = getattr(consultation.patient, "patient_profile", None)
    for flag in risk_rules.evaluate(profile, patient_profile):
        RiskFlag.objects.create(consultation=consultation, **flag)


def rescore_only(consultation):
    """Recompute just the score and risk flags from the current
    LifestyleProfile (doctor_overrides included) - used after a doctor edits
    overrides. Deliberately does not touch Symptoms or Recommendations."""
    with transaction.atomic():
        profile, _ = LifestyleProfile.objects.get_or_create(consultation=consultation)
        _rescore(consultation, profile)
    logger.info("pipeline.rescore_only_complete", extra={"consultation_id": consultation.id})


def run_analysis(consultation):
    with transaction.atomic():
        profile, _ = LifestyleProfile.objects.get_or_create(consultation=consultation)

        consultation.symptoms.filter(source=Symptom.Source.SCISPACY).delete()
        nlp.sync_symptoms_from_messages(consultation)

        _rescore(consultation, profile)

        Recommendation.objects.filter(consultation=consultation).delete()
        try:
            recommender.generate_recommendations(consultation)
        except Exception:
            logger.exception(
                "pipeline.recommendations_failed", extra={"consultation_id": consultation.id}
            )

    logger.info("pipeline.run_analysis_complete", extra={"consultation_id": consultation.id})
