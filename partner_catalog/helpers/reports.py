"""Helper functions for generating CSV reports."""
import csv

from django.http import HttpResponse
from rest_framework.response import Response


def get_nested_value(item, field):
    """
    Get a value from a nested dictionary using '__' notation.

    Args:
        item: The dictionary to extract the value from.
        field: The field name, which may contain '__' for nested access.

    Returns:
        The value at the nested path, or an empty string if not found.
    """
    if "__" not in field:
        return item.get(field, "")

    keys = field.split("__")
    value = item
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key, "")
        else:
            return ""
    return value


def generate_csv_report(data, fields, filename="report.csv"):
    """
    Generate a CSV report from serialized data.

    Args:
        data: List of dictionaries (serialized data).
        fields: List of field names to include in the CSV.
        filename: Name of the CSV file to download.

    Returns:
        HttpResponse with CSV content or Response with error if no data.
    """
    if not data:
        return Response({"detail": "No data to report."}, status=400)

    filtered_data = [
        {field: get_nested_value(item, field) for field in fields}
        for item in data
    ]

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.DictWriter(response, fieldnames=fields)
    writer.writeheader()
    writer.writerows(filtered_data)

    return response
