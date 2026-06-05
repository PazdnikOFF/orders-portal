"""Reusable role-based access guards for views (server-side, TЗ §17)."""
from functools import wraps

from django.core.exceptions import PermissionDenied


def role_required(*predicates):
    """
    Decorator factory. `predicates` are names of boolean User capabilities
    (e.g. "can_manage_users"). Access is granted if ANY predicate is truthy.

        @role_required("can_access_backups")
        def view(request): ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                raise PermissionDenied
            if not any(getattr(user, p, False) for p in predicates):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


class RoleRequiredMixin:
    """CBV counterpart of :func:`role_required`."""

    required_capabilities: tuple[str, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            raise PermissionDenied
        if self.required_capabilities and not any(
            getattr(user, p, False) for p in self.required_capabilities
        ):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
