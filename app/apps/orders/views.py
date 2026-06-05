import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from . import matrix
from .forms import OrderForm
from .models import KANBAN_STATUSES, Order, Status
from .services import (
    can_view_order,
    change_status,
    create_order,
    update_order,
    visible_orders,
)

SORT_FIELDS = {
    "number": "order_number",
    "request_date": "request_date",
    "forecast_date": "forecast_date",
    "status": "status",
}


def _order_form_initial(order: Order) -> dict:
    return {
        "manager": order.manager_id,
        "distributor_inn": order.distributor.inn,
        "potential_user_inn": order.potential_user.inn,
        "participant_inns": json.dumps(list(order.participants.values_list("inn", flat=True))),
        "kit": order.kit,
        "forecast_date": order.forecast_date,
        "status": order.status,
    }


def _filtered_orders(request):
    """Per-column filtering — each table column has its own filter input."""
    qs = visible_orders(request.user)
    g = request.GET
    needs_distinct = False

    if v := g.get("f_manager", "").strip():
        qs = qs.filter(Q(manager__last_name__icontains=v) | Q(manager__first_name__icontains=v))
    if v := g.get("f_distributor", "").strip():
        qs = qs.filter(Q(distributor__name__icontains=v) | Q(distributor__inn__icontains=v))
    if v := g.get("f_potential", "").strip():
        qs = qs.filter(Q(potential_user__name__icontains=v) | Q(potential_user__inn__icontains=v))
    if v := g.get("f_participant", "").strip():
        qs = qs.filter(Q(participants__name__icontains=v) | Q(participants__inn__icontains=v))
        needs_distinct = True
    if v := g.get("f_kit", "").strip():
        qs = qs.filter(kit__icontains=v)
    if v := parse_date(g.get("f_request_date", "")):
        qs = qs.filter(request_date=v)
    if v := parse_date(g.get("f_forecast_date", "")):
        qs = qs.filter(forecast_date=v)
    if v := "".join(ch for ch in g.get("f_number", "") if ch.isdigit()):
        qs = qs.filter(order_number=int(v))
    if (v := g.get("f_status", "")) in Status.values:
        qs = qs.filter(status=v)

    if needs_distinct:
        qs = qs.distinct()

    sort = g.get("sort", "number")
    field = SORT_FIELDS.get(sort, "order_number")
    direction = "-" if g.get("dir", "desc") == "desc" else ""
    return qs.order_by(f"{direction}{field}")


# --------------------------------------------------------------------------- #
# Table view (default) — TЗ §8, amendment §4
# --------------------------------------------------------------------------- #
@login_required
def table(request):
    orders = _filtered_orders(request)
    filter_keys = ["f_manager", "f_distributor", "f_potential", "f_participant",
                   "f_kit", "f_request_date", "f_forecast_date", "f_number", "f_status"]
    context = {
        "orders": orders,
        "statuses": Status.choices,
        "has_filters": any(request.GET.get(k) for k in filter_keys),
        "view": "table",
    }
    return render(request, "orders/table.html", context)


# --------------------------------------------------------------------------- #
# Kanban view — amendment §4
# --------------------------------------------------------------------------- #
@login_required
def kanban(request):
    orders = visible_orders(request.user)
    columns = []
    for status in KANBAN_STATUSES:
        columns.append({
            "status": status,
            "label": Status(status).label,
            "orders": [o for o in orders if o.status == status],
        })
    return render(request, "orders/kanban.html", {"columns": columns, "view": "kanban"})


# --------------------------------------------------------------------------- #
# Bottom block — order card (TЗ §9)
# --------------------------------------------------------------------------- #
@login_required
def order_card(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not can_view_order(request.user, order):
        raise PermissionDenied
    form = OrderForm(
        user=request.user, stage=order.stage, initial=_order_form_initial(order)
    )
    return render(request, "orders/_card.html", _card_context(request, order, form))


def _card_context(request, order, form):
    return {
        "order": order,
        "form": form,
        "can_edit": (request.user.is_admin or request.user.is_operator) and (
            request.user.is_admin or not order.is_locked
        ),
        "history": order.history.select_related("user")[:50],
        "active_file": order.active_file,
        "statuses": Status.choices,
    }


@login_required
@require_http_methods(["GET", "POST"])
def order_new(request):
    if not request.user.can_create_orders:
        raise PermissionDenied
    if request.method == "POST":
        form = OrderForm(request.POST, user=request.user, stage=matrix.STAGE_CREATE, is_create=True)
        if form.is_valid():
            try:
                order = create_order(request, form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, exc.messages)
            else:
                messages.success(request, f"Создан заказ {order.order_code}.")
                resp = HttpResponse(status=204)
                resp["HX-Redirect"] = f"/orders/?selected={order.pk}"
                return resp
        return render(request, "orders/_card_new.html", {"form": form})
    form = OrderForm(user=request.user, stage=matrix.STAGE_CREATE, is_create=True,
                     initial={"status": Status.PLANNED})
    return render(request, "orders/_card_new.html", {"form": form})


@login_required
@require_http_methods(["POST"])
def order_update(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not can_view_order(request.user, order):
        raise PermissionDenied
    form = OrderForm(request.POST, user=request.user, stage=order.stage,
                     initial=_order_form_initial(order))
    if form.is_valid():
        try:
            update_order(request, order, form.cleaned_data)
        except (PermissionDenied, ValidationError) as exc:
            form.add_error(None, getattr(exc, "messages", [str(exc)]))
        else:
            messages.success(request, f"Заказ {order.order_code} сохранён.")
            order.refresh_from_db()
            form = OrderForm(user=request.user, stage=order.stage,
                             initial=_order_form_initial(order))
    return render(request, "orders/_card.html", _card_context(request, order, form))


# --------------------------------------------------------------------------- #
# Inline status change (table + Kanban drag-drop) — TЗ §8.2, amendment §4
# --------------------------------------------------------------------------- #
@login_required
@require_http_methods(["POST"])
def order_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    new_status = request.POST.get("status")
    try:
        change_status(request, order, new_status)
    except PermissionDenied as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=403)
    except ValidationError as exc:
        return JsonResponse({"ok": False, "error": "; ".join(exc.messages)}, status=400)

    if request.headers.get("HX-Request") and request.POST.get("render") == "row":
        return render(request, "orders/_table_row.html", {"order": order, "statuses": Status.choices})
    return JsonResponse({
        "ok": True,
        "status": order.status,
        "status_label": order.get_status_display(),
    })


@login_required
def order_history(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not can_view_order(request.user, order):
        raise PermissionDenied
    return render(request, "orders/_history.html",
                  {"history": order.history.select_related("user")[:100], "order": order})
