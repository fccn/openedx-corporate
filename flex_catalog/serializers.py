"""Serializers for the flexible catalog app."""

from rest_framework import serializers

from corporate_partner_access.edxapp_wrapper.course_module import course_overview, course_overview_base_serializer

from .models import FlexibleCatalogModel

CourseOverview = course_overview()
CourseOverviewBaseSerializer = course_overview_base_serializer()


class CourseOverviewSimpleSerializer(serializers.ModelSerializer):
    """Serializer for the course overview."""

    class Meta:
        """Meta class for CourseOverviewSimpleSerializer."""

        model = CourseOverview
        fields = ["id", "display_name"]


class FlexibleCatalogModelSerializer(serializers.ModelSerializer):
    """Serializer for the FlexibleCatalogModel."""

    course_runs = serializers.SerializerMethodField()

    class Meta:
        """Meta class for FlexibleCatalogModelSerializer."""

        model = FlexibleCatalogModel
        fields = ["id", "name", "slug", "course_runs"]

    def get_course_runs(self, obj):
        """
        Fetch the related course runs using the `get_course_runs` method.
        """
        course_runs = obj.get_course_runs()
        return CourseOverviewBaseSerializer(course_runs, many=True).data
