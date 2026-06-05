from django.contrib import admin

from .models import Order, OrderHistory, OrderSequence


class OrderHistoryInline(admin.TabularInline):
    model = OrderHistory
    extra = 0
    can_delete = False
    readonly_fields = ("changed_at", "user", "field_label", "old_value", "new_value")
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "manager", "distributor", "potential_user", "status",
                    "request_date", "forecast_date")
    list_filter = ("status", "request_date")
    search_fields = ("order_number", "manager__last_name", "distributor__name", "kit")
    readonly_fields = ("order_number", "request_date", "created_at", "updated_at",
                       "created_by", "updated_by")
    inlines = [OrderHistoryInline]
    # Deletion is forbidden by the spec — soft delete only (amendment §10).
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrderSequence)
class OrderSequenceAdmin(admin.ModelAdmin):
    list_display = ("name", "value")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
