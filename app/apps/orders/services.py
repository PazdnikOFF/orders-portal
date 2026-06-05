"""Order business logic: visibility, create/update, status changes, history."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import QuerySet

from apps.audit.models import ActionType
from apps.audit.services import log_action

from .matrix import can_edit_field
from .models import Order, OrderHistory, Status


def visible_orders(user) -> QuerySet[Order]:
    """
    Row-level visibility (TЗ §3, amendment §2):
      - Admin / Operator / Director: all records.
      - Manager: only records where he is the assigned «Менеджер».
    """
    qs = Order.objects.select_related(
        "manager", "distributor", "potential_user", "created_by", "updated_by"
    ).prefetch_related("participants", "files")

    if user.sees_only_own_orders:
        if user.employee_id:
            return qs.filter(manager_id=user.employee_id)
        return qs.none()
    return qs


def can_view_order(user, order: Order) -> bool:
    if user.sees_only_own_orders:
        return bool(user.employee_id) and order.manager_id == user.employee_id
    return True


def record_change(order, user, field, label, old, new):
    if str(old) == str(new):
        return None
    return OrderHistory.objects.create(
        order=order, user=user, field=field, field_label=label,
        old_value="" if old is None else str(old),
        new_value="" if new is None else str(new),
    )


def change_status(request, order: Order, new_status: str) -> Order:
    """
    Change order status with full server-side validation (used by table inline
    edit, Kanban drag-drop, and the card). Honors role + stage matrix.
    """
    user = request.user
    if new_status not in Status.values:
        raise ValidationError("Недопустимый статус.")
    if order.status == new_status:
        return order
    if not can_edit_field(user, "status", order.stage):
        raise PermissionDenied("Изменение статуса запрещено на текущей стадии или для вашей роли.")
    if not can_view_order(user, order):
        raise PermissionDenied("Нет доступа к записи.")

    old_label = order.get_status_display()
    order.status = new_status
    order.updated_by = user
    order.save(update_fields=["status", "updated_by", "updated_at"])

    record_change(order, user, "status", "Статус", old_label, order.get_status_display())
    log_action(
        request, ActionType.STATUS_CHANGE, target=order,
        summary=f"{order.order_code}: статус «{old_label}» → «{order.get_status_display()}»",
    )
    return order


@transaction.atomic
def create_order(request, cleaned) -> Order:
    """Create a new order from validated card-form data (TЗ §12/§13)."""
    user = request.user
    if not user.can_create_orders:
        raise PermissionDenied("Создание записей запрещено для вашей роли.")

    distributor = cleaned["distributor_org"]
    potential_user = cleaned["potential_user_org"]
    participants = list(cleaned.get("participant_orgs") or [])

    order = Order(
        manager=cleaned["manager"],
        distributor=distributor,
        potential_user=potential_user,
        kit=cleaned["kit"],
        forecast_date=cleaned["forecast_date"],
        status=cleaned.get("status") or Status.PLANNED,
        created_by=user,
        updated_by=user,
    )
    order.save()  # allocates gapless order_number
    if participants:
        order.participants.set(participants)

    log_action(
        request, ActionType.ORDER_CREATE, target=order,
        summary=f"Создан {order.order_code} (менеджер {order.manager.short_name})",
    )
    return order


@transaction.atomic
def update_order(request, order: Order, cleaned) -> Order:
    """
    Apply editable changes to an existing order, recording per-field history.
    Only fields the user may edit at the current stage are touched; the form
    already disables the rest, this re-checks server-side (defense in depth).
    """
    user = request.user
    if not can_view_order(user, order):
        raise PermissionDenied("Нет доступа к записи.")
    if user.is_manager or user.is_director:
        raise PermissionDenied("Редактирование запрещено для вашей роли.")

    stage = order.stage
    changed = []

    def allowed(field):
        return can_edit_field(user, field, stage)

    # --- simple scalar fields ---
    if allowed("manager") and cleaned.get("manager") and cleaned["manager"] != order.manager:
        record_change(order, user, "manager", "Менеджер", order.manager.short_name, cleaned["manager"].short_name)
        order.manager = cleaned["manager"]
        changed.append("manager")

    if allowed("kit") and cleaned.get("kit") != order.kit:
        record_change(order, user, "kit", "Комплект", order.kit, cleaned["kit"])
        order.kit = cleaned["kit"]
        changed.append("kit")

    if allowed("forecast_date") and cleaned.get("forecast_date") != order.forecast_date:
        record_change(order, user, "forecast_date", "Прогнозируемая дата",
                      order.forecast_date, cleaned["forecast_date"])
        order.forecast_date = cleaned["forecast_date"]
        changed.append("forecast_date")

    # --- organization FK fields (chosen Organization by id) ---
    if allowed("distributor") and (org := cleaned.get("distributor_org")):
        if org.pk != order.distributor_id:
            record_change(order, user, "distributor", "Дистрибьютор",
                          order.distributor.display_name, org.display_name)
            order.distributor = org
            changed.append("distributor")

    if allowed("potential_user") and (org := cleaned.get("potential_user_org")):
        if org.pk != order.potential_user_id:
            record_change(order, user, "potential_user", "Потенциальный пользователь",
                          order.potential_user.display_name, org.display_name)
            order.potential_user = org
            changed.append("potential_user")

    # --- status (lock transitions handled by matrix) ---
    new_status = cleaned.get("status")
    if allowed("status") and new_status and new_status != order.status:
        old_label = order.get_status_display()
        order.status = new_status
        record_change(order, user, "status", "Статус", old_label, order.get_status_display())
        changed.append("status")

    if changed:
        order.updated_by = user
        order.save()

    # --- participants M2M ---
    if allowed("participants") and "participant_orgs" in cleaned:
        new_orgs = list(cleaned["participant_orgs"])
        old_ids = set(order.participants.values_list("pk", flat=True))
        new_ids = {o.pk for o in new_orgs}
        if old_ids != new_ids:
            old_disp = ", ".join(o.display_name for o in order.participants.all())
            new_disp = ", ".join(o.display_name for o in new_orgs)
            order.participants.set(new_orgs)
            record_change(order, user, "participants", "Участники проекта", old_disp, new_disp)
            changed.append("participants")

    if changed:
        log_action(
            request, ActionType.ORDER_UPDATE, target=order,
            summary=f"{order.order_code}: изменено — {', '.join(changed)}",
        )
    return order
