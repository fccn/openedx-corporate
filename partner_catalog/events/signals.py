"""Signals for Partner Catalog Events."""

from openedx_events.tooling import OpenEdxPublicSignal

from partner_catalog.events.data import CatalogLearnerInvitationData

CATALOG_LEARNER_INVITATION_CREATED_V1 = OpenEdxPublicSignal(
    event_type="org.partner.catalog.learner.invitation.created.v1",
    data={"invitation": CatalogLearnerInvitationData},
)

CATALOG_LEARNER_INVITATION_REMOVED_V1 = OpenEdxPublicSignal(
    event_type="org.partner.catalog.learner.invitation.removed.v1",
    data={"invitation": CatalogLearnerInvitationData},
)

CATALOG_LEARNER_INVITATION_ACCEPTED_V1 = OpenEdxPublicSignal(
    event_type="org.partner.catalog.learner.invitation.accepted.v1",
    data={"invitation": CatalogLearnerInvitationData},
)

CATALOG_LEARNER_INVITATION_DECLINED_V1 = OpenEdxPublicSignal(
    event_type="org.partner.catalog.learner.invitation.declined.v1",
    data={"invitation": CatalogLearnerInvitationData},
)
