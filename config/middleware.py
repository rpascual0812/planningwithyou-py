from __future__ import annotations

from .error_logging import log_request_error


class ErrorLoggingMiddleware:
    """
    Outermost middleware: log any unhandled exception for the full request chain
    (other middleware, DRF views, and plain Django views).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as exc:
            log_request_error(request, exception=exc, status_code=500)
            raise
