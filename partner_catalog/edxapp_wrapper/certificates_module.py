"""Certificates module definitions (wrapper around edx-platform)."""

from importlib import import_module

from django.conf import settings


def _backend():
    """Return the backend module for certificates operations."""
    path = getattr(
        settings,
        "CERTIFICATES_MODULE_BACKEND",
        "partner_catalog.edxapp_wrapper.backends.certificates_module_v1",
    )
    return import_module(path)


def generated_certificate_model():
    """Return the GeneratedCertificate model class from the backend."""
    return _backend().generated_certificate_model()


def certificate_statuses_model():
    """Return the CertificateStatuses class from the backend."""
    return _backend().certificate_statuses_model()
