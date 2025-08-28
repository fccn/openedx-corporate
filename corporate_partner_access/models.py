"""Models for managing course catalogs and access for corporate partners."""

import regex
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from corporate_partner_access.edxapp_wrapper.course_module import course_overview
from corporate_partner_access.helpers.current_user import safe_get_current_user
from corporate_partner_access.services.allowed_courses import CatalogAllowedCoursesService
from flex_catalog.models import FlexibleCatalogModel


class CorporatePartner(models.Model):
    """Company that manages one or more course catalogs."""

    id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to="partner_logos/", blank=True, null=True)
    homepage_url = models.URLField(blank=True, null=True)

    class Meta:
        """Meta options for CorporatePartner model."""

        verbose_name = "Corporate Partner"
        verbose_name_plural = "Corporate Partners"
        ordering = ["name"]

    def __str__(self):
        """Return a string representation of the CorporatePartner instance."""
        return f"<CorporatePartner: {self.name} (Code: {self.code})>"


class CorporatePartnerCatalog(FlexibleCatalogModel):
    """Catalog model for corporate partners."""

    corporate_partner = models.ForeignKey(
        "CorporatePartner",
        on_delete=models.CASCADE,
        related_name="catalogs",
    )
    course_enrollment_limit = models.PositiveIntegerField(
        default=0, help_text="Max enrollments allowed in this catalog."
    )
    user_limit = models.PositiveIntegerField(
        default=0, help_text="Max users allowed in this catalog."
    )
    is_self_enrollment = models.BooleanField(default=False)
    available_start_date = models.DateTimeField(null=True, blank=True)
    available_end_date = models.DateTimeField(null=True, blank=True)
    custom_courses = models.BooleanField(
        default=False, help_text="If True, allows custom courses."
    )
    authorization_additional_message = models.TextField(blank=True, null=True)
    support_email = models.EmailField(blank=True, null=True)
    is_public = models.BooleanField(default=False)
    catalog_alternative_link = models.URLField(blank=True, null=True)

    courses = models.ManyToManyField(
        course_overview(),
        through="CorporatePartnerCatalogCourse",
        related_name="partner_catalogs",
    )

    learners = models.ManyToManyField(
        get_user_model(),
        through="CorporatePartnerCatalogLearner",
        related_name="enrolled_catalogs",
    )

    class Meta:
        """Meta options for CorporatePartnerCatalog model."""

        verbose_name = "Corporate Partner Catalog"
        verbose_name_plural = "Corporate Partner Catalogs"
        ordering = ["name"]

    def get_course_runs(self):
        """Return all catalog course runs associated with this instance."""
        user = safe_get_current_user()
        return CatalogAllowedCoursesService.course_runs_for_user(catalog=self, user=user)


class CorporatePartnerCatalogEmailRegex(models.Model):
    """Regex pattern for validating emails for a partner's catalog."""

    id = models.AutoField(primary_key=True)
    catalog = models.ForeignKey(
        "CorporatePartnerCatalog",
        on_delete=models.CASCADE,
        related_name="email_regexes",
    )
    regex = models.CharField(
        max_length=500, help_text="Regex pattern for email validation."
    )

    def __str__(self):
        """Return a string representation of the CorporatePartnerCatalogEmailRegex instance."""
        return (
            f"<CorporatePartnerCatalogEmailRegex: {self.catalog.name} - {self.regex}>"
        )

    def clean(self):
        """Validate and normalize the regex pattern."""
        pattern = (self.regex or "").strip()
        if not pattern:
            raise ValidationError("Regex pattern cannot be empty.")

        # Detects if the regex contains nested quantifiers or multiple consecutive wildcards.
        if regex.search(r'\((?:\.\*|\.\+)\)[*+{]|(\.\*.*\.\*)|(\.\+.*\.\+)', pattern):
            raise ValidationError(f"Invalid regex, nested quantifiers detected: {pattern}")

        pattern = pattern.lstrip("^").rstrip("$")
        pattern = f"^{pattern}$"

        try:
            regex.compile(pattern)
        except regex.error as exc:
            raise ValidationError(f"Invalid regex pattern: {pattern} ({exc})") from exc

        self.regex = pattern

    def save(self, *args, **kwargs):
        """Ensure clean is called before saving."""
        self.clean()
        super().save(*args, **kwargs)


class CorporatePartnerCatalogCourse(models.Model):
    """Pivot table linking catalogs to courses with ordering."""

    id = models.AutoField(primary_key=True)
    catalog = models.ForeignKey("CorporatePartnerCatalog", on_delete=models.CASCADE)
    course_overview = models.ForeignKey(course_overview(), on_delete=models.CASCADE)
    position = models.PositiveIntegerField(
        default=0, help_text="Ordering of the course within the catalog."
    )

    class Meta:
        """Meta options for CorporatePartnerCatalogCourse model."""

        verbose_name = "Corporate Partner Catalog Course"
        verbose_name_plural = "Corporate Partner Catalog Courses"
        unique_together = ("catalog", "course_overview")
        ordering = ["position"]
        indexes = [
            models.Index(fields=["catalog", "course_overview"], name="catalog_course_idx"),
        ]

    def __str__(self):
        """Return string representation of the CorporatePartnerCatalogCourse instance."""
        return f"<CorporatePartnerCatalogCourse: {self.course_overview.id}>"  # pylint: disable=no-member


