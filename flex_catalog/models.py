"""Flexible catalog models - reusable catalog functionality."""

import uuid

from django.db import models
from model_utils.managers import InheritanceManager
from model_utils.models import TimeStampedModel


class FlexibleCatalogModel(TimeStampedModel):
    """
    Abstract base class for catalog models with common attributes.

    This model provides the core functionality for any catalog system,
    making it reusable across different applications and contexts.

    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True, blank=True, max_length=255)
    name = models.CharField(max_length=255, help_text="Human friendly name")

    objects = InheritanceManager()

    def get_courses(self):
        """
        Return courses for this catalog.

        Subclasses must implement this method.

        """
        raise NotImplementedError("Subclasses must implement this method.")

    def __str__(self):
        """Return string representation of this model instance."""
        return f"<FlexibleCatalogModel: {self.name} (ID: {self.id})>"

    class Meta:
        """Meta options for FlexibleCatalogModel."""

        abstract = True
