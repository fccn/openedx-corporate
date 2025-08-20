"""Mixins for corporate_partner_access API v1."""

import csv

from django.http import HttpResponse
from rest_framework.decorators import action
from rest_framework.response import Response

from corporate_partner_access.api.v1.schemas import report_schema


class InjectNestedFKMixin:
    """Generic mixin to inject/override a nested FK id from URL kwargs into serializer data.

    Subclasses set:
      nested_lookup_kwarg: name of kwarg added by nested router.
      target_field_name: serializer field to populate.
    """

    nested_lookup_kwarg = None
    target_field_name = None

    def get_serializer(self, *args, **kwargs):
        """Inject the nested FK id into serializer data if applicable."""
        if (
            "data" in kwargs
            and self.nested_lookup_kwarg
            and self.target_field_name
            and self.kwargs.get(self.nested_lookup_kwarg)
        ):
            data = kwargs["data"]
            if hasattr(data, "copy"):
                data = data.copy()
            data[self.target_field_name] = self.kwargs[self.nested_lookup_kwarg]
            kwargs["data"] = data
        return super().get_serializer(*args, **kwargs)


class ReportMixin:
    """
    Mixin to add a 'report' action to a ViewSet that returns a CSV report file.
    This Mixin expects each view to Override the `report_fields` attribute in order
    to specify which fields should be included in the report.
    """

    report_fields = ["id"]

    @report_schema
    @action(detail=False, methods=["get"], url_path="report")
    def report(self, request, *args, **kwargs):
        """Return a CSV file with the selected report fields."""

        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        if not data:
            return Response({"detail": "No data to report."}, status=400)

        headers = self.report_fields
        filtered_data = [
            {field: item.get(field, "") for field in headers} for item in data
        ]

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="report.csv"'

        writer = csv.DictWriter(response, fieldnames=headers)
        writer.writeheader()
        writer.writerows(filtered_data)
        return response
