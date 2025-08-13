"""Corporate Partner Access API v0 URLs."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from corporate_partner_access.api.v0.views import (
    CorporatePartnerCatalogCourseViewSet,
    CorporatePartnerCatalogLearnerViewSet,
    CorporatePartnerCatalogViewSet,
    CorporatePartnerViewSet,
)

router = DefaultRouter()

router.register(r"partners", CorporatePartnerViewSet, basename="partner")
router.register(r"catalogs", CorporatePartnerCatalogViewSet, basename="catalog")
router.register(r"catalog-learners", CorporatePartnerCatalogLearnerViewSet, basename="catalog-learner")
router.register(r"catalog-courses", CorporatePartnerCatalogCourseViewSet, basename="catalog-course")

urlpatterns = [
    path("", include(router.urls)),
]
