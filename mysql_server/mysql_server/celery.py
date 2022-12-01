from __future__ import absolute_import, unicode_literals
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysql_server.settings')
app = Celery('mysql_server')
app.config_from_object('django.conf:settings', namespace='CELERY')
# app.config_from_object(os.environ.get('DJANGO_SETTINGS_MODULE'), namespace='CELERY')
app.autodiscover_tasks()


