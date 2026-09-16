import logging

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsDoctor, IsPatient
from assessment import pipeline
from assessment.engine import orchestrator
from assessment.serializers import LifestyleProfileSerializer
from core.services import groq_client
from consultations.models import Consultation, Message
from consultations.serializers import (
    AudioMessageInputSerializer,
    ConsultationCreateSerializer,
    ConsultationDetailSerializer,
    ConsultationListSerializer,
    MessageSerializer,
    TextMessageInputSerializer,
)

logger = logging.getLogger("consultations.views")


def _get_owned_consultation(request, pk):
    return get_object_or_404(Consultation, pk=pk, patient=request.user)


def _reject_unless_in_progress(consultation):
    if consultation.status != Consultation.Status.IN_PROGRESS:
        raise ValidationError(
            {"detail": f"Consultation is not in progress (status={consultation.status})."}
        )


def _groq_error_response():
    """A Groq call failed upstream after retries. Never let that surface as a
    bare 500 - the full exception is already logged (via logger.exception at
    the call site), this is just the short, safe message the UI can show."""
    return Response(
        {"detail": "We couldn't process that right now. Please try again."},
        status=status.HTTP_502_BAD_GATEWAY,
    )


def _message_turn_response(request, patient_message, ai_message, consultation):
    return Response(
        {
            "patient_message": MessageSerializer(patient_message, context={"request": request}).data,
            "ai_message": MessageSerializer(ai_message, context={"request": request}).data,
            "slot_status": orchestrator.get_slot_status(consultation),
            "status": consultation.status,
        },
        status=status.HTTP_201_CREATED,
    )


class ConsultationListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsPatient]

    def get_queryset(self):
        return Consultation.objects.filter(patient=self.request.user)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ConsultationCreateSerializer
        return ConsultationListSerializer

    def create(self, request, *args, **kwargs):
        profile = getattr(request.user, "patient_profile", None)
        if profile is None or profile.consent_given_at is None:
            raise PermissionDenied(
                "Consent is required before starting a consultation. "
                "Call POST /api/auth/consent/ first."
            )
        return super().create(request, *args, **kwargs)


class ConsultationDetailView(generics.RetrieveAPIView):
    permission_classes = [IsPatient]
    serializer_class = ConsultationDetailSerializer

    def get_queryset(self):
        return Consultation.objects.filter(patient=self.request.user)


class ConsultationStateView(APIView):
    permission_classes = [IsPatient]

    def get(self, request, pk):
        consultation = _get_owned_consultation(request, pk)
        profile = getattr(consultation, "lifestyle_profile", None)
        return Response(
            {
                "status": consultation.status,
                "slot_status": orchestrator.get_slot_status(consultation),
                "profile": LifestyleProfileSerializer(profile).data if profile else {},
            }
        )


class ConsultationReanalyseView(APIView):
    permission_classes = [IsDoctor]

    def post(self, request, pk):
        consultation = get_object_or_404(Consultation, pk=pk)
        pipeline.run_analysis(consultation)
        return Response(
            {
                "status": consultation.status,
                "slot_status": orchestrator.get_slot_status(consultation),
                "detail": "Analysis regenerated.",
            }
        )


class ConsultationAudioMessageView(APIView):
    permission_classes = [IsPatient]

    def post(self, request, pk):
        consultation = _get_owned_consultation(request, pk)
        _reject_unless_in_progress(consultation)

        input_serializer = AudioMessageInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        audio_file = input_serializer.validated_data["audio"]

        try:
            transcription = groq_client.transcribe(
                audio_file, language_hint=consultation.language
            )
            text_original = transcription["text"]

            if consultation.language == "en":
                # Already English - reuse the transcription, no second API call.
                text_english = text_original
            else:
                text_english = groq_client.translate_text(
                    text_original, source_lang=consultation.language, target_lang="en"
                )

            audio_file.seek(0)
            message = Message.objects.create(
                consultation=consultation,
                sender=Message.Sender.PATIENT,
                text_original=text_original,
                text_english=text_english,
                language=consultation.language,
                audio=audio_file,
            )
            consultation.turn_count += 1
            consultation.save(update_fields=["turn_count"])

            ai_message = orchestrator.handle_patient_message(consultation, message)
        except groq_client.GroqServiceError:
            logger.exception(
                "consultation_audio.groq_failed", extra={"consultation_id": consultation.id}
            )
            return _groq_error_response()

        return _message_turn_response(request, message, ai_message, consultation)


class ConsultationTextMessageView(APIView):
    permission_classes = [IsPatient]

    def post(self, request, pk):
        consultation = _get_owned_consultation(request, pk)
        _reject_unless_in_progress(consultation)

        input_serializer = TextMessageInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        text_original = input_serializer.validated_data["text"]

        try:
            text_english = groq_client.translate_text(
                text_original, source_lang=consultation.language, target_lang="en"
            )

            message = Message.objects.create(
                consultation=consultation,
                sender=Message.Sender.PATIENT,
                text_original=text_original,
                text_english=text_english,
                language=consultation.language,
            )
            consultation.turn_count += 1
            consultation.save(update_fields=["turn_count"])

            ai_message = orchestrator.handle_patient_message(consultation, message)
        except groq_client.GroqServiceError:
            logger.exception(
                "consultation_text.groq_failed", extra={"consultation_id": consultation.id}
            )
            return _groq_error_response()

        return _message_turn_response(request, message, ai_message, consultation)
