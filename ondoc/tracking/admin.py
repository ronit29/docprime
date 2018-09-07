from django.contrib import admin
from .models import Visitor, Visits, VisitorEvents
# Register your models here.
admin.site.register(Visitor)
admin.site.register(Visits)
admin.site.register(VisitorEvents)
