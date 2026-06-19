from django.contrib import admin

from .models import Distributor, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "inn", "kpp", "status", "source", "updated_at")
    search_fields = ("name", "full_name", "inn", "ogrn")
    list_filter = ("status", "source")
    readonly_fields = ("updated_at",)


@admin.register(Distributor)
class DistributorAdmin(admin.ModelAdmin):
    list_display = ("name", "inn", "kpp", "is_active", "status", "source", "updated_at")
    search_fields = ("name", "full_name", "inn", "ogrn")
    list_filter = ("is_active", "status", "source")
    readonly_fields = ("created_at", "updated_at")
