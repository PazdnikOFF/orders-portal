from django.urls import path

from . import views

app_name = "directories"

urlpatterns = [
    path("org-suggest/", views.org_suggest, name="org_suggest"),
    path("distributor-suggest/", views.distributor_suggest, name="distributor_suggest"),
    path("distributors/", views.distributor_list, name="distributor_list"),
    path("distributors/add/", views.distributor_add, name="distributor_add"),
    path("distributors/<int:pk>/edit/", views.distributor_edit, name="distributor_edit"),
    path("distributors/<int:pk>/refresh/", views.distributor_refresh, name="distributor_refresh"),
    path("distributors/<int:pk>/toggle/", views.distributor_toggle, name="distributor_toggle"),
]
