from openedx_events.tooling import OpenEdxPublicSignal

from corporate_partner_access.events.data import CatalogCourseEnrollmentAllowedData

CATALOG_CEA_CREATED_V1 = OpenEdxPublicSignal(
    event_type="org.cpa.catalog.course.enrollment.allowed.created.v1",
    data={"invite": CatalogCourseEnrollmentAllowedData},
)

CATALOG_CEA_UPDATED_V1 = OpenEdxPublicSignal(
    event_type="org.cpa.catalog.course.enrollment.allowed.updated.v1",
    data={"invite": CatalogCourseEnrollmentAllowedData},
)

CATALOG_CEA_ACCEPTED_V1 = OpenEdxPublicSignal(
    event_type="org.cpa.catalog.course.enrollment.allowed.accepted.v1",
    data={"invite": CatalogCourseEnrollmentAllowedData},
)

CATALOG_CEA_DECLINED_V1 = OpenEdxPublicSignal(
    event_type="org.cpa.catalog.course.enrollment.allowed.declined.v1",
    data={"invite": CatalogCourseEnrollmentAllowedData},
)
