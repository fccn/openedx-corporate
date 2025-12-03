"""Serializer for partner catalog API v1."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from flex_catalog.serializers import CourseOverviewSimpleSerializer
from partner_catalog.edxapp_wrapper.course_module import course_overview
from partner_catalog.models import (
    CatalogCourse,
    CatalogCourseEnrollment,
    CatalogLearner,
    CatalogLearnerInvitation,
    Partner,
    PartnerCatalog,
)
from partner_catalog.services.catalog_courses import CatalogCourseService
from partner_catalog.services.catalogs import PartnerCatalogService
from partner_catalog.services.certificates import user_has_certificate
from partner_catalog.services.progress import (
    compute_catalog_completion_rate,
    compute_catalog_course_completion_rate,
    compute_progress_percent_by_user,
)

User = get_user_model()

CourseOverview = course_overview()


class BasicCourseOverviewSerializer(serializers.ModelSerializer):
    """Minimal serializer for CourseOverview with only id and display_name."""

    class Meta:
        model = CourseOverview
        fields = ["id", "display_name"]
        read_only_fields = ["display_name"]


class UserSimpleSerializer(serializers.ModelSerializer):
    """Minimal serializer for user data."""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "full_name", "last_login"]

    def get_full_name(self, obj):
        """Return the user's full name, or username/email if full name is not set."""
        first = getattr(obj, "first_name", "") or ""
        last = getattr(obj, "last_name", "") or ""
        full = (first + " " + last).strip()

        if not full:
            full = getattr(obj, "username", "") or getattr(obj, "email", "") or ""

        return full or None


class PartnerSerializer(serializers.ModelSerializer):
    """Serializer for Partner data."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(source="organization.name", read_only=True)
    slug = serializers.CharField(source="organization.short_name", read_only=True)
    logo = serializers.SerializerMethodField()

    catalogs = serializers.IntegerField(source="catalogs_count", read_only=True)
    courses = serializers.IntegerField(source="courses_count", read_only=True)
    enrollments = serializers.IntegerField(source="learners_count", read_only=True)
    certified = serializers.IntegerField(source="certified_count", read_only=True)

    class Meta:
        model = Partner
        fields = [
            "id",
            "slug",
            "name",
            "homepage_url",
            "logo",
            "catalogs",
            "courses",
            "enrollments",
            "certified",
        ]
        read_only_fields = ["id", "org_id", "org_name", "org_short_name"]
        extra_kwargs = {
            "homepage_url": {"required": False, "allow_null": True},
        }

    def get_logo(self, obj):
        """Return the URL of the corporate partner organization's logo."""
        try:
            if obj.organization and obj.organization.logo:
                return f"{settings.LMS_ROOT_URL}{obj.organization.logo.url}"
        except (ValueError, AttributeError):
            pass
        return None


class SimpleCatalogCourseSerializer(serializers.ModelSerializer):
    """Simplified serializer for courses in a corporate partner catalog."""
    order = serializers.IntegerField(source='position', read_only=True)
    course_key = serializers.SerializerMethodField()

    class Meta:
        model = CatalogCourse
        ordering = ["position"]
        fields = [
            "order",
            "course_key",
        ]

    def get_course_key(self, obj):
        return str(obj.course_overview.id)


