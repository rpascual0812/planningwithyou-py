from __future__ import annotations

from rest_framework.views import exception_handler

from .error_logging import log_request_error


def custom_exception_handler(exc, context):
    """Log server errors, then delegate to DRF's default handler."""
    response = exception_handler(exc, context)
    request = context.get('request')

    if response is None:
        log_request_error(request, exception=exc, status_code=500)
    elif response.status_code >= 500:
        log_request_error(
            request,
            exception=exc,
            status_code=response.status_code,
        )

    return response
