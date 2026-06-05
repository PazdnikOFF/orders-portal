from django.urls import path

from . import views

app_name = "backups"

urlpatterns = [
    path("", views.backup_list, name="list"),
    path("create/", views.backup_create, name="create"),
    path("<int:pk>/restore/", views.backup_restore, name="restore"),
    path("<int:pk>/delete/", views.backup_delete, name="delete"),
]
