from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def songs(request: HttpRequest) -> HttpResponse:
    return render(request, "song/songs.html")
