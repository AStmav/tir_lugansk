import os

# Путь к проекту (каталог, где лежит этот файл)
base_dir = os.path.dirname(os.path.abspath(__file__))

bind = "0.0.0.0:8000"
workers = 3
worker_class = "sync"
timeout = 30
keepalive = 2

accesslog = os.path.join(base_dir, "logs", "gunicorn_access.log")
errorlog = os.path.join(base_dir, "logs", "gunicorn_error.log")
loglevel = "info"

daemon = False
pidfile = None
