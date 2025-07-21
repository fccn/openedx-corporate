"""
URLs for corporate_partner_access.
"""
from django.urls import path

from corporate_partner_access import views

urlpatterns = [
    path("info/", views.info_view, name="corporate-access-info"),
]
