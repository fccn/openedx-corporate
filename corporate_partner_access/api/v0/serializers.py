"""Serializer for Corporate Partner access API v0."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from corporate_partner_access.edxapp_wrapper.course_module import course_overview
from corporate_partner_access.models import (
    CorporatePartner,
    CorporatePartnerCatalog,
    CorporatePartnerCatalogCourse,
    CorporatePartnerCatalogLearner,
)
from flex_catalog.serializers import CourseOverviewSimpleSerializer

User = get_user_model()

CourseOverview = course_overview()


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
        try:
            return obj.logo.url
        except (ValueError, AttributeError):
            return None


class CorporatePartnerCatalogSerializer(serializers.ModelSerializer):
    """Serializer for Corporate Partner Catalog data."""

    corporate_partner = serializers.PrimaryKeyRelatedField(
        queryset=CorporatePartner.objects.all()
    )

    class Meta:
        model = CorporatePartnerCatalog
        fields = [
            "id",
            "name",
            "slug",
            "corporate_partner",
            "course_enrollment_limit",
            "user_limit",
            "is_self_enrollment",
            "available_start_date",
            "available_end_date",
            "custom_courses",
            "authorization_additional_message",
            "support_email",
            "is_public",
            "catalog_alternative_link",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "authorization_additional_message": {
                "required": False,
                "allow_blank": True,
            },
            "support_email": {
                "required": False,
                "allow_blank": True,
            },
            "catalog_alternative_link": {
                "required": False,
                "allow_blank": True,
            },
        }

    def validate(self, attrs):
        start = attrs.get("available_start_date", None)
        end = attrs.get("available_end_date", None)
        if start and end and end < start:
            raise serializers.ValidationError(
                "Available end date cannot be before available start date."
            )
        return attrs


class CatalogLearnerSerializer(serializers.ModelSerializer):
    """Minimal serializer for learners in a catalog."""

    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
    )
    catalog = serializers.PrimaryKeyRelatedField(
        queryset=CorporatePartnerCatalog.objects.all(),
        write_only=True,
    )

    class Meta:
        model = CorporatePartnerCatalogLearner
        fields = ["id", "active", "user", "catalog"]
        read_only_fields = ["id"]


class CatalogCourseSerializer(serializers.ModelSerializer):
    """Serializer for courses in a corporate partner catalog."""

    course_overview = serializers.PrimaryKeyRelatedField(
        queryset=CourseOverview.objects.all(),
        write_only=True,
    )
    catalog = serializers.PrimaryKeyRelatedField(
        queryset=CorporatePartnerCatalog.objects.all(),
    )

    course_run = CourseOverviewSimpleSerializer(
        source="course_overview", read_only=True
    )

    class Meta:
        model = CorporatePartnerCatalogCourse
        fields = ["id", "course_overview", "position", "catalog", "course_run"]
        read_only_fields = ["id", "course_run"]
