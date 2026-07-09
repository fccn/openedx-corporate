"""Admin configuration for Partner Catalog models."""

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from flex_catalog.admin import CourseKeysMixin
from partner_catalog.edxapp_wrapper.course_module import course_overview
from partner_catalog.models import (
    BaseCatalog,
    BaseCatalogCourse,
    CatalogCourse,
    CatalogCourseEnrollment,
    CatalogEmailRegex,
    CatalogLearner,
    CatalogLearnerInvitation,
    CatalogManager,
    Partner,
    PartnerCatalog,
)


class BulkAddCoursesForm(forms.Form):
    """Form for bulk-adding courses to a BaseCatalog using a visual dual-list picker."""

    courses = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=FilteredSelectMultiple("Courses", is_stacked=False),
        required=False,
        help_text="Select one or more courses to add. Use the search box to filter results.",
    )

    def __init__(self, *args, available_courses=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['courses'].queryset = available_courses if available_courses is not None else \
            course_overview().objects.none()


@admin.register(BaseCatalog)
class BaseCatalogAdmin(admin.ModelAdmin):
    """Admin interface for BaseCatalog model."""

    list_display = ('name', 'slug', 'course_count', 'course_ids', 'add_course')
    readonly_fields = ('created', 'modified', 'course_count', 'course_ids_display', 'add_course_button')
    fields = ('name', 'slug', 'created', 'modified', 'course_count', 'course_ids_display', 'add_course_button')
    search_fields = ('name', 'slug')

    def get_urls(self):
        """Register custom admin URLs including the bulk-add-courses view."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<uuid:pk>/bulk-add-courses/',
                self.admin_site.admin_view(self.bulk_add_courses_view),
                name='partner_catalog_basecatalog_bulk_add_courses',
            ),
        ]
        return custom_urls + urls

    def bulk_add_courses_view(self, request, pk):
        """Custom admin view: visual dual-list picker to bulk-add courses to a BaseCatalog."""
        base_catalog = get_object_or_404(BaseCatalog, pk=pk)
        CourseOverview = course_overview()

        existing_course_ids = base_catalog.base_catalog_courses.values_list(
            'course_overview_id', flat=True
        )
        available_courses = (
            CourseOverview.objects
            .exclude(id__in=existing_course_ids)
            .order_by('display_name')
        )

        if request.method == 'POST':
            form = BulkAddCoursesForm(request.POST, available_courses=available_courses)
            if form.is_valid():
                selected_courses = form.cleaned_data['courses']
                added = 0
                for course in selected_courses:
                    _, created = BaseCatalogCourse.objects.get_or_create(
                        base_catalog=base_catalog,
                        course_overview=course,
                        defaults={'added_by': request.user},
                    )
                    if created:
                        added += 1

                self.message_user(
                    request,
                    f"Successfully added {added} course(s) to \"{base_catalog.name}\".",
                    messages.SUCCESS,
                )
                return HttpResponseRedirect(
                    reverse('admin:partner_catalog_basecatalog_change', args=[pk])
                )
        else:
            form = BulkAddCoursesForm(available_courses=available_courses)

        context = {
            **self.admin_site.each_context(request),
            'title': f'Bulk Add Courses to "{base_catalog.name}"',
            'base_catalog': base_catalog,
            'form': form,
            'media': self.media + form.media,
            'opts': self.model._meta,
            'has_change_permission': self.has_change_permission(request),
        }
        return TemplateResponse(
            request,
            'admin/partner_catalog/basecatalog/bulk_add_courses.html',
            context,
        )

    def get_queryset(self, request):
        """Optimize queryset with prefetch."""
        qs = super().get_queryset(request)
        return qs.prefetch_related('courses', 'base_catalog_courses')

    def course_count(self, obj):
        """Display the total number of courses in the catalog."""
        return obj.courses.count()
    course_count.short_description = 'Total Courses'

    def course_ids(self, obj):
        """Display preview of course IDs in the list view."""
        course_runs = obj.get_course_runs()

        if course_runs:
            course_ids = [str(course.id) for course in course_runs]
            return format_html('<br>'.join(course_ids))

        return format_html('<em style="color: #999;">No courses</em>')

    course_ids.short_description = 'Course IDs'

    def course_ids_display(self, obj):
        """Display all course IDs in the detail view."""
        course_runs = obj.get_course_runs()

        if course_runs:
            course_ids = [str(course.id) for course in course_runs]
            return format_html('<br>'.join(course_ids))

        return format_html('<em style="color: #999;">No courses</em>')

    course_ids_display.short_description = 'Course IDs'

    def add_course_button(self, obj):
        """Render action buttons for adding courses to this BaseCatalog."""
        if not obj.pk:
            return format_html('<em style="color: #999;">Save the catalog first</em>')

        single_url = reverse(
            f"admin:{BaseCatalogCourse._meta.app_label}_{BaseCatalogCourse._meta.model_name}_add"
        ) + f"?base_catalog={obj.pk}"

        bulk_url = reverse('admin:partner_catalog_basecatalog_bulk_add_courses', args=[obj.pk])

        return format_html(
            '<a href="{}" class="button" style="background-color:#417690;margin-right:8px;">+ Add Single Course</a>'
            '<a href="{}" class="button" style="background-color:#28a745;">+ Bulk Add Courses</a>',
            single_url,
            bulk_url,
        )

    add_course_button.short_description = "Add Courses"

    def add_course(self, obj):
        """Render bulk-add link in the list view."""
        if not obj.pk:
            return format_html('')

        bulk_url = reverse('admin:partner_catalog_basecatalog_bulk_add_courses', args=[obj.pk])
        return format_html(
            '<a href="{}" style="font-weight:bold;">+ Bulk Add Courses</a>',
            bulk_url,
        )

    add_course.short_description = "Add Courses"


@admin.register(BaseCatalogCourse)
class BaseCatalogCourseAdmin(admin.ModelAdmin):
    """Admin interface for BaseCatalogCourse model."""

    list_display = ["id", "base_catalog", "course_overview", "added_by", "added_at"]
    list_filter = ["base_catalog"]
    search_fields = ["base_catalog__name", "course_overview__display_name"]
    ordering = ["-added_at"]
    raw_id_fields = ["base_catalog", "course_overview"]
    readonly_fields = ["added_at", "added_by"]

    fieldsets = (
        ("Course Assignment", {"fields": ("base_catalog", "course_overview")}),
        ("Metadata", {"fields": ("added_by", "added_at")}),
    )

    def save_model(self, request, obj, form, change):
        """Asigna el usuario actual al campo added_by si es una creación nueva."""
        if not change and not obj.added_by:
            obj.added_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("base_catalog", "course_overview", "added_by")


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    """Admin interface for Partner model."""

    fields = ("organization", "homepage_url")
    raw_id_fields = ("organization",)

    list_display = (
        "organization_short_name",
        "organization_name",
        "homepage_url",
        "organization_logo_thumb",
        "catalog_count",
    )
    list_display_links = ("organization_short_name", "organization_name")
    ordering = ("organization__short_name",)
    search_fields = (
        "organization__short_name",
        "organization__name",
        "homepage_url",
    )

    list_select_related = ("organization",)

    def get_queryset(self, request):
        """Queryset with annotated catalog count."""
        qs = super().get_queryset(request)
        return qs.select_related("organization").annotate(
            _catalog_count=Count("catalogs", distinct=True)
        )

    def organization_short_name(self, obj):
        """Display the short name of the organization."""
        return getattr(obj.organization, "short_name", str(obj.organization))

    organization_short_name.short_description = "Org. short name"
    organization_short_name.admin_order_field = "organization__short_name"

    def organization_name(self, obj):
        """Display the full name of the organization."""
        return getattr(obj.organization, "name", "")

    organization_name.short_description = "Organization"
    organization_name.admin_order_field = "organization__name"

    def organization_logo_thumb(self, obj):
        """Display a small organization logo if available."""
        logo = getattr(obj.organization, "logo", "")

        try:
            return format_html(
                '<img src="{}" width="32" height="32" '
                'style="object-fit:cover;border-radius:4px;" />',
                logo.url,
            )
        except (ValueError, AttributeError):
            return format_html(
                '<span style="color: #999; font-style: italic;">No logo</span>'
            )

    organization_logo_thumb.short_description = "Logo"

    def catalog_count(self, obj):
        """Display the number of catalogs linked to this partner."""
        return getattr(obj, "_catalog_count", 0)

    catalog_count.short_description = "Catalogs"
    catalog_count.admin_order_field = "_catalog_count"


class CatalogEmailRegexInline(admin.TabularInline):
    """Inline admin for email regex patterns."""

    model = CatalogEmailRegex
    extra = 1
    fields = ["regex"]
    verbose_name = "Email Regex Pattern"
    verbose_name_plural = "Email Regex Patterns"


@admin.register(PartnerCatalog)
class PartnerCatalogAdmin(admin.ModelAdmin, CourseKeysMixin):
    """Admin interface for PartnerCatalog model."""

    inlines = [CatalogEmailRegexInline]

    list_display = [
        "name",
        "partner_name",
        "is_self_enrollment",
        "course_count",
        "learner_count",
        "add_learner",
        "add_course",
        "add_manager",
        "image_thumb",
    ]
    list_filter = [
        "partner",
        "is_self_enrollment",
    ]
    search_fields = [
        "name",
        "partner__organization__name",
        "partner__organization__short_name",
    ]
    ordering = ["partner__organization__short_name", "name"]
    raw_id_fields = ["partner"]
    readonly_fields = ["course_keys", "slug"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "partner", "slug", "image")}),
        (
            "Enrollment Settings",
            {
                "fields": (
                    "is_self_enrollment",
                    "course_enrollments_limit",
                    "user_limit",
                )
            },
        ),
        (
            "Availability",
            {
                "fields": ("available_start_date", "available_end_date"),
            },
        ),
        (
            "Additional Information",
            {
                "fields": ("authorization_message", "support_email", "alternative_link"),
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
        """Display the name of the partner."""
        if obj.partner and obj.partner.organization:
            org = obj.partner.organization
            return f"{org.name} ({org.short_name})"
        return "No Partner"

    partner_name.short_description = "Partner"
    partner_name.admin_order_field = "partner__organization__short_name"

    def course_count(self, obj):
        """Display the number of courses in this catalog."""
        return obj.catalog_courses.count()

    course_count.short_description = "Courses"

    def learner_count(self, obj):
        """Display the number of learners in this catalog."""
        return obj.catalog_learners.count()

    learner_count.short_description = "Learners"

    def image_thumb(self, obj):
        """Display a thumbnail preview of the catalog image if available."""
        if obj.image:
            return format_html(
                '<img src="{}" width="64" height="36" style="object-fit:cover;border-radius:4px;" />',
                obj.image.url,
            )
        return format_html(
            '<span style="color: #999; font-style: italic;">No image</span>'
        )

    image_thumb.short_description = "Image"

    def add_learner(self, obj):
        """Generate a link to add a new invitation for this catalog."""
        invitation_model = CatalogLearnerInvitation
        add_invitation_url = reverse(
            f"admin:{invitation_model._meta.app_label}_{invitation_model._meta.model_name}_add"
        )
        full_url = f"{add_invitation_url}?catalog={obj.pk}"

        return format_html(
            '<a href="{}" style="font-weight: bold;"> Add Learner </a>',
            full_url,
        )

    add_learner.short_description = "Add Learner"

    def add_course(self, obj):
        """Generate a link to add a new course to this catalog."""
        course_model = CatalogCourse
        add_course_url = reverse(
            f"admin:{course_model._meta.app_label}_{course_model._meta.model_name}_add"
        )
        full_url = f"{add_course_url}?catalog={obj.pk}"

        return format_html(
            '<a href="{}" style="font-weight: bold;"> Add Course </a>',
            full_url,
        )

    add_course.short_description = "Add Course"

    def add_manager(self, obj):
        """Generate a link to add a new manager (catalog-level)."""
        manager_model = CatalogManager
        add_manager_url = reverse(
            f"admin:{manager_model._meta.app_label}_{manager_model._meta.model_name}_add"
        )
        full_url = f"{add_manager_url}?catalog={obj.pk}"

        return format_html(
            '<a href="{}" style="font-weight: bold;"> Add Manager </a>',
            full_url,
        )

    add_manager.short_description = "Add Manager"

    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related."""
        queryset = super().get_queryset(request)
        return queryset.select_related("partner__organization").prefetch_related(
            "catalog_courses", "catalog_learners", "catalog_email_regexes"
        )


@admin.register(CatalogCourse)
class CatalogCourseAdmin(admin.ModelAdmin):
    """Admin interface for CatalogCourse model."""

    list_display = [
        "id",
        "catalog",
        "course_overview",
        "position",
    ]
    list_filter = ["catalog__partner"]
    search_fields = ["catalog__name", "course_overview__display_name"]
    ordering = ["catalog__name", "position"]
    raw_id_fields = ["catalog", "course_overview"]

    fieldsets = (
        ("Course Assignment", {"fields": ("catalog", "course_overview", "position")}),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("catalog", "course_overview")


@admin.register(CatalogLearner)
class CatalogLearnerAdmin(admin.ModelAdmin):
    """Admin interface for CatalogLearner model - Read-only, learners are created via invitations."""

    list_display = [
        "id",
        "user",
        "user_email",
        "catalog",
        "active",
        "invited_at",
        "removed_at",
        "created_at",
    ]
    list_filter = ["catalog__partner", "active"]
    search_fields = ["user__username", "user__email", "catalog__name"]
    ordering = ["catalog__name", "user__username"]
    date_hierarchy = "created_at"

    def has_change_permission(self, request, obj=None):
        """Disable editing learners directly."""
        return False

    readonly_fields = [
        "catalog",
        "user",
        "current_invitation",
        "active",
        "created_at",
        "invited_at",
        "removed_at",
        "invited_by_display",
        "removed_by_display",
    ]

    fieldsets = (
        ("Learner Assignment", {"fields": ("catalog", "user", "current_invitation")}),
        ("Status", {"fields": ("active", "created_at")}),
        (
            "Invitation Details",
            {
                "fields": (
                    "invited_at",
                    "invited_by_display",
                    "removed_at",
                    "removed_by_display",
                )
            },
        ),
    )

    def user_email(self, obj):
        """Display the user's email."""
        return obj.user.email

    user_email.short_description = "Email"
    user_email.admin_order_field = "user__email"

    def invited_at(self, obj):
        """Display when the current invitation was sent."""
        return obj.current_invitation.invited_at

    invited_at.short_description = "Invited At"
    invited_at.admin_order_field = "current_invitation__invited_at"

    def removed_at(self, obj):
        """Display when the learner was removed."""
        return obj.current_invitation.removed_at

    removed_at.short_description = "Removed At"

    def invited_by_display(self, obj):
        """Display who sent the invitation."""
        if obj.current_invitation and obj.current_invitation.invited_by:
            return obj.current_invitation.invited_by.username
        return "-"

    invited_by_display.short_description = "Invited By"

    def removed_by_display(self, obj):
        """Display who removed the learner."""
        if obj.current_invitation and obj.current_invitation.removed_by:
            return obj.current_invitation.removed_by.username
        return "-"

    removed_by_display.short_description = "Removed By"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related(
            "catalog__partner__organization",
            "user",
            "current_invitation",
            "current_invitation__invited_by",
            "current_invitation__removed_by",
        )


@admin.register(CatalogLearnerInvitation)
class CatalogLearnerInvitationAdmin(admin.ModelAdmin):
    """Admin interface for CatalogLearnerInvitation model - Create and view only."""

    list_display = [
        "id",
        "user_display",
        "catalog_slug",
        "invited_at",
        "status_display",
    ]

    list_filter = [
        "status",
        "catalog__partner",
        "invited_at",
        "accepted_at",
        "declined_at",
        "removed_at",
    ]

    search_fields = ["invite_email", "user__username", "user__email", "catalog__name"]
    ordering = ["-invited_at"]
    raw_id_fields = ["catalog", "user"]
    date_hierarchy = "invited_at"

    def get_readonly_fields(self, request, obj=None):
        """No readonly fields when creating, all readonly when viewing."""
        if obj is None:
            # Creating new invitation
            return []

        return [
            "catalog",
            "invite_email",
            "user",
            "invited_by_display",
            "invited_at",
            "status_display",
            "accepted_at",
            "declined_at",
            "removed_at",
            "removed_by_display",
        ]

    def has_change_permission(self, request, obj=None):
        """Disable editing invitations - they can only be viewed."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Only allow deletion if no learner is linked to this invitation."""
        if obj and hasattr(obj, 'learner') and obj.learner:
            return False
        return True

    def get_fieldsets(self, request, obj=None):
        """Dynamic fieldsets: simple for add, detailed for view."""
        if obj is None:
            return (
                (
                    "New Invitation",
                    {
                        "fields": ("catalog", "invite_email", "user"),
                        "description": "Provide either an email address or select an existing user.",
                    },
                ),
            )

        fieldsets = [
            (
                "Invitation Details",
                {
                    "fields": (
                        "catalog",
                        "invite_email",
                        "user",
                        "invited_by_display",
                        "invited_at",
                        "status_display",
                        "accepted_at",
                        "declined_at",
                    )
                },
            ),
        ]

        if obj.removed_at or obj.removed_by:
            fieldsets.append(
                (
                    "Revocation",
                    {"fields": ("removed_at", "removed_by_display")},
                )
            )

        return fieldsets

    def save_model(self, request, obj, form, change):
        """Auto-populate invited_by when creating new invitations."""
        if not change:
            obj.invited_by = request.user
        super().save_model(request, obj, form, change)

    def user_display(self, obj):
        """Display user username or email."""
        if obj.user:
            display_name = obj.user.username if obj.user.username else obj.user.email
            return display_name
        return obj.invite_email if obj.invite_email else "—"

    user_display.short_description = "User"
    user_display.admin_order_field = "user__username"

    def catalog_slug(self, obj):
        """Display catalog slug."""
        return obj.catalog.slug if obj.catalog else "—"

    catalog_slug.short_description = "Catalog"
    catalog_slug.admin_order_field = "catalog__slug"

    def invited_by_display(self, obj):
        """Display who sent the invitation (readonly)."""
        if obj.invited_by:
            username = obj.invited_by.username or "—"
            email = obj.invited_by.email or "—"
            return format_html("{} ({})", username, email)
        return format_html('<em style="color:#999">Unknown</em>')

    invited_by_display.short_description = "Invited By"

    def removed_by_display(self, obj):
        """Display who removed/revoked the invitation (readonly)."""
        if obj.removed_by:
            username = obj.removed_by.username or "—"
            email = obj.removed_by.email or "—"
            return format_html("{} ({})", username, email)
        return format_html('<em style="color:#999">—</em>')

    removed_by_display.short_description = "Removed By"

    def status_display(self, obj):
        """Display status with color coding."""
        base_style = "padding:3px 10px;border-radius:12px;color:#fff;font-weight:600;display:inline-block;"
        status_colors = {
            obj.Status.SENT: ("Sent", "#64748b"),
            obj.Status.ACCEPTED: ("Accepted", "#16a34a"),
            obj.Status.DECLINED: ("Declined", "#f59e0b"),
            obj.Status.REMOVED: ("Removed", "#dc2626"),
        }
        label, bg = status_colors.get(obj.status, ("Unknown", "#6b7280"))
        return format_html(
            '<span style="{}background:{}">{}</span>', base_style, bg, label
        )

    status_display.short_description = "Status"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related(
            "catalog__partner__organization",
            "user",
            "invited_by",
            "removed_by",
        )


@admin.register(CatalogManager)
class CatalogManagerAdmin(admin.ModelAdmin):
    """Admin interface for CatalogManager model."""

    list_display = ["id", "catalog", "user", "user_email", "active"]
    list_filter = ["catalog__partner", "catalog", "active"]
    search_fields = [
        "catalog__name",
        "catalog__partner__organization__name",
        "user__username",
        "user__email",
    ]
    ordering = [
        "catalog__partner__organization__short_name",
        "catalog__name",
        "user__username",
    ]
    raw_id_fields = ["catalog", "user"]

    fieldsets = (("Assignment", {"fields": ("catalog", "user", "active")}),)

    def user_email(self, obj):
        """Display the user's email."""
        return obj.user.email

    user_email.short_description = "Email"
    user_email.admin_order_field = "user__email"

    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related("catalog__partner__organization", "user")


@admin.register(CatalogCourseEnrollment)
class CatalogCourseEnrollmentAdmin(admin.ModelAdmin):
    """Admin interface for CatalogCourseEnrollment model."""

    list_display = (
        "id",
        "user_username",
        "user_email",
        "catalog_course_display",
        "is_active",
    )

    list_filter = ("active", "catalog_course__catalog__partner")
    search_fields = ("user__username", "user__email", "catalog_course__catalog__name")
    ordering = ("id",)

    raw_id_fields = ("user", "catalog_course")
    list_select_related = ("user", "catalog_course__catalog")

    fieldsets = (("Enrollment", {"fields": ("user", "catalog_course", "active")}),)

    def is_active(self, obj):
        """Return whether the enrollment is active (for boolean display in admin)."""
        return obj.active

    is_active.boolean = True
    is_active.short_description = "Active"

    def user_username(self, obj):
        """Return the username of the user associated with this enrollment."""
        return getattr(obj.user, "username", obj.user_id)

    user_username.admin_order_field = "user__username"
    user_username.short_description = "Username"

    def user_email(self, obj):
        """Display the user's email."""
        return obj.user.email

    user_email.short_description = "Email"
    user_email.admin_order_field = "user__email"

    def catalog_course_display(self, obj):
        """Display catalog and course info."""
        return f"{obj.catalog_course.catalog.name} - {obj.catalog_course.course_overview.display_name}"

    catalog_course_display.short_description = "Catalog - Course"

    def get_queryset(self, request):
        """Return the queryset for the admin changelist, with related user and catalog_course prefetched."""
        qs = super().get_queryset(request)
        return qs.select_related(
            "user",
            "catalog_course__catalog__partner__organization",
            "catalog_course__course_overview",
        )
