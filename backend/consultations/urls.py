from django.urls import path

from consultations.views import (
    ConsultationAudioMessageView,
    ConsultationDetailView,
    ConsultationListCreateView,
    ConsultationReanalyseView,
    ConsultationStateView,
    ConsultationTextMessageView,
)

urlpatterns = [
    path("", ConsultationListCreateView.as_view(), name="consultation-list-create"),
    path("<int:pk>/", ConsultationDetailView.as_view(), name="consultation-detail"),
    path("<int:pk>/state/", ConsultationStateView.as_view(), name="consultation-state"),
    path(
        "<int:pk>/reanalyse/",
        ConsultationReanalyseView.as_view(),
        name="consultation-reanalyse",
    ),
    path(
        "<int:pk>/audio/",
        ConsultationAudioMessageView.as_view(),
        name="consultation-audio-message",
    ),
    path(
        "<int:pk>/text/",
        ConsultationTextMessageView.as_view(),
        name="consultation-text-message",
    ),
]
