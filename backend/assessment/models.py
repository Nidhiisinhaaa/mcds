from django.conf import settings
from django.db import models

from consultations.models import Consultation


class LifestyleProfile(models.Model):
    class SmokingStatus(models.TextChoices):
        NONE = "none", "None"
        OCCASIONAL = "occasional", "Occasional"
        DAILY = "daily", "Daily"

    class AlcoholFrequency(models.TextChoices):
        NONE = "none", "None"
        OCCASIONAL = "occasional", "Occasional"
        WEEKLY = "weekly", "Weekly"
        DAILY = "daily", "Daily"

    class DietPattern(models.TextChoices):
        BALANCED = "balanced", "Balanced"
        MIXED = "mixed", "Mixed"
        FREQUENT_FAST_FOOD = "frequent_fast_food", "Frequent fast food"
        HIGH_SUGAR = "high_sugar", "High sugar"
        IRREGULAR = "irregular", "Irregular"

    class StressLevel(models.TextChoices):
        LOW = "low", "Low"
        MODERATE = "moderate", "Moderate"
        HIGH = "high", "High"

    consultation = models.OneToOneField(
        Consultation, on_delete=models.CASCADE, related_name="lifestyle_profile"
    )

    sleep_hours = models.FloatField(null=True, blank=True)
    exercise_days_per_week = models.IntegerField(null=True, blank=True)
    exercise_minutes_per_session = models.IntegerField(null=True, blank=True)
    smoking_status = models.CharField(
        max_length=15, choices=SmokingStatus.choices, null=True, blank=True
    )
    cigarettes_per_day = models.IntegerField(null=True, blank=True)
    alcohol_frequency = models.CharField(
        max_length=15, choices=AlcoholFrequency.choices, null=True, blank=True
    )
    diet_pattern = models.CharField(
        max_length=20, choices=DietPattern.choices, null=True, blank=True
    )
    water_litres_per_day = models.FloatField(null=True, blank=True)
    stress_level = models.CharField(
        max_length=10, choices=StressLevel.choices, null=True, blank=True
    )
    sitting_hours_per_day = models.FloatField(null=True, blank=True)

    evidence = models.JSONField(null=True, blank=True)
    doctor_overrides = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"LifestyleProfile for Consultation #{self.consultation_id}"


class Symptom(models.Model):
    class Severity(models.TextChoices):
        MILD = "mild", "Mild"
        MODERATE = "moderate", "Moderate"
        SEVERE = "severe", "Severe"
        UNKNOWN = "unknown", "Unknown"

    class Source(models.TextChoices):
        LLM = "llm", "LLM"
        SCISPACY = "scispacy", "scispaCy"
        DOCTOR = "doctor", "Doctor"

    consultation = models.ForeignKey(
        Consultation, on_delete=models.CASCADE, related_name="symptoms"
    )
    name = models.CharField(max_length=200)
    duration_text = models.CharField(max_length=200, blank=True)
    severity = models.CharField(
        max_length=10, choices=Severity.choices, default=Severity.UNKNOWN
    )
    source = models.CharField(max_length=10, choices=Source.choices)

    def __str__(self):
        return f"{self.name} ({self.severity})"


class RiskFlag(models.Model):
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    consultation = models.ForeignKey(
        Consultation, on_delete=models.CASCADE, related_name="risk_flags"
    )
    code = models.CharField(max_length=50)
    label = models.CharField(max_length=200)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    reason = models.TextField(blank=True)

    def __str__(self):
        return f"{self.code} ({self.severity})"


class WellnessScore(models.Model):
    consultation = models.OneToOneField(
        Consultation, on_delete=models.CASCADE, related_name="wellness_score"
    )
    total = models.PositiveSmallIntegerField()
    band = models.CharField(max_length=50)
    breakdown = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"WellnessScore {self.total} ({self.band}) - Consultation #{self.consultation_id}"


class Recommendation(models.Model):
    consultation = models.ForeignKey(
        Consultation, on_delete=models.CASCADE, related_name="recommendations"
    )
    category = models.CharField(max_length=100)
    text_english = models.TextField()
    text_patient_language = models.TextField(blank=True)
    sources = models.JSONField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.category} recommendation for Consultation #{self.consultation_id}"


class DoctorNote(models.Model):
    consultation = models.ForeignKey(
        Consultation, on_delete=models.CASCADE, related_name="doctor_notes"
    )
    doctor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Note by {self.doctor} on Consultation #{self.consultation_id}"
