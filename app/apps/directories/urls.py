from django.urls import path

from . import views

app_name = "directories"

urlpatterns = [
    path("org-lookup/", views.org_lookup, name="org_lookup"),
    path("employees/", views.employee_list, name="employee_list"),
    path("employees/new/", views.employee_create, name="employee_create"),
    path("employees/<int:pk>/edit/", views.employee_edit, name="employee_edit"),
]
