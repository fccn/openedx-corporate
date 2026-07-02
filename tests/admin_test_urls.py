"""Minimal URL conf for admin-related tests that need reverse('admin:...')."""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
