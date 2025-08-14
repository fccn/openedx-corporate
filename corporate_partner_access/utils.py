def spectacular_filter_hook(endpoints):
    # Only include endpoints starting with /corporate_access/api/
    return [
        (path, path_regex, method, callback)
        for (path, path_regex, method, callback) in endpoints
        if path.startswith("/corporate_access/api/")
    ]
