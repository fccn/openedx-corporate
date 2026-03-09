"""
Simple factory helpers for creating test model instances.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from organizations.models import Organization

from partner_catalog.models import (
    CatalogLearner,
    CatalogLearnerInvitation,
    Partner,
    PartnerCatalog,
)

User = get_user_model()

_counter = 0


def _unique_id():
    global _counter
    _counter += 1
    return _counter


def make_user(username=None, email=None, is_staff=False, is_superuser=False):
    """Create and return a User instance with a unique username."""
    username = username or f"user_{_unique_id()}"
    email = email or f"{username}@example.com"
    return User.objects.create_user(
        username=username,
        email=email,
        password="password",
        is_staff=is_staff,
        is_superuser=is_superuser,
    )


def make_organization(short_name=None):
    """Create and return an Organization with a unique short_name."""
    short_name = short_name or f"org_{_unique_id()}"
    return Organization.objects.create(
        name=f"Organization {short_name}",
        short_name=short_name,
    )


def make_partner(organization=None):
    """Create and return a Partner, creating an Organization if none is provided."""
    organization = organization or make_organization()
    return Partner.objects.create(organization=organization)


def make_catalog(partner=None, slug=None, **kwargs):
    """Create and return a PartnerCatalog with sensible date defaults."""
    partner = partner or make_partner()
    now = timezone.now()
    defaults = {
        "name": f"Catalog {_unique_id()}",
        "available_start_date": now - timedelta(days=1),
        "available_end_date": now + timedelta(days=30),
    }
    defaults.update(kwargs)
    catalog = PartnerCatalog(partner=partner, **defaults)
    if slug:
        catalog.slug = slug
    catalog.save()
    return catalog


def make_invitation(catalog, invite_email=None, user=None, invited_by=None, **kwargs):
    """Create and return a CatalogLearnerInvitation for the given catalog."""
    invite_email = invite_email or f"learner_{_unique_id()}@example.com"
    return CatalogLearnerInvitation.objects.create(
        catalog=catalog,
        invite_email=invite_email,
        user=user,
        invited_by=invited_by,
        **kwargs,
    )


def make_learner(catalog, user, invitation):
    """Create and return a CatalogLearner linked to the given catalog, user, and invitation."""
    return CatalogLearner.objects.create(
        catalog=catalog,
        user=user,
        current_invitation=invitation,
    )
