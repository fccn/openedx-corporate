"""
Tests for InvitationEmailService — verifies that emails are rendered
in the language configured by settings.LANGUAGE_CODE.
"""

import ast
import gettext
import logging
import os
import re

import pytest
from django.core import mail
from django.test import override_settings
from django.utils.translation.template import templatize

from partner_catalog.services.emails import InvitationEmailService
from partner_catalog.settings.production import LOCALE_DIR
from tests.factories import make_catalog, make_invitation

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.join(_BASE_DIR, "partner_catalog", "templates")
EMAIL_TEMPLATES = [
    os.path.join(TEMPLATES_DIR, "partner_catalog", "emails", name)
    for name in ("invitation_created_subject.txt", "invitation_created_body.txt", "invitation_created_body.html")
]
PT_PT_MESSAGES_DIR = os.path.join(LOCALE_DIR, "pt_PT", "LC_MESSAGES")
PT_PT_PO = os.path.join(PT_PT_MESSAGES_DIR, "django.po")
# One msgid from each template, to notice when extraction stops finding strings.
KNOWN_MSGIDS = {
    "You've been invited to view %(catalog_name)s",
    "Visit the catalog to see available courses:",
    "View Catalog",
}

# LOCALE_PATHS is deliberately not overridden: the tests use the path the app's settings add.
_COMMON_SETTINGS = {
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "TEMPLATES": [{
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
}

ENGLISH_TEXT = [
    "Hello,",
    "Visit the catalog to see available courses:",
    "Need help? Contact support@example.com",
    "This is a notification email. You do not need to reply to this message.",
]
ENGLISH_HTML = [
    "Hello,",
    "Click the button below to visit the catalog and view available courses.",
    "View Catalog",
    "If the button above doesn't work, you can also visit this link:",
    'Need help? <a href="mailto:support@example.com">Contact support</a>',
    "This is a notification email. You do not need to reply to this message.",
]
PORTUGUESE_TEXT = [
    "Olá,",
    "Foi convidado/a para consultar o catálogo Test Catalog na plataforma corporativa de aprendizagem",
    "Aceda ao catálogo para ver os cursos disponíveis:",
    "Precisa de ajuda? Contacte support@example.com",
    "Esta é uma mensagem de notificação. Não é necessário responder a este email.",
]
PORTUGUESE_HTML = [
    "Olá,",
    "Foi convidado/a para consultar o catálogo <strong>Test Catalog</strong>",
    "Clique no botão abaixo para aceder ao catálogo e visualizar os cursos disponíveis.",
    "Ver Catálogo",
    "Se o botão acima não funcionar, pode também aceder através desta ligação:",
    'Precisa de ajuda? <a href="mailto:support@example.com">Contacte o suporte</a>',
    "Esta é uma mensagem de notificação. Não é necessário responder a este email.",
]


def _send_invitation_email():
    """Send the invitation email for a new catalog and return the sent message."""
    catalog = make_catalog(name="Test Catalog", support_email="support@example.com")
    invitation = make_invitation(catalog, invite_email="test@example.com")
    InvitationEmailService().send_invitation_created(invitation.id)

    assert len(mail.outbox) == 1
    return mail.outbox[0]


def _html_body(message):
    """Return the HTML alternative of an email message."""
    return next(content for content, mimetype in message.alternatives if mimetype == "text/html")


def _template_msgids():
    """Return the msgids of every translatable string in the invitation email templates."""
    msgids = set()
    for template in EMAIL_TEMPLATES:
        with open(template, encoding="utf-8") as template_file:
            source = templatize(template_file.read())
        for literal in re.findall(r"""gettext\(u?('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")\)""", source):
            msgids.add(ast.literal_eval(literal))
    return msgids


def _po_entries(path=PT_PT_PO):
    """Return the msgid -> msgstr pairs of a .po file; raise on plural forms and contexts."""
    entries, entry, field = {}, {}, None
    with open(path, encoding="utf-8") as po_file:
        for line in po_file:
            line = line.strip()
            if line.startswith(("msgctxt", "msgid_plural", "msgstr[")):
                raise ValueError(f"{path}: {line.split()[0]!r} entries are not supported by this reader")
            if line.startswith(("msgid ", "msgstr ")):
                field, _, value = line.partition(" ")
                if field == "msgid" and "msgstr" in entry:
                    entries[entry["msgid"]] = entry["msgstr"]
                    entry = {}
                entry[field] = ast.literal_eval(value)
            elif line.startswith('"') and field:
                entry[field] += ast.literal_eval(line)
    if "msgstr" in entry:
        entries[entry["msgid"]] = entry["msgstr"]
    entries.pop("", None)
    return entries


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE="en", **_COMMON_SETTINGS)
def test_invitation_email_sent_in_english():
    """Subject, text body and HTML body are in English when LANGUAGE_CODE is 'en'."""
    message = _send_invitation_email()

    assert message.subject == "You've been invited to view Test Catalog"
    for text in ENGLISH_TEXT:
        assert text in message.body
    for text in ENGLISH_HTML:
        assert text in _html_body(message)


@pytest.mark.django_db
@pytest.mark.parametrize("language_code", ["pt-PT", "pt-pt", "pt"])
def test_invitation_email_sent_in_portuguese(language_code):
    """Subject, text body and HTML body are fully in Portuguese for every pt code in use."""
    with override_settings(LANGUAGE_CODE=language_code, **_COMMON_SETTINGS):
        message = _send_invitation_email()

    html_body = _html_body(message)
    assert message.subject == "Foi convidado/a para consultar o catálogo Test Catalog"
    for text in PORTUGUESE_TEXT:
        assert text in message.body
    for text in PORTUGUESE_HTML:
        assert text in html_body
    for text in ENGLISH_TEXT:
        assert text not in message.body
    for text in ENGLISH_HTML:
        assert text not in html_body


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE="de", **_COMMON_SETTINGS)
def test_invitation_email_falls_back_to_english():
    """A language without a catalog in the package renders the English strings."""
    message = _send_invitation_email()

    assert message.subject == "You've been invited to view Test Catalog"
    for text in ENGLISH_TEXT:
        assert text in message.body
    for text in ENGLISH_HTML:
        assert text in _html_body(message)


