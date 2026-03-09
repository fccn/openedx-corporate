"""
Tests for PartnerCatalog model (Suite 5).

Covers:
- PartnerCatalog.active property (date-based availability window)
- PartnerCatalog.save() slug auto-generation
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from django.utils.text import slugify

from tests.factories import make_catalog, make_organization, make_partner



# ---------------------------------------------------------------------------
# PartnerCatalog.active — date-based availability window
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_catalog_active_within_date_window():
    """active is True when current date is between available_start_date and available_end_date."""
    now = timezone.now()
    catalog = make_catalog(
        available_start_date=now - timedelta(days=1),
        available_end_date=now + timedelta(days=1),
    )

    assert catalog.active is True


@pytest.mark.django_db
def test_catalog_inactive_before_start_date():
    """active is False when current date is before available_start_date."""
    now = timezone.now()
    catalog = make_catalog(
        available_start_date=now + timedelta(days=1),
        available_end_date=now + timedelta(days=2),
    )

    assert catalog.active is False


@pytest.mark.django_db
def test_catalog_inactive_after_end_date():
    """active is False when current date is after available_end_date."""
    now = timezone.now()
    catalog = make_catalog(
        available_start_date=now - timedelta(days=2),
        available_end_date=now - timedelta(days=1),
    )

    assert catalog.active is False


# ---------------------------------------------------------------------------
# PartnerCatalog.save() — slug auto-generation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_slug_auto_generated_when_not_provided():
    """Slug is auto-generated from org short_name and catalog name when not provided."""
    organization = make_organization(short_name="acme")
    partner = make_partner(organization=organization)
    catalog_name = "My Catalog"

    catalog = make_catalog(partner=partner, name=catalog_name)

    expected_slug = f"{slugify('acme')}-{slugify(catalog_name)}"
    assert catalog.slug == expected_slug


@pytest.mark.django_db
def test_slug_not_overwritten_when_already_set():
    """Slug is preserved on subsequent save() calls when already set."""
    organization = make_organization(short_name="acme")
    partner = make_partner(organization=organization)
    custom_slug = "my-custom-slug"

    catalog = make_catalog(partner=partner, slug=custom_slug)

    # Trigger another save and verify slug is unchanged
    catalog.name = "Updated Name"
    catalog.save()

    assert catalog.slug == custom_slug
