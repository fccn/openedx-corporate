"""Admin configuration for Corporate Partner Access models."""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from flex_catalog.admin import CourseKeysMixin

from .models import (
    CorporatePartner,
    CorporatePartnerCatalog,
    CorporatePartnerCatalogCourse,
    CorporatePartnerCatalogEmailRegex,
    CorporatePartnerCatalogLearner,
)


@admin.register(CorporatePartner)
class CorporatePartnerAdmin(admin.ModelAdmin):
    """Admin interface for CorporatePartner model."""

    list_display = ["code", "name", "logo_thumbnail", "homepage_url", "catalog_count"]
    list_filter = ["name", "code"]
    search_fields = ["name", "code", "homepage_url"]
    ordering = ["code"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "code")}),
        ("Media & Links", {"fields": ("logo", "homepage_url")}),
    )

    def catalog_count(self, obj):
        """Display the number of catalogs associated with this partner."""
        return obj.catalogs.count()

    catalog_count.short_description = "Catalogs"
    catalog_count.admin_order_field = "catalogs__count"

    def logo_thumbnail(self, obj):
        """Display a thumbnail of the partner's logo."""
        if obj.logo:
            return format_html(
                '<img src="{}" width="40" height="40" style="object-fit: cover; border-radius: 4px;"/>',
                obj.logo.url,
            )
        return format_html(
            '<span style="color: #999; font-style: italic;">No logo</span>'
        )

    logo_thumbnail.short_description = "Logo"

    def get_queryset(self, request):
        """Optimize queryset with prefetch_related for catalog count."""
        queryset = super().get_queryset(request)
        return queryset.prefetch_related("catalogs")


class CorporatePartnerCatalogEmailRegexInline(admin.TabularInline):
    """Inline admin for email regex patterns."""

    model = CorporatePartnerCatalogEmailRegex
    extra = 1
    fields = ["regex"]
    verbose_name = "Email Regex Pattern"
    verbose_name_plural = "Email Regex Patterns"


@admin.register(CorporatePartnerCatalog)
class CorporatePartnerCatalogAdmin(admin.ModelAdmin, CourseKeysMixin):
    """Admin interface for CorporatePartnerCatalog model."""

    inlines = [CorporatePartnerCatalogEmailRegexInline]

    list_display = [
        "name",
        "partner_name",
        "is_public",
        "is_self_enrollment",
        "course_count",
        "learner_count",
        "add_learner",
        "add_course",
    ]
    list_filter = [
        "corporate_partner",
        "is_public",
        "is_self_enrollment",
        "custom_courses",
    ]
    search_fields = ["name", "corporate_partner__name", "corporate_partner__code"]
    ordering = ["corporate_partner__code", "name"]
    raw_id_fields = ["corporate_partner"]
    readonly_fields = ["course_keys"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "corporate_partner", "slug")}),
        (
            "Enrollment Settings",
            {
                "fields": (
                    "is_self_enrollment",
                    "course_enrollment_limit",
                    "user_limit",
                    "custom_courses",
                )
            },
        ),
        (
            "Availability",
            {
                "fields": ("available_start_date", "available_end_date", "is_public"),
            },
        ),
        (
            "Additional Information",
            {
                "fields": (
                    "authorization_additional_message",
                    "support_email",
                    "catalog_alternative_link",
                ),
            },
        ),
        (
            "Course Information",
            {
                "fields": ("course_keys",),
                "classes": ("collapse",),
            },
        ),
    )

    def partner_name(self, obj):
        """Display the name of the corporate partner."""
        return (
            f"{obj.corporate_partner.name} ({obj.corporate_partner.code})"
            if obj.corporate_partner
            else "No Partner"
        )

    def course_count(self, obj):
        """Display the number of courses in this catalog."""
        return obj.courses.count()

    course_count.short_description = "Courses"
    course_count.admin_order_field = "courses__count"

    def learner_count(self, obj):
        """Display the number of learners in this catalog."""
        return obj.learners.count()

    learner_count.short_description = "Learners"
    learner_count.admin_order_field = "learners__count"

    def add_learner(self, obj):
        """Generate a link to add a new learner to this catalog."""
        learner_model = CorporatePartnerCatalogLearner
        add_learner_url = reverse(
            f"admin:{learner_model._meta.app_label}_{learner_model._meta.model_name}_add"
        )
        full_url = f"{add_learner_url}?catalog={obj.pk}"

        return format_html(
            '<a href="{}" style="font-weight: bold;">➕ Add</a>',
            full_url,
        )

    add_learner.short_description = "Add Learner"

    def add_course(self, obj):
        """Generate a link to add a new course to this catalog."""
        course_model = CorporatePartnerCatalogCourse
        add_course_url = reverse(
            f"admin:{course_model._meta.app_label}_{course_model._meta.model_name}_add"
        )
        full_url = f"{add_course_url}?catalog={obj.pk}"

        return format_html(
            '<a href="{}" style="font-weight: bold;">➕ Add</a>',
            full_url,
        )

    add_course.short_description = "Add Course"

    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related."""
        queryset = super().get_queryset(request)
        return queryset.select_related("corporate_partner").prefetch_related(
            "courses", "learners", "email_regexes"
        )


@admin.register(CorporatePartnerCatalogCourse)
class CorporatePartnerCatalogCourseAdmin(admin.ModelAdmin):
    """Admin interface for CorporatePartnerCatalogCourse model."""

    list_display = ["id", "catalog", "course_overview", "position"]
    list_filter = ["catalog__corporate_partner"]
    search_fields = ["catalog__name", "course_overview__display_name"]
    ordering = ["catalog__name", "position"]
    raw_id_fields = ["catalog", "course_overview"]

    fieldsets = (
        ("Course Assignment", {"fields": ("catalog", "course_overview", "position")}),
    )


@admin.register(CorporatePartnerCatalogLearner)
class CorporatePartnerCatalogLearnerAdmin(admin.ModelAdmin):
    """Admin interface for CorporatePartnerCatalogLearner model."""

    list_display = ["id", "user", "catalog", "active"]
    list_filter = ["catalog__corporate_partner", "active"]
    search_fields = ["user__username", "user__email", "catalog__name"]
    ordering = ["catalog__name", "user__username"]
    raw_id_fields = ["catalog", "user"]

    fieldsets = (("Learner Assignment", {"fields": ("catalog", "user", "active")}),)

    def user_email(self, obj):
        """Display the user's email."""
        return obj.user.email

    user_email.short_description = "Email"
