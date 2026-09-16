import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestRootView:
    def test_root_returns_service_info(self, api_client):
        response = api_client.get(reverse("root"))
        assert response.status_code == 200
        assert response.data == {
            "service": "Multilingual Clinical Dialogue System API",
            "status": "ok",
            "admin": "/admin/",
            "api": "/api/",
        }


@pytest.mark.django_db
class TestHealthCheckView:
    def test_health_check_ok(self, api_client):
        response = api_client.get(reverse("health-check"))
        assert response.status_code == 200
        assert response.data == {"status": "ok"}

    def test_health_check_returns_503_on_db_failure(self, api_client, monkeypatch):
        from django.db.utils import OperationalError

        def broken_cursor(*args, **kwargs):
            raise OperationalError("db is down")

        monkeypatch.setattr(
            "django.db.connection.cursor", broken_cursor
        )

        response = api_client.get(reverse("health-check"))
        assert response.status_code == 503
        assert response.data == {"status": "error"}
