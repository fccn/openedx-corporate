"""
Tests for Partner Course Offering (Suite 10).

Covers Partner.get_partner_course_offering() in partner_catalog/models.py.

Note: The actual implementation simply does:
    CourseOverview.objects.filter(org=self.organization.short_name)
There is no BaseCatalog involvement in this method — the test plan item
"Returns courses from the BaseCatalog" is N/A for the current code.

CourseOverviewTestModel has no `org` field, so `course_overview()` is mocked
to avoid a FieldError and keep tests focused on the filter logic.
"""

import pytest
from unittest.mock import MagicMock, patch

from tests.factories import make_organization, make_partner

PATCH_COURSE_OVERVIEW = "partner_catalog.models.course_overview"


@pytest.mark.django_db
def test_get_partner_course_offering_filters_by_partner_org():
    """get_partner_course_offering() queries CourseOverview filtered by the partner's org short_name."""
    partner = make_partner()

    mock_qs = MagicMock()
    mock_model = MagicMock()
    mock_model.objects.filter.return_value = mock_qs

    with patch(PATCH_COURSE_OVERVIEW, return_value=mock_model):
        result = partner.get_partner_course_offering()

    mock_model.objects.filter.assert_called_once_with(org=partner.organization.short_name)
    assert result is mock_qs


@pytest.mark.django_db
def test_get_partner_course_offering_does_not_include_other_orgs():
    """get_partner_course_offering() does not filter by a different org's short_name."""
    partner = make_partner()
    other_org = make_organization()

    mock_model = MagicMock()

    with patch(PATCH_COURSE_OVERVIEW, return_value=mock_model):
        partner.get_partner_course_offering()

    call_kwargs = mock_model.objects.filter.call_args.kwargs
    assert call_kwargs.get("org") == partner.organization.short_name
    assert call_kwargs.get("org") != other_org.short_name
