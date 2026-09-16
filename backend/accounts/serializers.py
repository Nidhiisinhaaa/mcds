from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from accounts.models import PatientProfile, User


class PatientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = [
            "full_name",
            "age",
            "sex",
            "height_cm",
            "weight_kg",
            "preferred_language",
            "consent_given_at",
        ]
        read_only_fields = ["consent_given_at"]


class MeSerializer(serializers.ModelSerializer):
    profile = PatientProfileSerializer(source="patient_profile", required=False)

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "profile"]
        read_only_fields = ["id", "username", "role"]

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("patient_profile", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if profile_data is not None and instance.role == User.Role.PATIENT:
            profile, _ = PatientProfile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance

    def to_representation(self, instance):
        if instance.role != User.Role.PATIENT:
            data = super().to_representation(instance)
            data.pop("profile", None)
            return data
        return super().to_representation(instance)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    full_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    preferred_language = serializers.ChoiceField(
        choices=PatientProfile.Language.choices,
        required=False,
        default=PatientProfile.Language.ENGLISH,
        write_only=True,
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "full_name", "preferred_language"]

    def create(self, validated_data):
        full_name = validated_data.pop("full_name", "")
        preferred_language = validated_data.pop(
            "preferred_language", PatientProfile.Language.ENGLISH
        )
        password = validated_data.pop("password")

        user = User(role=User.Role.PATIENT, **validated_data)
        user.set_password(password)
        user.save()

        PatientProfile.objects.create(
            user=user, full_name=full_name, preferred_language=preferred_language
        )
        return user


class ConsentSerializer(serializers.Serializer):
    def save(self, **kwargs):
        user = self.context["request"].user
        profile, _ = PatientProfile.objects.get_or_create(user=user)
        profile.consent_given_at = timezone.now()
        profile.save(update_fields=["consent_given_at"])
        return profile
