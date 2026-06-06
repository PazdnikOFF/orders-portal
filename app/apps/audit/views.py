from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils.dateparse import parse_date

from apps.accounts.models import User
from apps.accounts.permissions import role_required

from .models import ActionLog, ActionType


@login_required
@role_required("can_manage_users")  # Admin-only view of the action journal
def action_log(request):
    qs = ActionLog.objects.select_related("user").all()
    g = request.GET

    action = g.get("action") or ""
    if action:
        qs = qs.filter(action_type=action)

    user_id = g.get("user") or ""
    if user_id.isdigit():
        qs = qs.filter(user_id=int(user_id))

    if df := parse_date(g.get("date_from", "")):
        qs = qs.filter(created_at__date__gte=df)
    if dt := parse_date(g.get("date_to", "")):
        qs = qs.filter(created_at__date__lte=dt)

    paginator = Paginator(qs, 100)
    page = paginator.get_page(g.get("page"))
    return render(request, "audit/log.html", {
        "page": page,
        "action_types": ActionType.choices,
        "users": User.objects.order_by("last_name", "first_name", "username"),
        "selected": action,
        "sel_user": user_id,
        "date_from": g.get("date_from", ""),
        "date_to": g.get("date_to", ""),
    })
