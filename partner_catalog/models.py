"""Models for managing course catalogs and access for corporate partners."""

import regex
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from organizations.models import Organization

from flex_catalog.models import FlexibleCatalogModel
from partner_catalog.edxapp_wrapper.course_module import course_overview
from partner_catalog.helpers.current_user import safe_get_current_user
from partner_catalog.services.allowed_courses import CatalogAllowedCoursesService


class Partner(models.Model):
    """
    Partner model representing a corporate partner organization.
    """

    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="partner_profile"
    )
    homepage_url = models.URLField(blank=True, null=True)

    class Meta:
        """Meta options for Partner model."""

        verbose_name = "Corporate Partner"
        verbose_name_plural = "Corporate Partners"
        ordering = ["organization__short_name"]

    def __str__(self):
        """Return a string representation of the Partner instance."""
        return f"Partner for {self.organization.short_name}"


class PartnerCatalog(FlexibleCatalogModel):
    """Catalog model for corporate partners."""

    partner = models.ForeignKey(
        "Partner",
        on_delete=models.CASCADE,
        related_name="catalogs",
    )
    course_enrollments_limit = models.PositiveIntegerField(
        default=0, help_text="Limit of enrollments per course."
    )
    user_limit = models.PositiveIntegerField(
        default=0, help_text="Limit for the number of users that can enroll."
    )
    is_self_enrollment = models.BooleanField(default=False)
    available_start_date = models.DateTimeField()
    available_end_date = models.DateTimeField()
    authorization_message = models.TextField(blank=True, null=True)

    class Meta:
        """Meta options for PartnerCatalog model."""

        verbose_name = "Partner Catalog"
        verbose_name_plural = "Partner Catalogs"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        """Save and generate a slug for the partner catalog."""
        current_slug = self.slug

        if not current_slug:
            name_value = str(self.name or "catalog")
            org_slug = slugify(self.partner.organization.short_name)
            base_slug = f"{org_slug}-{slugify(name_value)}"
            current_slug = base_slug

            existing_count = PartnerCatalog.objects.filter(
                slug__startswith=current_slug
            ).count()

            if existing_count > 0:
                current_slug = f"{base_slug}-{existing_count + 1}"

            self.slug = current_slug
        super().save(*args, **kwargs)

    @property
    def active(self):
        """
        Check if the catalog is currently active based on availability dates.

        Returns:
            bool: True if current time is within the availability window, False otherwise.
        """
        now = timezone.now()
        return self.available_start_date <= now <= self.available_end_date

    def get_course_runs(self):
        """Return all catalog course runs associated with this instance."""
        user = safe_get_current_user()
        return CatalogAllowedCoursesService.course_runs_for_user(
            catalog=self, user=user
        )


class CatalogEmailRegex(models.Model):
    """Regex pattern for validating emails for a partner's catalog."""

    id = models.AutoField(primary_key=True)
    catalog = models.ForeignKey(
        "PartnerCatalog",
        on_delete=models.CASCADE,
        related_name="catalog_email_regexes",
    )
    regex = models.CharField(
        max_length=500, help_text="Regex pattern for email validation."
    )

    def __str__(self):
        """Return a string representation of the CatalogEmailRegex instance."""
        return f"<CatalogEmailRegex: {self.regex}>"

    def clean(self):
        """Validate and normalize the regex pattern."""
        pattern = (self.regex or "").strip()
        if not pattern:
            raise ValidationError("Regex pattern cannot be empty.")

        # Detects if the regex contains nested quantifiers or multiple consecutive wildcards.
        if regex.search(r"\((?:\.\*|\.\+)\)[*+{]|(\.\*.*\.\*)|(\.\+.*\.\+)", pattern):
            raise ValidationError(
                f"Invalid regex, nested quantifiers detected: {pattern}"
            )

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


