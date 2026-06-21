from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.urls import path

# Give the admin index more than one app to reorder. auth already registers
# User + Group; these add the `contenttypes` and `sessions` apps.
admin.site.register(ContentType)
admin.site.register(Session)

urlpatterns = [path("admin/", admin.site.urls)]