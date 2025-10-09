"""Tasks module for partner_catalog."""

from celery import shared_task

from partner_catalog.services.enrollments import (
    deactivate_catalog_enrollment,
    ensure_catalog_enrollment_exists,
)


@shared_task(bind=True, max_retries=5, default_retry_delay=60, acks_late=True)
def ensure_catalog_enrollment_task(self, user_id: int, course_id: str):
    """Celery task to ensure a CatalogCourseEnrollment exists for a user and course."""
    obj, created = ensure_catalog_enrollment_exists(user_id=user_id, course_id=course_id)
    if obj is None:
        raise self.retry(countdown=min(60 * (2 ** self.request.retries), 15 * 60))
    return {"id": obj.id, "created": created}


@shared_task(max_retries=5, default_retry_delay=60, acks_late=True)
def deactivate_catalog_enrollment_task(user_id: int, course_id: str):
    """Celery task to deactivate a CatalogCourseEnrollment when user unenrolls."""
    obj, changed = deactivate_catalog_enrollment(user_id=user_id, course_id=course_id)
    return {"id": obj.id, "active": obj.active, "changed": changed}
