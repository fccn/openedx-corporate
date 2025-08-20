"""Corporate Partner Access API v1 Schemas."""
from textwrap import dedent

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema


def bulk_upload_learner_schema(func):
    return extend_schema(
        summary="Bulk upload learners to catalog via CSV",
        description=dedent("""
        Upload a CSV file to associate multiple users to a catalog asynchronously.

        **CSV Format:**
        - `username` (optional): User's username (preferred identifier)
        - `email` (optional): User's email address (alternative to username)
        - `active` (optional): Whether the user should be active in the catalog (defaults to True)

        **CSV Example:**
        ```csv
        username,email,active
        john_doe,john@example.com,True
        jane_smith,jane@example.com,False
        ,bob@example.com,True
        ```

        **Notes:**
        - At least one of `username` or `email` must be provided per row
        - If both username and email are provided, username takes precedence
        - The `active` field accepts: True, False, 1, 0, Yes, No, Y, N, T, F
        - Processing is done asynchronously via Celery
        """),
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'file': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'CSV file with learner data'
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
                        value={"task_id": "550e8400-e29b-41d4-a716-446655440000", "status": "processing"}
                    )
                ]
            ),
            400: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Bad request - missing file or invalid format",
                examples=[OpenApiExample('Missing File', value={"detail": "No file uploaded."})]
            )
        },
        tags=["Learners"]
    )(func)


def bulk_status_learner_schema(func):
    return extend_schema(
        summary="Check bulk upload task status",
        description=dedent("""
        Check the status and results of a bulk upload task.

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
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
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
                            "created": [
                                {
                                    "user_id": 123,
                                    "username": "john_doe",
                                    "email": "john@example.com",
                                    "active": True
                                }
                            ],
                            "failed": [{"username": "unknown_user", "error": "User not found"}]
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
                examples=[OpenApiExample('Missing Task ID', value={"detail": "task_id parameter is required."})]
            ),
        },
        tags=["Learners"]
    )(func)


def bulk_upload_invitations_schema(func):
    return extend_schema(
        summary="Bulk upload invitations to catalog course via CSV",
        description=dedent("""
        Upload a CSV file to invite multiple users to a catalog course asynchronously.

        **CSV Format:**
        - `email`: User's email address

        **CSV Example:**
        ```csv
        email
        john@example.com
        jane@example.com
        ```

        **Notes:**
        - Processing is done asynchronously via Celery
        """),
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'file': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'CSV file with learner data'
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
                        value={"task_id": "550e8400-e29b-41d4-a716-446655440000", "status": "processing"}
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


def bulk_status_invitations_schema(func):
    return extend_schema(
        summary="Check bulk invitations upload task status",
        description=dedent("""
        Check the status and results of a bulk upload task.

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
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
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
                            "created": [
                                {
                                    "id": 1,
                                    "email": "john@example.com",
                                    "catalog_course_id": 1,
                                    "status": 10,
                                    "status_display": "Sent",
                                    "created_now": True,
                                }
                            ],
                            "failed": [
                                {
                                    "email": "john@example.com",
                                    "catalog_course_id": 1,
                                    "error": "Error message",
                                    "row": {"email": "john@example.com"},
                                }
                            ]
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
                examples=[OpenApiExample('Missing Task ID', value={"detail": "task_id parameter is required."})]
            ),
        },
        tags=["Invitations"]
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
