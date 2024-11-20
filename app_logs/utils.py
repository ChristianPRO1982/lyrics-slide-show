from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth.decorators import user_passes_test
import os
import logging
from datetime import datetime, timedelta



LOG_DIR = os.path.join(settings.BASE_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


def get_log_file(app_name):
    date_str = datetime.now().strftime('%Y-%m-%d')
    return os.path.join(LOG_DIR, f"{app_name}_{date_str}.log")


def create_log(app_name, function_name, text, log_type='info'):
    log_file = get_log_file(app_name)
    logger = logging.getLogger(app_name)
    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    log_method = getattr(logger, log_type, 'info')
    log_method(f"{function_name}: {text}")
    logger.removeHandler(handler)


def delete_old_logs():
    retention_days = int(os.getenv('LOG_RETENTION_DAYS', '30'))
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    for log_file in os.listdir(LOG_DIR):
        log_path = os.path.join(LOG_DIR, log_file)
        if os.path.isfile(log_path):
            file_mod_time = datetime.fromtimestamp(os.path.getmtime(log_path))
            if file_mod_time < cutoff_date:
                os.remove(log_path)


@user_passes_test(lambda u: u.is_superuser)
def view_logs(request):
    log_files = os.listdir(LOG_DIR)
    log_content = ""
    for log_file in log_files:
        with open(os.path.join(LOG_DIR, log_file), 'r') as file:
            log_content += file.read() + "\n"
    return HttpResponse(f"<pre>{log_content}</pre>")