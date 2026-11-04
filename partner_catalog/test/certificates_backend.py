"""This file contains all the necessary backends in a test scenario for certificates."""

from django.conf import settings
from django.db import models


class CertiticateStatusedMock:
    """Mock of lms.djangoapps.certificates.data.CertificateStatuses (the statuses used in tests)."""

    downloadable = "downloadable"
    generating = "generating"
    notpassing = "notpassing"
    invalidated = "invalidated"
    unavailable = "unavailable"

    PASSED_STATUSES = (downloadable, generating)


class GeneratedCertificateTestModel(models.Model):
    """Test model to enable unit testing of the certified_count SQL annotations.

    ``course_id`` holds the ``CourseOverviewTestModel`` primary key, mirroring how
    the real ``GeneratedCertificate.course_id`` matches ``CourseOverview.id``.
    """

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    course_id = models.IntegerField()
    status = models.CharField(max_length=32)

    class Meta:
        """Meta class."""

        app_label = "partner_catalog"
        # Same as the LMS model: one certificate per (user, course).
        unique_together = (("user", "course_id"),)


def generated_certificate_model():
    """Fake generated_certificate_model class."""
    return GeneratedCertificateTestModel


def certificate_statuses_model():
    """Fake certificate_statuses_model class."""
    return CertiticateStatusedMock
