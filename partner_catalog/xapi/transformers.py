"""
xAPI transformers for partner_catalog tracking events.
"""

from __future__ import annotations

from partner_catalog.xapi import constants as partner_constants

try:
    from django.conf import settings
    from event_routing_backends.processors.xapi import constants as xapi_constants
    from event_routing_backends.processors.xapi.registry import XApiTransformersRegistry
    from event_routing_backends.processors.xapi.transformer import XApiTransformer
    from tincan import Activity, ActivityDefinition, Agent, Extensions, LanguageMap, Verb
except ImportError:  # pragma: no cover
    EVENT_ROUTING_BACKENDS_AVAILABLE = False
else:
    EVENT_ROUTING_BACKENDS_AVAILABLE = True


if EVENT_ROUTING_BACKENDS_AVAILABLE:
    class BasePartnerCatalogTransformer(XApiTransformer):
        """
        Base transformer for partner catalog events.
        """

        @staticmethod
        def _clean(mapping: dict) -> dict:
            """
            Return a copy without ``None`` values.
            """
            return {key: value for key, value in mapping.items() if value is not None}

        def get_actor(self):
            """
            Prefer standard actor generation, fallback to invitation-based actor.
            """
            if self.get_data("data.user_id") is not None:
                return super().get_actor()

            invitation_id = self.get_data("data.invitation_id")
            if invitation_id is not None:
                return Agent(
                    account={
                        "homePage": settings.LMS_ROOT_URL,
                        "name": f"corporate-catalog-invitation-{invitation_id}",
                    }
                )

            return Agent(
                account={
                    "homePage": settings.LMS_ROOT_URL,
                    "name": "corporate-catalog-anonymous",
                }
            )

        def get_context_extensions(self):
            """
            Attach catalog dimensions to context extensions.
            """
            base = dict(super().get_context_extensions())
            base.update(self._clean({
                partner_constants.XAPI_EXTENSION_EVENT_NAME: self.get_data("data.event_name"),
                partner_constants.XAPI_EXTENSION_CATALOG_ID: self.get_data("data.catalog_id"),
                partner_constants.XAPI_EXTENSION_PARTNER_ID: self.get_data("data.partner_id"),
            }))
            return Extensions(base)


    class BaseInvitationTransformer(BasePartnerCatalogTransformer):
        """
        Base transformer for invitation lifecycle events.
        """

        def get_object(self) -> Activity:
            """
            Return invitation object metadata for xAPI statement.
            """
            invitation_id = self.get_data("data.invitation_id")
            extensions = self._clean({
                partner_constants.XAPI_EXTENSION_INVITATION_ID: invitation_id,
                partner_constants.XAPI_EXTENSION_INVITED_BY_ID: self.get_data("data.invited_by_id"),
                partner_constants.XAPI_EXTENSION_REMOVED_BY_ID: self.get_data("data.removed_by_id"),
                partner_constants.XAPI_EXTENSION_LEARNER_USER_ID: self.get_data("data.learner_user_id"),
                partner_constants.XAPI_EXTENSION_INVITATION_CHANNEL: self.get_data("data.invitation_channel"),
            })

            return Activity(
                id=self.get_object_iri("corporate-catalog-invitation", invitation_id),
                definition=ActivityDefinition(
                    type=partner_constants.XAPI_ACTIVITY_CORPORATE_CATALOG_INVITATION,
                    extensions=Extensions(extensions),
                ),
            )


    class BaseEnrollmentTransformer(BasePartnerCatalogTransformer):
        """
        Base transformer for course enrollment lifecycle events.
        """

        def get_object(self) -> Activity:
            """
            Return course object for enrollment statements.
            """
            course_id = self.get_data("data.course_id")
            catalog_course_id = self.get_data("data.catalog_course_id")
            extensions = self._clean({
                partner_constants.XAPI_EXTENSION_CATALOG_COURSE_ID: catalog_course_id,
                partner_constants.XAPI_EXTENSION_ENROLLMENT_MODE: self.get_data("data.enrollment_mode"),
                partner_constants.XAPI_EXTENSION_BLOCKED_REASON: self.get_data("data.blocked_reason"),
            })

            if course_id is not None:
                object_id = self.get_object_iri("course", course_id)
            else:
                object_id = self.get_object_iri("catalog-course", catalog_course_id)

            return Activity(
                id=object_id,
                definition=ActivityDefinition(
                    type=xapi_constants.XAPI_ACTIVITY_COURSE,
                    extensions=Extensions(extensions),
                ),
            )


    @XApiTransformersRegistry.register(partner_constants.EVENT_NAME_INVITATION_SENT)
    class CatalogInvitationSentTransformer(BaseInvitationTransformer):
        """
        Transformer for invitation-sent events.
        """

        _verb = Verb(
            id=partner_constants.XAPI_VERB_SENT,
            display=LanguageMap({partner_constants.EN: partner_constants.SENT}),
        )


    @XApiTransformersRegistry.register(partner_constants.EVENT_NAME_INVITATION_ACCEPTED)
    class CatalogInvitationAcceptedTransformer(BaseInvitationTransformer):
        """
        Transformer for invitation-accepted events.
        """

        _verb = Verb(
            id=partner_constants.XAPI_VERB_ACCEPTED,
            display=LanguageMap({partner_constants.EN: partner_constants.ACCEPTED}),
        )


    @XApiTransformersRegistry.register(partner_constants.EVENT_NAME_INVITATION_DECLINED)
    class CatalogInvitationDeclinedTransformer(BaseInvitationTransformer):
        """
        Transformer for invitation-declined events.
        """

        _verb = Verb(
            id=partner_constants.XAPI_VERB_DECLINED,
            display=LanguageMap({partner_constants.EN: partner_constants.DECLINED}),
        )


    @XApiTransformersRegistry.register(partner_constants.EVENT_NAME_INVITATION_REMOVED)
    class CatalogInvitationRemovedTransformer(BaseInvitationTransformer):
        """
        Transformer for invitation-removed events.
        """

        _verb = Verb(
            id=partner_constants.XAPI_VERB_REMOVED,
            display=LanguageMap({partner_constants.EN: partner_constants.REMOVED}),
        )


    @XApiTransformersRegistry.register(partner_constants.EVENT_NAME_COURSE_ENROLLMENT_ACTIVATED)
    class CatalogCourseEnrollmentActivatedTransformer(BaseEnrollmentTransformer):
        """
        Transformer for enrollment-activated events.
        """

        _verb = Verb(
            id=xapi_constants.XAPI_VERB_REGISTERED,
            display=LanguageMap({xapi_constants.EN: xapi_constants.REGISTERED}),
        )


    @XApiTransformersRegistry.register(partner_constants.EVENT_NAME_COURSE_ENROLLMENT_DEACTIVATED)
    class CatalogCourseEnrollmentDeactivatedTransformer(BaseEnrollmentTransformer):
        """
        Transformer for enrollment-deactivated events.
        """

        _verb = Verb(
            id=xapi_constants.XAPI_VERB_UNREGISTERED,
            display=LanguageMap({xapi_constants.EN: xapi_constants.UNREGISTERED}),
        )


    @XApiTransformersRegistry.register(partner_constants.EVENT_NAME_COURSE_ENROLLMENT_BLOCKED)
    class CatalogCourseEnrollmentBlockedTransformer(BaseEnrollmentTransformer):
        """
        Transformer for enrollment-blocked events.
        """

        _verb = Verb(
            id=partner_constants.XAPI_VERB_BLOCKED,
            display=LanguageMap({partner_constants.EN: partner_constants.BLOCKED}),
        )
