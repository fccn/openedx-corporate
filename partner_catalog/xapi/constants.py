"""
Constants for partner_catalog xAPI tracking.
"""

# Tracking event names
EVENT_NAME_INVITATION_SENT = "openedx.corporate.catalog.invitation.sent"
EVENT_NAME_INVITATION_ACCEPTED = "openedx.corporate.catalog.invitation.accepted"
EVENT_NAME_INVITATION_DECLINED = "openedx.corporate.catalog.invitation.declined"
EVENT_NAME_INVITATION_REMOVED = "openedx.corporate.catalog.invitation.removed"
EVENT_NAME_COURSE_ENROLLMENT_ACTIVATED = "openedx.corporate.catalog.course_enrollment.activated"
EVENT_NAME_COURSE_ENROLLMENT_DEACTIVATED = "openedx.corporate.catalog.course_enrollment.deactivated"
EVENT_NAME_COURSE_ENROLLMENT_BLOCKED = "openedx.corporate.catalog.course_enrollment.blocked"

ALL_EVENTS = [
    EVENT_NAME_INVITATION_SENT,
    EVENT_NAME_INVITATION_ACCEPTED,
    EVENT_NAME_INVITATION_DECLINED,
    EVENT_NAME_INVITATION_REMOVED,
    EVENT_NAME_COURSE_ENROLLMENT_ACTIVATED,
    EVENT_NAME_COURSE_ENROLLMENT_DEACTIVATED,
    EVENT_NAME_COURSE_ENROLLMENT_BLOCKED,
]

# xAPI verb URIs for invitation lifecycle events
XAPI_VERB_SENT = "https://w3id.org/xapi/openedx/verb/sent"
XAPI_VERB_ACCEPTED = "https://w3id.org/xapi/openedx/verb/accepted"
XAPI_VERB_DECLINED = "https://w3id.org/xapi/openedx/verb/declined"
XAPI_VERB_REMOVED = "https://w3id.org/xapi/openedx/verb/removed"
XAPI_VERB_BLOCKED = "https://w3id.org/xapi/openedx/verb/blocked"

# Verb display values
SENT = "sent"
ACCEPTED = "accepted"
DECLINED = "declined"
REMOVED = "removed"
BLOCKED = "blocked"

# Common language key
EN = "en"

# xAPI activity types
XAPI_ACTIVITY_CORPORATE_CATALOG_INVITATION = (
    "https://w3id.org/xapi/openedx/activity/corporate-catalog-invitation"
)

# xAPI extension keys
XAPI_EXTENSION_EVENT_NAME = "https://w3id.org/xapi/openedx/extension/event-name"
XAPI_EXTENSION_CATALOG_ID = "https://w3id.org/xapi/openedx/extension/catalog-id"
XAPI_EXTENSION_PARTNER_ID = "https://w3id.org/xapi/openedx/extension/partner-id"
XAPI_EXTENSION_INVITATION_ID = "https://w3id.org/xapi/openedx/extension/invitation-id"
XAPI_EXTENSION_INVITED_BY_ID = "https://w3id.org/xapi/openedx/extension/invited-by-id"
XAPI_EXTENSION_REMOVED_BY_ID = "https://w3id.org/xapi/openedx/extension/removed-by-id"
XAPI_EXTENSION_LEARNER_USER_ID = "https://w3id.org/xapi/openedx/extension/learner-user-id"
XAPI_EXTENSION_INVITATION_CHANNEL = "https://w3id.org/xapi/openedx/extension/invitation-channel"
XAPI_EXTENSION_CATALOG_COURSE_ID = "https://w3id.org/xapi/openedx/extension/catalog-course-id"
XAPI_EXTENSION_ENROLLMENT_MODE = "https://w3id.org/xapi/openedx/extension/enrollment-mode"
XAPI_EXTENSION_BLOCKED_REASON = "https://w3id.org/xapi/openedx/extension/blocked-reason"

# Invitation origin channels
INVITATION_CHANNEL_MANUAL = "manual"
INVITATION_CHANNEL_BULK_CSV = "bulk_csv"
INVITATION_CHANNEL_SELF_ENROLL = "self_enroll"
