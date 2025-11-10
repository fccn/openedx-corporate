"""Serializer for partner catalog API v1."""

from __future__ import annotations

from django.db.models import Q
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers

from flex_catalog.serializers import CourseOverviewSimpleSerializer
from partner_catalog.edxapp_wrapper.course_module import course_overview
from partner_catalog.models import (
    CatalogCourse,
    CatalogCourseEnrollment,
    CatalogEmailRegex,
    CatalogLearner,
    CatalogLearnerInvitation,
    Partner,
    PartnerCatalog,
    CatalogManager,
)
from partner_catalog.services.assessments import get_assessments_counts
from partner_catalog.services.progress import (
    compute_catalog_completion_rate,
    compute_catalog_course_completion_rate,
    compute_progress_percent_by_user,
)

User = get_user_model()

CourseOverview = course_overview()


class UserSimpleSerializer(serializers.ModelSerializer):
    """Minimal serializer for user data."""

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "full_name"]

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


class PartnerCatalogSerializer(serializers.ModelSerializer):
    """Serializer for Corporate Partner Catalog data."""

    partner = serializers.PrimaryKeyRelatedField(
        queryset=Partner.objects.all()
    )
    
    image = serializers.ImageField(read_only=True)
    email_regexes = serializers.SerializerMethodField()
    org = serializers.SerializerMethodField()
    courses = serializers.IntegerField(source="courses_count", read_only=True)
    enrollments = serializers.IntegerField(source="total_enrollments", read_only=True)
    certified = serializers.IntegerField(source="certified_count", read_only=True)
    completion_rate = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField(read_only=True)
    is_manager = serializers.SerializerMethodField(read_only=True)

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
            "certified",
            "completion_rate",
            "org",
            "image",
            "status",
            "is_manager",
        ]
        read_only_fields = [
            "id",
            "email_regexes",
            "courses",
            "slug",
            "image",
            "status",
            "is_manager",
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

    def get_org(self, obj):
        return obj.partner.organization.short_name

    def get_email_regexes(self, obj):
        return list(obj.catalog_email_regexes.all().values_list("regex", flat=True))

    def get_completion_rate(self, obj):
        rate_statistics = compute_catalog_completion_rate(obj.id)
        return rate_statistics.get("completion_rate")

    def get_status(self, obj):
        """
        Returns the current invitation status for the requesting user on this catalog.

        If there is no invitation for the user (by user FK or by their email), returns None.
        If multiple invitations exist, returns the most recent one (by invited_at).
        """
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return None

        user = request.user
        email = getattr(user, "email", None)

        qs = CatalogLearnerInvitation.objects.filter(catalog=obj)
        if email:
            qs = qs.filter(Q(user=user) | Q(invite_email__iexact=email))
        else:
            qs = qs.filter(user=user)

        inv = qs.select_related("user").order_by("-invited_at").first()

        if not inv:
            return None

        return inv.get_status_display()

    def get_is_manager(self, obj):
        """
        Returns True if the current user is an active CatalogManager for this catalog.
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        user = request.user
        return CatalogManager.objects.filter(
            catalog=obj, user=user, active=True
        ).exists()


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

    def get_completion_rate(self, obj):
        rate_statistics = compute_catalog_course_completion_rate(obj.id)
        return rate_statistics.get("completion_rate")


class CatalogEmailRegexSerializer(serializers.ModelSerializer):
    """Serializer for catalog email regex patterns."""

    catalog_id = serializers.PrimaryKeyRelatedField(
        source="catalog", queryset=PartnerCatalog.objects.all()
    )

    class Meta:
        model = CatalogEmailRegex
        fields = ["id", "catalog_id", "regex"]
        read_only_fields = ["id"]


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
    progress = serializers.SerializerMethodField()
    completed_assessments = serializers.SerializerMethodField()
    pending_assessments = serializers.SerializerMethodField()

    class Meta:
        model = CatalogCourseEnrollment
        fields = [
            "id",
            "user",
            "catalog_course",
            "active",
            "progress",
            "completed_assessments",
            "pending_assessments",
        ]
        read_only_fields = ["id", "user", "catalog_course"]

    def get_progress(self, obj):
        """Return user's progress percent in this course run."""
        key = self._course_key_str(obj)
        if not key:
            return None
        return compute_progress_percent_by_user(course_key_str=key, user=obj.user)

    def get_completed_assessments(self, obj):
        """Return count of completed graded assessments for this user in this course run."""
        key = self._course_key_str(obj)
        if not key:
            return None
        result = get_assessments_counts(key, obj.user)
        return result.get("completed")

    def get_pending_assessments(self, obj):
        """Return count of pending graded assessments for this user in this course run."""
        key = self._course_key_str(obj)
        if not key:
            return None
        result = get_assessments_counts(key, obj.user)
        return result.get("pending")

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
