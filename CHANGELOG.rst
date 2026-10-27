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

* fix: load the package's pt_PT catalog in the LMS and CMS, so invitation emails are sent in Portuguese. The theme and platform catalogs keep priority: a msgid they also translate uses their translation
* fix: enroll learners with the open mode the course actually offers (audit or honor) instead of a hardcoded "audit", which crashed catalog course enrollment on honor-mode courses
* fix(admin): keep base_catalog pre-filled after "Save and add another" in BaseCatalogCourseAdmin
