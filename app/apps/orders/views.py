from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Value
from django.db.models.functions import Concat
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from apps.accounts.models import Role, User
from apps.directories.models import Distributor, Organization

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
    "manager": "manager__last_name",
    "distributor": "distributor__name",
    "potential": "potential_user__name",
    "kit": "kit",
    "request_date": "request_date",
    "forecast_date": "forecast_date",
    "number": "order_number",
    "status": "status",
}
DEFAULT_SORT = "request_date"


def _participant_orgs(order: Order) -> list:
    # [{"org": Organization, "display": "Наименование (ИНН[, КПП])"}]
    return order.participants_display()


def _order_form_initial(order: Order) -> dict:
    return {
        "manager": order.manager_id,
        "distributor_org": order.distributor_id,
        "potential_user_org": order.potential_user_id,
        "participant_orgs": list(order.participants.values_list("pk", flat=True)),
        "kit": order.kit,
        "forecast_date": order.forecast_date,
        "status": order.status,
    }


DONE_STATUSES = [Status.PRODUCED, Status.CANCELLED]


def _apply_common_filters(request, qs):
    """Filters shared by table and Kanban: manager, distributor, user, date range."""
    g = request.GET
    if v := g.get("f_manager", "").strip():
        qs = qs.annotate(
            _mgr_name=Concat("manager__last_name", Value(" "), "manager__first_name")
        ).filter(
            Q(_mgr_name__icontains=v)
            | Q(manager__last_name__icontains=v)
            | Q(manager__first_name__icontains=v)
        )
    if v := g.get("f_distributor", "").strip():
        qs = qs.filter(Q(distributor__name__icontains=v) | Q(distributor__inn__icontains=v))
    if v := g.get("f_potential", "").strip():
        qs = qs.filter(Q(potential_user__name__icontains=v) | Q(potential_user__inn__icontains=v))
    if v := parse_date(g.get("f_forecast_from", "")):
        qs = qs.filter(forecast_date__gte=v)
    if v := parse_date(g.get("f_forecast_to", "")):
        qs = qs.filter(forecast_date__lte=v)
    return qs


def _distinct_names(qs):
    return sorted({n for n in qs if n})


def _filter_options(request) -> dict:
    """Datalist autocomplete for filter inputs — distinct values actually used
    in each column of the records visible to the user."""
    base = visible_orders(request.user)
    managers = []
    seen = set()
    for ln, fn in base.values_list("manager__last_name", "manager__first_name").distinct():
        name = f"{ln or ''} {fn or ''}".strip()
        if name and name not in seen:
            seen.add(name)
            managers.append(name)
    managers.sort()
    return {
        "dl_managers": managers,
        "dl_distributors": _distinct_names(
            Distributor.objects.filter(orders__in=base, is_active=True).values_list("name", flat=True)),
        "dl_potentials": _distinct_names(
            Organization.objects.filter(potential_user_orders__in=base).values_list("name", flat=True)),
        "dl_participants": _distinct_names(
            Organization.objects.filter(participant_orders__in=base).values_list("name", flat=True)),
        "dl_kits": _distinct_names(base.values_list("kit", flat=True)),
    }


def _hide_done(request, qs):
    """Hide produced/cancelled by default unless «show_done» or filtered to one."""
    if request.GET.get("show_done") == "1":
        return qs
    if request.GET.get("f_status", "") in DONE_STATUSES:
        return qs
    return qs.exclude(status__in=DONE_STATUSES)


def _filtered_orders(request):
    """Per-column filtering — each table column has its own filter input."""
    qs = _apply_common_filters(request, visible_orders(request.user))
    g = request.GET
    needs_distinct = False

    if v := g.get("f_participant", "").strip():
        qs = qs.filter(Q(participants__name__icontains=v) | Q(participants__inn__icontains=v))
        needs_distinct = True
    if v := g.get("f_kit", "").strip():
        qs = qs.filter(kit__icontains=v)
    if v := parse_date(g.get("f_request_date", "")):
        qs = qs.filter(request_date=v)
    # Forecast date is a range (f_forecast_from / f_forecast_to) handled in
    # _apply_common_filters, shared with Kanban.
    if v := "".join(ch for ch in g.get("f_number", "") if ch.isdigit()):
        qs = qs.filter(order_number=int(v))
    if (v := g.get("f_status", "")) in Status.values:
        qs = qs.filter(status=v)

    qs = _hide_done(request, qs)
    if needs_distinct:
        qs = qs.distinct()

    sort = g.get("sort", DEFAULT_SORT)
    field = SORT_FIELDS.get(sort, SORT_FIELDS[DEFAULT_SORT])
    direction = "-" if g.get("dir", "desc") == "desc" else ""
    # Stable secondary ordering so equal keys keep a consistent order.
    return qs.order_by(f"{direction}{field}", "-order_number")


