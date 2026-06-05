from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.table, name="table"),
    path("kanban/", views.kanban, name="kanban"),
    path("new/", views.order_new, name="new"),
    path("<int:pk>/card/", views.order_card, name="card"),
    path("<int:pk>/update/", views.order_update, name="update"),
    path("<int:pk>/status/", views.order_status, name="status"),
    path("<int:pk>/history/", views.order_history, name="history"),
]
