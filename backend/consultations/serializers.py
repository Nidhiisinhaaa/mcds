from django.conf import settings
from rest_framework import serializers

from accounts.models import PatientProfile
from assessment.serializers import RecommendationSerializer, WellnessScoreSerializer
from consultations.models import Consultation, Message

ALLOWED_AUDIO_EXTENSIONS = {"webm", "ogg", "m4a", "mp4", "wav", "mp3"}
MAX_AUDIO_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "text_original",
            "text_english",
            "language",
            "audio",
            "slot_target",
            "created_at",
        ]
        read_only_fields = fields


class ConsultationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consultation
        fields = [
            "id",
            "language",
            "status",
            "chief_complaint_original",
            "chief_complaint_english",
            "turn_count",
            "started_at",
            "completed_at",
            "reviewed_at",
        ]
        read_only_fields = fields


class ConsultationDetailSerializer(ConsultationListSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    wellness_score = serializers.SerializerMethodField()
    recommendations = serializers.SerializerMethodField()

    class Meta(ConsultationListSerializer.Meta):
        fields = ConsultationListSerializer.Meta.fields + [
            "messages",
            "wellness_score",
            "recommendations",
        ]
        read_only_fields = fields

    def get_wellness_score(self, consultation):
        score = getattr(consultation, "wellness_score", None)
        return WellnessScoreSerializer(score).data if score else None

    def get_recommendations(self, consultation):
        recommendations = consultation.recommendations.order_by("order")
        return RecommendationSerializer(recommendations, many=True).data


class ConsultationCreateSerializer(serializers.ModelSerializer):
    language = serializers.ChoiceField(
        choices=PatientProfile.Language.choices, required=False
    )

    class Meta:
        model = Consultation
        fields = ["id", "language", "status", "started_at"]
        read_only_fields = ["id", "status", "started_at"]

    def create(self, validated_data):
        user = self.context["request"].user
        if "language" not in validated_data:
            profile = getattr(user, "patient_profile", None)
            validated_data["language"] = (
                profile.preferred_language if profile else PatientProfile.Language.ENGLISH
            )
        return Consultation.objects.create(patient=user, **validated_data)


class TextMessageInputSerializer(serializers.Serializer):
    text = serializers.CharField(allow_blank=False, trim_whitespace=True)


class AudioMessageInputSerializer(serializers.Serializer):
    audio = serializers.FileField()

    def validate_audio(self, value):
        extension = value.name.rsplit(".", 1)[-1].lower() if "." in value.name else ""
        if extension not in ALLOWED_AUDIO_EXTENSIONS:
            raise serializers.ValidationError(
                f"Unsupported audio format '{extension}'. Allowed formats: "
                f"{', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}."
            )
        if value.size > MAX_AUDIO_SIZE_BYTES:
            raise serializers.ValidationError(
                f"Audio file is too large ({value.size} bytes). Maximum size is "
                f"{MAX_AUDIO_SIZE_BYTES} bytes (20 MB)."
            )
        return value
