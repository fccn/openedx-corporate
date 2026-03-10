"""Custom API exceptions for catalog enrollment and limits flows."""

from rest_framework import status
from rest_framework.exceptions import APIException


class CatalogEnrollmentError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "catalog_enrollment_error"
    default_detail = "Catalog enrollment error."

class InactiveCatalogEnrollment(CatalogEnrollmentError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "catalog_unavailable"
    default_detail = (
		"The catalog is not currently available. "
		"It can only be accessed within its configured availability period."
	)

class NotAllowedToEnroll(CatalogEnrollmentError):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "not_allowed_to_enroll"
    default_detail = "User is not allowed to enroll in this catalog course."


class UserNotEnrolled(CatalogEnrollmentError):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "user_not_enrolled"
    default_detail = "User is not enrolled in the specified catalog course."


class HonorSelfEnrollment(CatalogEnrollmentError):
    status_code = status.HTTP_200_OK
    default_code = "honor_self_enrollment"
    default_detail = "User already has honor enrollment; no catalog license is consumed."


class UnsupportedEnrollmentMode(CatalogEnrollmentError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "unsupported_enrollment_mode"
    default_detail = "Unsupported enrollment mode for LMS enrollment."


class UserLimitReached(CatalogEnrollmentError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "user_limit_reached"
    default_detail = "User limit reached for this catalog."


class CourseLimitReached(CatalogEnrollmentError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "course_limit_reached"
    default_detail = "Course enrollment limit reached for this catalog."
