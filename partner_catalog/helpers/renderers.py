"""Custom DRF renderers for CSV export."""

import csv
import io

from rest_framework.renderers import BaseRenderer


class CSVReportRenderer(BaseRenderer):
    """
    Renderer that serializes data to CSV format.

    Reads ``csv_fields`` and ``csv_labels`` from the view to control
    which columns are included and how they are named in the header row.
    Nested dictionaries are flattened using dot notation
    (e.g. ``{"user": {"email": "a@b.c"}}`` becomes ``"user.email"``).
    """

    media_type = "text/csv"
    format = "csv"
    charset = "utf-8"

    def flatten_item(self, item, parent_key=""):
        """Flatten a nested dict using dot-separated keys."""
        flat = {}
        for key, value in item.items():
            full_key = f"{parent_key}.{key}" if parent_key else key
            if isinstance(value, dict):
                flat.update(self.flatten_item(value, full_key))
            else:
                flat[full_key] = value if value is not None else ""
        return flat

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return ""

        # Handle paginated responses.
        if isinstance(data, dict) and "results" in data:
            data = data["results"]

        if not isinstance(data, list):
            data = [data]

        flat_data = [self.flatten_item(item) for item in data]

        if not flat_data:
            return ""

        view = renderer_context.get("view") if renderer_context else None
        csv_fields = getattr(view, "csv_fields", None) or list(flat_data[0].keys())
        csv_labels = getattr(view, "csv_labels", {})

        headers = [csv_labels.get(field, field) for field in csv_fields]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        for item in flat_data:
            writer.writerow([item.get(field, "") for field in csv_fields])

        return output.getvalue()