class CatalogCourse(models.Model):
    """Represents a course included in a Partner Catalog."""

    id = models.AutoField(primary_key=True)
    catalog = models.ForeignKey(
        "PartnerCatalog",
        on_delete=models.CASCADE,
        related_name="catalog_courses",
    )
    course_overview = models.ForeignKey(course_overview(), on_delete=models.CASCADE)
    position = models.PositiveIntegerField(
        default=0, help_text="Ordering of the course within the catalog."
    )

    class Meta:
        """Meta options for CatalogCourse model."""

        verbose_name = "Catalog Course"
        verbose_name_plural = "Catalog Courses"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["catalog", "course_overview"],
                name="pcc_unique_catalog_course",
            )
        ]
        indexes = [
            models.Index(
                fields=["catalog", "course_overview"], name="catalog_course_idx"
            ),
        ]

    def __str__(self):
        """Return string representation of the CatalogCourse instance."""
        return f"<CatalogCourse: {self.course_overview.id}>"  # pylint: disable=no-member


class CatalogManager(models.Model):
    """
    Represents a manager assigned to a Partner Catalog.

    A CatalogManager is a user who has management permissions for a specific
    PartnerCatalog, allowing them to oversee catalog operations and configurations.
    A user can only manage catalogs from a single partner organization.
    """

    id = models.AutoField(primary_key=True)
    catalog = models.ForeignKey(
        "PartnerCatalog",
        on_delete=models.CASCADE,
        related_name="catalog_managers",
    )
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    active = models.BooleanField(default=True)

    class Meta:
        """Meta options for CatalogManager model."""

        verbose_name = "Catalog Manager"
        verbose_name_plural = "Catalog Managers"
        constraints = [
            models.UniqueConstraint(
                fields=["catalog", "user"],
                name="pcm_unique_catalog_manager",
            )
        ]
        indexes = [models.Index(fields=["catalog", "user"])]

    def clean(self):
        """Validate that the user does not manage catalogs from different partners."""
        super().clean()

        if self.user_id and self.catalog_id:
            partner_id = self.catalog.partner_id
            conflicting = (
                CatalogManager.objects.filter(user_id=self.user_id)
                .exclude(pk=self.pk)  # Exclude self when updating
                .exclude(catalog__partner_id=partner_id)
                .exists()
            )
            if conflicting:
                raise ValidationError({
                    'catalog': 'This user already manages catalogs from a different partner organization.'
                })

    def save(self, *args, **kwargs):
        """Ensure clean is called before saving."""
        self.clean()
        super().save(*args, **kwargs)

    # pylint: disable=no-member
    def __str__(self):
        """Return a string representation of the CatalogManager instance."""
        return f"<CatalogManager: {self.user.username} in {self.catalog.name}>"


class CatalogLearner(models.Model):
    """
    Represents a learner enrolled in a Partner Catalog.

    Tracks active/inactive status and links to the user and catalog.
    A Learner in the catalog is created once the user accepts an invitation to join
    the catalog in CatalogLearnerInvitation.
    """

    id = models.AutoField(primary_key=True)
    catalog = models.ForeignKey(
        "PartnerCatalog",
        on_delete=models.CASCADE,
        related_name="catalog_learners",
    )
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    current_invitation = models.OneToOneField(
        "CatalogLearnerInvitation",
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        related_name="current_for_learner",
    )

    class Meta:
        """Meta options for CatalogLearner model."""

        verbose_name = "Catalog Learner"
        verbose_name_plural = "Catalog Learners"
        constraints = [
            models.UniqueConstraint(
                fields=["catalog", "user"],
                name="pcl_unique_catalog_learner",
            )
        ]
        indexes = [models.Index(fields=["catalog", "user"])]

    def clean(self):
        """Validate the consistency with the current_invitation status."""
        super().clean()

        invitation = self.current_invitation
        if not invitation:
            raise ValidationError({
                'current_invitation': 'A learner must have a current invitation assigned.'
            })
        if invitation.catalog_id != self.catalog_id or invitation.user_id != self.user_id:
            raise ValidationError({
                'current_invitation': 'Current invitation record must match the catalog and user of this learner.'
            })

    def _compute_active(self):
        """Compute the active status based on current_invitation."""
        invitation = self.current_invitation
        return bool(invitation and invitation.status == CatalogLearnerInvitation.Status.ACCEPTED)

    def save(self, *args, **kwargs):
        """Save and update active status."""
        self.active = self._compute_active()
        super().save(*args, **kwargs)

    # pylint: disable=no-member
    def __str__(self):
        """Return a string representation of the CatalogLearner instance."""
        return f"<CatalogLearner: {self.user.username} in {self.catalog.name}>"


