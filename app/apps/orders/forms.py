"""
Order card form. Organization fields (distributor, potential user, participants)
are comboboxes: the user types an INN, picks an organization from the dropdown,
and the chosen Organization is submitted by id. Field availability is gated by
the stage/role matrix — non-editable fields are rendered read-only.
"""
from django import forms

from apps.accounts.models import Role, User
from apps.directories.models import Organization

from . import matrix
from .models import Status


class OrgMultipleChoiceField(forms.ModelMultipleChoiceField):
    """ModelMultipleChoiceField that silently drops empty participant rows."""

    def clean(self, value):
        if value:
            value = [v for v in value if v not in (None, "", " ")]
        return super().clean(value)


class OrderForm(forms.Form):
    manager = forms.ModelChoiceField(
        label="Менеджер",
        queryset=User.objects.filter(role=Role.MANAGER, is_active=True),
        widget=forms.Select(attrs={"class": "input"}),
        empty_label="— выберите менеджера —",
    )
    distributor_org = forms.ModelChoiceField(
        label="Дистрибьютор", queryset=Organization.objects.all(),
        widget=forms.HiddenInput(),
    )
    potential_user_org = forms.ModelChoiceField(
        label="Потенциальный пользователь", queryset=Organization.objects.all(),
        widget=forms.HiddenInput(),
    )
    participant_orgs = OrgMultipleChoiceField(
        label="Участники проекта", queryset=Organization.objects.all(),
        required=False, widget=forms.MultipleHiddenInput(),
    )
    kit = forms.CharField(
        label="Комплект", max_length=500, widget=forms.TextInput(attrs={"class": "input"})
    )
    forecast_date = forms.DateField(
        label="Прогнозируемая дата реализации",
        input_formats=["%d.%m.%Y", "%Y-%m-%d"],
        widget=forms.DateInput(attrs={"class": "input", "placeholder": "ДД.ММ.ГГГГ"}, format="%d.%m.%Y"),
    )
    status = forms.ChoiceField(
        label="Статус", choices=Status.choices,
        widget=forms.Select(attrs={"class": "input"}),
    )

    # Map form fields to matrix field keys.
    FIELD_TO_MATRIX = {
        "manager": "manager",
        "distributor_org": "distributor",
        "potential_user_org": "potential_user",
        "participant_orgs": "participants",
        "kit": "kit",
        "forecast_date": "forecast_date",
        "status": "status",
    }

    def __init__(self, *args, user=None, stage=matrix.STAGE_CREATE, is_create=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.stage = stage
        self.is_create = is_create
        # Disable any field the user may not edit at this stage (server-enforced).
        for form_field, matrix_field in self.FIELD_TO_MATRIX.items():
            if not matrix.can_edit_field(user, matrix_field, stage):
                self.fields[form_field].disabled = True

    def clean(self):
        cleaned = super().clean()
        # «Комментарий» (участники) — необязательное поле. Клиент задаёт вопрос,
        # подставлять ли «Потенциального пользователя», если поле осталось пустым.

        # The same organization (ИНН + КПП) must not repeat among participants.
        # Branches (same INN, different КПП) are different organizations and are
        # allowed. Sharing with the distributor / potential user is allowed too.
        if not self.fields["participant_orgs"].disabled and hasattr(self.data, "getlist"):
            raw_ids = [v for v in self.data.getlist("participant_orgs") if v]
            seen, dups = set(), set()
            for rid in raw_ids:
                if rid in seen:
                    dups.add(rid)
                seen.add(rid)
            if dups:
                names = ", ".join(
                    o.display_name for o in Organization.objects.filter(pk__in=dups)
                )
                self.add_error(
                    "participant_orgs",
                    f"Эту организацию нельзя добавить в участники несколько раз: {names}.",
                )
        return cleaned
