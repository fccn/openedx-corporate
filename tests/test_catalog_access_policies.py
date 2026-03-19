"""
Tests for Catalog Access Policies (Suite 3).

Covers `can_access_catalog()` in partner_catalog/policies/catalogs.py.

Access rules implemented in the source:
  1. Staff or superuser → always True
  2. is_self_enrollment catalog → True for any user (no email check needed)
  3. Active CatalogLearner → True
  4. Email matches a catalog email regex → True (only for authenticated, non-self-enrollment)
  5. All other cases → False
"""

import pytest
from django.utils import timezone

from partner_catalog.helpers.regex_cache import clear_email_regex_cache
from partner_catalog.models import CatalogEmailRegex
from partner_catalog.policies.catalogs import can_access_catalog
from tests.factories import make_catalog, make_invitation, make_learner, make_user


@pytest.fixture(autouse=True)
def _clear_regex_cache():
    """
    Clear the thread-level email regex LRU cache before and after every test
    so that regex patterns created in one test do not bleed into another.
    """
    clear_email_regex_cache()
    yield
    clear_email_regex_cache()


# ---------------------------------------------------------------------------
# Staff / superuser — unconditional access
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_staff_can_access_any_catalog():
    """Staff user bypasses all other checks and always has access."""
    staff = make_user(is_staff=True)
    catalog = make_catalog()

    assert can_access_catalog(user=staff, catalog=catalog) is True


@pytest.mark.django_db
def test_superuser_can_access_any_catalog():
    """Superuser bypasses all other checks and always has access."""
    superuser = make_user(is_superuser=True)
    catalog = make_catalog()

    assert can_access_catalog(user=superuser, catalog=catalog) is True


# ---------------------------------------------------------------------------
# CatalogLearner.active flag
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_active_learner_can_access_catalog():
    """Active CatalogLearner (active=True) is granted access."""
    user = make_user()
    catalog = make_catalog()
    invitation = make_invitation(catalog, user=user, invite_email=user.email, accepted_at=timezone.now())
    make_learner(catalog, user, invitation)  # active=True — invitation is ACCEPTED

    assert can_access_catalog(user=user, catalog=catalog) is True


@pytest.mark.django_db
def test_inactive_learner_without_email_match_cannot_access():
    """Inactive CatalogLearner (active=False) with no email regex match is denied access."""
    user = make_user()
    catalog = make_catalog()
    # REMOVED invitation → learner.active=False (DB constraint requires accepted_at when removed_at is set)
    invitation = make_invitation(
        catalog,
        user=user,
        invite_email=user.email,
        accepted_at=timezone.now(),
        removed_at=timezone.now(),
    )
    make_learner(catalog, user, invitation)
    # No email regex patterns on this catalog → email_matches_catalog returns False

    assert can_access_catalog(user=user, catalog=catalog) is False


# ---------------------------------------------------------------------------
# Self-enrollment catalog
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_self_enrollment_catalog_grants_access_to_any_authenticated_user():
    """
    A catalog with is_self_enrollment=True is accessible to any user.
    The code returns True immediately on the is_self_enrollment flag,
    without consulting learner records or email regex patterns.
    """
    user = make_user()
    catalog = make_catalog(is_self_enrollment=True)
    # No learner record, no email regex — should still be True

    assert can_access_catalog(user=user, catalog=catalog) is True


# ---------------------------------------------------------------------------
# Email regex matching (non-self-enrollment catalog)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_email_matching_regex_grants_access():
    """
    Authenticated user whose email matches a catalog email regex can access
    a non-self-enrollment catalog (even without a learner record).
    """
    user = make_user(email="alice@company.com")
    catalog = make_catalog(is_self_enrollment=False)
    CatalogEmailRegex.objects.create(catalog=catalog, regex=r".*@company\.com")

    assert can_access_catalog(user=user, catalog=catalog) is True


@pytest.mark.django_db
def test_email_not_matching_regex_denies_access():
    """
    Authenticated user whose email does not match any catalog email regex
    is denied access to a non-self-enrollment catalog.
    """
    user = make_user(email="alice@other.com")
    catalog = make_catalog(is_self_enrollment=False)
    CatalogEmailRegex.objects.create(catalog=catalog, regex=r".*@company\.com")

    assert can_access_catalog(user=user, catalog=catalog) is False


@pytest.mark.django_db
def test_catalog_with_no_regex_patterns_denies_unenrolled_user():
    """
    Authenticated user with no learner record and no email regex patterns
    defined for the catalog is denied access.
    """
    user = make_user()
    catalog = make_catalog(is_self_enrollment=False)
    # No CatalogEmailRegex rows for this catalog

    assert can_access_catalog(user=user, catalog=catalog) is False
