"""
URL configuration for planningwithyou project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from planningwithyou.redirects import (
    redirect_invitation_rsvp_to_frontend,
    redirect_invitation_to_frontend,
    redirect_pay_to_frontend,
    redirect_root_to_frontend,
)

urlpatterns = [
    path('', redirect_root_to_frontend),
    path('pay/<uuid:token>/', redirect_pay_to_frontend),
    path('invitations/<slug:slug>/rsvp/', redirect_invitation_rsvp_to_frontend),
    path('invitations/<slug:slug>/', redirect_invitation_to_frontend),
    path('', include('planningwithyou.file_urls')),
    path('', include('users.urls')),
    path('', include('companies.urls')),
    path('', include('emails.urls')),
    path('', include('documents.urls')),
    path('', include('contacts.urls')),
    path('', include('bookings.urls')),
    path('', include('calendars.urls')),
    path('', include('suppliers.urls')),
    path('', include('packages.urls')),
    path('', include('subscriptions.urls')),
    path('', include('payments.urls')),
    path('', include('config.urls')),
    path('', include('system_notifications.urls')),
    path('', include('system_settings.urls')),
    path('', include('support.urls')),
    path('', include('template_studio.urls')),
    path('', include('ai_assistant.urls')),
    # After REST ``admin/*`` API routes (kyb, payouts, notifications, legal).
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
