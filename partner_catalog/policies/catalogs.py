"""
Policies for access to corporate partner course catalogs.

This module provides utility functions to determine whether a user can view
courses in a given corporate partner catalog, including logic for staff,
public catalogs, enrolled learners, and email-based access via regex patterns.
"""

from __future__ import annotations

from django.apps import apps
from django.core.exceptions import ValidationError

from partner_catalog.exceptions import UserLimitReached
from partner_catalog.helpers.regex_cache import compiled_email_regexes_for_catalog
from partner_catalog.models import BaseCatalog, CatalogLearnerInvitation

Status = CatalogLearnerInvitation.Status


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


def can_access_catalog(*, user, catalog) -> bool:
    """
    Determine if a user is allowed to see courses in a given corporate partner catalog.

    Args:
        user: The user object to check access for.
        catalog: The catalog instance to check access against.

    Returns:
        True if the user can see courses in the catalog, False otherwise.

    Access is granted if:
        - The user is staff or a superuser,
        - The catalog is self-enrollment,
        - The user is an active enrolled learner in the catalog,
        - The user's email matches any of the catalog's allowed regex patterns.
    """
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    if getattr(catalog, "is_self_enrollment", False):
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


def can_course_be_added_to_catalog(*, catalog, course) -> bool:
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
    base_catalog = BaseCatalog.get_instance()

    if base_catalog.get_course_runs().filter(id=course.id).exists():
        return True

    catalog_org = catalog.partner.organization
    course_org = course.org

    if catalog_org.short_name != course_org:
        return False
    return True


def validate_catalog_enrollment_request(*, invitation) -> None:
    """
    Validate if a user can enroll in the specified catalog.

    Args:
        user: The user object requesting enrollment.
        catalog: The catalog instance to enroll in
    Raises:
        ValidationError: If the user cannot enroll in the catalog.
    """

    if invitation.status != Status.ACCEPTED:
        raise ValidationError("Invitation must be accepted to enroll in the catalog.")

    if not invitation.catalog.active:
        raise ValidationError("Catalog is not available for enrollment.")

    CatalogLearner = apps.get_model("partner_catalog", "CatalogLearner")
    already_active = CatalogLearner.objects.filter(
        catalog_id=invitation.catalog_id,
        user_id=invitation.user_id,
        active=True,
    ).exists()
    if not already_active and not has_catalog_capacity(catalog=invitation.catalog):
        raise UserLimitReached()
