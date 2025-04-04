from django.shortcuts import render
from app_logs.utils import delete_old_logs



def error_404(request, exception):
    return render(request, 'root/404.html', status=404)


def homepage(request):
    delete_old_logs()
    return render(request, 'app_main/homepage.html', {
        'error': '',
    })