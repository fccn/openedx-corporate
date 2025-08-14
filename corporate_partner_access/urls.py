"""
URLs for corporate_partner_access.
"""

from django.urls import include, path

from corporate_partner_access import views
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from django.urls import reverse_lazy

urlpatterns = [
    path("info/", views.info_view, name="corporate-access-info"),
    path("api/", include("corporate_partner_access.api.urls")),
]

urlpatterns += [
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('swagger/', SpectacularSwaggerView.as_view(url_name='corporate_partner_access:schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='corporate_partner_access:schema'), name='redoc-ui'),
]
