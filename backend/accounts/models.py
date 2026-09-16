from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        PATIENT = "patient", "Patient"
        DOCTOR = "doctor", "Doctor"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.PATIENT)

    def __str__(self):
        return f"{self.username} ({self.role})"


class PatientProfile(models.Model):
    class Sex(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        HINDI = "hi", "Hindi"
        MARATHI = "mr", "Marathi"
        TAMIL = "ta", "Tamil"
        TELUGU = "te", "Telugu"
        BENGALI = "bn", "Bengali"
        KANNADA = "kn", "Kannada"
        GUJARATI = "gu", "Gujarati"
        MALAYALAM = "ml", "Malayalam"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="patient_profile"
    )
    full_name = models.CharField(max_length=150, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    sex = models.CharField(max_length=10, choices=Sex.choices, blank=True)
    height_cm = models.FloatField(null=True, blank=True)
    weight_kg = models.FloatField(null=True, blank=True)
    preferred_language = models.CharField(
        max_length=5, choices=Language.choices, default=Language.ENGLISH
    )
    consent_given_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.full_name or self.user.username
