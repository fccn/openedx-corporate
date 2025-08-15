"""Serializer for Corporate Partner access API v1."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from corporate_partner_access.edxapp_wrapper.course_module import course_overview
from corporate_partner_access.models import (
    CorporatePartner,
    CorporatePartnerCatalog,
    CorporatePartnerCatalogCourse,
    CorporatePartnerCatalogEmailRegex,
    CorporatePartnerCatalogLearner,
)
from flex_catalog.serializers import CourseOverviewSimpleSerializer

User = get_user_model()

CourseOverview = course_overview()


class UserSimpleSerializer(serializers.ModelSerializer):
    """Minimal serializer for user data."""

    class Meta:
        model = User
        fields = ["id", "username", "email"]


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

    email_regexes = serializers.SerializerMethodField()

    class Meta:
        model = CorporatePartnerCatalog
        fields = [
            "id",
            "name",
            "slug",
            "corporate_partner",
            "email_regexes",
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
        read_only_fields = ["id", "email_regexes"]
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

    def get_email_regexes(self, obj):
        return list(obj.email_regexes.all().values_list("regex", flat=True))


class CatalogLearnerSerializer(serializers.ModelSerializer):
    """Minimal serializer for learners in a catalog."""

    user_id = serializers.PrimaryKeyRelatedField(
        source="user",
        queryset=User.objects.all(),
        write_only=True,
    )
    catalog_id = serializers.PrimaryKeyRelatedField(
        source="catalog",
        queryset=CorporatePartnerCatalog.objects.all(),
    )
    user = UserSimpleSerializer(read_only=True)

    class Meta:
        model = CorporatePartnerCatalogLearner
        fields = ["id", "active", "user", "catalog_id", "user_id"]
        read_only_fields = ["id"]


class CatalogCourseSerializer(serializers.ModelSerializer):
    """Serializer for courses in a corporate partner catalog."""

    course_overview = serializers.PrimaryKeyRelatedField(
        queryset=CourseOverview.objects.all(),
        write_only=True,
    )
    catalog_id = serializers.PrimaryKeyRelatedField(
        source="catalog",
        queryset=CorporatePartnerCatalog.objects.all(),
    )
    course_run = CourseOverviewSimpleSerializer(
        source="course_overview", read_only=True
    )

    class Meta:
        model = CorporatePartnerCatalogCourse
        fields = ["id", "course_overview", "position", "catalog_id", "course_run"]
        read_only_fields = ["id", "course_run"]


class CatalogEmailRegexSerializer(serializers.ModelSerializer):
    """Serializer for catalog email regex patterns."""

    catalog_id = serializers.PrimaryKeyRelatedField(
        source="catalog", queryset=CorporatePartnerCatalog.objects.all()
    )

    class Meta:
        model = CorporatePartnerCatalogEmailRegex
        fields = ["id", "catalog_id", "regex"]
        read_only_fields = ["id"]
