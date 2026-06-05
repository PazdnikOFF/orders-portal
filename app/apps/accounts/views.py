from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.audit.services import log_action
from apps.audit.models import ActionType

from .forms import LoginForm, UserCreateForm, UserEditForm
from .models import User
from .permissions import role_required


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("orders:table")
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        auth_login(request, user)  # updates last_login via Django's signal
        log_action(request, ActionType.LOGIN, target=user, summary="Вход в систему")
        next_url = request.GET.get("next") or reverse("orders:table")
        return redirect(next_url)
    return render(request, "accounts/login.html", {"form": form})


@login_required
def logout_view(request):
    log_action(request, ActionType.LOGOUT, target=request.user, summary="Выход из системы")
    auth_logout(request)
    messages.info(request, "Вы вышли из системы.")
    return redirect("accounts:login")


# --------------------------------------------------------------------------- #
# User management — Admin only (TЗ §3.1)
# --------------------------------------------------------------------------- #
@login_required
@role_required("can_manage_users")
def user_list(request):
    users = User.objects.all().order_by("full_name", "username")
    return render(request, "accounts/user_list.html", {"users": users})


@login_required
@role_required("can_manage_users")
@require_http_methods(["GET", "POST"])
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        log_action(
            request, ActionType.USER_CREATE, target=user,
            summary=f"Создан пользователь {user.username} ({user.get_role_display()})",
        )
        messages.success(request, "Пользователь создан.")
        return redirect("accounts:user_list")
    return render(request, "accounts/user_form.html", {"form": form, "mode": "create"})


@login_required
@role_required("can_manage_users")
@require_http_methods(["GET", "POST"])
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserEditForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(
            request, ActionType.USER_UPDATE, target=user,
            summary=f"Изменён пользователь {user.username} (роль {user.get_role_display()})",
        )
        messages.success(request, "Изменения сохранены.")
        return redirect("accounts:user_list")
    return render(
        request, "accounts/user_form.html",
        {"form": form, "mode": "edit", "edited_user": user},
    )


@login_required
@role_required("can_manage_users")
@require_http_methods(["POST"])
def user_toggle_block(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "Нельзя заблокировать собственную учётную запись.")
        return redirect("accounts:user_list")
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    action = ActionType.USER_UNBLOCK if user.is_active else ActionType.USER_BLOCK
    state = "разблокирован" if user.is_active else "заблокирован"
    log_action(request, action, target=user, summary=f"Пользователь {user.username} {state}")
    messages.success(request, f"Пользователь {state}.")
    return redirect("accounts:user_list")
