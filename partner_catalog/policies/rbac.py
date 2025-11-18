"""
RBAC integration for corporate partner catalogs.

This module provides integration with edx-rbac by defining role assignment functions
that can be registered in SYSTEM_WIDE_ROLE_CLASSES. These functions generate JWT claims
based on the user's CatalogManager and CatalogLearner assignments.

"""

from __future__ import annotations

import logging

from django.db import DatabaseError

from partner_catalog.models import CatalogLearner, CatalogManager

logger = logging.getLogger(__name__)


def get_catalog_role_assignments(user):
    """
    Generate role assignments for a user based on their catalog relationships.

    This function is designed to be called by edx-rbac's create_role_auth_claim_for_user
    to populate JWT tokens with catalog-specific roles.
    """

    if not user or not user.is_authenticated:
        return

    try:
        if CatalogManager.objects.filter(user=user, active=True).exists():
            yield ("catalog_manager", "active")

        if CatalogLearner.objects.filter(user=user, active=True).exists():
            yield ("catalog_learner", "active")
    except (DatabaseError, AttributeError) as e:
        logger.warning(f"Could not retrieve catalog roles for user {user.id}: {e}")
        return
