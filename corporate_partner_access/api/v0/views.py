"""Corporate Partner Access API v0 Views."""

from edx_rest_framework_extensions.permissions import IsAuthenticated
from rest_framework import viewsets

from corporate_partner_access.api.v0.serializers import CorporatePartnerSerializer
from corporate_partner_access.models import CorporatePartner


class CorporatePartnerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Corporate Partner data.
    Provides read-only access to corporate partner information.
    """

    queryset = CorporatePartner.objects.all()
    serializer_class = CorporatePartnerSerializer
    permission_classes = [IsAuthenticated]
