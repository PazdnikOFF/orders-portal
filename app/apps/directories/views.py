from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.permissions import role_required
from apps.integrations.providers import OrgLookupError

from .forms import EmployeeForm
from .models import Employee
from .services import upsert_organization


# --------------------------------------------------------------------------- #
# Organization lookup by INN — used by the order card (HTMX) (TЗ §14)
# --------------------------------------------------------------------------- #
@login_required
@require_http_methods(["POST"])
def org_lookup(request):
    """
    Resolve an INN to an organization: fetch via provider, upsert locally,
    and return a fragment with the resolved name + hidden org id, so the card
    can attach the FK. `field` echoes which form field triggered the lookup.
    """
    inn = (request.POST.get("inn") or "").strip()
    field = request.POST.get("field", "org")
    try:
        org = upsert_organization(inn)
    except OrgLookupError as exc:
        return render(
            request, "directories/_org_lookup_result.html",
            {"error": str(exc), "field": field}, status=200,
        )
    return render(
        request, "directories/_org_lookup_result.html",
        {"org": org, "field": field},
    )


# --------------------------------------------------------------------------- #
# Employee directory — managed by Admin (reference data)
# --------------------------------------------------------------------------- #
@login_required
def employee_list(request):
    employees = Employee.objects.all()
    return render(request, "directories/employee_list.html", {"employees": employees})


@login_required
@role_required("can_manage_users")
@require_http_methods(["GET", "POST"])
def employee_create(request):
    form = EmployeeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Сотрудник добавлен.")
        return redirect("directories:employee_list")
    return render(request, "directories/employee_form.html", {"form": form, "mode": "create"})


@login_required
@role_required("can_manage_users")
@require_http_methods(["GET", "POST"])
def employee_edit(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    form = EmployeeForm(request.POST or None, instance=employee)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Изменения сохранены.")
        return redirect("directories:employee_list")
    return render(request, "directories/employee_form.html", {"form": form, "mode": "edit"})
