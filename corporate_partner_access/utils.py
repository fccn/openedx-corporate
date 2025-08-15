"""Utility functions for corporate_partner_access, including drf-spectacular hooks."""


def spectacular_filter_hook(endpoints):
    """Filter endpoints to only include those starting with /corporate_access/api/."""
    # Only include endpoints starting with /corporate_access/api/
    return [
        (path, path_regex, method, callback)
        for (path, path_regex, method, callback) in endpoints
        if path.startswith("/corporate_access/api/")
    ]
