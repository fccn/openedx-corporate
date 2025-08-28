"""Permission classes for corporate partner access."""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from corporate_partner_access.models import CorporatePartnerManager, PartnerManagerRole


class IsPartnerCatalogManager(BasePermission):
    """
    Corporate partner catalog manager permissions.

    This permission grants access to corporate partner resources based on the user's role.
    If the user is a Manager of the current catalog, they have full access.
    If the user is a Viewer, they have read-only access.

    """

    message = "Insufficient permissions for this resource."

    def has_permission(self, request, view):
        """Permission check for partner catalog managers."""
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return False

        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return True

        catalog_pk = view.kwargs.get("catalog_pk")
        partner_pk = view.kwargs.get("partner_pk")

        qs = CorporatePartnerManager.objects.filter(user=user, active=True)
        if catalog_pk:
            qs = qs.filter(catalog_id=catalog_pk)
        elif partner_pk:
            qs = qs.filter(catalog__corporate_partner_id=partner_pk)
        else:
            return True

        roles = set(qs.values_list("role", flat=True))
        if PartnerManagerRole.PARTNER_MANAGER in roles:
            return True
        if PartnerManagerRole.PARTNER_VIEWER in roles:
            return request.method in SAFE_METHODS

        return False
