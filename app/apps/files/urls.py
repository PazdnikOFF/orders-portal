from django.urls import path

from . import views

app_name = "files"

urlpatterns = [
    path("upload/<int:order_pk>/", views.upload, name="upload"),
    path("detach/<int:pk>/", views.detach, name="detach"),
    path("serve/<int:pk>/", views.serve, name="serve"),
]
