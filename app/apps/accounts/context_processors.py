"""Expose capability flags to every template (drives UI gating)."""
from django.conf import settings


def user_permissions(request):
    user = getattr(request, "user", None)
    idle = int(settings.SESSION_IDLE_TIMEOUT.total_seconds())
    if not user or not user.is_authenticated:
        return {"caps": {}, "idle_timeout_seconds": idle}
    return {
        "idle_timeout_seconds": idle,
        "caps": {
            "manage_users": user.can_manage_users,
            "access_backups": user.can_access_backups,
            "create_orders": user.can_create_orders,
            "change_status": user.can_change_status,
            "manage_files": user.can_manage_files,
            "is_admin": user.is_admin,
            "is_operator": user.is_operator,
            "is_manager": user.is_manager,
            "is_director": user.is_director,
            "role_label": user.get_role_display(),
        }
    }
