"""
Utilities for retrieving the current user in a safe and consistent way.

This module provides helper functions to obtain the current user object,
falling back to an AnonymousUser if no authenticated user is available.
It isolates CRUM (Current Request User Middleware) usage away from models
and other business logic, promoting cleaner separation of concerns.
"""

from __future__ import annotations

from crum import get_current_user
from django.contrib.auth.models import AnonymousUser


def safe_get_current_user():
    """
    Return the current user if available and authenticated; else AnonymousUser.
    This isolates CRUM away from models/services/policies.
    """
    u = get_current_user()
    return u if getattr(u, "is_authenticated", False) else AnonymousUser()
