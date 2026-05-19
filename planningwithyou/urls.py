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

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('planningwithyou.file_urls')),
    path('api/', include('users.urls')),
    path('api/', include('companies.urls')),
    path('api/', include('emails.urls')),
    path('api/', include('documents.urls')),
    path('api/', include('contacts.urls')),
    path('api/', include('bookings.urls')),
    path('api/', include('calendars.urls')),
    path('api/', include('suppliers.urls')),
    path('api/', include('subscriptions.urls')),
    path('api/', include('config.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
