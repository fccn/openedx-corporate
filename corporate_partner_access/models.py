"""Models for managing course catalogs and access for corporate partners."""

import regex
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

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
