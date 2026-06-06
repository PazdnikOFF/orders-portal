from django.urls import path

from . import views

app_name = "directories"

urlpatterns = [
    path("org-suggest/", views.org_suggest, name="org_suggest"),
]
