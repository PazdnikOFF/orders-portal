import mimetypes
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.encoding import iri_to_uri
from django.views.decorators.http import require_http_methods


def _content_disposition(filename: str, ascii_fallback: str = "", kind: str = "inline") -> str:
    """
    Build a Content-Disposition header that survives Cyrillic file names on
    Windows, macOS and Linux clients.

    RFC 6266 + RFC 5987: send both an ASCII fallback (filename=) and the real
    UTF-8 name in filename* — browsers (Chrome, Safari, Firefox, Edge) pick
    the UTF-8 variant and show «РЭ-000037.png» to the user.
    """
    encoded = quote(filename, safe="", encoding="utf-8")
    fallback = ascii_fallback or filename.encode("ascii", "ignore").decode("ascii") or "file"
    fallback = fallback.replace('"', "").replace("\\", "")
    return f'{kind}; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'

from apps.orders.models import Order
from apps.orders.services import can_view_order

from .models import OrderFile
from .services import detach_order_file, save_order_file


def _card_file(request, order, error=None, note=None):
    # Inline feedback (no top-of-page flash messages — these are HTMX fragments).
    return render(request, "files/_card_file.html", {
        "order": order, "active_file": order.active_file,
        "file_error": error, "file_note": note,
    })


@login_required
@require_http_methods(["POST"])
def upload(request, order_pk):
    order = get_object_or_404(Order, pk=order_pk)
    if not can_view_order(request.user, order):
        raise PermissionDenied
    uploaded = request.FILES.get("file")
    if not uploaded:
        return _card_file(request, order, error="Файл не выбран.")
    try:
        save_order_file(request, order, uploaded)
    except ValidationError as exc:
        order.refresh_from_db()
        return _card_file(request, order, error="; ".join(exc.messages))
    order.refresh_from_db()
    return _card_file(request, order, note="Файл загружен.")


@login_required
@require_http_methods(["POST"])
def detach(request, pk):
    order_file = get_object_or_404(OrderFile, pk=pk)
    order = order_file.order
    if not can_view_order(request.user, order):
        raise PermissionDenied
    detach_order_file(request, order_file)
    order.refresh_from_db()
    return _card_file(request, order, note="Файл откреплён (физически сохранён).")


@login_required
def serve(request, pk):
    """
    Protected file delivery (TЗ §17). In production nginx streams the file via
    an internal X-Accel-Redirect location after this view authorizes access;
    in DEBUG we stream it directly from Django.
    """
    order_file = get_object_or_404(OrderFile, pk=pk)
    if not can_view_order(request.user, order_file.order):
        raise PermissionDenied

    # Имя файла при скачивании = ровно «РЭ-000037.<ext>» (без оригинального
    # имени, выбранного пользователем). ASCII-вариант — file_code (RE-000037)
    # на случай совсем древних клиентов без RFC 5987.
    download_name = order_file.stored_name
    suffix = Path(order_file.stored_name).suffix
    ascii_fallback = f"{order_file.order.file_code}{suffix}"
    content_type = order_file.content_type or mimetypes.guess_type(order_file.stored_name)[0] \
        or "application/octet-stream"
    cd_header = _content_disposition(download_name, ascii_fallback=ascii_fallback, kind="inline")

    if settings.DEBUG:
        if not order_file.abs_path.exists():
            raise Http404("Файл не найден на диске.")
        resp = FileResponse(open(order_file.abs_path, "rb"), content_type=content_type)
        resp["Content-Disposition"] = cd_header
        return resp

    resp = HttpResponse(content_type=content_type)
    resp["Content-Disposition"] = cd_header
    resp["X-Accel-Redirect"] = iri_to_uri(order_file.internal_redirect)
    return resp
