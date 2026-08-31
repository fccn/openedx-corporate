"""
Tests for InvitationEmailService — verifies that emails are rendered
in the language configured by settings.LANGUAGE_CODE.
"""

import os

import pytest
from django.core import mail
from django.test import override_settings

from partner_catalog.services.emails import InvitationEmailService
from tests.factories import make_catalog, make_invitation

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONF_LOCALE_DIR = os.path.join(_BASE_DIR, "partner_catalog", "conf", "locale")
TEMPLATES_DIR = os.path.join(_BASE_DIR, "partner_catalog", "templates")

_COMMON_SETTINGS = dict(
    LOCALE_PATHS=[CONF_LOCALE_DIR],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    TEMPLATES=[{
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [TEMPLATES_DIR],
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }],
)


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE="en", **_COMMON_SETTINGS)
def test_invitation_email_sent_in_english():
    """Email subject and body are in English when LANGUAGE_CODE is 'en'."""
    invitation = make_invitation(make_catalog(), invite_email="test@example.com")
    InvitationEmailService().send_invitation_created(invitation.id)

    assert len(mail.outbox) == 1
    assert "invited to view" in mail.outbox[0].subject.lower()
    assert "Hello," in mail.outbox[0].body


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE="pt-pt", **_COMMON_SETTINGS)
def test_invitation_email_sent_in_portuguese():
    """Email subject and body are in Portuguese when LANGUAGE_CODE is 'pt-pt'."""
    invitation = make_invitation(make_catalog(), invite_email="test@example.com")
    InvitationEmailService().send_invitation_created(invitation.id)

    assert len(mail.outbox) == 1
    assert "Foi convidado" in mail.outbox[0].subject
    assert "Olá," in mail.outbox[0].body
