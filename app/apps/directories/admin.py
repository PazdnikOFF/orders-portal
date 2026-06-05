from django.contrib import admin

from .models import Employee, Organization


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("short_name", "type", "is_active")
    list_filter = ("type", "is_active")
    search_fields = ("last_name", "first_name", "middle_name")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "inn", "kpp", "status", "source", "updated_at")
    search_fields = ("name", "full_name", "inn", "ogrn")
    list_filter = ("status", "source")
    readonly_fields = ("updated_at",)
