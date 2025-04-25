from django.shortcuts import render, redirect
from app_logs.utils import delete_old_logs
from .utils import is_no_loader



def error_404(request, exception):
    no_loader = is_no_loader(request)

    return render(request, 'root/404.html', status=404)


def homepage(request):
    error = ''
    css = request.session.get('css', 'normal.css')
    no_loader = is_no_loader(request)

    delete_old_logs()
    return render(request, 'app_main/homepage.html', {
        'error': error,
        'css': css,
        'no_loader': no_loader,
    })


def kill_loader(request):
    request.session['no_loader'] = True
    return redirect('homepage')


def loader(request):
    del request.session['no_loader']
    return redirect('homepage')


def theme_normal(request):
    request.session['css'] = 'normal.css'
    return redirect('homepage')


def theme_scout(request):
    request.session['css'] = 'scout.css'
    return redirect('homepage')