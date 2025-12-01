"""Service layer for catalog course operations."""

from django.db import transaction
from django.db.models import F
from rest_framework.exceptions import ValidationError

from partner_catalog.edxapp_wrapper.course_module import course_overview as CourseOverviewModel
from partner_catalog.models import CatalogCourse
from partner_catalog.policies.catalogs import can_course_be_added_to_catalog

CourseOverview = CourseOverviewModel()


class CatalogCourseService:
    """Service layer for managing catalog courses."""

    @staticmethod
    @transaction.atomic
    def add_catalog_courses(catalog, course_overview_ids, position=None):
        """
        Add one or multiple courses to a catalog at a specific position.

        Args:
            catalog: PartnerCatalog instance
            course_overview_ids: Single course ID string or list of course ID strings
            position: Position where courses will be inserted (None = append at end)

        Returns:
            List of created CatalogCourse instances

        Raises:
            ValidationError: If any course doesn't exist or validation fails
        """
        if isinstance(course_overview_ids, str):
            course_overview_ids = [course_overview_ids]

        valid_course_ids = CourseOverview.objects.filter(
            id__in=course_overview_ids
        ).values_list("id", flat=True)

        if valid_course_ids.count() != len(course_overview_ids):
            found_ids = set(valid_course_ids)
            missing_ids = set(course_overview_ids) - found_ids
            raise ValidationError(
                {"course_ids": f"Courses not found: {', '.join(missing_ids)}"}
            )

        courses_to_add = len(course_overview_ids)
        if position is None:
            position = CatalogCourse.objects.filter(catalog=catalog).count()

        CatalogCourse.objects.filter(catalog=catalog, position__gte=position).update(
            position=F("position") + courses_to_add
        )

        created_courses = []
        for idx, course_id in enumerate(course_overview_ids):
            course_overview = CourseOverview.objects.get(id=course_id)

            try:
                if not can_course_be_added_to_catalog(
                    catalog=catalog, course=course_overview
                ):
                    raise ValidationError(
                        {"course_ids": f"Course {course_id} cannot be added to this catalog."}
                    )
                catalog_course = CatalogCourse(
                    catalog=catalog,
                    course_overview=course_overview,
                    position=position + idx,
                )
                catalog_course.save()
                created_courses.append(catalog_course)
            except Exception as exc:
                raise ValidationError(
                    {"course_ids": f"Error adding course {course_id}: {exc}"}
                ) from exc

        return created_courses

    @staticmethod
    @transaction.atomic
    def remove_catalog_courses(catalog, catalog_course_ids):
        """
        Remove one or multiple catalog courses and reorganize positions.

        Args:
            catalog: PartnerCatalog instance
            catalog_course_ids: Single CatalogCourse ID or list of CatalogCourse IDs

        Returns:
            int: Number of courses deleted

        Raises:
            ValidationError: If any CatalogCourse doesn't exist in the catalog
        """
        if isinstance(catalog_course_ids, int):
            catalog_course_ids = [catalog_course_ids]

        courses_to_delete = CatalogCourse.objects.filter(
            catalog=catalog, id__in=catalog_course_ids
        )

        if courses_to_delete.count() != len(catalog_course_ids):
            found_ids = set(courses_to_delete.values_list("id", flat=True))
            missing_ids = set(catalog_course_ids) - found_ids
            raise ValidationError(
                {"catalog_courses": f"CatalogCourse IDs not found: {', '.join(map(str, missing_ids))}"}
            )

        try:
            deleted_count, _ = courses_to_delete.delete()
        except Exception as exc:
            raise ValidationError(
                {"catalog_courses": f"Error deleting catalog courses: {str(exc)}"}
            ) from exc

        CatalogCourseService._reorganize_positions(catalog)
        return deleted_count

    @staticmethod
    @transaction.atomic
    def update_course_position(catalog_course, new_position):
        """
        Update a course position and reorganize other courses accordingly.

        Args:
            catalog_course: CatalogCourse instance to update
            new_position: New position for the course
        """
        old_position = catalog_course.position

        if old_position == new_position:
            return catalog_course

        catalog = catalog_course.catalog

        if new_position < old_position:
            CatalogCourse.objects.filter(
                catalog=catalog, position__gte=new_position, position__lt=old_position
            ).update(position=F("position") + 1)
        else:
            CatalogCourse.objects.filter(
                catalog=catalog, position__gt=old_position, position__lte=new_position
            ).update(position=F("position") - 1)

        catalog_course.position = new_position
        catalog_course.save(update_fields=["position"])

        return catalog_course

    @staticmethod
    @transaction.atomic
    def _reorganize_positions(catalog):
        """
        Reorganize all course positions sequentially starting from 0.

        Args:
            catalog: PartnerCatalog instance
        """
        courses = list(
            CatalogCourse.objects.filter(catalog=catalog).order_by("position")
        )

        courses_to_update = []
        for idx, course in enumerate(courses):
            if course.position != idx:
                course.position = idx
                courses_to_update.append(course)

        if courses_to_update:
            CatalogCourse.objects.bulk_update(courses_to_update, ["position"])
