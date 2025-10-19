"""Partner Catalog API v1 URLs."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter

from partner_catalog.api.v1.views import (
    CatalogCourseEnrollmentViewSet,
    CorporatePartnerCatalogCourseViewSet,
    CorporatePartnerCatalogEmailRegexViewSet,
    CorporatePartnerCatalogLearnerViewSet,
    CorporatePartnerCatalogViewSet,
    CorporatePartnerViewSet,
)

router = DefaultRouter()
router.register(r"partners", CorporatePartnerViewSet, basename="partner")

partners_router = NestedDefaultRouter(router, r"partners", lookup="partner")
partners_router.register(r"catalogs", CorporatePartnerCatalogViewSet, basename="partner-catalog")

catalogs_router = NestedDefaultRouter(partners_router, r"catalogs", lookup="catalog")
catalogs_router.register(r"learners", CorporatePartnerCatalogLearnerViewSet, basename="partner-catalog-learners")
catalogs_router.register(r"courses", CorporatePartnerCatalogCourseViewSet, basename="partner-catalog-courses")
catalogs_router.register(
    r"email-regexes", CorporatePartnerCatalogEmailRegexViewSet,
    basename="partner-catalog-email-regexes",
)

courses_router = NestedDefaultRouter(catalogs_router, r"courses", lookup="course")
courses_router.register(
    r"enrollments",
    CatalogCourseEnrollmentViewSet,
    basename="partner-catalog-course-enrollments",
)
urlpatterns = [
    path("", include(router.urls)),
    path("", include(partners_router.urls)),
    path("", include(catalogs_router.urls)),
    path("", include(courses_router.urls)),
]
