"""This file contains all the necessary backends in a test scenario."""

from django.db import models
from rest_framework import serializers


class CourseOverviewTestModel(models.Model):
    """Test model to enable unit testing."""

    id = models.AutoField(primary_key=True)

    class Meta:
        """Meta class."""

        app_label = "corporate_partner_access"


class CourseOverviewTestSerializer(serializers.ModelSerializer):
    """Test serializer to enable unit testing."""

    class Meta:
        model = CourseOverviewTestModel
        fields = ["id"]


def course_overview_model():
    """Fake get_course_enrollment_model class."""
    return CourseOverviewTestModel


def course_overview_base_serializer():
    """Fake get_course_enrollment_serializer class."""
    return CourseOverviewTestSerializer
