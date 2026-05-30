import os
import ssl

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planningwithyou.settings')

app = Celery('planningwithyou')
app.conf.broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
app.conf.result_backend = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

app.conf.broker_transport_options = {
    "ssl_cert_reqs": ssl.CERT_NONE
}

app.conf.result_backend_transport_options = {
    "ssl_cert_reqs": ssl.CERT_NONE
}

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
