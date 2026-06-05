"""Single entry point for writing audit-log records (TЗ §18)."""
from .middleware import get_client_ip, get_current_request, get_current_user
from .models import ActionLog


def log_action(request=None, action_type=None, *, target=None, summary=""):
    """
    Persist an audit record. `request` may be omitted — the current request is
    recovered from thread-local storage, so Celery tasks and signals can log too.
    """
    if request is None:
        request = get_current_request()

    user = request.user if (request and request.user.is_authenticated) else get_current_user()

    target_type = target_id = ""
    if target is not None:
        target_type = target.__class__.__name__
        target_id = str(getattr(target, "pk", "") or "")

    return ActionLog.objects.create(
        user=user if (user and user.is_authenticated) else None,
        action_type=action_type,
        summary=summary[:500],
        target_type=target_type,
        target_id=target_id,
        ip_address=get_client_ip(request),
    )
