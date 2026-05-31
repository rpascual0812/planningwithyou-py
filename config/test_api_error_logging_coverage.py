"""Verify every API route is served by DRF and covered by global error logging."""

from django.test import SimpleTestCase
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView

# Root routes that are not JSON API endpoints.
NON_API_PATH_PREFIXES = (
    'admin/',
)

# Plain Django function views (frontend redirects).
NON_API_VIEW_NAMES = {
    'redirect_root_to_frontend',
    'redirect_pay_to_frontend',
    'redirect_invitation_to_frontend',
    'redirect_invitation_rsvp_to_frontend',
}


def _is_drf_api_view(callback) -> bool:
    view_cls = getattr(callback, 'cls', None)
    if view_cls is None:
        view_cls = getattr(callback, 'view_class', None)
    if view_cls is None:
        return False
    try:
        return issubclass(view_cls, (APIView, GenericAPIView))
    except TypeError:
        return False


def _iter_routes(resolver, prefix: str = ''):
    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLResolver):
            nested = prefix + str(pattern.pattern)
            yield from _iter_routes(pattern, nested)
            continue
        if not isinstance(pattern, URLPattern):
            continue
        route = prefix + str(pattern.pattern)
        yield route, pattern.callback, getattr(pattern, 'name', None)


class ApiErrorLoggingCoverageTests(SimpleTestCase):
    def test_global_drf_exception_handler_is_configured(self):
        from django.conf import settings

        self.assertEqual(
            settings.REST_FRAMEWORK['EXCEPTION_HANDLER'],
            'config.drf_exception_handler.custom_exception_handler',
        )

    def test_error_logging_middleware_wraps_api_requests(self):
        from django.conf import settings

        self.assertEqual(
            settings.MIDDLEWARE[0],
            'config.middleware.ErrorLoggingMiddleware',
        )

    def test_all_api_routes_use_drf_views(self):
        resolver = get_resolver()
        non_drf_routes: list[str] = []

        for route, callback, name in _iter_routes(resolver):
            if any(route.startswith(prefix) for prefix in NON_API_PATH_PREFIXES):
                continue
            if getattr(callback, '__module__', '').startswith('django.views.static'):
                continue
            if getattr(callback, '__name__', '') in NON_API_VIEW_NAMES:
                continue
            if _is_drf_api_view(callback):
                continue
            label = name or callback.__name__
            non_drf_routes.append(f'{route} ({label})')

        self.assertEqual(
            non_drf_routes,
            [],
            'Non-DRF routes are not covered by REST_FRAMEWORK EXCEPTION_HANDLER:\n'
            + '\n'.join(non_drf_routes),
        )

    def test_paymongo_webhook_logs_swallowed_errors(self):
        import inspect

        from bookings.payment_link_views import PayMongoWebhookView

        source = inspect.getsource(PayMongoWebhookView.post)
        self.assertIn('log_request_error', source)