class CatalogLearnerInvitation(models.Model):
    """
    Represent an invitation record for a learner to join a Partner Catalog.

    Tracks invitation, acceptance, declination and removal timestamps, along with
    the user and catalog involved.
    """

    class Status(models.IntegerChoices):
        """Possible Learner invitation statuses."""

        SENT = 10, "Sent"
        ACCEPTED = 20, "Accepted"
        DECLINED = 30, "Declined"
        REMOVED = 40, "Removed"

    id = models.AutoField(primary_key=True)
    catalog = models.ForeignKey("PartnerCatalog", on_delete=models.CASCADE)
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="learner_invitations",
        null=True,
        blank=True,
    )

    # Invitation / consent
    invite_email = models.EmailField(
        null=True,
        blank=True,
        help_text="Email address to which the invitation was sent.",
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    invited_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_learner_invitations",
    )

    # Revocation
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="removed_learner_invitations",
    )

    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)

    status = models.PositiveSmallIntegerField(
        choices=Status.choices,
        default=Status.SENT,
        help_text="Current status of the learner invitation.",
    )

    # Invitation History link
    learner = models.ForeignKey(
        "CatalogLearner",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitation_history",
    )

    class Meta:
        """Meta options for CatalogLearnerInvitation model."""

        verbose_name = "Catalog Learner Invitation"
        verbose_name_plural = "Catalog Learner Invitations"
        indexes = [
            models.Index(fields=["catalog", "user"]),
            models.Index(fields=["catalog", "invited_at"]),
            models.Index(fields=["accepted_at"]),
            models.Index(fields=["declined_at"]),
            models.Index(fields=["removed_at"]),
        ]
        constraints = [
            # Can't be accepted and declined simultaneously
            models.CheckConstraint(
                name="cla_not_both_accepted_and_declined",
                check=~(models.Q(accepted_at__isnull=False) & models.Q(declined_at__isnull=False)),
            ),
            # If removed, it must have been accepted before
            models.CheckConstraint(
                name="cla_removed_implies_accepted",
                check=models.Q(removed_at__isnull=True) | models.Q(accepted_at__isnull=False),
            ),
        ]

    def _compute_status(self):
        """Compute the current status based on timestamps."""
        if self.removed_at:
            return self.Status.REMOVED
        if self.declined_at:
            return self.Status.DECLINED
        if self.accepted_at:
            return self.Status.ACCEPTED
        return self.Status.SENT

    def save(self, *args, **kwargs):
        """Compute the current status based on timestamps before saving."""
        self.status = self._compute_status()
        super().save(*args, **kwargs)

    def __str__(self):
        """Return a string representation of the CatalogLearnerInvitation instance."""
        return f"<CatalogLearnerInvitation: {self.invite_email} in {self.catalog.slug} ({self.get_status_display()})>"


class CatalogCourseEnrollment(models.Model):
    """
    Represents a user's enrollment in a specific catalog course.

    Tracks active/inactive status, invitation and acceptance timestamps, and
    links to the user and catalog course.

    Used to manage and enforce enrollment limits and statuses within a corporate
    partner catalog.
    """

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="catalog_course_enrollments",
    )
    catalog_course = models.ForeignKey(
        "CatalogCourse",
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    active = models.BooleanField(default=True)

    class Meta:
        """Meta options for CatalogCourseEnrollment model."""

        constraints = [
            models.UniqueConstraint(
                fields=["user", "catalog_course"],
                name="pcce_unique_user_catalog_course_enrollment",
            )
        ]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["catalog_course"]),
            models.Index(fields=["user", "active"]),
        ]

    def clean(self):
        """Validate that the user is a learner in the catalog before enrolling."""
        if self.user and self.catalog_course:
            catalog = self.catalog_course.catalog
            is_active_learner = CatalogLearner.objects.filter(
                catalog=catalog,
                user=self.user,
                active=True
            ).exists()

            if not is_active_learner:
                raise ValidationError({
                    'user': 'User must be an active learner in the catalog to enroll in its courses.'
                })

    def save(self, *args, **kwargs):
        """Ensure validation runs before saving."""
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        """Return a readable string representation of the CatalogCourseEnrollment instance."""
        state = "active" if self.active else "inactive"
        return f"Enrollment(user_id={self.user_id}, catalog_course_id={self.catalog_course_id}, {state})"
