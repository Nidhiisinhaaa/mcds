"""Doctor-facing serializers. Unlike the patient-facing ones in
consultations/serializers.py and assessment/serializers.py, these expose
internal fields (text_english, sources, evidence, doctor_overrides) that are
appropriate for clinical review but not for the patient's own view."""

import uuid

from rest_framework import serializers

from accounts.models import PatientProfile, User
from assessment import risk_rules
from assessment.engine import slots as slots_engine
from assessment.models import DoctorNote, LifestyleProfile, Recommendation, RiskFlag, Symptom
from assessment.serializers import WellnessScoreSerializer
from consultations.models import Consultation
from consultations.serializers import MessageSerializer


class DoctorPatientProfileSerializer(serializers.ModelSerializer):
    bmi = serializers.SerializerMethodField()
    consent_recorded_by = serializers.SerializerMethodField()

    class Meta:
        model = PatientProfile
        fields = [
            "full_name",
            "age",
            "sex",
            "height_cm",
            "weight_kg",
            "preferred_language",
            "bmi",
            "consent_given_at",
            "consent_recorded_by",
        ]
        read_only_fields = fields

    def get_bmi(self, profile):
        return risk_rules.compute_bmi(profile)

    def get_consent_recorded_by(self, profile):
        doctor = profile.consent_recorded_by
        return doctor.username if doctor else None


class DoctorPatientSerializer(serializers.ModelSerializer):
    """Search results for the "pick an existing patient" dropdown, and the
    inline "create a new patient record" form, when a doctor starts an
    in-clinic consultation (see DoctorConsultationListCreateView). The
    created User has no usable password - this patient record exists for
    clinical purposes, not for the patient to log into the app themselves."""

    id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = PatientProfile
        fields = [
            "id",
            "username",
            "full_name",
            "age",
            "sex",
            "height_cm",
            "weight_kg",
            "preferred_language",
        ]
        read_only_fields = ["id", "username"]
        extra_kwargs = {"full_name": {"required": True, "allow_blank": False}}

    def create(self, validated_data):
        username = f"patient-{uuid.uuid4().hex[:12]}"
        user = User(username=username, role=User.Role.PATIENT)
        user.set_unusable_password()
        user.save()
        return PatientProfile.objects.create(user=user, **validated_data)


class DoctorConsultationCreateSerializer(serializers.ModelSerializer):
    """A doctor starting an in-clinic consultation on behalf of a patient
    they've picked or just created - see DoctorConsultationListCreateView."""

    patient_id = serializers.PrimaryKeyRelatedField(
        source="patient", queryset=User.objects.filter(role=User.Role.PATIENT)
    )
    language = serializers.ChoiceField(choices=PatientProfile.Language.choices, required=False)

    class Meta:
        model = Consultation
        fields = ["id", "patient_id", "language", "status", "started_at"]
        read_only_fields = ["id", "status", "started_at"]

    def create(self, validated_data):
        doctor = self.context["request"].user
        patient = validated_data.pop("patient")
        if "language" not in validated_data:
            profile = getattr(patient, "patient_profile", None)
            validated_data["language"] = (
                profile.preferred_language if profile else PatientProfile.Language.ENGLISH
            )
        return Consultation.objects.create(patient=patient, doctor=doctor, **validated_data)


class DoctorLifestyleProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = LifestyleProfile
        fields = [
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
            "evidence",
            "doctor_overrides",
        ]
        read_only_fields = fields


class SymptomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Symptom
        fields = ["id", "name", "duration_text", "severity", "source"]
        read_only_fields = fields


class RiskFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskFlag
        fields = ["code", "label", "severity", "reason"]
        read_only_fields = fields


class DoctorRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recommendation
        fields = ["category", "text_english", "text_patient_language", "sources", "order"]
        read_only_fields = fields


class DoctorNoteSerializer(serializers.ModelSerializer):
    doctor_username = serializers.CharField(source="doctor.username", read_only=True)

    class Meta:
        model = DoctorNote
        fields = ["id", "doctor_username", "text", "created_at"]
        read_only_fields = ["id", "doctor_username", "created_at"]


class DoctorConsultationListSerializer(serializers.ModelSerializer):
    """One row of the doctor queue table."""

    patient_name = serializers.SerializerMethodField()
    patient_age = serializers.SerializerMethodField()
    wellness_total = serializers.SerializerMethodField()
    wellness_band = serializers.SerializerMethodField()
    flag_count = serializers.SerializerMethodField()

    class Meta:
        model = Consultation
        fields = [
            "id",
            "patient_name",
            "patient_age",
            "language",
            "status",
            "chief_complaint_english",
            "wellness_total",
            "wellness_band",
            "flag_count",
            "started_at",
            "completed_at",
        ]
        read_only_fields = fields

    def _patient_profile(self, consultation):
        return getattr(consultation.patient, "patient_profile", None)

    def get_patient_name(self, consultation):
        profile = self._patient_profile(consultation)
        if profile and profile.full_name:
            return profile.full_name
        return consultation.patient.username

    def get_patient_age(self, consultation):
        profile = self._patient_profile(consultation)
        return profile.age if profile else None

    def get_wellness_total(self, consultation):
        score = getattr(consultation, "wellness_score", None)
        return score.total if score else None

    def get_wellness_band(self, consultation):
        score = getattr(consultation, "wellness_score", None)
        return score.band if score else None

    def get_flag_count(self, consultation):
        # Annotated on the queryset (see DoctorConsultationListView) for
        # efficiency; fall back to a live count if used without it.
        annotated = getattr(consultation, "flag_count", None)
        return annotated if annotated is not None else consultation.risk_flags.count()


class DoctorConsultationDetailSerializer(serializers.ModelSerializer):
    patient_profile = serializers.SerializerMethodField()
    messages = MessageSerializer(many=True, read_only=True)
    lifestyle_profile = serializers.SerializerMethodField()
    slot_status = serializers.SerializerMethodField()
    symptoms = SymptomSerializer(many=True, read_only=True)
    wellness_score = serializers.SerializerMethodField()
    risk_flags = RiskFlagSerializer(many=True, read_only=True)
    recommendations = DoctorRecommendationSerializer(many=True, read_only=True)
    doctor_notes = DoctorNoteSerializer(many=True, read_only=True)

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
            "patient_profile",
            "messages",
            "lifestyle_profile",
            "slot_status",
            "symptoms",
            "wellness_score",
            "risk_flags",
            "recommendations",
            "doctor_notes",
        ]
        read_only_fields = fields

    def get_patient_profile(self, consultation):
        profile = getattr(consultation.patient, "patient_profile", None)
        return DoctorPatientProfileSerializer(profile).data if profile else None

    def get_lifestyle_profile(self, consultation):
        profile = getattr(consultation, "lifestyle_profile", None)
        return DoctorLifestyleProfileSerializer(profile).data if profile else None

    def get_slot_status(self, consultation):
        """Per-slot "filled"/"skipped"/"pending" status, so the frontend can
        clearly list which slots were skipped or never answered rather than
        just showing blank values indistinguishable from "not asked yet"."""
        profile = getattr(consultation, "lifestyle_profile", None)
        return slots_engine.slot_status_map(profile) if profile else None

    def get_wellness_score(self, consultation):
        score = getattr(consultation, "wellness_score", None)
        return WellnessScoreSerializer(score).data if score else None