# --------------------------------------------------------------------------- #
# Table view (default) — TЗ §8, amendment §4
# --------------------------------------------------------------------------- #
PAGE_SIZES = [30, 50, 100]
PAGINATION_THRESHOLD = 30  # hide pagination while there are fewer records


@login_required
def table(request):
    qs = _filtered_orders(request)
    filter_keys = ["f_manager", "f_distributor", "f_potential", "f_participant",
                   "f_kit", "f_request_date", "f_forecast_date", "f_number", "f_status"]
    # After creating an order we land on ?selected=<pk> to auto-open its card.
    selected = request.GET.get("selected")
    selected_pk = int(selected) if selected and selected.isdigit() else None

    try:
        per_page = int(request.GET.get("per_page", PAGE_SIZES[0]))
    except (TypeError, ValueError):
        per_page = PAGE_SIZES[0]
    if per_page not in PAGE_SIZES:
        per_page = PAGE_SIZES[0]
    paginator = Paginator(qs, per_page)
    page = paginator.get_page(request.GET.get("page"))

    context = {
        "page": page,
        "orders": page.object_list,
        "paginator": paginator,
        "per_page": per_page,
        "page_sizes": PAGE_SIZES,
        # Pagination is hidden until there are at least 30 records.
        "show_pagination": paginator.count >= PAGINATION_THRESHOLD,
        "statuses": Status.choices,
        "has_filters": any(request.GET.get(k) for k in filter_keys),
        "show_done": request.GET.get("show_done") == "1",
        "selected_pk": selected_pk,
        "cur_sort": request.GET.get("sort", DEFAULT_SORT),
        "cur_dir": "desc" if request.GET.get("dir", "desc") == "desc" else "asc",
        "view": "table",
        **_filter_options(request),
    }
    return render(request, "orders/table.html", context)


# --------------------------------------------------------------------------- #
# Kanban view — amendment §4
# --------------------------------------------------------------------------- #
@login_required
def kanban(request):
    qs = _apply_common_filters(request, visible_orders(request.user))
    show_done = request.GET.get("show_done") == "1"
    statuses = list(KANBAN_STATUSES) if show_done else [Status.PLANNED, Status.IN_PROGRESS]
    orders = list(qs)
    columns = [{
        "status": status,
        "label": Status(status).label,
        "orders": [o for o in orders if o.status == status],
    } for status in statuses]
    filter_keys = ["f_manager", "f_distributor", "f_potential", "f_forecast_from", "f_forecast_to"]
    context = {
        "columns": columns,
        "col_count": len(columns),
        "show_done": show_done,
        "has_filters": any(request.GET.get(k) for k in filter_keys),
        "view": "kanban",
        **_filter_options(request),
    }
    return render(request, "orders/kanban.html", context)


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
        "participant_values": _participant_orgs(order),
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
        # Re-render keeping the participant orgs the user already chose.
        chosen = list(Organization.objects.filter(pk__in=request.POST.getlist("participant_orgs")))
        return render(request, "orders/_card_new.html",
                      {"form": form, "participant_values": Order.org_display_list(chosen)})
    form = OrderForm(user=request.user, stage=matrix.STAGE_CREATE, is_create=True,
                     initial={"status": Status.PLANNED})
    return render(request, "orders/_card_new.html", {"form": form, "participant_values": []})


@login_required
@require_http_methods(["POST"])
def order_update(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not can_view_order(request.user, order):
        raise PermissionDenied
    form = OrderForm(request.POST, user=request.user, stage=order.stage,
                     initial=_order_form_initial(order))
    saved = False
    if form.is_valid():
        try:
            update_order(request, order, form.cleaned_data)
        except (PermissionDenied, ValidationError) as exc:
            form.add_error(None, getattr(exc, "messages", [str(exc)]))
        else:
            order.refresh_from_db()
            form = OrderForm(user=request.user, stage=order.stage,
                             initial=_order_form_initial(order))
            saved = True

    context = _card_context(request, order, form)
    context["saved"] = saved
    card_html = render_to_string("orders/_card.html", context, request=request)
    if not saved:
        return HttpResponse(card_html)
    # On success, also refresh the matching table row in place (HTMX OOB swap).
    # The <tr> must be wrapped in <template> or the browser drops it while
    # parsing the response (a bare <tr> can't live outside a table).
    row_html = render_to_string(
        "orders/_table_row.html",
        {"order": order, "statuses": Status.choices, "oob": True},
        request=request,
    )
    return HttpResponse(card_html + "<template>" + row_html + "</template>")


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
    if request.user.is_manager:           # history is not available to managers
        raise PermissionDenied
    if not can_view_order(request.user, order):
        raise PermissionDenied
    return render(request, "orders/_history.html",
                  {"history": order.history.select_related("user")[:100], "order": order})
