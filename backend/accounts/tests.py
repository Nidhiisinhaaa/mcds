import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import PatientProfile, User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def doctor_user(db):
    user = User.objects.create_user(
        username="dr_house", password="StrongPass123", role=User.Role.DOCTOR
    )
    return user


@pytest.fixture
def patient_user(db):
    user = User.objects.create_user(
        username="patient1", password="StrongPass123", role=User.Role.PATIENT
    )
    PatientProfile.objects.create(user=user, full_name="Patient One")
    return user


@pytest.mark.django_db
class TestRegistration:
    def test_register_creates_patient_user_and_profile(self, api_client):
        url = reverse("auth-register")
        payload = {
            "username": "newpatient",
            "email": "newpatient@example.com",
            "password": "StrongPass123",
            "full_name": "New Patient",
            "preferred_language": "hi",
        }
        response = api_client.post(url, payload, format="json")

        assert response.status_code == 201
        user = User.objects.get(username="newpatient")
        assert user.role == User.Role.PATIENT
        assert user.check_password("StrongPass123")

        profile = user.patient_profile
        assert profile.full_name == "New Patient"
        assert profile.preferred_language == "hi"

    def test_register_duplicate_username_fails(self, api_client, patient_user):
        url = reverse("auth-register")
        payload = {
            "username": "patient1",
            "password": "StrongPass123",
        }
        response = api_client.post(url, payload, format="json")
        assert response.status_code == 400


@pytest.mark.django_db
class TestLogin:
    def test_login_returns_jwt_pair(self, api_client, patient_user):
        url = reverse("auth-login")
        response = api_client.post(
            url, {"username": "patient1", "password": "StrongPass123"}, format="json"
        )
        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" in response.data

    def test_login_wrong_password_fails(self, api_client, patient_user):
        url = reverse("auth-login")
        response = api_client.post(
            url, {"username": "patient1", "password": "wrong"}, format="json"
        )
        assert response.status_code == 401

    def test_refresh_returns_new_access_token(self, api_client, patient_user):
        login_url = reverse("auth-login")
        login_response = api_client.post(
            login_url,
            {"username": "patient1", "password": "StrongPass123"},
            format="json",
        )
        refresh_token = login_response.data["refresh"]

        refresh_url = reverse("auth-refresh")
        response = api_client.post(refresh_url, {"refresh": refresh_token}, format="json")
        assert response.status_code == 200
        assert "access" in response.data


@pytest.mark.django_db
class TestMeEndpoint:
    def test_get_me_requires_auth(self, api_client):
        url = reverse("auth-me")
        response = api_client.get(url)
        assert response.status_code == 401

    def test_get_me_returns_user_and_profile(self, api_client, patient_user):
        api_client.force_authenticate(user=patient_user)
        url = reverse("auth-me")
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data["username"] == "patient1"
        assert response.data["profile"]["full_name"] == "Patient One"

    def test_patch_me_updates_profile(self, api_client, patient_user):
        api_client.force_authenticate(user=patient_user)
        url = reverse("auth-me")
        response = api_client.patch(
            url, {"profile": {"age": 30, "height_cm": 175.5}}, format="json"
        )
        assert response.status_code == 200
        patient_user.patient_profile.refresh_from_db()
        assert patient_user.patient_profile.age == 30
        assert patient_user.patient_profile.height_cm == 175.5

    def test_doctor_me_has_no_profile_field(self, api_client, doctor_user):
        api_client.force_authenticate(user=doctor_user)
        url = reverse("auth-me")
        response = api_client.get(url)
        assert response.status_code == 200
        assert "profile" not in response.data


@pytest.mark.django_db
class TestConsent:
    def test_consent_requires_auth(self, api_client):
        url = reverse("auth-consent")
        response = api_client.post(url)
        assert response.status_code == 401

    def test_consent_sets_timestamp(self, api_client, patient_user):
        api_client.force_authenticate(user=patient_user)
        url = reverse("auth-consent")
        response = api_client.post(url)
        assert response.status_code == 200
        assert response.data["consent_given_at"] is not None

        patient_user.patient_profile.refresh_from_db()
        assert patient_user.patient_profile.consent_given_at is not None


@pytest.mark.django_db
class TestRolePermissions:
    def test_is_patient_permission(self, patient_user, doctor_user):
        from accounts.permissions import IsPatient

        class DummyRequest:
            def __init__(self, user):
                self.user = user

        permission = IsPatient()
        assert permission.has_permission(DummyRequest(patient_user), None) is True
        assert permission.has_permission(DummyRequest(doctor_user), None) is False

    def test_is_doctor_permission(self, patient_user, doctor_user):
        from accounts.permissions import IsDoctor

        class DummyRequest:
            def __init__(self, user):
                self.user = user

        permission = IsDoctor()
        assert permission.has_permission(DummyRequest(doctor_user), None) is True
        assert permission.has_permission(DummyRequest(patient_user), None) is False


@pytest.mark.django_db
class TestCreateDoctorCommand:
    def test_create_doctor_management_command(self):
        from django.core.management import call_command

        call_command(
            "create_doctor",
            username="dr_new",
            password="StrongPass123",
            name="Jane Doe",
        )
        user = User.objects.get(username="dr_new")
        assert user.role == User.Role.DOCTOR
        assert user.check_password("StrongPass123")
        assert user.first_name == "Jane"
        assert user.last_name == "Doe"
