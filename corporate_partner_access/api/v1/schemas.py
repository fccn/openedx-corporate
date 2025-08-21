"""Corporate Partner Access API v1 Schemas."""
from textwrap import dedent

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema


def bulk_upload_schema(func):
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


def bulk_status_schema(func):
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
