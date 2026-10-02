"""
Tests for the metrics exposed by PartnerViewset / PartnerSerializer.
"""

from types import SimpleNamespace

import pytest
from django.utils import timezone

from partner_catalog.api.v1.serializers import PartnerSerializer
from partner_catalog.api.v1.views import PartnerViewset
from tests.factories import make_catalog, make_invitation, make_learner, make_user

pytestmark = pytest.mark.django_db


def _add_learner(catalog, removed=False):
    """Create a CatalogLearner, active unless its accepted invitation was later removed."""
    user = make_user()
    now = timezone.now()
    invitation = make_invitation(
        catalog,
        user=user,
        invite_email=user.email,
        accepted_at=now,
        removed_at=now if removed else None,
    )
    return make_learner(catalog, user, invitation)


def test_partner_enrollments_counts_only_active_learners():
    catalog = make_catalog()
    other_catalog = make_catalog(partner=catalog.partner)
    _add_learner(catalog)
    _add_learner(other_catalog)
    _add_learner(catalog, removed=True)

    view = PartnerViewset()
    view.request = SimpleNamespace(user=make_user(is_staff=True))
    partner = view.get_queryset().get(pk=catalog.partner.pk)

    assert PartnerSerializer(partner).data["enrollments"] == 2
