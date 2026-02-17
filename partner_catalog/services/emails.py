"""Services for building and sending partner catalog emails."""

import logging
from typing import Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from partner_catalog.utils.urls import build_catalog_url

logger = logging.getLogger("partner_catalog.services.emails")


class InvitationEmailService:
    """Service responsible for preparing and sending invitation emails."""

    def send_invitation_created(self, invitation_id: int) -> None:
        """Load invitation and send the 'invitation created' notification email.

        The email contains a link to the MFE catalog (no token) and basic branding.
        """
        from partner_catalog.models import CatalogLearnerInvitation

        try:
            invitation = (
                CatalogLearnerInvitation.objects.select_related(
                    "catalog", "catalog__partner", "catalog__partner__organization"
                ).get(pk=invitation_id)
            )
        except CatalogLearnerInvitation.DoesNotExist:
            logger.warning("Invitation id=%s not found, skipping email", invitation_id)
            return

        invite_email = invitation.invite_email
        if not invite_email:
            logger.warning("Invitation id=%s has no invite_email, skipping", invitation_id)
            return

        catalog = invitation.catalog
        partner = getattr(catalog, "partner", None)
        org = getattr(partner, "organization", None)

        partner_slug = getattr(org, "short_name", None) or getattr(org, "name", None) or ""
        catalog_slug = getattr(catalog, "slug", "") or ""

        catalog_url = build_catalog_url(partner_slug=partner_slug, catalog_slug=catalog_slug)

        partner_name = getattr(org, "short_name", None) or getattr(org, "name", None) or "Partner"

        partner_logo_url: Optional[str] = None
        if getattr(org, "logo", None):
            logo = org.logo
            if hasattr(logo, "url"):
                partner_logo_url = logo.url

        brand_primary_color = (
            getattr(catalog, "brand_primary_color", None)
            or getattr(partner, "brand_primary_color", None)
            or getattr(org, "brand_primary_color", None)
            or "#6B7280"
        )

        support_email = (
            catalog.support_email
            or getattr(settings, "DEFAULT_SUPPORT_EMAIL", None)
            or getattr(settings, "DEFAULT_FROM_EMAIL", None)
            or "support@example.com"
        )

        catalog_name = getattr(catalog, "name", None) or catalog_slug

        context = {
            "catalog_name": catalog_name,
            "catalog_url": catalog_url,
            "partner_name": partner_name,
            "partner_logo_url": partner_logo_url,
            "brand_primary_color": brand_primary_color,
            "support_email": support_email,
        }

        subject = render_to_string("partner_catalog/emails/invitation_created_subject.txt", context).strip()
        text_body = render_to_string("partner_catalog/emails/invitation_created_body.txt", context)
        html_body = render_to_string("partner_catalog/emails/invitation_created_body.html", context)

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or support_email

        msg = EmailMultiAlternatives(subject=subject, body=text_body, from_email=from_email, to=[invite_email])
        msg.attach_alternative(html_body, "text/html")

        try:
            msg.send()
            logger.info("Sent invitation email id=%s to %s", invitation_id, invite_email)
        except Exception:  # pragma: no cover - external mail failures
            logger.exception("Failed sending invitation email id=%s to %s", invitation_id, invite_email)
            raise
