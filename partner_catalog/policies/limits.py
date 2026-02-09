from django.db.models import Count
from partner_catalog.models import CatalogCourseEnrollment

def can_consume_user_limit(*, catalog) -> bool:
    if getattr(catalog, "user_limit", 0) in (0, None):
        return True
    used = (
        CatalogCourseEnrollment.objects
        .filter(active=True, catalog_course__catalog_id=catalog.id)
        .values("user_id").distinct().count()
    )
    return used < catalog.user_limit

def can_consume_course_limit(*, catalog, course_overview_id) -> bool:
    if getattr(catalog, "course_enrollments_limit", 0) in (0, None):
        return True
    used = (
        CatalogCourseEnrollment.objects
        .filter(
            active=True,
            catalog_course__catalog_id=catalog.id,
            course_overview_id=course_overview_id,
        )
        .count()
    )
    return used < catalog.course_enrollments_limit
