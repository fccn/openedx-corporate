"""Utility functions for partner_catalog, including drf-spectacular hooks."""


def spectacular_filter_hook(endpoints):
    """Filter endpoints to only include those starting with /partner_catalog/api/."""
    # Only include endpoints starting with /partner_catalog/api/
    return [
        (path, path_regex, method, callback)
        for (path, path_regex, method, callback) in endpoints
        if path.startswith("/partner_catalog/api/")
    ]
