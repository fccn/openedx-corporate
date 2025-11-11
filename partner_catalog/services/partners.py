"""Service layer for partner operations."""

from partner_catalog.edxapp_wrapper.course_module import course_overview


class PartnerService:
    """Service layer for partner-related business logic."""

    def get_available_courses(self, partner):
        """
        Get all courses available for a partner.

        Args:
            partner: The Partner instance.

        Returns:
            List of CourseOverview instances.
        """
        CourseOverview = course_overview()
        partner_courses = partner.get_partner_course_offering()

        # TODO: Add the BaseCatalog courses once they are available.
        return CourseOverview.objects.filter(id__in=partner_courses)
