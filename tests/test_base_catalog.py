"""
Tests for BaseCatalog Singleton (Suite 9).

Covers BaseCatalog.get_instance() in partner_catalog/models.py:
- Returns the existing instance when one already exists
- Creates the instance when none exists
- Multiple calls return the same object (no duplicates)
"""

import pytest

from partner_catalog.models import BaseCatalog


@pytest.mark.django_db
def test_get_instance_creates_when_none_exists():
    """get_instance() creates a BaseCatalog when the table is empty."""
    assert BaseCatalog.objects.count() == 0

    instance = BaseCatalog.get_instance()

    assert instance is not None
    assert BaseCatalog.objects.count() == 1


@pytest.mark.django_db
def test_get_instance_returns_existing_instance():
    """get_instance() returns the existing BaseCatalog without creating a duplicate."""
    first = BaseCatalog.get_instance()

    second = BaseCatalog.get_instance()

    assert second.pk == first.pk
    assert BaseCatalog.objects.count() == 1


@pytest.mark.django_db
def test_get_instance_multiple_calls_return_same_object():
    """Calling get_instance() three times always yields the same record."""
    pks = {BaseCatalog.get_instance().pk for _ in range(3)}

    assert len(pks) == 1
    assert BaseCatalog.objects.count() == 1
