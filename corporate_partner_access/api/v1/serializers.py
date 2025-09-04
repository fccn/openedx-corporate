"""Serializer for Corporate Partner access API v1."""
from __future__ import annotations

import random
from typing import Any, Dict, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from corporate_partner_access.edxapp_wrapper.course_module import course_overview
from corporate_partner_access.models import (
    CatalogCourseEnrollmentAllowed,
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

    logo = serializers.SerializerMethodField()
    catalogs = serializers.IntegerField(source="catalogs_count", read_only=True)
    courses = serializers.IntegerField(source="courses_count", read_only=True)

    # TODO: Replace implementation
    enrollments = serializers.SerializerMethodField()
    certified = serializers.SerializerMethodField()

    class Meta:
        model = CorporatePartner
        fields = [
            "id",
            "code",
            "name",
            "homepage_url",
            "logo",
            "catalogs",
            "courses",
            "enrollments",
            "certified",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "homepage_url": {"required": False, "allow_null": True},
            "logo": {"required": False, "allow_null": True, "write_only": True},
        }

    def get_logo(self, obj):
        """Return the URL of the corporate partner's logo."""
        try:
            return f"{settings.LMS_ROOT_URL}{obj.logo.url}"
        except (ValueError, AttributeError):
            return None

    # TODO: Replace implementation
    def get_enrollments(self, obj):  # pylint: disable=unused-argument
        """Mocked enrollments count. Replace with real implementation."""
        return random.randint(0, 10000)

    def get_certified(self, obj):  # pylint: disable=unused-argument
        """Mocked certified count. Replace with real implementation."""
        return random.randint(0, 5000)


class CorporatePartnerCatalogSerializer(serializers.ModelSerializer):
    """Serializer for Corporate Partner Catalog data."""

    corporate_partner = serializers.PrimaryKeyRelatedField(
        queryset=CorporatePartner.objects.all()
    )

    email_regexes = serializers.SerializerMethodField()
    courses = serializers.IntegerField(source="courses_count", read_only=True)

    # TODO: Replace implementation
    enrollments = serializers.SerializerMethodField()
    certified = serializers.SerializerMethodField()
    completion_rate = serializers.SerializerMethodField()

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
            "courses",
            "enrollments",
            "certified",
            "completion_rate",
        ]
        read_only_fields = [
            "id",
            "email_regexes",
            "courses",
        ]
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

    # TODO: Replace implementation
    def get_enrollments(self, obj):  # pylint: disable=unused-argument
        """Mocked enrollments count. Replace with real implementation."""
        return random.randint(0, 10000)

    def get_certified(self, obj):  # pylint: disable=unused-argument
        """Mocked certified count. Replace with real implementation."""
        return random.randint(0, 5000)

    def get_completion_rate(self, obj):  # pylint: disable=unused-argument
        """Mocked completion rate. Replace with real implementation."""
        return random.randint(0, 100)


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

    # TODO: Replace implementation
    enrollments = serializers.SerializerMethodField()
    certified = serializers.SerializerMethodField()
    completion_rate = serializers.SerializerMethodField()

    class Meta:
        model = CorporatePartnerCatalogCourse
        fields = [
            "id",
            "course_overview",
            "position",
            "catalog_id",
            "course_run",
            "enrollments",
            "certified",
            "completion_rate",
        ]
        read_only_fields = ["id"]

    # TODO: Replace implementation
    def get_enrollments(self, obj):  # pylint: disable=unused-argument
        """Mocked enrollments count. Replace with real implementation."""
        return random.randint(0, 10000)

    def get_certified(self, obj):  # pylint: disable=unused-argument
        """Mocked certified count. Replace with real implementation."""
        return random.randint(0, 5000)

    def get_completion_rate(self, obj):  # pylint: disable=unused-argument
        """Mocked completion rate. Replace with real implementation."""
        return random.randint(0, 100)


class CatalogEmailRegexSerializer(serializers.ModelSerializer):
    """Serializer for catalog email regex patterns."""

    catalog_id = serializers.PrimaryKeyRelatedField(
        source="catalog", queryset=CorporatePartnerCatalog.objects.all()
    )

    class Meta:
        model = CorporatePartnerCatalogEmailRegex
        fields = ["id", "catalog_id", "regex"]
        read_only_fields = ["id"]


class CatalogCourseEnrollmentAllowedSerializer(serializers.ModelSerializer):
    """Read serializer."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    catalog_course = serializers.PrimaryKeyRelatedField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    invited_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = CatalogCourseEnrollmentAllowed
        fields = [
            "id",
            "catalog_course",
            "user",
            "invite_email",
            "status",
            "status_display",
            "invited_by",
            "invited_at",
            "status_changed_at",
            "accepted_at",
            "declined_at",
        ]
        read_only_fields = [
            "id",
            "catalog_course",
            "user",
            "invited_by",
            "invited_at",
            "status_changed_at",
            "accepted_at",
            "declined_at",
            "status_display",
        ]


class CatalogCourseEnrollmentAllowedCreateSerializer(serializers.ModelSerializer):
    """
    Create serializer (only accepts `email`).

    - Normalizes `email` to lowercase.
    - If a user exists with that email, attach it to the invite.
    - Idempotent on (catalog_course, email).
    """

    email = serializers.EmailField(write_only=True)

    class Meta:
        model = CatalogCourseEnrollmentAllowed
        fields = ["email"]

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        email = attrs.get("email", "").strip().lower()
        if not email:
            raise serializers.ValidationError({"email": "This field is required."})
        attrs["email"] = email
        return attrs

    @transaction.atomic
    def create(self, validated_data: Dict[str, Any]) -> CatalogCourseEnrollmentAllowed:
        request = self.context.get("request")
        catalog_course: CorporatePartnerCatalogCourse = self.context["catalog_course"]

        email: str = validated_data["email"]

        user: Optional[User] = User.objects.filter(email__iexact=email).first()

        obj, created = CatalogCourseEnrollmentAllowed.objects.get_or_create(
            catalog_course=catalog_course,
            invite_email=email,
            defaults={
                "user": user,
                "invited_by": request.user if request and request.user.is_authenticated else None,
                "status": CatalogCourseEnrollmentAllowed.Status.SENT,
            },
        )

        # If it existed and we just found the user, attach it now.
        if not created and user and obj.user_id is None:
            obj.user = user
            obj.save(update_fields=["user"])

        return obj


class InvitationSelfActionSerializer(serializers.Serializer):
    """
    Input schema for accept/decline endpoints.
    No fields for now; kept for future extensibility (e.g., consent flags).
    """

    def create(self, validated_data):
        """No-op: this serializer is not used to create DB objects."""
        return validated_data

    def update(self, instance, validated_data):
        """No-op: this serializer does not mutate instances directly."""
        return instance
