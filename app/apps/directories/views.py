from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.permissions import role_required
from apps.integrations.providers import OrgLookupError

from .forms import EmployeeForm
from .models import Employee
from .services import suggest_orgs


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
