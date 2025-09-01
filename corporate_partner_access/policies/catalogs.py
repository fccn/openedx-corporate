"""
Policies for access to corporate partner course catalogs.

This module provides utility functions to determine whether a user can view
courses in a given corporate partner catalog, including logic for staff,
public catalogs, enrolled learners, and email-based access via regex patterns.
"""

from __future__ import annotations

from django.apps import apps

from corporate_partner_access.helpers.regex_cache import compiled_email_regexes_for_catalog


def email_matches_catalog(email: str | None, catalog_id: int) -> bool:
    """
    Check if the given email matches any of the compiled regex patterns for the specified catalog.

    Args:
        email: The email address to check.
        catalog_id: The ID of the catalog whose regex patterns to use.

    Returns:
        True if the email matches any pattern for the catalog, False otherwise.
    """
    if not email:
        return False
    normalized = email.casefold().strip()
    for pat in compiled_email_regexes_for_catalog(catalog_id):
        if pat.fullmatch(normalized):
            return True
    return False


def can_user_see_catalog_courses(*, user, catalog) -> bool:
    """
    Determine if a user is allowed to see courses in a given corporate partner catalog.

    Args:
        user: The user object to check access for.
        catalog: The catalog instance to check access against.

    Returns:
        True if the user can see courses in the catalog, False otherwise.

    Access is granted if:
        - The user is staff or a superuser,
        - The catalog is public,
        - The user is an active enrolled learner in the catalog,
        - The user's email matches any of the catalog's allowed regex patterns.
    """
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    if getattr(catalog, "is_public", False):
        return True
    if not getattr(user, "is_authenticated", False):
        return False

    CatalogLearner = apps.get_model(
        'corporate_partner_access', 'CorporatePartnerCatalogLearner'
    )
    if CatalogLearner.objects.filter(catalog=catalog, user=user, active=True).exists():
        return True

    return email_matches_catalog(getattr(user, "email", None), catalog.id)
