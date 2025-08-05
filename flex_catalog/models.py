"""Flexible catalog models - reusable catalog functionality."""

import uuid

from django.db import models
from model_utils.managers import InheritanceManager
from model_utils.models import TimeStampedModel

from corporate_partner_access.edxapp_wrapper.course_module import course_overview


class FlexibleCatalogModel(TimeStampedModel):
    """
    Base class for catalog models with common attributes.

    This model provides the core functionality for any catalog system,
    making it reusable across different applications and contexts.

    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True, blank=True, max_length=255)
    name = models.CharField(max_length=255, help_text="Human friendly name")

    objects = InheritanceManager()

    def get_course_runs(self):
        """
        Return a queryset of course runs associated with this catalog.

        Base implementation returns all course runs.
        Subclasses can override this method to provide specific course run filtering.

        """
        return course_overview().objects.all()

    def __str__(self):
        """Return string representation of this model instance."""
        return f"<FlexibleCatalogModel: {self.name} (ID: {self.id})>"
