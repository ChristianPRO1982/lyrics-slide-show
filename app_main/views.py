from django.shortcuts import render



def error_404(request, exception):
    return render(request, 'root/404.html', status=404)


def homepage(request):
    return render(request, 'app_main/homepage.html')