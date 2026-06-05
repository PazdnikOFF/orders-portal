from django.contrib import admin

from .models import Backup


@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    list_display = ("filename", "kind", "status", "size", "created_at", "created_by")
    list_filter = ("kind", "status", "created_at")
    readonly_fields = ("filename", "rel_path", "size", "kind", "status", "note",
                       "created_at", "created_by")

    def has_add_permission(self, request):
        return False
