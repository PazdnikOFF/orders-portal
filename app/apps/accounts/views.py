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
from .models import Role, User
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
    users = User.objects.all().order_by("last_name", "first_name", "username")
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
    old_username = user.username
    form = UserEditForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        pwd_changed = bool(form.cleaned_data.get("new_password"))
        renamed = old_username != user.username
        summary = f"Изменён пользователь {user.username} (роль {user.get_role_display()})"
        if renamed:
            summary += f"; логин изменён с «{old_username}» на «{user.username}»"
        if pwd_changed:
            summary += "; задан новый пароль"
        log_action(request, ActionType.USER_UPDATE, target=user, summary=summary)
        notes = []
        if renamed:
            notes.append(f"Новый логин: {user.username}.")
        if pwd_changed:
            notes.append("Пароль обновлён.")
        messages.success(request, "Изменения сохранены. " + " ".join(notes))
        return redirect("accounts:user_list")
    return render(
        request, "accounts/user_form.html",
        {"form": form, "mode": "edit", "edited_user": user},
    )


@login_required
@role_required("can_manage_users")
@require_http_methods(["POST"])
def user_toggle_block(request, pk):
    from apps.orders.models import Order, Status
    from apps.orders.services import record_change

    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "Нельзя заблокировать собственную учётную запись.")
        return redirect("accounts:user_list")

    # --- Unblock: straightforward ---
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
        log_action(request, ActionType.USER_UNBLOCK, target=user,
                   summary=f"Пользователь {user.username} разблокирован")
        messages.success(request, "Пользователь разблокирован.")
        return redirect("accounts:user_list")

    # --- Block: reassign manager on non-completed orders first ---
    done = [Status.PRODUCED, Status.CANCELLED]
    active_orders = list(Order.objects.filter(manager=user).exclude(status__in=done))
    if active_orders:
        available = User.objects.filter(role=Role.MANAGER, is_active=True).exclude(pk=user.pk)
        replacement_pk = request.POST.get("replacement_manager")
        if not replacement_pk:
            if not available.exists():
                messages.error(
                    request,
                    "Нельзя заблокировать: пользователь — менеджер по активным заказам, "
                    "а других активных менеджеров для замены нет.",
                )
                return redirect("accounts:user_list")
            return render(request, "accounts/user_block_reassign.html", {
                "blocked_user": user,
                "active_count": len(active_orders),
                "managers": available,
            })
        replacement = get_object_or_404(User, pk=replacement_pk, role=Role.MANAGER, is_active=True)
        for order in active_orders:
            record_change(order, request.user, "manager", "Менеджер",
                          user.short_name, replacement.short_name)
            order.manager = replacement
            order.updated_by = request.user
            order.save(update_fields=["manager", "updated_by", "updated_at"])
        log_action(
            request, ActionType.USER_BLOCK, target=user,
            summary=(f"При блокировке {user.short_name} переназначен менеджер на "
                     f"{len(active_orders)} активных заказах → {replacement.short_name}"),
        )

    user.is_active = False
    user.save(update_fields=["is_active"])
    log_action(request, ActionType.USER_BLOCK, target=user,
               summary=f"Пользователь {user.username} заблокирован")
    msg = "Пользователь заблокирован."
    if active_orders and request.POST.get("replacement_manager"):
        msg = f"Пользователь заблокирован; {len(active_orders)} активных заказов переназначено."
    messages.success(request, msg)
    return redirect("accounts:user_list")
