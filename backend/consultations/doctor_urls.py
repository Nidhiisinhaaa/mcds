from django.urls import path

from consultations.doctor_views import (
    DoctorConsentConfirmView,
    DoctorConsultationDetailView,
    DoctorConsultationListView,
    DoctorLifestyleOverrideView,
    DoctorNoteCreateView,
    DoctorPatientListCreateView,
    DoctorReviewView,
)

urlpatterns = [
    path("patients/", DoctorPatientListCreateView.as_view(), name="doctor-patient-list-create"),
    path("consultations/", DoctorConsultationListView.as_view(), name="doctor-consultation-list"),
    path(
        "consultations/<int:pk>/",
        DoctorConsultationDetailView.as_view(),
        name="doctor-consultation-detail",
    ),
    path(
        "consultations/<int:pk>/consent/",
        DoctorConsentConfirmView.as_view(),
        name="doctor-consultation-consent",
    ),
    path(
        "consultations/<int:pk>/lifestyle/",
        DoctorLifestyleOverrideView.as_view(),
        name="doctor-consultation-lifestyle",
    ),
    path(
        "consultations/<int:pk>/notes/",
        DoctorNoteCreateView.as_view(),
        name="doctor-consultation-notes",
    ),
    path(
        "consultations/<int:pk>/review/",
        DoctorReviewView.as_view(),
        name="doctor-consultation-review",
    ),
]
