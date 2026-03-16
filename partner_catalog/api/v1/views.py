"""Partner Catalog API v1 Views."""

from django.db.models import Count, F, OuterRef, Q, Subquery
from django_filters.rest_framework import DjangoFilterBackend
from edx_rest_framework_extensions.permissions import IsAuthenticated, IsStaff, IsSuperuser
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from partner_catalog.api.v1.filters import CatalogCourseOrderingFilter, PartnerCatalogFilter, PartnerFilter
from partner_catalog.api.v1.mixins import InjectNestedFKMixin
from partner_catalog.api.v1.schemas import (
    add_courses_schema,
    bulk_remove_invitations_schema,
    bulk_status_invitations_schema,
    bulk_upload_invitations_schema,
    remove_courses_schema,
)
from partner_catalog.api.v1.serializers import (
    BasicCourseOverviewSerializer,
    BulkRemoveInvitationSerializer,
    CatalogCourseEnrollmentSerializer,
    CatalogCourseSerializer,
    CatalogLearnerInvitationSerializer,
    CatalogLearnerSerializer,
    InvitationActionSerializer,
    PartnerCatalogSerializer,
    PartnerSerializer,
)
from partner_catalog.api.v1.tasks import bulk_remove_invitations, bulk_upload_invitations
from partner_catalog.helpers.mixins import CSVExportMixin
from partner_catalog.models import (
    CatalogCourse,
    CatalogCourseEnrollment,
    CatalogLearner,
    CatalogLearnerInvitation,
    Partner,
    PartnerCatalog,
)
from partner_catalog.permissions import IsPartnerCatalogManager
from partner_catalog.services.catalog_courses import CatalogCourseService
from partner_catalog.services.catalogs import PartnerCatalogService
from partner_catalog.services.certificates import (
    annotate_catalog_certified_count,
    annotate_course_certified_count,
    annotate_learner_certified_count,
    annotate_partner_certified_count,
)
from partner_catalog.services.invitations import CatalogLearnerInvitationService
from partner_catalog.xapi.constants import INVITATION_CHANNEL_MANUAL


