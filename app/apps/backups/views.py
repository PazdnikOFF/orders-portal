from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.permissions import role_required

from .models import Backup, BackupKind
from .services import delete_backup, run_backup, run_restore


@login_required
@role_required("can_access_backups")  # Admin only (TЗ §5.2)
def backup_list(request):
    backups = Backup.objects.select_related("created_by").all()
    return render(request, "backups/list.html", {"backups": backups})


@login_required
@role_required("can_access_backups")
def backup_download(request, pk):
    """Download a backup file (admin only) — triggered by clicking the row."""
    backup = get_object_or_404(Backup, pk=pk)
    if not backup.exists_on_disk:
        raise Http404("Файл резервной копии отсутствует на диске.")
    return FileResponse(open(backup.abs_path, "rb"), as_attachment=True,
                        filename=backup.filename)


@login_required
@role_required("can_access_backups")
@require_http_methods(["POST"])
def backup_create(request):
    backup = run_backup(kind=BackupKind.MANUAL, user=request.user, request=request)
    if backup.status == "ok":
        messages.success(request, f"Создана резервная копия {backup.filename}.")
    else:
        messages.error(request, f"Ошибка создания копии: {backup.note}")
    return redirect("backups:list")


@login_required
@role_required("can_access_backups")
@require_http_methods(["POST"])
def backup_restore(request, pk):
    backup = get_object_or_404(Backup, pk=pk)
    ok = run_restore(backup, user=request.user, request=request)
    if ok:
        messages.success(request, f"База восстановлена из {backup.filename}.")
    else:
        messages.error(request, f"Не удалось восстановить из {backup.filename}.")
    return redirect("backups:list")


@login_required
@role_required("can_access_backups")
@require_http_methods(["POST"])
def backup_delete(request, pk):
    backup = get_object_or_404(Backup, pk=pk)
    name = backup.filename
    delete_backup(backup, user=request.user, request=request)
    messages.success(request, f"Резервная копия {name} удалена.")
    return redirect("backups:list")
