"""Models for managing catalogs for corporate partners."""

import uuid

from django.contrib.auth import get_user_model
from django.db import models
from model_utils.managers import InheritanceManager
from model_utils.models import TimeStampedModel

from corporate_partner_access.edxapp_wrapper.course_module import course_overview


class FlexibleCatalogModel(TimeStampedModel):
    """Abstract base class for catalog models with common attributes."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True, blank=True, max_length=255)
    name = models.CharField(max_length=255, help_text="Human friendly")

    objects = InheritanceManager()

    def get_courses(self):
        """Returns all CourseOverview objects."""
        return course_overview().objects.all()

    def __str__(self):
        """String representation of this model instance."""
        return f"<FlexibleCatalogModel, ID: {self.id}>"


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
        verbose_name = "Corporate Partner Catalog"
        verbose_name_plural = "Corporate Partner Catalogs"
        ordering = ["name"]

    def get_courses(self):
        """Returns catalog courses ordered by position."""
        return self.courses.all()
