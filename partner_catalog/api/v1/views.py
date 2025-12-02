"""Partner Catalog API v1 Views."""

from django.db.models import Count, OuterRef, Q, Subquery
from django_filters.rest_framework import DjangoFilterBackend
from edx_rest_framework_extensions.permissions import IsAuthenticated
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from partner_catalog.api.v1.filters import PartnerCatalogFilter, PartnerFilter
from partner_catalog.api.v1.mixins import InjectNestedFKMixin
from partner_catalog.api.v1.schemas import (
    bulk_remove_invitations_schema,
    bulk_status_invitations_schema,
    bulk_upload_invitations_schema,
)
from partner_catalog.api.v1.serializers import (
    BulkRemoveInvitationSerializer,
    CatalogCourseEnrollmentSerializer,
    CatalogCourseSerializer,
    CatalogEmailRegexSerializer,
    CatalogLearnerInvitationSerializer,
    CatalogLearnerSerializer,
    InvitationActionSerializer,
    PartnerCatalogSerializer,
    PartnerSerializer,
)
from partner_catalog.api.v1.tasks import bulk_remove_invitations, bulk_upload_invitations
from partner_catalog.models import (
    CatalogCourse,
    CatalogCourseEnrollment,
    CatalogEmailRegex,
    CatalogLearner,
    CatalogLearnerInvitation,
    Partner,
    PartnerCatalog,
)
from partner_catalog.permissions import IsPartnerCatalogManager
from partner_catalog.services.catalogs import PartnerCatalogService
from partner_catalog.services.certificates import (
    annotate_catalog_certified_count,
    annotate_course_certified_count,
    annotate_learner_certified_count,
    annotate_partner_certified_count,
)
from partner_catalog.services.invitations import CatalogLearnerInvitationService


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


class PartnerCatalogViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Corporate Partner Catalog data.
    Provides access to corporate partner catalog information.
    """

    # pylint: disable=E1111
    queryset = PartnerCatalog.objects.all()
    serializer_class = PartnerCatalogSerializer
    permission_classes = [IsPartnerCatalogManager]
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
            total_enrollments=Count("catalog_learners", distinct=True),
        )
        qs = annotate_catalog_certified_count(qs)
        return qs

    @action(detail=True, methods=["post"], url_path="enroll")
    def enroll(self, request, *args, **kwargs):
        """Allow a user to self-enroll in a catalog."""
        catalog = self.get_object()
        user = request.user

        learner = self.service.self_enroll_user_in_catalog(user=user, catalog=catalog)
        serializer = CatalogLearnerSerializer(learner)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CatalogLearnerViewset(InjectNestedFKMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Corporate Partner Catalog Learner data.
    Provides access to corporate partner catalog learner information.
    """

    queryset = CatalogLearner.objects.select_related("catalog", "user")
    serializer_class = CatalogLearnerSerializer
    permission_classes = [IsPartnerCatalogManager]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["catalog", "active", "user"]
    search_fields = ["user__username", "user__email"]
    ordering_fields = [
        "id",
        "user_id",
        "accepted_at",
        "removed_at",
        "active",
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

        enrollments_subquery = CatalogCourseEnrollment.objects.filter(
            user_id=OuterRef("user_id"),
            catalog_course__catalog_id=OuterRef("catalog_id"),
            active=True,
        ).values("user_id").annotate(count=Count("id")).values("count")

        qs = qs.annotate(enrollments_count=Subquery(enrollments_subquery))
        qs = annotate_learner_certified_count(qs)
        return qs


class CatalogCourseViewSet(
    InjectNestedFKMixin, viewsets.ModelViewSet,
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
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["catalog", "course_overview"]
    search_fields = ["course_overview__display_name"]
    ordering_fields = ["id", "position"]
    ordering = ["position"]

    # Mixin config
    nested_lookup_kwarg = "catalog_pk"
    target_field_name = "catalog_id"

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


class CatalogEmailRegexViewSet(
    InjectNestedFKMixin, viewsets.ModelViewSet
):
    """ViewSet for catalog email regex patterns."""

    queryset = CatalogEmailRegex.objects.all()
    serializer_class = CatalogEmailRegexSerializer
    permission_classes = [IsPartnerCatalogManager]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["catalog"]

    # Mixin config
    nested_lookup_kwarg = "catalog_pk"
    target_field_name = "catalog_id"

    def get_queryset(self):
        """Get the queryset for catalog email regex patterns."""
        qs = self.queryset
        catalog_pk = self.kwargs.get("catalog_pk")
        return qs.filter(catalog_id=catalog_pk) if catalog_pk else qs


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
        """Create a new invitation."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        catalog_id = self.kwargs.get('catalog_pk')

        invitation = self.service.create_new_invitation(
            invite_email=serializer.validated_data.get('invite_email'),
            catalog_id=catalog_id,
            invited_by=request.user,
        )

        output_serializer = self.get_serializer(invitation)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="accept")
    def accept_invite(self, request, pk=None, **kwargs):
        """Accept an invitation."""
        invitation = self.service.accept_invitation(invitation_id=pk, user=request.user)

        serializer = CatalogLearnerInvitationSerializer(invitation)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="decline")
    def decline_invite(self, request, pk=None, **kwargs):
        """Decline an invitation."""
        invitation = self.service.decline_invitation(invitation_id=pk, user=request.user)

        serializer = CatalogLearnerInvitationSerializer(invitation)
        return Response(serializer.data, status=status.HTTP_200_OK)

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
    viewsets.ReadOnlyModelViewSet, InjectNestedFKMixin
):
    """
    ViewSet for Catalog Course Enrollments.
    Provides read-only access to enrollments in a specific catalog course.
    """

    queryset = CatalogCourseEnrollment.objects.select_related("user", "catalog_course")
    serializer_class = CatalogCourseEnrollmentSerializer
    permission_classes = [IsPartnerCatalogManager]
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
        course_pk = self.kwargs.get("course_pk")
        return qs.filter(catalog_course_id=course_pk) if course_pk else qs
