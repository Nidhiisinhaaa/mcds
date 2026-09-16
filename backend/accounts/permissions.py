from rest_framework.permissions import BasePermission

from accounts.models import User


class IsPatient(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.PATIENT
        )


class IsDoctor(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.DOCTOR
        )


class IsPatientOrDoctor(BasePermission):
    """Role check only - which specific consultations a patient or doctor may
    act on is enforced separately (see consultations.views._get_accessible_consultation),
    since that depends on which patient/doctor owns the consultation, not just
    the requester's role."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (User.Role.PATIENT, User.Role.DOCTOR)
        )
