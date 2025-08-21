"""OpenAPI schema helpers for API v1 (reports, bulk operations, etc.)."""

from textwrap import dedent

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema


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
