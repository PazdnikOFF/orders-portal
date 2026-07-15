"""
Field-edit permission matrix by stage (TЗ §11) + role rules (TЗ §3, amendment §2).

Single source of truth shared by the server (enforcement) and templates (UI
gating). Stages map to statuses; the special "create" stage is the new-record
form before the order exists.
"""

# Stage keys
STAGE_CREATE = "create"
STAGE_PLANNED = "planned"
STAGE_IN_PROGRESS = "in_progress"
STAGE_PRODUCED = "produced"
STAGE_CANCELLED = "cancelled"

# Editable order fields (system fields are handled separately below)
FIELDS = [
    "manager",
    "distributor",
    "trading_org",
    "potential_user",
    "participants",
    "kit",
    "request_date",
    "forecast_date",
    "order_number",
    "status",
]

# System fields: never editable by anyone, regardless of role/stage (TЗ §12.6/§12.8).
SYSTEM_FIELDS = {"request_date", "order_number"}

# TЗ §11 — "+" editable, "-" locked, per stage.
_T, _F = True, False
MATRIX = {
    #                 create  planned in_progress produced cancelled
    "manager":        {STAGE_CREATE: _T, STAGE_PLANNED: _F, STAGE_IN_PROGRESS: _T, STAGE_PRODUCED: _F, STAGE_CANCELLED: _F},
    "distributor":    {STAGE_CREATE: _T, STAGE_PLANNED: _F, STAGE_IN_PROGRESS: _F, STAGE_PRODUCED: _F, STAGE_CANCELLED: _F},
    "trading_org":    {STAGE_CREATE: _T, STAGE_PLANNED: _F, STAGE_IN_PROGRESS: _F, STAGE_PRODUCED: _F, STAGE_CANCELLED: _F},
    "potential_user": {STAGE_CREATE: _T, STAGE_PLANNED: _F, STAGE_IN_PROGRESS: _F, STAGE_PRODUCED: _F, STAGE_CANCELLED: _F},
    "participants":   {STAGE_CREATE: _T, STAGE_PLANNED: _T, STAGE_IN_PROGRESS: _F, STAGE_PRODUCED: _F, STAGE_CANCELLED: _F},
    "kit":            {STAGE_CREATE: _T, STAGE_PLANNED: _T, STAGE_IN_PROGRESS: _F, STAGE_PRODUCED: _F, STAGE_CANCELLED: _F},
    "request_date":   {STAGE_CREATE: _F, STAGE_PLANNED: _F, STAGE_IN_PROGRESS: _F, STAGE_PRODUCED: _F, STAGE_CANCELLED: _F},
    "forecast_date":  {STAGE_CREATE: _T, STAGE_PLANNED: _T, STAGE_IN_PROGRESS: _T, STAGE_PRODUCED: _F, STAGE_CANCELLED: _F},
    "order_number":   {STAGE_CREATE: _F, STAGE_PLANNED: _F, STAGE_IN_PROGRESS: _F, STAGE_PRODUCED: _F, STAGE_CANCELLED: _F},
    "status":         {STAGE_CREATE: _T, STAGE_PLANNED: _T, STAGE_IN_PROGRESS: _T, STAGE_PRODUCED: _F, STAGE_CANCELLED: _F},
}


def stage_allows(field: str, stage: str) -> bool:
    return MATRIX.get(field, {}).get(stage, False)


def can_edit_field(user, field: str, stage: str) -> bool:
    """
    Combine role rules with the stage matrix (server-side enforcement, TЗ §11
    note: «если роль запрещает редактирование, поле заблокировано независимо
    от стадии»).

    - System fields: never editable.
    - Manager / Director: read-only (amendment §2, TЗ §3.4).
    - Admin: full access — may edit any non-system field at any stage (TЗ §3.1).
    - Operator: follows the stage matrix exactly.
    """
    if field in SYSTEM_FIELDS:
        return False
    if not user.is_authenticated:
        return False
    if user.is_manager or user.is_director:
        return False
    if user.is_admin:
        return True
    if user.is_operator:
        return stage_allows(field, stage)
    return False


def editable_fields(user, stage: str) -> set[str]:
    return {f for f in FIELDS if can_edit_field(user, f, stage)}
