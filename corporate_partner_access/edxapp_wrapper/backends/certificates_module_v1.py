"""Backend abstraction for certificates from edx-platform."""

# pylint: disable=import-error
from lms.djangoapps.certificates.data import CertificateStatuses
from lms.djangoapps.certificates.models import GeneratedCertificate


def generated_certificate_model():
    """Return GeneratedCertificate class."""
    return GeneratedCertificate


def certificate_statuses_model():
    """Return CertificateStatuses class."""
    return CertificateStatuses
