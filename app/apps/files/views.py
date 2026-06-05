import mimetypes

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.encoding import iri_to_uri
from django.views.decorators.http import require_http_methods

from apps.orders.models import Order
from apps.orders.services import can_view_order

from .models import OrderFile
from .services import detach_order_file, save_order_file


@login_required
@require_http_methods(["POST"])
def upload(request, order_pk):
    order = get_object_or_404(Order, pk=order_pk)
    if not can_view_order(request.user, order):
        raise PermissionDenied
    uploaded = request.FILES.get("file")
    if not uploaded:
        messages.error(request, "Файл не выбран.")
        return render(request, "files/_card_file.html", {"order": order, "active_file": order.active_file})
    try:
        save_order_file(request, order, uploaded)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    except PermissionDenied as exc:
        raise
    order.refresh_from_db()
    return render(request, "files/_card_file.html",
                  {"order": order, "active_file": order.active_file})


@login_required
@require_http_methods(["POST"])
def detach(request, pk):
    order_file = get_object_or_404(OrderFile, pk=pk)
    order = order_file.order
    if not can_view_order(request.user, order):
        raise PermissionDenied
    detach_order_file(request, order_file)
    messages.success(request, "Файл откреплён от карточки (физически сохранён).")
    order.refresh_from_db()
    return render(request, "files/_card_file.html",
                  {"order": order, "active_file": order.active_file})


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

    download_name = f"{order_file.order.order_code}_{order_file.original_name}"
    content_type = order_file.content_type or mimetypes.guess_type(order_file.stored_name)[0] \
        or "application/octet-stream"

    if settings.DEBUG:
        if not order_file.abs_path.exists():
            raise Http404("Файл не найден на диске.")
        resp = FileResponse(open(order_file.abs_path, "rb"), content_type=content_type)
        resp["Content-Disposition"] = f'inline; filename="{iri_to_uri(download_name)}"'
        return resp

    resp = HttpResponse(content_type=content_type)
    resp["Content-Disposition"] = f'inline; filename="{iri_to_uri(download_name)}"'
    resp["X-Accel-Redirect"] = iri_to_uri(order_file.internal_redirect)
    return resp
