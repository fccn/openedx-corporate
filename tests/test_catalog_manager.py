"""
Tests for CatalogManager Validation (Suite 8).

Covers model-level constraints in partner_catalog/models.py → CatalogManager:
- A user can be assigned as manager to a catalog from their partner's organization
- A user cannot manage catalogs from two different partner organizations
- Unique constraint prevents the same user from being assigned to the same catalog twice
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from partner_catalog.models import CatalogManager
from tests.factories import make_catalog, make_partner, make_user

# ---------------------------------------------------------------------------
# Valid assignment
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manager_can_be_assigned_to_own_partner_catalog():
    """A user can be assigned as manager to a catalog belonging to their partner."""
    user = make_user()
    catalog = make_catalog()

    manager = CatalogManager(catalog=catalog, user=user)
    manager.save()  # should not raise

    assert CatalogManager.objects.filter(catalog=catalog, user=user).exists()


# ---------------------------------------------------------------------------
# Cross-partner constraint
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manager_cannot_manage_catalogs_from_different_partners():
    """A user already managing a catalog cannot be assigned to a catalog from a different partner."""
    user = make_user()

    partner_a_catalog = make_catalog()
    partner_b_catalog = make_catalog()  # different partner (make_catalog creates a new one each time)

    # Assign user to partner A's catalog
    CatalogManager.objects.create(catalog=partner_a_catalog, user=user)

    # Attempt to assign the same user to partner B's catalog
    manager = CatalogManager(catalog=partner_b_catalog, user=user)
    with pytest.raises(ValidationError, match="different partner organization"):
        manager.save()


@pytest.mark.django_db
def test_manager_can_manage_multiple_catalogs_from_same_partner():
    """A user can manage two catalogs that belong to the same partner."""
    user = make_user()
    partner = make_partner()

    catalog_a = make_catalog(partner=partner)
    catalog_b = make_catalog(partner=partner)

    CatalogManager.objects.create(catalog=catalog_a, user=user)

    manager = CatalogManager(catalog=catalog_b, user=user)
    manager.save()  # should not raise

    assert CatalogManager.objects.filter(user=user).count() == 2


# ---------------------------------------------------------------------------
# Unique constraint
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_same_user_cannot_be_assigned_to_same_catalog_twice():
    """UniqueConstraint prevents duplicate (catalog, user) assignments."""
    user = make_user()
    catalog = make_catalog()

    CatalogManager.objects.create(catalog=catalog, user=user)

    with pytest.raises(IntegrityError):
        CatalogManager.objects.create(catalog=catalog, user=user)
