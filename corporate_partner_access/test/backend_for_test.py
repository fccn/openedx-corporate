"""This file contains all the necessary backends in a test scenario."""

from django.db import models


class CourseOverviewTestModel(models.Model):
    """Test model to enable unit testing."""

    id = models.AutoField(primary_key=True)

    class Meta:
        """Meta class."""

        app_label = "corporate_partner_access"


def course_overview_backend():
    """Fake get_course_enrollment_model class."""
    return CourseOverviewTestModel
