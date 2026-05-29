from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    InvitationTemplateViewSet,
    MarketplaceTemplateListView,
    PublicInvitationRsvpExportView,
    PublicInvitationRsvpView,
    PublicInvitationView,
    PublicTemplateAssetView,
    TemplateAssetUploadView,
)

router = DefaultRouter()
router.register(
    'template-studio/templates',
    InvitationTemplateViewSet,
    basename='template-studio-template',
)

urlpatterns = [
    path(
        'template-studio/assets/upload/',
        TemplateAssetUploadView.as_view(),
        name='template-studio-asset-upload',
    ),
    path(
        'template-studio/marketplace/',
        MarketplaceTemplateListView.as_view(),
        name='template-studio-marketplace',
    ),
    path(
        'public/template-assets/<uuid:asset_uuid>/',
        PublicTemplateAssetView.as_view(),
        name='public-template-asset',
    ),
    path(
        'public/invitations/<slug:slug>/rsvp/export/',
        PublicInvitationRsvpExportView.as_view(),
        name='public-invitation-rsvp-export',
    ),
    path(
        'public/invitations/<slug:slug>/rsvp/',
        PublicInvitationRsvpView.as_view(),
        name='public-invitation-rsvp',
    ),
    path(
        'public/invitations/<slug:slug>/',
        PublicInvitationView.as_view(),
        name='public-invitation',
    ),
    path('', include(router.urls)),
]
