from django.contrib import admin

from .models import ActionLog


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action_type", "summary", "ip_address")
    list_filter = ("action_type", "created_at")
    search_fields = ("summary", "target_id", "user__username")
    readonly_fields = [f.name for f in ActionLog._meta.fields]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
