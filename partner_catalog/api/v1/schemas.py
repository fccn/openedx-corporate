"""Partner Catalog API v1 Schemas."""
from textwrap import dedent

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema


def bulk_upload_invitations_schema(func):
    return extend_schema(
        summary="Bulk upload invitations to catalog via CSV",
        description=dedent("""
        Upload a CSV file to invite multiple users to a catalog asynchronously.

        **CSV Format:**
        - `email`: User's email address (required)

        **CSV Example:**
        ```csv
        email
        john@example.com
        jane@example.com
        bob@example.com
        ```

        **Notes:**
        - Each email will receive an invitation to the catalog
        - Processing is done asynchronously via Celery
        - Returns a task ID to track the operation status
        """),
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'file': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'CSV file with email addresses'
                    }
                },
                'required': ['file']
            }
        },
        responses={
            202: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Task queued successfully",
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={"task_id": "550e8400-e29b-41d4-a716-446655440000", "status": "PENDING"}
                    )
                ]
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Bad request - missing file or invalid format",
                examples=[OpenApiExample('Missing File', value={"detail": "No file uploaded."})]
            )
        },
        tags=["Invitations"]
    )(func)


def bulk_remove_invitations_schema(func):
    return extend_schema(
        summary="Bulk remove invitations from catalog",
        description=dedent("""
        Remove multiple learner invitations from a catalog asynchronously.

        **Request Body:**
        ```json
        {
            "learner_ids": [1, 2, 3, 4, 5]
        }
        ```

        **Notes:**
        - Provide a list of CatalogLearner IDs to remove
        - Only accepted invitations can be removed
        - Processing is done asynchronously via Celery
        - Returns a task ID to track the operation status
        """),
        responses={
            202: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Task queued successfully",
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={"task_id": "550e8400-e29b-41d4-a716-446655440000", "status": "PENDING"}
                    )
                ]
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Bad request - invalid data",
                examples=[
                    OpenApiExample(
                        'Invalid Data',
                        value={"learner_ids": ["This field is required."]}
                    )
                ]
            )
        },
        tags=["Invitations"]
    )(func)


def bulk_status_invitations_schema(func):
    return extend_schema(
        summary="Check bulk invitations task status",
        description=dedent("""
        Check the status and results of a bulk invitation task.

        **Task Statuses:**
        - `PENDING`: Task is queued but not yet started
        - `STARTED`: Task is currently running
        - `SUCCESS`: Task completed successfully
        - `FAILURE`: Task failed with an error

        **Response includes:**
        - Task status and ID
        - Results (if completed successfully)
        - Error details (if failed)
        """),
        parameters=[
            OpenApiParameter(
                name="task_id",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description="Celery task ID returned from bulk upload endpoint",
                required=True,
            )
        ],
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Task status retrieved successfully",
                examples=[
                    OpenApiExample(
                        'Pending Task',
                        value={
                            "task_id": "550e8400-e29b-41d4-a716-446655440000",
                            "status": "PENDING"
                        }
                    ),
                    OpenApiExample('Completed Task', value={
                        "task_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "SUCCESS",
                        "result": {
                            "success": [
                                {
                                    "row": 2,
                                    "email": "john@example.com",
                                    "invitation_id": 123,
                                    "status": "Sent"
                                }
                            ],
                            "failed": [
                                {
                                    "row": 3,
                                    "email": "duplicate@example.com",
                                    "error": "An active invitation already exists for this user."
                                }
                            ],
                            "total": 2,
                            "success_count": 1,
                            "failed_count": 1
                        }
                    }),
                    OpenApiExample(
                        'Failed Task',
                        value={
                            "task_id": "550e8400-e29b-41d4-a716-446655440000",
                            "status": "FAILURE",
                            "error": "Invalid CSV format"
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Bad request - missing task_id",
                examples=[OpenApiExample('Missing Task ID', value={"detail": "task_id is required."})]
            ),
        },
        tags=["Invitations"]
    )(func)


def add_courses_schema(func):
    return extend_schema(
        summary="Add courses to catalog",
        description=dedent("""
        Add one or multiple courses to a catalog at a specific position.

        If position is specified, existing courses will be shifted.
        If position is omitted, courses are appended at the end.
        """),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'course_ids': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'List of course IDs to add',
                        'example': ["course-v1:edX+DemoX+Demo_Course"]
                    },
                    'position': {
                        'type': 'integer',
                        'description': 'Insert position (optional)',
                        'nullable': True,
                        'example': 0
                    }
                },
                'required': ['course_ids']
            }
        },
        responses={
            201: OpenApiResponse(
                description="Courses added successfully. Returns list of CatalogCourse objects.",
                examples=[
                    OpenApiExample(
                        'Success',
                        value=[
                            {
                                "id": 1,
                                "catalog_id": 1,
                                "position": 0,
                                "course_run": {
                                    "id": "course-v1:edX+DemoX+Demo_Course",
                                    "display_name": "Demo Course"
                                },
                                "enrollments": 0,
                                "certified": 0,
                                "completion_rate": 0.0
                            }
                        ]
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Validation error",
                examples=[
                    OpenApiExample('Missing Field', value={"course_ids": "This field is required."}),
                    OpenApiExample('Not Found', value={"detail": "Courses not found: course-v1:edX+Invalid"})
                ]
            )
        },
        tags=["Catalogs"]
    )(func)


def remove_courses_schema(func):
    return extend_schema(
        summary="Remove courses from catalog",
        description=dedent("""
        Remove one or multiple courses from a catalog.

        Positions are reorganized automatically after deletion.
        """),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'catalog_course_ids': {
                        'type': 'array',
                        'items': {'type': 'integer'},
                        'description': 'List of CatalogCourse IDs to remove',
                        'example': [1, 2, 3]
                    }
                },
                'required': ['catalog_course_ids']
            }
        },
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Courses removed successfully",
                examples=[
                    OpenApiExample('Success', value={"deleted_count": 3})
                ]
            ),
            400: OpenApiResponse(
                description="Validation error",
                examples=[
                    OpenApiExample('Missing Field', value={"catalog_course_ids": "This field is required."}),
                    OpenApiExample('Not Found', value={"detail": "CatalogCourse IDs not found: 999"})
                ]
            )
        },
        tags=["Catalogs"]
    )(func)


def report_schema(func):
    """Decorator to document CSV report endpoints.

    Expected behavior:
      * 200: Returns a CSV file attachment with the selected report fields as columns.
      * 400: Returns JSON error when there is no data available to export.

    Notes:
      * The CSV filename is always `report.csv` (may evolve later to be dynamic).
      * The set & order of columns comes from the view's `report_fields` attribute.
    """
    return extend_schema(
        summary="Download CSV report",
        description=dedent(
            """
            Generate and download a CSV report for the current resource scope.

            The columns included in the CSV are defined by the ViewSet's `report_fields` attribute.
            Filtering, search, or other query parameters applied to the list endpoint
            will also affect the dataset exported here.

            Responses:
            * 200: CSV file (text/csv) attachment named `report.csv`.
            * 400: JSON error when there is no data to include in the report.
            """
        ),
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description="CSV report generated successfully (text/csv attachment)",
                examples=[
                    OpenApiExample(
                        "CSV Preview (first lines)",
                        value="id,name\n1,Sample Name\n2,Another\n",
                    )
                ],
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="No data available to generate report",
                examples=[
                    OpenApiExample(
                        "No Data",
                        value={"detail": "No data to report."},
                    )
                ],
            ),
        },
        tags=["Reports"],
    )(func)
