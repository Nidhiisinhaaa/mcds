from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from config.views import HealthCheckView, RootView
from reports.views import ConsultationReportPDFView

urlpatterns = [
    path("", RootView.as_view(), name="root"),
    path("admin/", admin.site.urls),
    path("api/health/", HealthCheckView.as_view(), name="health-check"),
    path("api/auth/", include("accounts.urls")),
    path("api/consultations/", include("consultations.urls")),
    path("api/doctor/", include("consultations.doctor_urls")),
    path(
        "api/consultations/<int:pk>/report.pdf",
        ConsultationReportPDFView.as_view(),
        name="consultation-report-pdf",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
