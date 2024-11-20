from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth.decorators import user_passes_test
import os
import logging
from datetime import datetime, timedelta



SQL_REQUEST_LOG = os.environ
LOG_DIR = os.path.join(settings.BASE_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


def get_log_file(app_name):
    date_str = datetime.now().strftime('%Y-%m-%d')
    return os.path.join(LOG_DIR, f"{app_name}_{date_str}.log")


def setup_logger(app_name):
    log_file = get_log_file(app_name)
    logger = logging.getLogger(app_name)
    if not logger.hasHandlers():  # Prevents adding handlers multiple times
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)  # default level
    return logger


def create_log(app_name, function_name, text, log_type='info'):
    logger = setup_logger(app_name)
    log_method = getattr(logger, log_type, logger.info)  # défault 'info'
    log_method(f"{function_name}: {text}")


def create_SQL_log(app_name, function_name, request_name, request, params):
    if SQL_REQUEST_LOG:
        formatted_params = [
            f"'{str(param).replace('\'', '\\\'')}'" if isinstance(param, str) else str(param)
            for param in params
        ]
        
        request_for_print = request
        for param in formatted_params:
            request_for_print = request_for_print.replace('%s', param, 1)
        
        print(f"[{app_name}][{request_name}]: {request_for_print}")
        
    create_log(app_name, function_name, f"SQL: {request_name}")


def delete_old_logs():
    retention_days = int(os.getenv('LOG_RETENTION_DAYS', '30'))
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    for log_file in os.listdir(LOG_DIR):
        log_path = os.path.join(LOG_DIR, log_file)
        if os.path.isfile(log_path):
            try:
                file_mod_time = datetime.fromtimestamp(os.path.getmtime(log_path))
                if file_mod_time < cutoff_date:
                    os.remove(log_path)
            except Exception as e:
                create_log('system', 'delete_old_logs', f"Erreur lors de la suppression de {log_file}: {e}", 'error')


@user_passes_test(lambda u: u.is_superuser)
def view_logs(request):
    log_files = os.listdir(LOG_DIR)
    log_content = ""
    for log_file in log_files:
        log_path = os.path.join(LOG_DIR, log_file)
        try:
            with open(log_path, 'r') as file:
                log_content += f"==== {log_file} ====\n"
                log_content += file.read() + "\n\n"
        except Exception as e:
            log_content += f"Erreur lors de la lecture de {log_file}: {e}\n\n"
    return HttpResponse(f"<pre>{log_content}</pre>")
