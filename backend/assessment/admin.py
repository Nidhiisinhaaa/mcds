from django.contrib import admin

from assessment.models import (
    DoctorNote,
    LifestyleProfile,
    Recommendation,
    RiskFlag,
    Symptom,
    WellnessScore,
)


@admin.register(LifestyleProfile)
class LifestyleProfileAdmin(admin.ModelAdmin):
    list_display = [
        "consultation",
        "sleep_hours",
        "exercise_days_per_week",
        "smoking_status",
        "alcohol_frequency",
        "diet_pattern",
        "stress_level",
    ]
    list_filter = ["smoking_status", "alcohol_frequency", "diet_pattern", "stress_level"]
    search_fields = ["consultation__id"]


@admin.register(Symptom)
class SymptomAdmin(admin.ModelAdmin):
    list_display = ["name", "consultation", "severity", "source", "duration_text"]
    list_filter = ["severity", "source"]
    search_fields = ["name", "consultation__id"]


@admin.register(RiskFlag)
class RiskFlagAdmin(admin.ModelAdmin):
    list_display = ["code", "label", "consultation", "severity"]
    list_filter = ["severity", "code"]
    search_fields = ["code", "label", "consultation__id"]


@admin.register(WellnessScore)
class WellnessScoreAdmin(admin.ModelAdmin):
    list_display = ["consultation", "total", "band"]
    list_filter = ["band"]
    search_fields = ["consultation__id"]


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ["consultation", "category", "order"]
    list_filter = ["category"]
    search_fields = ["consultation__id", "text_english"]


@admin.register(DoctorNote)
class DoctorNoteAdmin(admin.ModelAdmin):
    list_display = ["consultation", "doctor", "created_at"]
    list_filter = ["doctor"]
    search_fields = ["text", "consultation__id"]
