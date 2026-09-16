"""
Doctor-facing views, mounted under /api/doctor/.

Single-clinic demo: any authenticated doctor can see and act on every
patient's consultations - there is no per-doctor assignment or clinic
scoping. A real multi-clinic deployment would need to filter these
querysets to the requesting doctor's own clinic/patient panel.
"""

import logging

from django.db.models import Case, Count, IntegerField, Q, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsDoctor
from assessment import pipeline
from assessment.models import LifestyleProfile
from consultations.doctor_serializers import (
    DoctorConsultationDetailSerializer,
    DoctorConsultationListSerializer,
    DoctorNoteSerializer,
)
from consultations.models import Consultation

logger = logging.getLogger("consultations.doctor_views")

_QUEUE_PRIORITY = Case(
    When(status=Consultation.Status.ESCALATED, then=0),
    When(status=Consultation.Status.COMPLETED, then=1),
    When(status=Consultation.Status.IN_PROGRESS, then=2),
    When(status=Consultation.Status.REVIEWED, then=3),
    default=4,
    output_field=IntegerField(),
)

ALLOWED_OVERRIDE_FIELDS = {
    "sleep_hours",
    "exercise_days_per_week",
    "exercise_minutes_per_session",
    "smoking_status",
    "cigarettes_per_day",
    "alcohol_frequency",
    "diet_pattern",
    "water_litres_per_day",
    "stress_level",
    "sitting_hours_per_day",
}


class DoctorConsultationListView(generics.ListAPIView):
    permission_classes = [IsDoctor]
    serializer_class = DoctorConsultationListSerializer

    def get_queryset(self):
        qs = (
            Consultation.objects.select_related("patient__patient_profile", "wellness_score")
            .annotate(flag_count=Count("risk_flags", distinct=True))
            .annotate(priority=_QUEUE_PRIORITY)
        )

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        query = self.request.query_params.get("q")
        if query:
            qs = qs.filter(
                Q(patient__patient_profile__full_name__icontains=query)
                | Q(patient__username__icontains=query)
                | Q(chief_complaint_english__icontains=query)
            )

        return qs.order_by("priority", "-started_at")


class DoctorConsultationDetailView(generics.RetrieveAPIView):
    permission_classes = [IsDoctor]
    serializer_class = DoctorConsultationDetailSerializer
    queryset = Consultation.objects.all()


class DoctorLifestyleOverrideView(APIView):
    permission_classes = [IsDoctor]

    def patch(self, request, pk):
        consultation = get_object_or_404(Consultation, pk=pk)

        overrides = request.data.get("doctor_overrides")
        if not isinstance(overrides, dict) or not overrides:
            raise ValidationError(
                {"doctor_overrides": "Required: an object of field name -> overridden value."}
            )
        unknown_fields = set(overrides) - ALLOWED_OVERRIDE_FIELDS
        if unknown_fields:
            raise ValidationError(
                {"doctor_overrides": f"Unknown field(s): {', '.join(sorted(unknown_fields))}."}
            )

        profile, _ = LifestyleProfile.objects.get_or_create(consultation=consultation)
        merged = dict(profile.doctor_overrides or {})
        merged.update(overrides)
        profile.doctor_overrides = merged
        profile.save(update_fields=["doctor_overrides"])

        pipeline.rescore_only(consultation)

        consultation.refresh_from_db()
        return Response(
            DoctorConsultationDetailSerializer(consultation, context={"request": request}).data
        )


class DoctorNoteCreateView(generics.CreateAPIView):
    permission_classes = [IsDoctor]
    serializer_class = DoctorNoteSerializer

    def perform_create(self, serializer):
        consultation = get_object_or_404(Consultation, pk=self.kwargs["pk"])
        serializer.save(consultation=consultation, doctor=self.request.user)


class DoctorReviewView(APIView):
    permission_classes = [IsDoctor]

    def post(self, request, pk):
        consultation = get_object_or_404(Consultation, pk=pk)
        consultation.doctor = request.user
        consultation.reviewed_at = timezone.now()
        consultation.status = Consultation.Status.REVIEWED
        consultation.save(update_fields=["doctor", "reviewed_at", "status"])
        return Response(
            DoctorConsultationDetailSerializer(consultation, context={"request": request}).data
        )
