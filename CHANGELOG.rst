Change Log
##########

..
   All enhancements and patches to partner_catalog will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
**********

* feat: add ``POST catalogs/<id>/course-load-failures/`` so the learner MFE can report the courses of a catalog page it could not load. Each report writes one line to the LMS log (a warning when some courses failed, an error when all did) with the catalog and the failed course keys; only courses of that catalog are accepted, and reports are limited to 30 per user per hour
* fix: load the package's pt_PT catalog in the LMS and CMS, so invitation emails are sent in Portuguese. The theme and platform catalogs keep priority: a msgid they also translate uses their translation
* fix: enroll learners with the open mode the course actually offers (audit or honor) instead of a hardcoded "audit", which crashed catalog course enrollment on honor-mode courses
* fix(admin): keep base_catalog pre-filled after "Save and add another" in BaseCatalogCourseAdmin
