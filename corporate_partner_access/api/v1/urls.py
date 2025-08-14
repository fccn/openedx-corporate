"""Corporate Partner Access API v1 URLs."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from corporate_partner_access.api.v1.views import (
    CorporatePartnerCatalogCourseViewSet,
    CorporatePartnerCatalogEmailRegexViewSet,
    CorporatePartnerCatalogLearnerViewSet,
    CorporatePartnerCatalogViewSet,
    CorporatePartnerViewSet,
)

router = DefaultRouter()

router.register(r"partners", CorporatePartnerViewSet, basename="partner")
router.register(r"catalogs", CorporatePartnerCatalogViewSet, basename="catalog")
router.register(r"catalog_learners", CorporatePartnerCatalogLearnerViewSet, basename="catalog_learner")
router.register(r"catalog_courses", CorporatePartnerCatalogCourseViewSet, basename="catalog_course")
router.register(r"catalog_regexes", CorporatePartnerCatalogEmailRegexViewSet, basename="catalog_regexes")

urlpatterns = [
    path("", include(router.urls)),
]
