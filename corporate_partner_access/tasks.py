from celery import shared_task

from corporate_partner_access.services.enrollments import ensure_catalog_enrollment_exists

@shared_task(bind=True, max_retries=5, default_retry_delay=60, acks_late=True)
def ensure_catalog_enrollment_task(self, user_id: int, course_id: str):
    obj, created = ensure_catalog_enrollment_exists(user_id=user_id, course_id=course_id)
    if obj is None:
        raise self.retry(countdown=min(60 * (2 ** self.request.retries), 15 * 60))
    return {"id": obj.id, "created": created}
