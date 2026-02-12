"""View mixins for CSV export support."""

from rest_framework.settings import api_settings

from partner_catalog.helpers.renderers import CSVReportRenderer


class CSVExportMixin:
    """
    Mixin that adds CSV export capability to list endpoints.

    Usage: add to a ViewSet's bases and define ``csv_filename``,
    ``csv_fields`` (ordered list of dot-notation keys) and
    ``csv_labels`` (mapping of keys to human-readable headers).

    Clients request CSV via ``?format=csv`` or ``Accept: text/csv``.
    Pagination is automatically skipped for CSV responses so the full
    dataset is exported.

    Note: Open edX sets ``URL_FORMAT_OVERRIDE = None`` which disables
    DRF's built-in ``?format=`` query parameter support. This mixin
    works around that by explicitly checking the query parameter in
    ``get_format_suffix()``.
    """

    csv_filename = "report.csv"
    csv_fields = None
    csv_labels = {}

    def get_renderers(self):
        renderers = super().get_renderers()
        if not any(isinstance(r, CSVReportRenderer) for r in renderers):
            renderers.append(CSVReportRenderer())
        return renderers

    def get_format_suffix(self, **kwargs):
        """
        Re-enable ``?format=`` query parameter for CSV requests.

        Open edX sets ``URL_FORMAT_OVERRIDE = None`` globally, which
        prevents DRF from reading the ``?format=`` query parameter.
        We restore this behaviour only for our CSV-enabled views.
        """
        fmt = super().get_format_suffix(**kwargs)
        if fmt is None:
            key = api_settings.URL_FORMAT_OVERRIDE or "format"
            fmt = self.request.query_params.get(key)
        return fmt

    def paginate_queryset(self, queryset):
        """Skip pagination when the client requested CSV format."""
        if getattr(self.request, "accepted_renderer", None) and self.request.accepted_renderer.format == "csv":
            return None
        return super().paginate_queryset(queryset)

    def finalize_response(self, request, response, *args, **kwargs):
        """Attach Content-Disposition header for CSV downloads."""
        response = super().finalize_response(request, response, *args, **kwargs)
        if getattr(response, "accepted_renderer", None) and response.accepted_renderer.format == "csv":
            response["Content-Disposition"] = f'attachment; filename="{self.csv_filename}"'
        return response
