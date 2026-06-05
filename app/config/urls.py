from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(pattern_name="orders:table", permanent=False)),
    path("accounts/", include("apps.accounts.urls")),
    path("orders/", include("apps.orders.urls")),
    path("directories/", include("apps.directories.urls")),
    path("files/", include("apps.files.urls")),
    path("backups/", include("apps.backups.urls")),
    path("audit/", include("apps.audit.urls")),
    # REST API (auth required) — amendment §10.
    path("api/v1/", include("config.api")),
]
