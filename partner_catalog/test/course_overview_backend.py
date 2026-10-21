"""This file contains all the necessary backends in a test scenario for course overview."""

from django.db import models
from rest_framework import serializers


class CourseOverviewTestModel(models.Model):
    """Test model to enable unit testing."""

    id = models.AutoField(primary_key=True)
    # Fields read by flex_catalog.serializers.CourseOverviewSimpleSerializer.
    display_name = models.TextField(null=True)
    start = models.DateTimeField(null=True)
    end = models.DateTimeField(null=True)
    enrollment_start = models.DateTimeField(null=True)
    enrollment_end = models.DateTimeField(null=True)
    course_image_url = models.TextField(null=True)

    class Meta:
        """Meta class."""

        app_label = "partner_catalog"


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
