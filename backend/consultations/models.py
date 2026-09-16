from django.conf import settings
from django.db import models

from accounts.models import PatientProfile


class Consultation(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        REVIEWED = "reviewed", "Reviewed"
        ESCALATED = "escalated", "Escalated"

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="consultations"
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_consultations",
        null=True,
        blank=True,
    )
    language = models.CharField(
        max_length=5, choices=PatientProfile.Language.choices, default=PatientProfile.Language.ENGLISH
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.IN_PROGRESS
    )
    chief_complaint_original = models.TextField(blank=True)
    chief_complaint_english = models.TextField(blank=True)
    turn_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Consultation #{self.id} ({self.patient}) - {self.status}"


class Message(models.Model):
    class Sender(models.TextChoices):
        PATIENT = "patient", "Patient"
        AI = "ai", "AI"

    consultation = models.ForeignKey(
        Consultation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.CharField(max_length=10, choices=Sender.choices)
    text_original = models.TextField(blank=True)
    text_english = models.TextField(blank=True)
    language = models.CharField(
        max_length=5, choices=PatientProfile.Language.choices, default=PatientProfile.Language.ENGLISH
    )
    audio = models.FileField(upload_to="consultations/audio/%Y/%m/", null=True, blank=True)
    slot_target = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message #{self.id} ({self.sender}) - Consultation #{self.consultation_id}"
