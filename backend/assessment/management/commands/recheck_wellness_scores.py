"""
One-off cleanup for scores computed before assessment.pipeline.MIN_FILLED_SLOTS
existed: a consultation with only a couple of filled slots used to rescale
those few answers up to fill the whole 0-100 scale (e.g. a near-empty "Hi" /
"Bye" conversation scoring 81-100 "Good"). New consultations are already
protected (see assessment.pipeline._rescore), but any WellnessScore row
written before that fix is still sitting in the DB and still shows up in the
doctor queue. This re-evaluates every existing WellnessScore against the
current rule and deletes the ones that no longer qualify - deliberately
leaves RiskFlags/Recommendations/everything else alone, this only touches
WellnessScore.
"""

import logging

from django.core.management.base import BaseCommand

from assessment import pipeline, scoring
from assessment.models import WellnessScore

logger = logging.getLogger("assessment.recheck_wellness_scores")


class Command(BaseCommand):
    help = (
        "Re-evaluates every existing WellnessScore against the current "
        "MIN_FILLED_SLOTS rule and deletes the ones that no longer qualify."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be cleared without deleting anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        cleared = 0
        kept = 0

        scores = WellnessScore.objects.select_related(
            "consultation", "consultation__lifestyle_profile"
        ).order_by("consultation_id")

        for score in scores:
            consultation = score.consultation
            profile = getattr(consultation, "lifestyle_profile", None)
            if profile is None:
                filled_slots = 0
            else:
                result = scoring.compute_wellness_score(profile)
                filled_slots = sum(1 for row in result["breakdown"] if row["sub_score"] is not None)

            if filled_slots < pipeline.MIN_FILLED_SLOTS:
                verb = "Would clear" if dry_run else "Clearing"
                self.stdout.write(
                    f"{verb} consultation #{consultation.id}: {score.total} {score.band} "
                    f"was computed from only {filled_slots} filled slot(s)."
                )
                if not dry_run:
                    logger.info(
                        "recheck_wellness_scores.cleared",
                        extra={
                            "consultation_id": consultation.id,
                            "total": score.total,
                            "band": score.band,
                            "filled_slots": filled_slots,
                        },
                    )
                    score.delete()
                cleared += 1
            else:
                kept += 1

        summary = (
            f"{'Would clear' if dry_run else 'Cleared'} {cleared} stale WellnessScore row(s), "
            f"kept {kept} that still meet the {pipeline.MIN_FILLED_SLOTS}-slot minimum."
        )
        self.stdout.write(self.style.SUCCESS(summary))
