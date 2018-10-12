from django.shortcuts import render
from .models import Sitemap, Robot
from django.http import HttpResponse

# Create your views here.
def index(request):
    if request.method == "GET":
        sitemap = Sitemap.objects.all().order_by('-created_at').first()
        return HttpResponse(sitemap.file.file, content_type='text/xml')

def robots(request):
    if request.method == "GET":
        robot = Robot.objects.all().order_by('-created_at').first()
        return HttpResponse(robot.file.file, content_type='text/plain')
