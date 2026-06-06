"""File upload / soft-delete logic (TЗ §6, §12.8, amendment §3)."""
import os
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.audit.models import ActionType
from apps.audit.services import log_action

from .models import OrderFile


def _validate_upload(uploaded):
    ext = Path(uploaded.name).suffix.lower().lstrip(".")
    if ext not in settings.FILE_UPLOAD_ALLOWED_EXTENSIONS:
        allowed = ", ".join(settings.FILE_UPLOAD_ALLOWED_EXTENSIONS)
        raise ValidationError(f"Недопустимый тип файла .{ext}. Разрешены: {allowed}.")
    if uploaded.size > settings.FILE_UPLOAD_MAX_SIZE:
        limit_mb = settings.FILE_UPLOAD_MAX_SIZE // (1024 * 1024)
        raise ValidationError(f"Файл превышает максимальный размер {limit_mb} МБ.")
    return ext


def save_order_file(request, order, uploaded) -> OrderFile:
    """
    Store an uploaded document under the order's folder, named by order number
    (TЗ §12.8). If a file is already attached, the old one is soft-detached
    first so there is exactly one active document per order.
    """
    user = request.user
    if not user.can_manage_files:
        raise PermissionDenied("Загрузка файлов запрещена для вашей роли.")
    if order.is_locked and not user.is_admin:
        raise PermissionDenied("Заказ завершён — изменение файлов доступно только администратору.")

    ext = _validate_upload(uploaded)

    # Detach any currently active file (keeps history, renames on disk).
    active = order.active_file
    if active:
        detach_order_file(request, active, log=False)

    order_dir = settings.ORDER_FILES_ROOT / str(order.order_number)
    order_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{order.order_code}.{ext}"
    abs_path = order_dir / stored_name
    # Avoid clobbering a previously detached file with the same target name.
    counter = 1
    while abs_path.exists():
        stored_name = f"{order.order_code}-{counter}.{ext}"
        abs_path = order_dir / stored_name
        counter += 1

    with open(abs_path, "wb") as fh:
        for chunk in uploaded.chunks():
            fh.write(chunk)

    rel_path = f"{order.order_number}/{stored_name}"
    order_file = OrderFile.objects.create(
        order=order,
        order_number=order.order_number,
        original_name=uploaded.name[:255],
        stored_name=stored_name,
        rel_path=rel_path,
        size=uploaded.size,
        content_type=getattr(uploaded, "content_type", "") or "",
        uploaded_by=user,
        is_detached=False,
    )
    log_action(request, ActionType.FILE_UPLOAD, target=order,
               summary=f"{order.order_code}: загружен файл «{uploaded.name}»")
    return order_file


def detach_order_file(request, order_file: OrderFile, log: bool = True) -> OrderFile:
    """
    Remove the file link from the card WITHOUT physical deletion (amendment §3):
    prepend "_" to the on-disk name; skip rename if it already starts with "_".
    """
    user = request.user
    if not user.can_manage_files:
        raise PermissionDenied("Удаление файлов запрещено для вашей роли.")
    if order_file.order.is_locked and not user.is_admin:
        raise PermissionDenied("Заказ завершён — изменение файлов доступно только администратору.")

    abs_path = order_file.abs_path
    directory = abs_path.parent
    name = abs_path.name

    if not name.startswith("_"):
        new_name = f"_{name}"
        new_abs = directory / new_name
        idx = 1
        while new_abs.exists():
            new_name = f"_{name}.{idx}"
            new_abs = directory / new_name
            idx += 1
        if abs_path.exists():
            os.rename(abs_path, new_abs)
        order_file.stored_name = new_name
        order_file.rel_path = f"{order_file.order_number}/{new_name}"

    order_file.is_detached = True
    order_file.detached_at = timezone.now()
    order_file.save(update_fields=["stored_name", "rel_path", "is_detached", "detached_at"])

    if log:
        log_action(request, ActionType.FILE_DETACH, target=order_file.order,
                   summary=f"{order_file.order.order_code}: файл откреплён от карточки")
    return order_file
