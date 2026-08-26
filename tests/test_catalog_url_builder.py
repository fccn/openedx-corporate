"""
Tests for partner_catalog.utils.urls.build_catalog_url.

Covers all meaningful combinations of CORPORATE_CATALOGS_MFE_BASE_URL
and LMS_ROOT_URL so that the URL is always produced correctly regardless
of how the settings are configured.
"""

import pytest
from django.test import override_settings

from partner_catalog.utils.urls import build_catalog_url

PARTNER = "FCT"
CATALOG = "fct-fundacao-para-a-ciencia-e-tecnologia"
EXPECTED_PATH = f"/learning-paths/{PARTNER}/catalog/{CATALOG}"


@override_settings(
    CORPORATE_CATALOGS_MFE_BASE_URL="https://lms.stage.nau.fccn.pt",
    LMS_ROOT_URL="https://lms.stage.nau.fccn.pt",
)
def test_base_url_without_learning_paths_prefix():
    """Base URL is the root domain — /learning-paths is appended once."""
    url = build_catalog_url(PARTNER, CATALOG)
    assert url == f"https://lms.stage.nau.fccn.pt{EXPECTED_PATH}"


@override_settings(
    CORPORATE_CATALOGS_MFE_BASE_URL="https://apps.example.com/learning-paths",
    LMS_ROOT_URL="https://lms.example.com",
)
def test_base_url_already_ends_with_learning_paths():
    """Base URL already contains /learning-paths — it must not be doubled."""
    url = build_catalog_url(PARTNER, CATALOG)
    assert "/learning-paths/learning-paths/" not in url
    assert url == f"https://apps.example.com{EXPECTED_PATH}"


@override_settings(
    CORPORATE_CATALOGS_MFE_BASE_URL="https://apps.example.com/learning-paths/",
    LMS_ROOT_URL="https://lms.example.com",
)
def test_base_url_with_trailing_slash_and_learning_paths():
    """Trailing slash on the /learning-paths suffix is also normalised."""
    url = build_catalog_url(PARTNER, CATALOG)
    assert "/learning-paths/learning-paths/" not in url
    assert url == f"https://apps.example.com{EXPECTED_PATH}"


@override_settings(
    CORPORATE_CATALOGS_MFE_BASE_URL="",
    LMS_ROOT_URL="https://lms.fallback.example.com",
)
def test_falls_back_to_lms_root_url_when_mfe_url_not_set():
    """When CORPORATE_CATALOGS_MFE_BASE_URL is empty, LMS_ROOT_URL is used."""
    url = build_catalog_url(PARTNER, CATALOG)
    assert url == f"https://lms.fallback.example.com{EXPECTED_PATH}"


@override_settings(
    CORPORATE_CATALOGS_MFE_BASE_URL=None,
    LMS_ROOT_URL="https://lms.fallback.example.com",
)
def test_falls_back_to_lms_root_url_when_mfe_url_is_none():
    """None value for CORPORATE_CATALOGS_MFE_BASE_URL also falls back."""
    url = build_catalog_url(PARTNER, CATALOG)
    assert url == f"https://lms.fallback.example.com{EXPECTED_PATH}"


@override_settings(
    CORPORATE_CATALOGS_MFE_BASE_URL="https://apps.example.com",
    LMS_ROOT_URL="https://lms.example.com",
)
def test_result_contains_partner_and_catalog_slugs():
    """Partner and catalog slugs appear verbatim in the generated URL."""
    url = build_catalog_url("my-partner", "my-catalog-slug")
    assert "/my-partner/catalog/my-catalog-slug" in url
