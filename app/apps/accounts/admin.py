from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "full_name", "role", "is_active", "last_login")
    list_filter = ("role", "is_active")
    search_fields = ("username", "full_name")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Профиль", {"fields": ("full_name", "role", "employee", "is_active")}),
        ("Системное", {"fields": ("last_login", "date_joined", "is_staff", "is_superuser")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "full_name", "role", "password1", "password2"),
        }),
    )
