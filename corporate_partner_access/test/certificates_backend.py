"""This file contains all the necessary backends in a test scenario for certificates."""

class CertiticateStatusedMock:
    """Mock class to enable unit testing."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    REVOKED = "revoked"

    PASSED_STATUSES = [ACTIVE]

class GeneratedCertificateMock:
    """Mock class to enable unit testing."""

    def __init__(self, user_id, course_id, status):
        self.user_id = user_id
        self.course_id = course_id
        self.status = status

def generated_certificate_model():
    """Fake generated_certificate_model class."""
    return GeneratedCertificateMock

def certificate_statuses_model():   
    """Fake certificate_statuses_model class."""
    return CertiticateStatusedMock
