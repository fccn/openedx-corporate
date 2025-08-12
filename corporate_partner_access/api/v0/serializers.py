"""Serializer for Corporate Partner access API v0."""

from rest_framework import serializers

from corporate_partner_access.models import CorporatePartner


class CorporatePartnerSerializer(serializers.ModelSerializer):
    """Serializer for Corporate Partner data."""

    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = CorporatePartner
        fields = ["id", "code", "name", "homepage_url", "logo", "logo_url"]
        read_only_fields = ["id", "logo_url"]
        extra_kwargs = {
            "homepage_url": {"required": False, "allow_null": True},
            "logo": {"required": False, "allow_null": True, "write_only": True},
        }

    def get_logo_url(self, obj):
        """Return the URL of the corporate partner's logo."""
        return obj.logo.url if obj.logo else None
