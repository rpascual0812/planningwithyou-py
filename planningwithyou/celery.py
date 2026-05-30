import os
import ssl

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planningwithyou.settings')

app = Celery('planningwithyou')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.broker_transport_options = {
    "ssl_cert_reqs": ssl.CERT_NONE
}

app.conf.result_backend_transport_options = {
    "ssl_cert_reqs": ssl.CERT_NONE
}
