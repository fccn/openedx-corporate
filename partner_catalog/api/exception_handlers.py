"""Custom exception handler that adds ``code`` to error responses.

Wired only on learner-facing viewsets to avoid changing the global
REST_FRAMEWORK["EXCEPTION_HANDLER"] setting.
"""

from rest_framework.views import exception_handler as drf_exception_handler


def catalog_exception_handler(exc, context):
    """
    Call DRF's default handler, then inject ``code`` from the exception's
    ``default_code`` into the response body.

    Keeps ``detail`` untouched for backwards compatibility.
    """
    response = drf_exception_handler(exc, context)

    if response is not None:
        code = getattr(exc, "default_code", None)
        if code and isinstance(response.data, dict) and "code" not in response.data:
            response.data["code"] = code

    return response
