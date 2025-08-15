"""Admin configuration for the flexible catalog models."""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import FlexibleCatalogModel


class CourseKeysMixin():
    """Mixin to provide course keys functionality in admin."""

    def course_keys(self, obj):
        """Render the IDs of the courses from get_course_runs."""
        course_runs = obj.get_course_runs()
        if course_runs.exists():
            course_ids = [
                str(course.id) for course in course_runs
            ]
            return format_html("<br>".join(course_ids))
        return "No course runs available"

    course_keys.short_description = "Course IDs"


@admin.register(FlexibleCatalogModel)
class FlexibleCatalogModelAdmin(admin.ModelAdmin, CourseKeysMixin):
    """Admin interface for FlexibleCatalogModel."""

    list_display = ("name", "slug", "id", "model_class_name", "course_keys")
    search_fields = ("name", "slug", "id")
    prepopulated_fields = {"slug": ("name",)}

    def model_class_name(self, obj):
        """
        Provide a link to the admin edit page for the specific subclass instance.
        """
        subclass_admin_url = reverse(
            f"admin:{obj._meta.app_label}_{obj.__class__.__name__.lower()}_change",
            args=[obj.id],
        )
        return format_html(
            '<a href="{}">{}</a>', subclass_admin_url, obj.__class__.__name__
        )

    model_class_name.short_description = "Update Link"

    def get_queryset(self, request):
        """
        Override the queryset to use select_subclasses for subclass resolution.
        """
        return FlexibleCatalogModel.objects.select_subclasses()
