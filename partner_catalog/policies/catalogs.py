"""
Policies for access to corporate partner course catalogs.

This module provides utility functions to determine whether a user can view
courses in a given corporate partner catalog, including logic for staff,
public catalogs, enrolled learners, and email-based access via regex patterns.
"""

from __future__ import annotations

from django.apps import apps
from django.core.exceptions import ValidationError

from partner_catalog.helpers.regex_cache import compiled_email_regexes_for_catalog


def email_matches_catalog(email: str | None, catalog_id: str) -> bool:
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


def can_access_catalog_courses(*, user, catalog) -> bool:
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
    if is_user_an_active_catalog_learner(user=user, catalog=catalog):
        return True

    return email_matches_catalog(getattr(user, "email", None), catalog.id)


def is_user_an_active_catalog_learner(*, user, catalog) -> bool:
    """
    Check if the user is an active learner in the specified catalog.

    Args:
        user: The user object to check.
        catalog: The catalog instance to check against.
    Returns:
        True if the user is an active learner in the catalog, False otherwise.
    """

    CatalogLearner = apps.get_model("partner_catalog", "CatalogLearner")
    if not getattr(user, "is_authenticated", False):
        return False

    return CatalogLearner.objects.filter(
        catalog=catalog, user=user, active=True
    ).exists()


def has_catalog_capacity(*, catalog) -> bool:
    """
    Check if the catalog has remaining capacity for new learners.

    Args:
        catalog: The catalog instance to check.
    Returns:
        True if the catalog has capacity, False if it has reached its limit.

    A catalog is considered to have capacity if:
        - its user_limit is set to 0 (indicating no limit), or
        - the current number of active learners is less than the user_limit.
    """

    CatalogLearner = apps.get_model("partner_catalog", "CatalogLearner")
    if catalog.user_limit == 0:
        return True

    current_count = CatalogLearner.objects.filter(catalog=catalog, active=True).count()
    return current_count < catalog.user_limit


def is_catalog_available(*, catalog) -> bool:
    """
    Verify if the catalog is currently available.

    Args:
        catalog: The catalog instance to check.

    Returns:
        True if the catalog is available, False otherwise.

    A catalog is considered available if:
        - it is marked as active, and
        - it has not reached its user capacity limit.
    """
    return catalog.active and has_catalog_capacity(catalog=catalog)


def can_course_be_added_to_catalog(*, catalog, course) -> bool:  # pylint: disable=unused-argument
    """
    Check if a course can be added to the specified catalog based on its active status.

    Args:
        catalog: The catalog instance to check.
    Returns:
        True if the catalog is active, False otherwise.

    A course can be added if:
        - its part of the catalogs partner(s) offerings or
        - is listed on the BaseCatalog list.
    """
    # TODO: Implement logic to check if a course can be added to the catalog.
    # A course can be added if its part of the catalogs partner(s) offerings or
    # is listed on the BaseCatalog list.

    # This functionality was implemented in PR #23 as part of the model clean() method.
    # Once that is verified, this function can be updated accordingly.

    return True


def validate_enrollment_request(*, user, catalog) -> None:
    """
    Validate if a user can enroll in the specified catalog.

    Args:
        user: The user object requesting enrollment.
        catalog: The catalog instance to enroll in
    Raises:
        ValidationError: If the user cannot enroll in the catalog.
    """

    if not is_catalog_available(catalog=catalog):
        raise ValidationError("Catalog is not available for enrollment.")

    if not can_access_catalog_courses(user=user, catalog=catalog):
        raise ValidationError("User is not allowed to enroll in this catalog.")
