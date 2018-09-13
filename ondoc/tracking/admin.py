from django.contrib import admin
from .models import TrackingVisitor, TrackingVisit, TrackingEvent
# Register your models here.
admin.site.register(TrackingVisitor)
admin.site.register(TrackingVisit)
admin.site.register(TrackingEvent)