class CorporatePartnerCatalogLearner(models.Model):
    """Pivot table linking catalogs to users with active status."""

    id = models.AutoField(primary_key=True)
    catalog = models.ForeignKey("CorporatePartnerCatalog", on_delete=models.CASCADE)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    active = models.BooleanField(default=True)

    class Meta:
        """Meta options for CorporatePartnerCatalogLearner model."""

        verbose_name = "Corporate Partner Catalog Learner"
        verbose_name_plural = "Corporate Partner Catalog Learners"
        unique_together = ("catalog", "user")

    # pylint: disable=no-member
    def __str__(self):
        """Return a string representation of the CorporatePartnerCatalogLearner instance."""
        return f"<CorporatePartnerCatalogLearner: {self.user.username} in {self.catalog.name}>"


class CatalogCourseEnrollmentAllowed(models.Model):
    """
    Invitation to enroll in a specific course within a corporate partner catalog.

    Tracks invitations sent to users (by email) to enroll in a catalog course,
    their status (sent, accepted, declined), and metadata such as who invited
    them and when the status changed. The `user` field may be null if the
    invitee does not yet have an account; it will be set when a user with the
    `invite_email` accepts or declines the invitation.
    """

    class Status(models.IntegerChoices):
        """Possible invitation statuses."""

        SENT = 10, "Sent"
        ACCEPTED = 20, "Accepted"
        DECLINED = 30, "Declined"

    id = models.AutoField(primary_key=True)
    catalog_course = models.ForeignKey(
        "CorporatePartnerCatalogCourse",
        on_delete=models.PROTECT,
        related_name="enrollment_invites",
    )
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text=(
            "Linked user. May be null if no user exists for invite_email; "
            "will be set once a user with this email accepts/declines."
        ),
        related_name="catalog_course_invites",
    )

    status = models.PositiveSmallIntegerField(
        choices=Status.choices,
        default=Status.SENT,
        help_text="Status of the course enrollment invitation."
    )

    invite_email = models.EmailField(
        null=True,
        blank=True,
        help_text="Invitation email address."
    )

    invited_at = models.DateTimeField(auto_now_add=True)
    status_changed_at = models.DateTimeField(auto_now=True)

    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)

    invited_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_enrollment_invites",
        help_text="Who created/sent the invite."
    )

    class Meta:
        """Database metadata and constraints for invitations."""

        db_table = "cp_course_enrl_allowed"
        indexes = [
            models.Index(Lower("invite_email"), name="cpcea_email_ci_idx"),
            models.Index(fields=["user"], name="cpcea_user_idx"),
            models.Index(fields=["catalog_course", "status"], name="cpcea_course_status_idx"),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["catalog_course", "user"],
                name="cpcea_unique_course_user",
                condition=models.Q(user__isnull=False),
            ),
            models.UniqueConstraint(
                Lower("invite_email"), "catalog_course",
                name="cpcea_unique_course_invite_email_ci",
                condition=models.Q(invite_email__isnull=False),
            ),
            models.CheckConstraint(
                check=models.Q(user__isnull=False) | models.Q(invite_email__isnull=False),
                name="cpcea_user_or_email_required",
            ),
            models.CheckConstraint(
                check=(
                    (
                        models.Q(status=10)
                        & models.Q(accepted_at__isnull=True)
                        & models.Q(declined_at__isnull=True)
                    )
                    | (
                        models.Q(status=20)
                        & models.Q(accepted_at__isnull=False)
                        & models.Q(declined_at__isnull=True)
                    )
                    | (
                        models.Q(status=30)
                        & models.Q(declined_at__isnull=False)
                        & models.Q(accepted_at__isnull=True)
                    )
                ),
                name="cpcea_status_timestamp_consistency",
            ),
        ]

    def save(self, *args, **kwargs):
        """
        Keep accepted_at / declined_at consistent with status.

        Rules:
          - SENT:      accepted_at = NULL, declined_at = NULL
          - ACCEPTED:  accepted_at = now() if missing, declined_at = NULL
          - DECLINED:  declined_at = now() if missing, accepted_at = NULL
        """
        now = timezone.now()
        touched_fields: set[str] = set()

        old_status = getattr(self, "_old_status", None)
        if old_status is None and self.pk:
            try:
                old_status = type(self).objects.only("status").get(pk=self.pk).status
            except type(self).DoesNotExist:
                old_status = None

        if self.status == self.Status.ACCEPTED:
            desired = {
                "accepted_at": self.accepted_at or now,
                "declined_at": None,
            }
        elif self.status == self.Status.DECLINED:
            desired = {
                "accepted_at": None,
                "declined_at": self.declined_at or now,
            }
        else:
            desired = {
                "accepted_at": None,
                "declined_at": None,
            }

        for field, value in desired.items():
            if getattr(self, field) != value:
                setattr(self, field, value)
                touched_fields.add(field)

        status_changed = (old_status is not None and old_status != self.status)
        if status_changed:
            touched_fields.add("status_changed_at")

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            uf = set(update_fields)
            if touched_fields:
                uf |= touched_fields
            if "status_changed_at" in touched_fields:
                uf.add("status_changed_at")
            kwargs["update_fields"] = list(uf)

        super().save(*args, **kwargs)

    def __str__(self):
        """Return a readable label with course id, target email/user, and status."""
        target = self.invite_email or getattr(self.user, "email", None) or "unknown"
        return f"{self.catalog_course_id} → {target} [{self.get_status_display()}]"
