"""Partner Catalog API v1 Learner Views.

These views are intended for regular learners/users to consume catalog data.
They provide read-only access to catalogs and courses where the user is an active learner.
"""

from django.db.models import Count, Exists, OuterRef, Q
from django_filters.rest_framework import DjangoFilterBackend
from edx_rest_framework_extensions.permissions import IsAuthenticated
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from partner_catalog.api.v1.filters import PartnerCatalogFilter
from partner_catalog.api.v1.mixins import InjectNestedFKMixin
from partner_catalog.api.v1.serializers import (
    CatalogLearnerInvitationSerializer,
    CatalogLearnerSerializer,
    LearnerCatalogCourseSerializer,
    LearnerPartnerCatalogSerializer,
)
from partner_catalog.models import CatalogCourse, CatalogLearner, CatalogLearnerInvitation, PartnerCatalog
from partner_catalog.services.catalogs import PartnerCatalogService
from partner_catalog.services.enrollments import CatalogCourseEnrollmentService


class LearnerCatalogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for learners to view their catalogs.

    Provides read-only access to catalogs where the authenticated user
    is an active learner. Only shows catalogs that are currently available
    based on their availability dates.
    """

    # pylint: disable=E1111
    queryset = PartnerCatalog.objects.all()
    serializer_class = LearnerPartnerCatalogSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = PartnerCatalogFilter
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "available_start_date", "available_end_date"]
    ordering = ["name"]

    catalog_service = PartnerCatalogService()

    def get_queryset(self):
        """
        Viewset for catalogs from the perspective of the learner.

        Shows catalogs where:
            - User is an active learner
            - User has pending invitations
            - Catalog allows self-enrollment
        """
        user = self.request.user

        is_active_learner = CatalogLearner.objects.filter(
            catalog=OuterRef("pk"),
            user=user,
            active=True,
        )

        has_pending_invitation = CatalogLearnerInvitation.objects.filter(
            catalog=OuterRef("pk"),
            status=CatalogLearnerInvitation.Status.SENT,
        ).filter(Q(user=user) | Q(invite_email=user.email))

        return self.queryset.filter(
            Exists(is_active_learner)
            | Exists(has_pending_invitation)
            | Q(is_self_enrollment=True)
        ).annotate(courses_count=Count("catalog_courses", distinct=True))

    @action(detail=True, methods=["post"], url_path="enroll")
    def enroll(self, request, **kwargs):
        """
        Enroll user in a catalog.

        This action allows an user to enroll in a catalog if they have a valid invitation
        or if the catalog allows self-enrollment.
        """
        catalog = self.get_object()
        user = request.user

        learner = self.catalog_service.enroll_user_in_catalog(
            user=user, catalog=catalog
        )
        serializer = CatalogLearnerSerializer(learner)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="unenroll")
    def unenroll(self, request, **kwargs):
        """Allow a user to unenroll from a catalog."""
        catalog = self.get_object()
        user = request.user

        learner = self.catalog_service.unenroll_user_from_catalog(
            user=user, catalog=catalog
        )
        serializer = CatalogLearnerSerializer(learner)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="decline")
    def decline(self, request, **kwargs):
        """Decline a pending invitation for this catalog."""
        catalog = self.get_object()
        user = request.user

        invitation = self.catalog_service.decline_catalog_invitation(
            user=user, catalog=catalog
        )
        serializer = CatalogLearnerInvitationSerializer(invitation)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LearnerCatalogCourseViewSet(InjectNestedFKMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for learners to view courses in their catalogs.
    """

    queryset = CatalogCourse.objects.select_related("catalog", "course_overview").all()
    serializer_class = LearnerCatalogCourseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["course_overview__display_name"]
    ordering_fields = ["position"]
    ordering = ["position"]

    # Mixin config
    nested_lookup_kwarg = "catalog_pk"
    target_field_name = "catalog_id"

    lookup_field = "course_overview_id"
    lookup_url_kwarg = "course_id"

    enrollment_service = CatalogCourseEnrollmentService()

    def get_queryset(self):
        """
        Queryset of catalog courses from the learners level.
        """
        qs = self.queryset

        catalog_pk = self.kwargs.get("catalog_pk")

        if catalog_pk:
            qs = qs.filter(catalog_id=catalog_pk)

        return qs.annotate(
            enrollments_count=Count(
                "enrollments",
                filter=Q(enrollments__active=True),
                distinct=True,
            )
        )

    @action(detail=True, methods=["post"], url_path="enroll")
    def enroll(self, request, **kwargs):
        """
        Enroll the current user in a catalog course.

        This action allows a user to enroll in a specific catalog course if they
        are an active learner in the catalog and meet enrollment requirements.
        """
        catalog_course = self.get_object()
        user = request.user

        self.enrollment_service.create_or_activate_course_enrollment(
            user_id=user.id,
            catalog_course_id=catalog_course.id,
        )

        return Response(
            {"detail": "Successfully enrolled in the course."},
            status=status.HTTP_200_OK,
        )
