from django.urls import path

from consultations.doctor_views import (
    DoctorConsultationDetailView,
    DoctorConsultationListView,
    DoctorLifestyleOverrideView,
    DoctorNoteCreateView,
    DoctorReviewView,
)

urlpatterns = [
    path("consultations/", DoctorConsultationListView.as_view(), name="doctor-consultation-list"),
    path(
        "consultations/<int:pk>/",
        DoctorConsultationDetailView.as_view(),
        name="doctor-consultation-detail",
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
