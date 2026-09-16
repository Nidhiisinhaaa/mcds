from rest_framework import serializers

from assessment.models import LifestyleProfile, Recommendation, WellnessScore


class LifestyleProfileSerializer(serializers.ModelSerializer):
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
        ]
        read_only_fields = fields


class WellnessScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = WellnessScore
        fields = ["total", "band", "breakdown"]
        read_only_fields = fields


class RecommendationSerializer(serializers.ModelSerializer):
    """Patient-facing view: only the patient-language text and category -
    text_english and sources are for the doctor's view, not the patient's."""

    class Meta:
        model = Recommendation
        fields = ["category", "text_patient_language", "order"]
        read_only_fields = fields
