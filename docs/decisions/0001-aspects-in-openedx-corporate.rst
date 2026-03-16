ADR 0001: xAPI-Only Functional Analytics for ``openedx-corporate``
===================================================================

Status
------

Proposed

Date
----

2026-03-10

Context
-------

We need analytics for corporate catalog behavior in Aspects, focused on functional
journeys (invitation, enrollment, learning progression), not operational snapshots.

Required analytics outcomes:

- Invitation lifecycle and conversion
- Invitation source effectiveness (manual, bulk CSV, self-enroll)
- Enrollment lifecycle and conversion after invitation acceptance
- Lost-demand visibility for blocked enrollment attempts
- Learning outcomes after enrollment (completion, certification)
- Funnel visibility across the full learner journey

Current implementation status:

- Invitation domain events exist as Open edX public signals.
- Enrollment lifecycle logic exists in service layer.
- No dedicated xAPI event contract exists yet for partner catalog functional analytics.

Decision Drivers
----------------

- Implement analytics from this repository without introducing sink-table coupling.
- Reuse standard Aspects xAPI pipeline (event-routing-backends -> Ralph/Vector -> ClickHouse).
- Keep analytics based on immutable event streams.
- Explicitly avoid state-heavy operational requirements (for example, real-time seat inventory).

Decision
--------

We will implement functional analytics using xAPI only.

Scope inside ``openedx-corporate``:

1. Define and emit partner catalog tracking events via ``eventtracking.tracker.emit``.
2. Register custom xAPI transformers for those events.
3. Configure event-routing-backends allowlists for the new event names.
4. Build functional metrics in dbt from ``xapi_events_all_parsed``.
5. Expose dashboards through Aspects/Superset embedding.

Functional Metrics
------------------

The following metrics are in scope and expected to be produced from xAPI events.

1. ``invitations_sent``:
   Count of invitation sent events.
2. ``invitation_acceptance_rate``:
   accepted invitations / sent invitations.
3. ``invitation_decline_rate``:
   declined invitations / sent invitations.
4. ``invitation_response_time_p50_p90``:
   percentile latency from invitation sent to first accepted/declined response, joined by ``invitation_id``.
5. ``catalog_activation_rate``:
   distinct accepted users who later activate at least one catalog course enrollment /
   distinct accepted users.
6. ``enrollments_after_acceptance``:
   number of enrollment activations after invitation acceptance (per learner/catalog).
7. ``time_to_first_enrollment_p50_p90``:
   percentile latency from acceptance to first enrollment activation.
8. ``course_completion_rate``:
   distinct users with completion event / distinct enrolled users (course and catalog cuts).
9. ``certificate_rate``:
   distinct users with certification event / distinct enrolled users (course and catalog cuts).
10. ``funnel_counts_and_conversion``:
    invited -> accepted -> enrolled -> completed -> certified.
11. ``weekly_active_learners``:
   distinct learners with at least one learning event in a 7-day window.
12. ``retention_d7_d30``:
   users with follow-up learning activity at day 7/day 30, anchored on acceptance or first enrollment.
13. ``blocked_enrollment_attempts_by_reason``:
   count of blocked enrollment attempts split by ``blocked_reason``.
14. ``invitation_source_effectiveness``:
   invitation sent/accepted/declined conversion split by ``invitation_channel``.

Required Partner Catalog Tracking Events
----------------------------------------

The implementation will emit these Open edX tracking events:

1. ``openedx.corporate.catalog.invitation.sent``
2. ``openedx.corporate.catalog.invitation.accepted``
3. ``openedx.corporate.catalog.invitation.declined``
4. ``openedx.corporate.catalog.invitation.removed``
5. ``openedx.corporate.catalog.course_enrollment.activated``
6. ``openedx.corporate.catalog.course_enrollment.deactivated``
7. ``openedx.corporate.catalog.course_enrollment.blocked``

xAPI Mapping Contract
---------------------

Each tracking event must have a dedicated transformer registered in
``XApiTransformersRegistry``.

Required payload fields:

- ``event_name``
- ``timestamp``
- ``catalog_id``
- ``partner_id``
- ``user_id``
- ``course_id`` (for enrollment events)
- ``catalog_course_id`` (for enrollment events)
- ``invitation_id`` (for invitation events)
- ``invited_by_id`` and ``removed_by_id`` when available
- ``invitation_channel`` for invitation-sent events
- ``enrollment_mode`` when available
- ``blocked_reason`` for blocked enrollment events

Verb guidance:

- Invitation accepted/declined/removed may use dedicated Open edX verb URIs.
- Enrollment activated/deactivated should align with standard enrollment verbs
  (registered/unregistered) to simplify reuse of existing Aspects enrollment models.

Implementation Plan (Code-Level)
--------------------------------

Changes in this repository:

1. Add xAPI event constants:

- ``partner_catalog/xapi/constants.py``

2. Add xAPI transformers:

- ``partner_catalog/xapi/transformers.py``

3. Add tracking emitter utilities:

- ``partner_catalog/xapi/emitter.py``
- Emit on ``transaction.on_commit`` to avoid pre-commit analytics writes.

4. Wire emissions in service layer:

- ``partner_catalog/services/invitations.py`` for invitation lifecycle events.
- ``partner_catalog/services/enrollments.py`` for enrollment activation/deactivation events.

5. Register transformers at app startup:

- import in ``partner_catalog/apps.py`` ``ready()``.

6. Extend plugin settings for event-routing-backends integration:

- append all new event names to ``EVENT_TRACKING_BACKENDS_ALLOWED_XAPI_EVENTS``.
- update ``EVENT_TRACKING_BACKENDS`` using ``event_tracking_backends_config`` when available.

7. Add automated tests:

- event emission tests (service-level),
- transformer contract tests (statement shape),
- settings wiring tests.

Tutor Plugin Responsibilities
-----------------------------

A Tutor plugin is required for deployment/runtime orchestration. It is responsible for:

1. Ensuring xAPI routing pipeline is enabled and configured
   (event-routing-backends, Ralph/Vector, ClickHouse).
2. Shipping dbt models for the functional metrics listed above,
   sourced from ``xapi_events_all_parsed``.
3. Shipping Superset assets (datasets/charts/dashboards) for those metrics.
4. Providing operational commands for backfill and transformation jobs
   (for example, ``transform-tracking-logs`` and dbt runs).
5. Defining deployment configuration defaults and environment wiring.

Out of Scope
------------

- Event sink model tables for partner catalog entities.
- Seat inventory and other real-time operational snapshot metrics.

Consequences
------------

Positive:

- Single analytics ingestion model (xAPI) for functional metrics.
- No dependency on custom event sink table contracts for this use case.
- Metrics are traceable to immutable events and support historical analysis.

Negative:

- Reconstructing current-state views from events is more complex.
- Late-arriving or duplicated events require careful dbt logic and deduplication.
- Functional metrics quality depends on strict event contract discipline.

Operational Assumptions
-----------------------

- ``event-routing-backends`` and xAPI pipeline are installed and enabled.
- ``EVENT_TRACKING_BACKENDS`` is configured for xAPI transformation/routing.
- Aspects xAPI storage (``xapi_events_all_parsed`` lineage) is available.
- dbt and Superset assets are deployed via Tutor plugin.

Decision Outcome
----------------

Adopt xAPI-only functional analytics for partner catalog in this repository, and
operate it through a Tutor plugin that provides dbt/Superset/runtime orchestration.
