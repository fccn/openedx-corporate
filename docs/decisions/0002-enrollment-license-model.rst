ADR 0002: Catalog Course Enrollment as a Single Cross-Catalog License
======================================================================

Status
------

Accepted

Date
----

2026-03-18

Context
-------

A corporate learner can belong to more than one ``PartnerCatalog``, and multiple
catalogs can contain the same course. When a learner requests access to a course that
appears in two or more of their catalogs, the system must decide:

1. How many enrollment records to create.
2. Which catalog "owns" the learner's paid seat for quota-accounting purposes.
3. What happens to LMS enrollment mode when access is revoked by one catalog but the
   learner still belongs to another that contains the same course.

The naive approach — one enrollment record per (user, catalog, course) — creates
overlapping ownership, double-counting in quota checks, and ambiguity about which
record controls the LMS enrollment mode.

Decision
--------

``CatalogCourseEnrollment`` is a **license**: one record per ``(user, course)``
across the entire platform, enforced by a ``UniqueConstraint`` on
``(user, course_overview)``.

The ``catalog_course`` foreign key on that record points to the **first catalog** that
granted the license — the *owner*. Subsequent catalogs that contain the same course
cannot create a second license for the same user; they simply observe that the license
already exists.

The ``course_overview`` field is denormalized from ``catalog_course.course_overview``
to enforce the uniqueness constraint at the database level without a composite key
spanning three tables.

Quota accounting
~~~~~~~~~~~~~~~~

``course_enrollments_limit`` (the paid-seat bag) counts active licenses *owned by* a
given catalog — i.e. records where ``catalog_course__catalog_id`` matches the catalog
being checked. A license owned by another catalog does not consume this catalog's quota,
even if the course appears in both catalogs.

LMS enrollment mode
~~~~~~~~~~~~~~~~~~~

The LMS ``CourseEnrollment`` record is managed separately and treated as a projection
of the catalog license state:

* License active → LMS enrollment upgraded to ``verified`` (or the configured paid mode).
* License deactivated → LMS enrollment downgraded to ``audit``.

The service layer (``CatalogCourseEnrollmentService``) is the single point responsible
for keeping both in sync. The LMS record is never created or modified directly by
models or signals.

Considered Alternatives
-----------------------

**One record per (user, catalog_course)**

Rejected. A user in two catalogs that share a course would have two active records for
the same LMS enrollment. The quota check would need to de-duplicate across catalogs to
avoid double-counting, and deactivating one catalog's record would need to check whether
another catalog still grants access before downgrading the LMS mode. The cross-catalog
reconciliation logic would be both complex and error-prone.

**One record per (user, catalog) with a course list**

Rejected. Breaks the relational model, makes per-course operations (activate/deactivate
a single course) more expensive, and complicates uniqueness enforcement at the DB level.

Consequences
------------

Positive:

* A single database row answers "does this user have a paid license for this course?"
  without joining across catalogs.
* Quota accounting is a simple filtered count on ``CatalogCourseEnrollment`` with no
  deduplication step.
* Deactivating a catalog's licenses (e.g. when a learner is removed) only touches
  records owned by that catalog and does not affect licenses granted by other catalogs.
* The ``UniqueConstraint`` prevents duplicate licenses at the database level, eliminating
  a class of race-condition bugs.

Negative:

* The "first catalog wins" ownership rule is implicit. A learner who is later added to a
  second catalog that contains the same course will not generate a new license record,
  which can be surprising if operators expect per-catalog reporting.
* When a license is deactivated, the system does not automatically check whether another
  active catalog would re-grant access. This is intentional (deactivation is an explicit
  operator action) but operators should be aware of the behaviour.
* The denormalized ``course_overview`` field must be kept in sync with
  ``catalog_course.course_overview``. This is handled in ``CatalogCourseEnrollment.save()``
  but must be accounted for in any future migration that moves courses between catalogs.
