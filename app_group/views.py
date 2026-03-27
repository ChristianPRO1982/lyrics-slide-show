from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def groups(request: HttpRequest) -> HttpResponse:
    return render(request, "group/groups.html")
