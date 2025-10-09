"""
URLs for partner_catalog.
"""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from partner_catalog import views

urlpatterns = [
    path("info/", views.info_view, name="corporate-access-info"),
    path("api/", include("partner_catalog.api.urls")),
]

urlpatterns += [
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('swagger/', SpectacularSwaggerView.as_view(url_name='partner_catalog:schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='partner_catalog:schema'), name='redoc-ui'),
]
