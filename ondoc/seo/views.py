from django.shortcuts import render
from .models import Sitemap, Robot, SitemapManger
from django.http import HttpResponse
from rest_framework import status


# Create your views here.
def index(request):
    if request.method == "GET":
        sitemap = Sitemap.objects.all().order_by('-created_at').first()
        return HttpResponse(sitemap.file.file, content_type='text/xml')


def robots(request):
    if request.method == "GET":
        robot = Robot.objects.all().order_by('-created_at').first()
        return HttpResponse(robot.file.file, content_type='text/plain')


def getsitemap(request):
    request_partial_path_list = request.path.split('/')
    if len(request_partial_path_list) < 2 :
        return HttpResponse(status=status.HTTP_400_BAD_REQUEST)

    sitemap_manager_qs = SitemapManger.objects.filter(file__contains=request_partial_path_list[len(request_partial_path_list)-1]).order_by('-created_at')
    if sitemap_manager_qs.exists():
        return HttpResponse(sitemap_manager_qs.first().file, content_type='application/gzip')
    else:
        return HttpResponse(status=status.HTTP_404_NOT_FOUND)
