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

from accounts.models import PatientProfile
from accounts.permissions import IsDoctor
from assessment import pipeline
from assessment.models import LifestyleProfile
from consultations.doctor_serializers import (
    DoctorConsultationCreateSerializer,
    DoctorConsultationDetailSerializer,
    DoctorConsultationListSerializer,
    DoctorNoteSerializer,
    DoctorPatientSerializer,
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


class DoctorConsultationListView(generics.ListCreateAPIView):
    """GET lists/searches the doctor queue (unchanged). POST starts a new
    in-clinic, doctor-led consultation for a patient the doctor picked or
    just created (see DoctorPatientListCreateView) - the doctor is
    pre-assigned as Consultation.doctor, which is what scopes their later
    permission to post messages into it (see
    consultations.views._get_accessible_consultation)."""

    permission_classes = [IsDoctor]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return DoctorConsultationCreateSerializer
        return DoctorConsultationListSerializer

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


class DoctorPatientListCreateView(generics.ListCreateAPIView):
    """GET searches existing patients (?q=) for the "start consultation"
    dropdown. POST creates a new patient record inline, for a patient who's
    never used the app before (walk-in / in-clinic case)."""

    permission_classes = [IsDoctor]
    serializer_class = DoctorPatientSerializer

    def get_queryset(self):
        qs = PatientProfile.objects.select_related("user").order_by("full_name")
        query = self.request.query_params.get("q")
        if query:
            qs = qs.filter(Q(full_name__icontains=query) | Q(user__username__icontains=query))
        return qs


class DoctorConsentConfirmView(APIView):
    """A doctor confirms they obtained the patient's verbal consent before
    an in-clinic consultation can proceed - see
    consultations.views._require_consent_for_doctor_led, which enforces this
    at message-post time and never silently bypasses it. Scoped to the
    assigned doctor only, same as message-posting: only the doctor actually
    running this consultation can attest to consent having been obtained."""

    permission_classes = [IsDoctor]

    def post(self, request, pk):
        consultation = get_object_or_404(Consultation, pk=pk, doctor=request.user)
        profile, _ = PatientProfile.objects.get_or_create(user=consultation.patient)
        profile.consent_given_at = timezone.now()
        profile.consent_recorded_by = request.user
        profile.save(update_fields=["consent_given_at", "consent_recorded_by"])
        return Response(
            {
                "consent_given_at": profile.consent_given_at,
                "consent_recorded_by": request.user.username,
            }
        )


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
