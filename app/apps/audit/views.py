from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from apps.accounts.permissions import role_required

from .models import ActionLog, ActionType


@login_required
@role_required("can_manage_users")  # Admin-only view of the action journal
def action_log(request):
    qs = ActionLog.objects.select_related("user").all()
    action = request.GET.get("action")
    if action:
        qs = qs.filter(action_type=action)
    paginator = Paginator(qs, 100)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request, "audit/log.html",
        {"page": page, "action_types": ActionType.choices, "selected": action},
    )
