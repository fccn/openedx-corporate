"""Unit tests for catalog enrollment limit policies."""

from types import SimpleNamespace
from unittest.mock import MagicMock


def test_can_consume_course_limit_counts_only_active_licenses(monkeypatch):
    from partner_catalog.policies import limits  # pylint: disable=import-outside-toplevel

    first_qs = MagicMock()
    first_qs.values_list.return_value.distinct.return_value = [101]

    second_qs = MagicMock()
    second_qs.count.return_value = 1

    filter_mock = MagicMock(side_effect=[first_qs, second_qs])

    monkeypatch.setattr(limits.CatalogCourseEnrollment.objects, "filter", filter_mock)
    monkeypatch.setattr(limits, "is_paid_course", lambda **_kwargs: True)

    catalog = SimpleNamespace(id=77, course_enrollments_limit=2)

    assert limits.can_consume_course_limit(catalog=catalog) is True
    assert filter_mock.call_args_list[0].kwargs == {
        "catalog_course__catalog_id": 77,
        "active": True,
    }
    assert filter_mock.call_args_list[1].kwargs == {
        "catalog_course__catalog_id": 77,
        "course_overview_id__in": [101],
        "active": True,
    }