def test_every_template_string_is_translated_in_the_po():
    """Each translatable string of the three templates has a non-empty pt_PT translation."""
    msgids = _template_msgids()
    entries = _po_entries()

    assert msgids, "No msgids extracted from the templates: has Django's templatize() output changed?"
    assert msgids >= KNOWN_MSGIDS, f"Extraction missed {sorted(KNOWN_MSGIDS - msgids)}"
    untranslated = sorted(msgid for msgid in msgids if not entries.get(msgid))
    assert not untranslated, f"Template strings without a pt_PT translation: {untranslated}"


@pytest.mark.parametrize("line", ['msgctxt "button"', 'msgid_plural "Catalogs"', 'msgstr[0] "Catálogo"'])
def test_po_reader_rejects_unsupported_entries(tmp_path, line):
    """The .po reader fails loudly on entries it cannot parse instead of misreading them."""
    po_path = tmp_path / "django.po"
    po_path.write_text(f'msgid "Catalog"\n{line}\nmsgstr "Catálogo"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="not supported"):
        _po_entries(po_path)


def test_compiled_mo_matches_the_po():
    """The committed .mo returns the .po translation for every entry, so it is not stale."""
    with open(os.path.join(PT_PT_MESSAGES_DIR, "django.mo"), "rb") as mo_file:
        compiled = gettext.GNUTranslations(mo_file)

    for msgid, msgstr in _po_entries().items():
        assert compiled.gettext(msgid) == msgstr
    for msgid in _template_msgids():
        assert compiled.gettext(msgid) != msgid


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE="en", **_COMMON_SETTINGS)
def test_invitation_email_body_has_no_leading_blank_line():
    """The {% load i18n %} tag must not push a blank line ahead of the greeting."""
    invitation = make_invitation(make_catalog(), invite_email="test@example.com")
    InvitationEmailService().send_invitation_created(invitation.id)

    body = mail.outbox[0].body
    assert not body.startswith(("\n", "\r\n"))
    assert body.startswith("Hello,")


@pytest.mark.django_db
@override_settings(
    LANGUAGE_CODE="en",
    CORPORATE_CATALOGS_MFE_BASE_URL="",
    LMS_ROOT_URL="",
    **_COMMON_SETTINGS,
)
def test_warns_when_catalog_url_has_no_host(caplog):
    """A misconfigured base URL yields a host-less link, which must be logged."""
    invitation = make_invitation(make_catalog(), invite_email="test@example.com")
    with caplog.at_level(logging.WARNING, logger="partner_catalog.services.emails"):
        InvitationEmailService().send_invitation_created(invitation.id)

    assert any("has no host" in record.getMessage() for record in caplog.records)


@pytest.mark.django_db
@override_settings(
    LANGUAGE_CODE="en",
    CORPORATE_CATALOGS_MFE_BASE_URL="https://apps.example.com",
    **_COMMON_SETTINGS,
)
def test_no_warning_when_catalog_url_is_absolute(caplog):
    """A properly configured base URL produces an absolute link and no warning."""
    invitation = make_invitation(make_catalog(), invite_email="test@example.com")
    with caplog.at_level(logging.WARNING, logger="partner_catalog.services.emails"):
        InvitationEmailService().send_invitation_created(invitation.id)

    assert "https://apps.example.com/learning-paths/" in mail.outbox[0].body
    assert not any("has no host" in record.getMessage() for record in caplog.records)