class PartnerCatalogSerializer(serializers.ModelSerializer):
    """Serializer for Corporate Partner Catalog data."""

    image = serializers.ImageField(read_only=True)
    email_regexes = serializers.ListField(
        child=serializers.CharField(max_length=500),
        required=False,
        allow_empty=True,
    )
    org = serializers.SerializerMethodField()
    courses = serializers.IntegerField(source="courses_count", read_only=True)
    enrollments = serializers.IntegerField(read_only=True)
    total_learners = serializers.IntegerField(read_only=True)
    active_learners = serializers.IntegerField(read_only=True)
    certified = serializers.IntegerField(source="certified_count", read_only=True)
    completion_rate = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField(read_only=True)

    MANAGER_EDITABLE_FIELDS = [
        "email_regexes",
        "authorization_message",
        "alternative_link",
        "support_email",
    ]

    class Meta:
        model = PartnerCatalog
        fields = [
            "id",
            "name",
            "slug",
            "partner",
            "email_regexes",
            "course_enrollments_limit",
            "user_limit",
            "is_self_enrollment",
            "available_start_date",
            "available_end_date",
            "authorization_message",
            "courses",
            "enrollments",
            "total_learners",
            "active_learners",
            "certified",
            "completion_rate",
            "org",
            "image",
            "status",
            "support_email",
            "alternative_link",
        ]
        read_only_fields = [
            "id",
            "courses",
            "slug",
            "image",
        ]
        extra_kwargs = {
            "authorization_message": {
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

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        if user and (user.is_staff or user.is_superuser):
            return fields

        if request and request.method in ['PUT', 'PATCH']:
            for field_name in fields:
                if field_name not in self.MANAGER_EDITABLE_FIELDS:
                    fields[field_name].read_only = True

        return fields

    def get_org(self, obj):
        return obj.partner.organization.short_name

    def get_email_regexes(self, obj):
        return list(obj.catalog_email_regexes.all().values_list("regex", flat=True))

    def get_completion_rate(self, obj):
        rate_statistics = compute_catalog_completion_rate(obj.id)
        return rate_statistics.get("completion_rate")

    def get_status(self, obj):
        """Return the catalog status for the current user."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        return PartnerCatalogService.get_user_catalog_invitation_status(
            catalog=obj,
            user=request.user
        )

    def update(self, instance, validated_data):
        """Update PartnerCatalog instance, including email regexes."""
        email_regexes = validated_data.pop('email_regexes', None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if email_regexes is not None:
                PartnerCatalogService.update_email_regexes(instance, email_regexes)

        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["email_regexes"] = self.get_email_regexes(instance)
        return data


class CatalogLearnerSerializer(serializers.ModelSerializer):
    """Minimal serializer for learners in a catalog."""

    user_id = serializers.PrimaryKeyRelatedField(
        source="user",
        queryset=User.objects.all(),
        write_only=True,
    )
    catalog_id = serializers.PrimaryKeyRelatedField(
        source="catalog",
        queryset=PartnerCatalog.objects.all(),
        write_only=True,
    )

    user = UserSimpleSerializer(read_only=True)
    active = serializers.BooleanField(read_only=True)
    invite_sent_at = serializers.DateTimeField(
        read_only=True,
        source="current_invitation.invited_at"
    )
    accepted_at = serializers.DateTimeField(
        read_only=True,
        source="current_invitation.accepted_at"
    )
    removed_at = serializers.DateTimeField(
        read_only=True,
        source="current_invitation.removed_at"
    )
    enrollments = serializers.IntegerField(source="enrollments_count", read_only=True)
    certified = serializers.IntegerField(source="certified_count", read_only=True)

    class Meta:
        model = CatalogLearner
        fields = [
            "id",
            "active",
            "user",
            "catalog_id",
            "user_id",
            "invite_sent_at",
            "accepted_at",
            "removed_at",
            "enrollments",
            "certified",
        ]
        read_only_fields = ["id"]


class CatalogCourseSerializer(serializers.ModelSerializer):
    """Serializer for courses in a corporate partner catalog."""

    course_overview = serializers.PrimaryKeyRelatedField(
        queryset=CourseOverview.objects.all(),
        write_only=True,
    )
    catalog_id = serializers.PrimaryKeyRelatedField(
        source="catalog",
        queryset=PartnerCatalog.objects.all(),
    )
    course_run = CourseOverviewSimpleSerializer(
        source="course_overview", read_only=True
    )
    enrollments = serializers.IntegerField(source="enrollments_count", read_only=True)
    certified = serializers.IntegerField(source="certified_count", read_only=True)
    completion_rate = serializers.SerializerMethodField()

    class Meta:
        model = CatalogCourse
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

    def get_fields(self):
        """Make course_overview and catalog_id read-only on update."""
        fields = super().get_fields()

        if self.instance is not None:
            fields["course_overview"].read_only = True
            fields["catalog_id"].read_only = True

        return fields

    def update(self, instance, validated_data):
        """Update catalog course position if changed."""
        new_position = validated_data.get("position")

        if new_position is not None and new_position != instance.position:
            return CatalogCourseService.update_course_position(instance, new_position)

        return super().update(instance, validated_data)

    def get_completion_rate(self, obj):
        rate_statistics = compute_catalog_course_completion_rate(obj.id)
        return rate_statistics.get("completion_rate")


class CatalogLearnerInvitationSerializer(serializers.ModelSerializer):
    """Serializer for CatalogLearnerInvitation data."""

    id = serializers.IntegerField(read_only=True)
    status = serializers.SerializerMethodField()
    catalog_id = serializers.PrimaryKeyRelatedField(
        source="catalog",
        queryset=PartnerCatalog.objects.all(),
    )
    invite_email = serializers.EmailField()

    class Meta:
        model = CatalogLearnerInvitation
        fields = [
            "id",
            "catalog_id",
            "invite_email",
            "invited_at",
            "accepted_at",
            "declined_at",
            "status"
        ]
        read_only_fields = [
            "id",
            "invited_at",
            "accepted_at",
            "declined_at",
        ]

    def get_status(self, obj):
        """Return the display string for the invitation status."""
        return obj.get_status_display()


class CatalogCourseEnrollmentSerializer(serializers.ModelSerializer):
    """Serializer for enrollments in a catalog course."""

    user = UserSimpleSerializer(read_only=True)
    catalog_course = serializers.PrimaryKeyRelatedField(read_only=True)
    course_overview = BasicCourseOverviewSerializer(
        source="catalog_course.course_overview", read_only=True
    )
    progress = serializers.SerializerMethodField()
    has_certificate = serializers.SerializerMethodField()

    class Meta:
        model = CatalogCourseEnrollment
        fields = [
            "id",
            "user",
            "catalog_course",
            "active",
            "progress",
            "course_overview",
            "has_certificate",
        ]
        read_only_fields = ["id", "user", "catalog_course", "course_overview", "has_certificate"]

    def get_progress(self, obj):
        """Return user's progress percent in this course run."""
        key = self._course_key_str(obj)
        if not key:
            return None
        return compute_progress_percent_by_user(course_key_str=key, user=obj.user)

    def get_has_certificate(self, obj):
        """Return whether the user has a certificate for this course run."""
        key = self._course_key_str(obj)
        if not key:
            return False
        return user_has_certificate(course_id=key, user_id=obj.user.id)

    def _course_key_str(self, obj):
        co = getattr(obj.catalog_course, "course_overview", None)
        return str(co.id)


class InvitationActionSerializer(serializers.Serializer):
    """
    Input schema for invitation action endpoints (accept/decline/remove).
    No fields required as these actions only use the invitation ID from the URL.
    Kept for future extensibility (e.g., consent flags, reason for revocation).
    """

    id = serializers.IntegerField(read_only=True)
    status = serializers.SerializerMethodField(read_only=True)
    catalog_id = serializers.IntegerField(read_only=True)
    invite_email = serializers.EmailField(read_only=True)

    def create(self, validated_data):
        """No-op: this serializer is not used to create DB objects."""
        return validated_data

    def update(self, instance, validated_data):
        """No-op: this serializer does not mutate instances directly."""
        return instance

    def get_status(self, obj):
        """Return the display string for the invitation status."""
        return obj.get_status_display()


class BulkRemoveInvitationSerializer(serializers.Serializer):
    """Serializer for bulk removal of invitations."""

    learner_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        help_text="List of CatalogLearner IDs to remove"
    )

    def create(self, validated_data):
        """No-op: this serializer is not used to create DB objects."""
        return validated_data

    def update(self, instance, validated_data):
        """No-op: this serializer does not mutate instances directly."""
        return instance


class LearnerPartnerCatalogSerializer(serializers.ModelSerializer):
    """
    Serializer for catalogs from the learner's perspective.

    Provides essential catalog information without management fields.
    Includes status, enrollment info, and user-specific data.
    """
    partner = PartnerSerializer()
    steps = SimpleCatalogCourseSerializer(
        source='catalog_courses',
        many=True,
        read_only=True,
    )
    image = serializers.ImageField(read_only=True)
    courses = serializers.IntegerField(source="courses_count", read_only=True)
    enrollments = serializers.IntegerField(source="total_enrollments", read_only=True)
    status = serializers.SerializerMethodField(read_only=True)
    is_manager = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PartnerCatalog
        fields = [
            "id",
            "name",
            "slug",
            "partner",
            "image",
            "is_self_enrollment",
            "available_start_date",
            "available_end_date",
            "authorization_message",
            "user_limit",
            "course_enrollments_limit",
            "courses",
            "enrollments",
            "status",
            "is_manager",
            "steps",
        ]
        read_only_fields = fields

    def get_status(self, obj):
        """
        Check the invitation status for the requesting user on this catalog.
        """
        request = self.context.get("request")
        if not request or not request.user:
            return None

        return PartnerCatalogService.get_user_catalog_invitation_status(
            catalog=obj,
            user=request.user
        )

    def get_is_manager(self, obj):
        """
        Checks if the requesting user is a manager of this catalog.
        """
        request = self.context.get("request")
        if not request or not request.user:
            return False

        return PartnerCatalogService.is_user_catalog_manager(
            catalog=obj,
            user=request.user
        )


class LearnerCatalogCourseSerializer(serializers.ModelSerializer):
    """
    Serializer for catalog courses from the learner's perspective.
    """

    catalog_id = serializers.IntegerField(source="catalog.id", read_only=True)
    course_run = CourseOverviewSimpleSerializer(source="course_overview", read_only=True)
    enrollments = serializers.IntegerField(source="enrollments_count", read_only=True)

    class Meta:
        model = CatalogCourse
        fields = [
            "id",
            "catalog_id",
            "course_run",
            "enrollments",
            "position",
        ]
        read_only_fields = fields
