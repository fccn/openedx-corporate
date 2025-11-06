"""Service layer for catalog operations."""

from django.contrib.auth import get_user_model
from django.db import transaction
from pydantic_core import ValidationError

from partner_catalog.models import CatalogLearner, CatalogLearnerInvitation
from partner_catalog.policies.catalogs import validate_enrollment_request
from partner_catalog.services.invitations import CatalogLearnerInvitationService

User = get_user_model()


class PartnerCatalogService():
    """
    Service layer for partner catalog operations.
    """

    @transaction.atomic
    def self_enroll_user_in_catalog(self, user, catalog) -> CatalogLearner:
        """
        Enroll the given user in the specified catalog as a CatalogLearner.

        It creates a new invitation and accepts it on behalf of the user, thereby
        triggering all associated business logic and events.

        Args:
            user: The user to enroll.
            catalog: The catalog to enroll the user in.
        Returns:
            The created CatalogLearner instance.
        """
        # Create the invitation to have record of the Data tracking agreements.
        invitation_service = CatalogLearnerInvitationService()
        invitation = invitation_service.create_new_invitation(
            invite_email=user.email,
            catalog_id=catalog.id,
            invited_by=None,
            emit_event=False
        )
        invitation_service.accept_invitation(
            invitation_id=invitation.id,
            user=user
        )

        # Refresh the invitation to get the recently created learner
        invitation.refresh_from_db()
        return invitation.learner

    @transaction.atomic
    def create_or_update_learner_from_invitation(
        self, invitation_id: int
    ) -> tuple[CatalogLearner, bool]:
        """
        Create or update a CatalogLearner based on a CatalogLearnerInvitation.
        Args:
            invitation_id: The ID of the CatalogLearnerInvitation.
        Returns:
            A tuple containing the CatalogLearner instance and a boolean indicating
            whether a new learner was created.
        """

        invitation = CatalogLearnerInvitation.objects.select_related('catalog').get(
            id=invitation_id
        )

        user = User.objects.get(id=invitation.user_id)
        validate_enrollment_request(
            catalog=invitation.catalog,
            user=user
        )

        learner, created = CatalogLearner.objects.get_or_create(
            user_id=invitation.user_id,
            catalog_id=invitation.catalog_id,
            defaults={'current_invitation_id': invitation.id}
        )

        # if the learner existed but has previous invitation, update it
        if not created and learner.current_invitation_id != invitation.id:
            learner.current_invitation_id = invitation.id
            learner.save()

        # Link the invitation back to the learner (history tracking)
        invitation.learner = learner
        invitation.save(update_fields=['learner'])

        return learner, created

    @transaction.atomic
    def deactivate_learner_from_invitation(
        self, invitation_id: int
    ) -> CatalogLearner:
        """
        Deactivate a CatalogLearner based on a CatalogLearnerInvitation.
        Args:
            invitation_id: The ID of the CatalogLearnerInvitation.
        """
        invitation = CatalogLearnerInvitation.objects.select_related('learner').get(
            id=invitation_id
        )
        learner = invitation.learner

        if not learner:
            raise ValidationError("No learner associated with this invitation.")

        # This triggers _compute_active() which sets active=False
        learner.save()
        return learner