class PartnerViewset(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Corporate Partner data.
    Provides access to corporate partner information.
    """

    queryset = Partner.objects.select_related("organization").all()
    serializer_class = PartnerSerializer
    permission_classes = [IsPartnerCatalogManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PartnerFilter
    search_fields = ["organization__short_name", "organization__name"]
    ordering_fields = ["organization__name", "organization__short_name", "id"]
    ordering = ["organization__short_name"]

    def get_queryset(self):
        """
        Limit non-staff users to partners where they are active managers.
        Staff/superusers see all partners.
        """
        qs = self.queryset
        user = self.request.user

        if not (user.is_staff or user.is_superuser):
            qs = qs.filter(
                catalogs__catalog_managers__user=user,
                catalogs__catalog_managers__active=True
            ).distinct()

        qs = qs.annotate(
            catalogs_count=Count("catalogs", distinct=True),
            courses_count=Count("catalogs__catalog_courses", distinct=True),
            learners_count=Count("catalogs__catalog_learners", distinct=True)
        )
        qs = annotate_partner_certified_count(qs)
        return qs


class PartnerCatalogViewSet(CSVExportMixin, viewsets.ModelViewSet):
    """
    ViewSet for Corporate Partner Catalog data.
    Provides access to corporate partner catalog information.
    """

    # pylint: disable=E1111
    queryset = PartnerCatalog.objects.all()
    serializer_class = PartnerCatalogSerializer
    permission_classes = [IsPartnerCatalogManager]

    csv_filename = "catalogs_report.csv"
    csv_fields = [
        "name", "slug", "status", "courses", "enrollments",
        "total_learners", "active_learners", "certified", "completion_rate",
        "available_start_date", "available_end_date",
    ]
    csv_labels = {
        "name": "Catalog Name",
        "slug": "Slug",
        "status": "Status",
        "courses": "Courses",
        "enrollments": "Enrollments",
        "total_learners": "Total Learners",
        "active_learners": "Active Learners",
        "certified": "Certified",
        "completion_rate": "Completion Rate",
        "available_start_date": "Available Start Date",
        "available_end_date": "Available End Date",
    }
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = PartnerCatalogFilter
    filterset_fields = ["partner"]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "id", "available_start_date", "available_end_date"]
    ordering = ["name"]

    service = PartnerCatalogService()

    def get_queryset(self):
        """Limit catalogs to those the user manages or views; staff see all."""
        qs = self.queryset
        user = self.request.user

        if not (user.is_staff or user.is_superuser):
            qs = qs.filter(
                catalog_managers__user=user,
                catalog_managers__active=True,
            ).distinct()

        qs = qs.annotate(
            courses_count=Count("catalog_courses", distinct=True),
            enrollments=Count(
                "catalog_courses__enrollments",
                filter=Q(catalog_courses__enrollments__active=True),
                distinct=True
            ),
            total_learners=Count("catalog_learners", distinct=True),
            active_learners=Count("catalog_learners", filter=Q(catalog_learners__active=True), distinct=True),
        )
        qs = annotate_catalog_certified_count(qs)
        return qs

    def get_permission_classes(self):
        """Get permission classes based on action."""

        admin_only_actions = [
            "create",
            "destroy",
        ]

        if self.action in admin_only_actions:
            return [IsStaff | IsSuperuser]
        return self.permission_classes

    @add_courses_schema
    @action(detail=True, methods=["post"], url_path="add_courses")
    def add_courses(self, request, **kwargs):
        """
        Add courses to a catalog.

        Expects: {"course_ids": [...], "position": int (optional)}
        Returns: List of created CatalogCourse instances
        """
        catalog = self.get_object()
        course_ids = request.data.get("course_ids", [])
        position = request.data.get("position")

        if not course_ids:
            return Response(
                {"course_ids": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        created_courses = CatalogCourseService.add_catalog_courses(
            catalog=catalog,
            course_overview_ids=course_ids,
            position=position
        )
        serializer = CatalogCourseSerializer(created_courses, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @remove_courses_schema
    @action(detail=True, methods=["post"], url_path="remove_courses")
    def remove_courses(self, request, **kwargs):
        """
        Remove courses from a catalog.

        Expects: {"catalog_course_ids": [...]}
        Returns: Number of courses deleted
        """
        catalog = self.get_object()
        catalog_course_ids = request.data.get("catalog_course_ids", [])

        if not catalog_course_ids:
            return Response(
                {"catalog_course_ids": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        deleted_count = CatalogCourseService.remove_catalog_courses(
            catalog=catalog,
            catalog_course_ids=catalog_course_ids
        )
        return Response(
            {"deleted_count": deleted_count},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["get"], url_path="available_courses")
    def available_courses(self, request, **kwargs):
        """
        List courses available to add to this catalog.

        Returns courses from both the base catalog and partner's organization offering
        that are not yet in the catalog.
        """
        catalog = self.get_object()
        courses = self.service.get_available_courses_for_catalog(catalog)

        base_courses = BasicCourseOverviewSerializer(courses['base'], many=True).data
        org_courses = BasicCourseOverviewSerializer(courses['organization'], many=True).data

        response_data = {
            'base': base_courses,
            'organization': org_courses,
        }
        return Response(response_data)


class CatalogLearnerViewset(CSVExportMixin, InjectNestedFKMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Corporate Partner Catalog Learner data.
    Provides access to corporate partner catalog learner information.
    """

    queryset = CatalogLearner.objects.select_related("catalog", "user", "current_invitation")
    serializer_class = CatalogLearnerSerializer
    permission_classes = [IsPartnerCatalogManager]

    csv_filename = "learners_report.csv"
    csv_fields = [
        "user.full_name", "user.email", "active", "invite_sent_at",
        "accepted_at", "user.last_login", "enrollments", "certified", "removed_at",
    ]
    csv_labels = {
        "user.full_name": "Full Name",
        "user.email": "Email",
        "active": "Active",
        "invite_sent_at": "Invite Sent At",
        "accepted_at": "Accepted At",
        "user.last_login": "Last Login",
        "enrollments": "Enrollments",
        "certified": "Certified",
        "removed_at": "Removed At",
    }
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["catalog", "active", "user"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "user__email"]
    ordering_fields = [
        "id",
        "user_id",
        "accepted_at",
        "removed_at",
        "active",
        "invite_sent_at",
        "user__last_login",
    ]
    ordering = ["id"]

    # Mixin config
    nested_lookup_kwarg = "catalog_pk"
    target_field_name = "catalog_id"

    def get_queryset(self):
        """Get the queryset for catalog learners with enrollment counts."""
        qs = self.queryset
        catalog_pk = self.kwargs.get("catalog_pk")

        if catalog_pk:
            qs = qs.filter(catalog_id=catalog_pk)

        qs = qs.annotate(
            invite_sent_at=F("current_invitation__invited_at"),
            accepted_at=F("current_invitation__accepted_at"),
            removed_at=F("current_invitation__removed_at"),
        )

        enrollments_subquery = CatalogCourseEnrollment.objects.filter(
            user_id=OuterRef("user_id"),
            catalog_course__catalog_id=OuterRef("catalog_id"),
            active=True,
        ).values("user_id").annotate(count=Count("id")).values("count")

        qs = qs.annotate(enrollments_count=Subquery(enrollments_subquery))
        qs = annotate_learner_certified_count(qs)
        return qs


class CatalogCourseViewSet(
    CSVExportMixin,
    InjectNestedFKMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for Corporate Partner Catalog Course data.
    Provides access to corporate partner catalog course information.
    """

    queryset = CatalogCourse.objects.select_related(
        "course_overview", "catalog"
    )
    serializer_class = CatalogCourseSerializer
    permission_classes = [IsPartnerCatalogManager]

    csv_filename = "courses_report.csv"
    csv_fields = [
        "course_run.display_name", "position", "course_run.start", "course_run.end",
        "course_run.enrollment_start", "course_run.enrollment_end",
        "enrollments", "certified", "completion_rate",
    ]
    csv_labels = {
        "course_run.display_name": "Course Name",
        "position": "Position",
        "course_run.start": "Start Date",
        "course_run.end": "End Date",
        "course_run.enrollment_start": "Enrollment Start",
        "course_run.enrollment_end": "Enrollment End",
        "enrollments": "Enrollments",
        "certified": "Certified",
        "completion_rate": "Completion Rate",
    }
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        CatalogCourseOrderingFilter,
    ]
    filterset_fields = ["catalog", "course_overview"]
    search_fields = ["course_overview__display_name"]
    ordering = ["position"]
    ordering_fields = [
        "id", "position",
        "course_start", "course_end",
        "enrollment_start", "enrollment_end",
        "enrollments", "certified",
    ]

    # Mixin config
    nested_lookup_kwarg = "catalog_pk"
    target_field_name = "catalog_id"

    lookup_field = "course_overview_id"
    lookup_url_kwarg = "course_id"

    def get_queryset(self):
        """Get the queryset for catalog courses."""
        qs = self.queryset

        catalog_pk = self.kwargs.get("catalog_pk")
        qs = qs.filter(catalog_id=catalog_pk) if catalog_pk else qs

        qs = qs.annotate(
            enrollments_count=Count(
                "enrollments",
                filter=Q(enrollments__active=True),
                distinct=True,
            )
        )
        qs = annotate_course_certified_count(qs)
        return qs


class CatalogLearnerInvitationViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
    InjectNestedFKMixin,
):
    """ViewSet for managing Catalog Learner Invitations."""

    queryset = CatalogLearnerInvitation.objects.select_related("catalog", "user")
    service = CatalogLearnerInvitationService()
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    # Mixin config
    nested_lookup_kwarg = "catalog_pk"
    target_field_name = "catalog_id"

    def get_queryset(self):
        """Get the queryset for catalog learner invitations."""
        qs = self.queryset
        catalog_pk = self.kwargs.get("catalog_pk")

        if catalog_pk:
            qs = qs.filter(catalog_id=catalog_pk)

        return qs

    def get_permission_classes(self):
        """Get permission classes based on action."""

        base_permissions = [IsAuthenticated]
        manager_actions = [
            "create",
            "remove_invite",
            "bulk_invite_upload",
            "bulk_remove_upload"
        ]
        if self.action in manager_actions:
            return base_permissions + [IsPartnerCatalogManager]
        return base_permissions

    def get_serializer_class(self):
        """Get the serializer class based on action."""

        if self.action in [
            "accept_invite",
            "decline_invite",
            "remove_invite",
            "bulk_invite",
            "bulk_invite_status",
        ]:
            return InvitationActionSerializer
        elif self.action == "bulk_remove":
            return BulkRemoveInvitationSerializer

        return CatalogLearnerInvitationSerializer

    def create(self, request, *args, **kwargs):
        """Create one or more invitations."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        catalog_id = self.kwargs.get('catalog_pk')

        invite_emails = serializer.validated_data.get('invite_email', [])

        created_invitations = []
        errors = []

        for email in invite_emails:
            try:
                invitation = self.service.create_new_invitation(
                    invite_email=email,
                    catalog_id=catalog_id,
                    invited_by=request.user,
                    invitation_channel=INVITATION_CHANNEL_MANUAL,
                )
                created_invitations.append(invitation)
            except ValidationError as e:
                errors.append({
                    'email': email,
                    'error': str(e.detail[0]) if hasattr(e, 'detail') else str(e)
                })
        output_serializer = self.get_serializer(created_invitations, many=True)

        response_data = {
            'invitations': output_serializer.data,
            'created_count': len(created_invitations),
            'total_requested': len(invite_emails),
        }

        # Include errors if any occurred
        if errors:
            response_data['errors'] = errors
            # Return partial success status if some succeeded
            if created_invitations:
                return Response(response_data, status=status.HTTP_207_MULTI_STATUS)
            # Return error status if all failed
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="remove")
    def remove_invite(self, request, pk=None, **kwargs):
        """Remove an invitation."""
        invitation = self.service.remove_invitation(invitation_id=pk, user=request.user)

        serializer = CatalogLearnerInvitationSerializer(invitation)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @bulk_upload_invitations_schema
    @action(detail=False, methods=["post"], url_path="bulk_invite", parser_classes=[MultiPartParser])
    def bulk_invite(self, request, *args, **kwargs):
        """Handle bulk upload of invitations via CSV file."""
        catalog_id = kwargs.get("catalog_pk")
        csv_file = request.FILES.get("file")

        if not csv_file:
            return Response(
                {"detail": "No file uploaded."},
                status=status.HTTP_400_BAD_REQUEST
            )

        csv_content = csv_file.read().decode("utf-8")
        task = bulk_upload_invitations.delay(
            csv_content=csv_content,
            catalog_id=catalog_id,
            invited_by_id=request.user.id,
        )

        return Response({
            "task_id": task.id,
            "status": task.status,
        }, status=status.HTTP_202_ACCEPTED)

    @bulk_remove_invitations_schema
    @action(detail=False, methods=["post"], url_path="bulk_remove")
    def bulk_remove(self, request, *args, **kwargs):
        """Handle bulk revocation of invitations."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        catalog_id = kwargs.get("catalog_pk")

        learner_ids = serializer.validated_data['learner_ids']
        task = bulk_remove_invitations.delay(
            learner_ids=learner_ids,
            removed_by_id=request.user.id,
            catalog_id=catalog_id
        )

        return Response({
            "task_id": task.id,
            "status": task.status,
        }, status=status.HTTP_202_ACCEPTED)

    @bulk_status_invitations_schema
    @action(detail=False, methods=["get"], url_path="bulk_task/status/(?P<task_id>[^/.]+)")
    def bulk_invite_status(self, request, task_id=None, **kwargs):
        """Check the status of a bulk invitation task."""
        if not task_id:
            return Response(
                {"detail": "task_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        task_status_response = self.service.get_task_status(task_id=task_id)
        return Response(task_status_response, status=status.HTTP_200_OK)


class CatalogCourseEnrollmentViewSet(
    CSVExportMixin, viewsets.ReadOnlyModelViewSet, InjectNestedFKMixin
):
    """
    ViewSet for Catalog Course Enrollments.
    Provides read-only access to enrollments in a specific catalog course.
    """

    queryset = CatalogCourseEnrollment.objects.select_related("user", "catalog_course")
    serializer_class = CatalogCourseEnrollmentSerializer
    permission_classes = [IsPartnerCatalogManager]

    csv_filename = "course_enrollments_report.csv"
    csv_fields = [
        "user.full_name", "user.email", "active", "user.last_login",
        "progress", "has_certificate",
    ]
    csv_labels = {
        "user.full_name": "Full Name",
        "user.email": "Email",
        "active": "Active",
        "user.last_login": "Last Login",
        "progress": "Progress",
        "has_certificate": "Has Certificate",
    }
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["catalog_course", "user"]
    search_fields = ["user__username", "user__email"]
    ordering_fields = ["id", "user_id"]
    ordering = ["id"]

    # Mixin config
    nested_lookup_kwarg = "course_pk"
    target_field_name = "catalog_course_id"

    def get_queryset(self):
        """Get the queryset for catalog course enrollments."""
        qs = self.queryset
        catalog_pk = self.kwargs.get("catalog_pk")
        # NestedDefaultRouter builds this kwarg from:
        # lookup="course" + CatalogCourseViewSet.lookup_url_kwarg ("course_id")
        course_id = self.kwargs.get("course_course_id") or self.kwargs.get("course_id")

        if catalog_pk:
            qs = qs.filter(catalog_course__catalog_id=catalog_pk)

        if course_id:
            qs = qs.filter(catalog_course__course_overview_id=course_id)

        return qs


class CatalogEnrollmentsViewSet(CSVExportMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving enrollments across all courses in a specific corporate partner catalog.

    This view provides read-only access to all user enrollments associated with a given PartnerCatalog,
    including user details and course enrollment information. Useful for administrators to list and audit
    active or historical enrollments for compliance and support purposes.
    """

    serializer_class = CatalogCourseEnrollmentSerializer
    permission_classes = [IsPartnerCatalogManager]

    csv_filename = "enrollments_report.csv"
    csv_fields = [
        "user.full_name", "user.email", "active", "user.last_login",
        "course_overview.display_name", "course_overview.id",
        "progress", "has_certificate",
    ]
    csv_labels = {
        "user.full_name": "Full Name",
        "user.email": "Email",
        "active": "Active",
        "user.last_login": "Last Login",
        "course_overview.display_name": "Course Name",
        "course_overview.id": "Course ID",
        "progress": "Progress",
        "has_certificate": "Has Certificate",
    }
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    filterset_fields = ["active", "user"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "user__email"]
    ordering_fields = ["id"]
    ordering = ["-id"]

    def get_queryset(self):
        catalog_pk = self.kwargs["catalog_pk"]
        return (
            CatalogCourseEnrollment.objects.filter(
                catalog_course__catalog_id=catalog_pk
            )
            .select_related("user", "catalog_course", "catalog_course__course_overview")
        )
