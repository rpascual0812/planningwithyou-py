from django.conf import settings
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_GET


def _frontend_base() -> str:
    return (getattr(settings, 'FRONTEND_URL', None) or 'http://localhost:5173').rstrip('/')


@require_GET
def redirect_root_to_frontend(request):
    """Browsers or PayMongo sometimes hit the API host at /; send them to the SPA."""
    return HttpResponseRedirect(_frontend_base())


@require_GET
def redirect_pay_to_frontend(request, token):
    """Payment links are served by the React app, not Django."""
    query = request.META.get('QUERY_STRING', '')
    url = f'{_frontend_base()}/pay/{token}'
    if query:
        url = f'{url}?{query}'
    return HttpResponseRedirect(url)


@require_GET
def redirect_invitation_to_frontend(request, slug):
    """Published invitations are rendered by the React app."""
    query = request.META.get('QUERY_STRING', '')
    url = f'{_frontend_base()}/invitations/{slug}'
    if query:
        url = f'{url}?{query}'
    return HttpResponseRedirect(url)


@require_GET
def redirect_invitation_rsvp_to_frontend(request, slug):
    """RSVP submissions list is rendered by the React app."""
    query = request.META.get('QUERY_STRING', '')
    url = f'{_frontend_base()}/invitations/{slug}/rsvp'
    if query:
        url = f'{url}?{query}'
    return HttpResponseRedirect(url)
