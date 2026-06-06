from django.contrib import admin

from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "inn", "kpp", "status", "source", "updated_at")
    search_fields = ("name", "full_name", "inn", "ogrn")
    list_filter = ("status", "source")
    readonly_fields = ("updated_at",)
