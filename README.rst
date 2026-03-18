openedx-corporate (partner-catalog)
####################################

An Open edX Django plugin that gives corporate partners their own course catalog,
learner invitation flow, and enrollment licensing — all running inside a standard
Tutor-based Open edX installation without forking the LMS.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
********

Corporate partners need more than the standard Open edX enrollment model. They need
to control which learners can access which courses, track who was invited and when,
enforce seat limits, and see functional analytics across the full learner journey.

This plugin adds that layer on top of the LMS without modifying the LMS itself. It
integrates via the Open edX plugin architecture (``lms.djangoapp`` entry point) and
keeps all partner-specific data in its own models.

Domain Model
************

The domain is built around five core concepts:

**Partner**
  A corporate organization that has contracted access to a set of courses. Backed by
  an ``organizations.Organization`` record already present in the LMS.

**PartnerCatalog**
  A time-bounded collection of courses belonging to a Partner. Controls who can access
  it (via email regex patterns or explicit invitation), how many learners can join
  (``user_limit``), and how many paid course seats are available (``course_enrollments_limit``).
  A catalog is *active* only between its ``available_start_date`` and ``available_end_date``.

**Learner invitation flow**
  Access to a catalog is granted through an invitation:

  1. A ``CatalogLearnerInvitation`` is created (status: ``SENT``).
  2. The learner accepts → status becomes ``ACCEPTED``.
  3. A ``CatalogLearner`` record is created/activated, linking the user to the catalog.
  4. The learner can now enroll in courses inside that catalog.

  Invitations can also be declined or removed. Status is derived from timestamps, not
  stored as a free-form string, so it is always consistent.

**CatalogCourse**
  The join table between a ``PartnerCatalog`` and a course (``CourseOverview`` in LMS
  terms). Carries a ``position`` field for ordering within the catalog.

**CatalogCourseEnrollment**
  A *license* that says "this user has been granted paid access to this course by this
  catalog." One record per user+course across the entire platform — the catalog that
  first granted the license *owns* it. See `Enrollment License Model`_ below for the
  reasoning behind this design.

How enrollment works
====================

When a learner requests access to a catalog course the enrollment service:

1. Verifies the user is an active catalog learner and the catalog is active.
2. Checks the current LMS enrollment mode for the user/course pair.
3. For **paid** courses:

   - If the user already has a paid LMS enrollment (e.g. ``verified``) → grant access,
     no changes needed.
   - If the catalog has remaining bag capacity → create or reactivate a
     ``CatalogCourseEnrollment`` and upgrade/create the LMS enrollment to ``verified``.
   - If the user is already in ``audit``/``honor`` and the bag is full → return a
     warning (access is kept at the open mode, no exception raised).
   - If there is no LMS enrollment and the bag is full → raise ``CourseLimitReached``.

4. For **open** courses (audit/honor only) → enroll in ``audit``, no license record created.

Deactivation works symmetrically: the license is set to inactive and the LMS enrollment
is downgraded to ``audit``.

Analytics
=========

All invitation and enrollment lifecycle events are emitted as Open edX tracking events
and transformed to xAPI statements for the Aspects analytics pipeline. See
`docs/decisions/0001-aspects-in-openedx-corporate.rst`_ for the full analytics ADR.

.. _docs/decisions/0001-aspects-in-openedx-corporate.rst: docs/decisions/0001-aspects-in-openedx-corporate.rst

Key Concepts Reference
**********************

Enrollment License Model
========================

``CatalogCourseEnrollment`` represents a *license*, not an enrollment. The LMS already
has its own enrollment record (``CourseEnrollment``). The catalog license tracks *which
catalog* granted paid access and whether that access is currently active.

The uniqueness constraint is on ``(user, course_overview)`` — not on
``(user, catalog_course)`` — because a user can only hold one license per course
regardless of how many catalogs contain that course. The first catalog to grant access
becomes the *owner*. See `docs/decisions/0002-enrollment-license-model.rst`_ for details.

.. _docs/decisions/0002-enrollment-license-model.rst: docs/decisions/0002-enrollment-license-model.rst

Bag Quota (``course_enrollments_limit``)
========================================

A catalog's ``course_enrollments_limit`` field sets the maximum number of active paid
licenses owned by that catalog. Zero means unlimited. The quota is checked before
creating or reactivating a license. It counts *distinct active paid-course enrollments*
owned by the catalog, not total learners.

User Quota (``user_limit``)
============================

``user_limit`` caps the number of active ``CatalogLearner`` records. Zero means
unlimited. Checked before accepting an invitation.

Self-enrollment catalogs
========================

When ``PartnerCatalog.is_self_enrollment`` is ``True``, any authenticated user can
access the catalog without an invitation. Email regex patterns and learner limits still
apply.

Getting Started
***************

Requirements
============

* Open edX **Sumac** (Tutor 19) or later
* Python **3.11**
* Django **4.2** or **5.2**

Development installation
========================

.. code-block:: bash

    git clone <repository-url>
    cd openedx-corporate
    pip install -e ".[dev]"
    python manage.py migrate --settings=test_settings

Running tests
=============

.. code-block:: bash

    # Unit + integration tests (SQLite, no LMS needed)
    pytest --ds=test_settings tests/ -v

    # Full pipeline (requires Tutor)
    bash scripts/run_tests.sh

    # Quality checks
    tox -e quality

Project Layout
==============

.. code-block:: text

    partner_catalog/
    ├── models.py               # All domain models
    ├── exceptions.py           # Domain exceptions (CourseLimitReached, etc.)
    ├── policies/
    │   ├── catalogs.py         # Access control (can_access_catalog, email regex)
    │   ├── enrollments.py      # Enrollment eligibility checks
    │   └── limits.py           # Quota checks (user_limit, course_enrollments_limit)
    ├── services/
    │   ├── enrollments.py      # CatalogCourseEnrollmentService
    │   ├── invitations.py      # CatalogLearnerInvitationService
    │   └── platform_enrollment.py  # LMS enrollment sync helpers
    └── xapi/
        ├── constants.py        # Event name constants
        ├── emitter.py          # Tracking event emission
        └── transformers.py     # xAPI statement builders

    tests/
    ├── factories.py            # Test data helpers
    ├── test_catalog_course_enrollment_service.py   # No-DB unit tests
    ├── test_invitation_service.py
    ├── test_catalog_access_policies.py
    └── ...                     # DB-backed integration tests

Architecture Decisions
**********************

* `ADR 0001 — xAPI-Only Functional Analytics <docs/decisions/0001-aspects-in-openedx-corporate.rst>`_
* `ADR 0002 — Enrollment License Model <docs/decisions/0002-enrollment-license-model.rst>`_

License
*******

AGPL 3.0. See `LICENSE.txt <LICENSE.txt>`_ for details.
