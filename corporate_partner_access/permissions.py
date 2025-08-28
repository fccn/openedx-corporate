"""Permission classes for corporate partner access."""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from corporate_partner_access.models import CorporatePartnerManager, PartnerManagerRole


class IsPartnerManager(BasePermission):
    """
    Corporate partner manager permissions.

    This permission grants access to corporate partner resources based on the user's role.
    If the user is a Manager of the current partner, they have full access.
    If the user is a Viewer, they have read-only access.

    """

    message = "Insufficient permissions for this partner resource."

    def has_permission(self, request, view):
        """Permission check for partner managers."""
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return False

        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return True

        partner_pk = view.kwargs.get("partner_pk")
        if partner_pk is None:
            return CorporatePartnerManager.objects.filter(
                user=user, active=True
            ).exists()

        membership = (
            CorporatePartnerManager.objects.filter(
                user=user, partner_id=partner_pk, active=True
            )
            .only("role")
            .first()
        )
        if not membership:
            return False

        if membership.role == PartnerManagerRole.PARTNER_MANAGER:
            return True

        if membership.role == PartnerManagerRole.PARTNER_VIEWER:
            return request.method in SAFE_METHODS

        return False
