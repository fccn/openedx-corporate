"""
Tests for Email Regex Validation (Suite 4).

Covers:
  - `CatalogEmailRegex.clean()` — normalization and validation on save
  - `email_matches_catalog()` — runtime email matching against stored patterns
"""

import pytest
from django.core.exceptions import ValidationError

from partner_catalog.helpers.regex_cache import clear_email_regex_cache
from partner_catalog.models import CatalogEmailRegex
from partner_catalog.policies.catalogs import email_matches_catalog
from tests.factories import make_catalog


@pytest.fixture(autouse=True)
def _clear_regex_cache():
    """Clear the LRU regex cache before and after every test to avoid cross-test contamination."""
    clear_email_regex_cache()
    yield
    clear_email_regex_cache()


# ---------------------------------------------------------------------------
# CatalogEmailRegex.clean() — pattern normalization
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pattern_is_normalized_to_anchored_form():
    """
    A bare pattern (without ^ and $) must be auto-wrapped to ^{pattern}$ on save.
    """
    catalog = make_catalog()
    entry = CatalogEmailRegex.objects.create(catalog=catalog, regex=r".*@company\.com")

    assert entry.regex == r"^.*@company\.com$"


@pytest.mark.django_db
def test_pattern_already_anchored_is_not_double_wrapped():
    """
    A pattern that already starts with ^ and ends with $ must not get extra anchors.
    """
    catalog = make_catalog()
    entry = CatalogEmailRegex.objects.create(catalog=catalog, regex=r"^.*@company\.com$")

    assert entry.regex == r"^.*@company\.com$"


@pytest.mark.django_db
def test_valid_pattern_saves_without_error():
    """A syntactically valid regex pattern must save successfully."""
    catalog = make_catalog()
    # Should not raise
    entry = CatalogEmailRegex.objects.create(catalog=catalog, regex=r"[a-z]+@example\.com")

    assert entry.pk is not None


@pytest.mark.django_db
def test_nested_quantifiers_raise_validation_error():
    """
    A pattern with nested quantifiers (e.g. (a+)+) must raise ValidationError.
    The check in clean() detects (.*)+ / (.+)+ style patterns.
    """
    catalog = make_catalog()
    instance = CatalogEmailRegex(catalog=catalog, regex=r"(.*)+@company\.com")

    with pytest.raises(ValidationError, match="nested quantifiers"):
        instance.clean()


@pytest.mark.django_db
def test_multiple_consecutive_wildcards_raise_validation_error():
    """
    A pattern with multiple consecutive .* wildcards (e.g. .*.*) must raise ValidationError.
    """
    catalog = make_catalog()
    instance = CatalogEmailRegex(catalog=catalog, regex=r".*.*@company\.com")

    with pytest.raises(ValidationError, match="nested quantifiers"):
        instance.clean()


@pytest.mark.django_db
def test_invalid_regex_syntax_raises_validation_error():
    """An unparseable regex (unclosed bracket) must raise ValidationError."""
    catalog = make_catalog()
    instance = CatalogEmailRegex(catalog=catalog, regex=r"[unclosed")

    with pytest.raises(ValidationError, match="Invalid regex"):
        instance.clean()


# ---------------------------------------------------------------------------
# email_matches_catalog() — runtime matching
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_email_matches_catalog_returns_true_on_match():
    """email_matches_catalog returns True when the email matches at least one pattern."""
    catalog = make_catalog()
    CatalogEmailRegex.objects.create(catalog=catalog, regex=r".*@company\.com")

    assert email_matches_catalog("alice@company.com", catalog.id) is True


@pytest.mark.django_db
def test_email_matches_catalog_returns_false_on_no_match():
    """email_matches_catalog returns False when the email matches none of the patterns."""
    catalog = make_catalog()
    CatalogEmailRegex.objects.create(catalog=catalog, regex=r".*@company\.com")

    assert email_matches_catalog("alice@other.org", catalog.id) is False


@pytest.mark.django_db
def test_email_matches_catalog_returns_false_when_no_patterns():
    """email_matches_catalog returns False when the catalog has no patterns defined."""
    catalog = make_catalog()
    # No CatalogEmailRegex rows

    assert email_matches_catalog("alice@company.com", catalog.id) is False


@pytest.mark.django_db
def test_email_matching_is_case_insensitive():
    """Pattern matching must be case-insensitive (IGNORECASE flag in the cache)."""
    catalog = make_catalog()
    CatalogEmailRegex.objects.create(catalog=catalog, regex=r".*@company\.com")

    assert email_matches_catalog("ALICE@COMPANY.COM", catalog.id) is True


@pytest.mark.django_db
def test_email_matches_first_of_multiple_patterns():
    """email_matches_catalog returns True when the email matches the first of several patterns."""
    catalog = make_catalog()
    CatalogEmailRegex.objects.create(catalog=catalog, regex=r".*@company\.com")
    CatalogEmailRegex.objects.create(catalog=catalog, regex=r".*@partner\.org")

    assert email_matches_catalog("bob@partner.org", catalog.id) is True


@pytest.mark.django_db
def test_none_email_returns_false():
    """email_matches_catalog returns False when email is None."""
    catalog = make_catalog()
    CatalogEmailRegex.objects.create(catalog=catalog, regex=r".*@company\.com")

    assert email_matches_catalog(None, catalog.id) is False
