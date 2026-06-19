from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.permissions import role_required
from apps.audit.models import ActionType
from apps.audit.services import log_action
from apps.integrations.providers import OrgLookupError

from .forms import DistributorAddForm, DistributorEditForm
from .models import Distributor
from .services import (
    create_distributor_from_inn,
    refresh_distributor_from_provider,
    suggest_orgs,
)


# --------------------------------------------------------------------------- #
# Organization suggest by INN — combobox dropdown (HTMX) (TЗ §14)
# --------------------------------------------------------------------------- #
@login_required
@require_http_methods(["POST"])
def org_suggest(request):
    """
    Resolve an INN to a list of organizations (head office + branches, each with
    its КПП), upsert them locally and return a dropdown the user picks from.
    """
    inn = (request.POST.get("inn") or "").strip()
    try:
        orgs = suggest_orgs(inn)
    except OrgLookupError as exc:
        return render(request, "directories/_org_options.html", {"error": str(exc)})
    return render(request, "directories/_org_options.html", {"orgs": orgs})


@login_required
@require_http_methods(["GET"])
def distributor_suggest(request):
    """
    Smart search over the local distributor directory (active only) by name or
    INN — feeds the order-card combobox dropdown. Returns the same option
    partial as the organization combobox (identical data attributes).
    """
    q = (request.GET.get("q") or "").strip()
    qs = Distributor.objects.filter(is_active=True)
    if q:
        # Typed query — narrow by name/INN, show the top matches.
        qs = qs.filter(
            Q(name__icontains=q) | Q(full_name__icontains=q) | Q(inn__icontains=q)
        )[:15]
    else:
        # No query (field focused) — show the full active list to pick from.
        qs = qs[:200]
    return render(request, "directories/_distributor_options.html", {"orgs": qs})


# --------------------------------------------------------------------------- #
# Distributor directory — admin only. Records can be disabled, never deleted.
# --------------------------------------------------------------------------- #
@login_required
@role_required("can_manage_users")
def distributor_list(request):
    q = (request.GET.get("q") or "").strip()
    show_all = request.GET.get("show_all") == "1"
    qs = Distributor.objects.all()
    if not show_all:
        qs = qs.filter(is_active=True)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(full_name__icontains=q) | Q(inn__icontains=q))
    return render(request, "directories/distributor_list.html", {
        "distributors": qs,
        "q": q,
        "show_all": show_all,
    })


@login_required
@role_required("can_manage_users")
@require_http_methods(["GET", "POST"])
def distributor_add(request):
    form = DistributorAddForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            dist = create_distributor_from_inn(form.cleaned_data["inn"])
        except OrgLookupError as exc:
            form.add_error("inn", str(exc))
        else:
            log_action(request, ActionType.DISTRIBUTOR_CREATE, target=dist,
                       summary=f"Добавлен дистрибьютор {dist.display_name}")
            messages.success(request, f"Дистрибьютор «{dist.name or dist.inn}» добавлен.")
            return redirect("directories:distributor_list")
    return render(request, "directories/distributor_form.html", {"form": form, "mode": "add"})


@login_required
@role_required("can_manage_users")
@require_http_methods(["GET", "POST"])
def distributor_edit(request, pk):
    dist = get_object_or_404(Distributor, pk=pk)
    form = DistributorEditForm(request.POST or None, instance=dist)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, ActionType.DISTRIBUTOR_UPDATE, target=dist,
                   summary=f"Изменён дистрибьютор {dist.display_name}")
        messages.success(request, "Изменения сохранены.")
        return redirect("directories:distributor_list")
    return render(request, "directories/distributor_form.html",
                  {"form": form, "mode": "edit", "dist": dist})


@login_required
@role_required("can_manage_users")
@require_http_methods(["POST"])
def distributor_refresh(request, pk):
    """Re-pull a distributor's data from DaData by its INN."""
    dist = get_object_or_404(Distributor, pk=pk)
    try:
        refresh_distributor_from_provider(dist)
    except OrgLookupError as exc:
        messages.error(request, f"Не удалось обновить из DaData: {exc}")
    else:
        log_action(request, ActionType.DISTRIBUTOR_UPDATE, target=dist,
                   summary=f"Обновлены данные из DaData: {dist.display_name}")
        messages.success(request, "Данные обновлены из DaData.")
    return redirect("directories:distributor_edit", pk=dist.pk)


@login_required
@role_required("can_manage_users")
@require_http_methods(["POST"])
def distributor_toggle(request, pk):
    """Enable/disable a distributor (deletion is not allowed)."""
    dist = get_object_or_404(Distributor, pk=pk)
    dist.is_active = not dist.is_active
    dist.save(update_fields=["is_active"])
    state = "включён" if dist.is_active else "отключён"
    log_action(request, ActionType.DISTRIBUTOR_TOGGLE, target=dist,
               summary=f"Дистрибьютор {dist.display_name} {state}")
    messages.success(request, f"Дистрибьютор {state}.")
    return redirect("directories:distributor_list")
