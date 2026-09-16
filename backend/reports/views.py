import logging

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from accounts.models import User
from consultations.models import Consultation
from reports.pdf import render_consultation_pdf

logger = logging.getLogger("reports.views")


class ConsultationReportPDFView(APIView):
    """GET /api/consultations/{id}/report.pdf - the owning patient or any doctor."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        consultation = get_object_or_404(Consultation, pk=pk)
        user = request.user

        is_owning_patient = user.role == User.Role.PATIENT and consultation.patient_id == user.id
        is_doctor = user.role == User.Role.DOCTOR
        if not (is_owning_patient or is_doctor):
            raise PermissionDenied("You do not have access to this consultation's report.")

        try:
            pdf_bytes = render_consultation_pdf(consultation)
        except Exception:
            logger.exception("reports.render_failed", extra={"consultation_id": consultation.id})
            return HttpResponse(
                "Could not generate the report right now. Please try again.",
                status=502,
                content_type="text/plain",
            )

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="consultation-{consultation.id}-report.pdf"'
        return response
