"""Partner Catalog API v1 URLs."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter

from partner_catalog.api.v1.learner_views import LearnerCatalogCourseViewSet, LearnerCatalogViewSet
from partner_catalog.api.v1.views import (
    CatalogCourseEnrollmentViewSet,
    CatalogCourseViewSet,
    CatalogLearnerInvitationViewSet,
    CatalogLearnerViewset,
    PartnerCatalogViewSet,
    PartnerViewset,
    CatalogEnrollmentsViewSet
)

router = DefaultRouter()
router.register(r"partners", PartnerViewset, basename="partner")
router.register(r"catalogs", LearnerCatalogViewSet, basename="learner-catalog")
router.register(r"manage/catalogs", PartnerCatalogViewSet, basename="partner-catalog")

catalogs_router = NestedDefaultRouter(router, r"catalogs", lookup="catalog")
catalogs_router.register(r"courses", LearnerCatalogCourseViewSet, basename="learner-catalog-courses")

manage_catalogs_router = NestedDefaultRouter(router, r"manage/catalogs", lookup="catalog")
manage_catalogs_router.register(r"learners", CatalogLearnerViewset, basename="catalog-learners")
manage_catalogs_router.register(r"courses", CatalogCourseViewSet, basename="catalog-courses")
manage_catalogs_router.register(r"invitations", CatalogLearnerInvitationViewSet, basename="catalog-learner-invitations")
manage_catalogs_router.register(r"enrollments", CatalogEnrollmentsViewSet, basename="catalog-enrollments")

courses_router = NestedDefaultRouter(manage_catalogs_router, r"courses", lookup="course")
courses_router.register(r"enrollments", CatalogCourseEnrollmentViewSet, basename="catalog-course-enrollments")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(catalogs_router.urls)),
    path("", include(manage_catalogs_router.urls)),
    path("", include(courses_router.urls)),
]
