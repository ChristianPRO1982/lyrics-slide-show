from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def animations(request: HttpRequest) -> HttpResponse:
    return render(request, "animation/animations.html")
