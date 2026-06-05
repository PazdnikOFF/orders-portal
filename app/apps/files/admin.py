from django.contrib import admin

from .models import OrderFile


@admin.register(OrderFile)
class OrderFileAdmin(admin.ModelAdmin):
    list_display = ("stored_name", "order_number", "size", "is_detached", "uploaded_at", "uploaded_by")
    list_filter = ("is_detached", "uploaded_at")
    search_fields = ("stored_name", "original_name", "order_number")
    readonly_fields = ("order", "order_number", "original_name", "stored_name", "rel_path",
                       "size", "content_type", "uploaded_at", "uploaded_by")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False  # physical deletion forbidden (TЗ §6)
