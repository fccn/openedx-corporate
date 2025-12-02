"""Service layer for catalog operations."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import ValidationError

from partner_catalog.edxapp_wrapper.course_module import course_overview
from partner_catalog.models import (
    BaseCatalog,
    CatalogEmailRegex,
    CatalogLearner,
    CatalogLearnerInvitation,
    CatalogManager,
)
from partner_catalog.policies.catalogs import is_user_an_active_catalog_learner, validate_catalog_enrollment_request
from partner_catalog.services.invitations import CatalogLearnerInvitationService

User = get_user_model()


class PartnerCatalogService():
    """
    Service layer for partner catalog operations.
    """

    ERROR_NOT_PENDING_INVITATION = "No pending invitation found for this catalog."
    ERROR_USER_NOT_ENROLLED = "User is not enrolled in this catalog."
    ERROR_USER_ALREADY_ENROLLED = "User is already enrolled in this catalog."

    @transaction.atomic
    def enroll_user_in_catalog(self, user, catalog) -> CatalogLearner:
        """
        Enroll a user in a catalog.

        This method attempts to enroll the user in the specified catalog.
        It checks for existing enrollment, pending invitations, and self-enrollment settings.

        Args:
            user: The user to enroll.
            catalog: The catalog to enroll the user in.
        Returns:
            The CatalogLearner instance.
        Raises:
            ValidationError: If user cannot be enrolled (no invitation and self-enrollment disabled).
        """

        if is_user_an_active_catalog_learner(user=user, catalog=catalog):
            return ValidationError(self.ERROR_USER_ALREADY_ENROLLED)

        invitation_service = CatalogLearnerInvitationService()
        invitation = invitation_service.get_latest_sent_invitation(
            user=user, catalog=catalog
        )

        if invitation:
            invitation_service.accept_invitation(
                invitation_id=invitation.id,
                user=user
            )
            invitation.refresh_from_db()
            return invitation.learner

        if not catalog.is_self_enrollment:
            raise ValidationError(self.ERROR_NOT_PENDING_INVITATION)

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
    def unenroll_user_from_catalog(self, user, catalog):
        """
        Unenroll a user from a catalog by removing their current invitation.

        This will mark the user's current invitation as removed and deactivate
        the learner, triggering all associated business logic and events.

        Args:
            user: The user to unenroll.
            catalog: The catalog to unenroll the user from.
        Returns:
            The deactivated CatalogLearner instance.
        Raises:
            ValidationError: If the user is not enrolled in the catalog.
        """
        learner = CatalogLearner.objects.filter(
            catalog=catalog,
            user=user,
            active=True
        ).select_related('current_invitation').first()

        if not learner or not learner.current_invitation:
            raise ValidationError(self.ERROR_USER_NOT_ENROLLED)

        invitation_service = CatalogLearnerInvitationService()
        invitation_service.remove_invitation(
            invitation_id=learner.current_invitation.id,
            user=user
        )
        learner.refresh_from_db()
        return learner

    @transaction.atomic
    def decline_catalog_invitation(self, user, catalog) -> CatalogLearnerInvitation:
        """
        Decline a pending invitation for a user in a catalog.

        Finds the user's pending invitation and declines it, triggering
        all associated business logic and events.

        Args:
            user: The user declining the invitation.
            catalog: The catalog for which to decline the invitation.
        Returns:
            The declined CatalogLearnerInvitation instance.
        Raises:
            ValidationError: If no pending invitation is found.
        """
        invitation_service = CatalogLearnerInvitationService()
        invitation = invitation_service.get_latest_sent_invitation(
            user=user, catalog=catalog
        )

        if not invitation:
            raise ValidationError(self.ERROR_NOT_PENDING_INVITATION)

        return invitation_service.decline_invitation(
            invitation_id=invitation.id,
            user=user
        )

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

        validate_catalog_enrollment_request(invitation=invitation)

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

    @staticmethod
    def get_user_catalog_invitation_status(catalog, user):
        """
        Get the invitation status for a user on a specific catalog.

        Returns the status display string of the user's current invitation.
        The user may be a CatalogLearner with a current invitation, or may have
        a latest sent invitation without being enrolled as a learner.

        Args:
            catalog: PartnerCatalog instance
            user: User instance

        Returns:
            str or None: Status display string (e.g., "Sent", "Accepted", "Declined")
        """
        if not user or not user.is_authenticated:
            return None

        learner = CatalogLearner.objects.filter(
            catalog=catalog,
            user=user,
            active=True
        ).select_related('current_invitation').first()

        if learner and learner.current_invitation:
            return learner.current_invitation.get_status_display()

        invitation_service = CatalogLearnerInvitationService()
        invitation = invitation_service.get_latest_sent_invitation(
            user=user, catalog=catalog
        )

        if invitation:
            return invitation.get_status_display()

        return None

    @staticmethod
    def is_user_catalog_manager(catalog, user):
        """
        Check if a user is an active manager of a specific catalog.

        Args:
            catalog: PartnerCatalog instance
            user: User instance

        Returns:
            bool: True if user is an active manager, False otherwise
        """
        if not user or not user.is_authenticated:
            return False

        return CatalogManager.objects.filter(
            catalog=catalog,
            user=user,
            active=True
        ).exists()

    @staticmethod
    @transaction.atomic
    def update_email_regexes(catalog, patterns):
        """
        Update email regex patterns for a catalog.

        Args:
            catalog: PartnerCatalog instance
            patterns: List of regex pattern strings

        Raises:
            ValidationError: If any pattern is invalid
        """
        existing_regexes = catalog.catalog_email_regexes.all()
        existing_patterns = set(existing_regexes.values_list('regex', flat=True))
        new_patterns = set(patterns)

        patterns_to_delete = existing_patterns - new_patterns
        patterns_to_create = new_patterns - existing_patterns

        if patterns_to_delete:
            existing_regexes.filter(regex__in=patterns_to_delete).delete()

        for pattern in patterns_to_create:
            try:
                email_regex = CatalogEmailRegex(catalog=catalog, regex=pattern)
                email_regex.save()
            except DjangoValidationError as exc:
                raise ValidationError({"email_regexes": exc.messages}) from exc

    def get_available_courses_for_catalog(self, catalog):
        """
        Get all courses available to add to a catalog.

        Returns courses from the base catalog and partner's offering
        that are not yet in this catalog.

        Args:
            catalog: The PartnerCatalog instance.

        Returns:
            dict: Dictionary with 'base' and 'organization' querysets of available courses.
        """
        CourseOverview = course_overview()
        base_catalog = BaseCatalog.get_instance()
        existing_course_ids = catalog.catalog_courses.values_list('course_overview_id', flat=True)

        base_available = (
            base_catalog.courses.exclude(id__in=existing_course_ids)
            if base_catalog else CourseOverview.objects.none()
        )
        org_available = (
            catalog.partner.get_partner_course_offering()
            .exclude(id__in=existing_course_ids)
        )

        return {
            'base': base_available,
            'organization': org_available
        }
