#!/bin/bash

export PYTHONOPTIMIZE=1
celery -A mysql_server worker -l info


#celery -A mysql_server worker -l info -P eventlet