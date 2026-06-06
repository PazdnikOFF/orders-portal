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
        # At creation all listed fields are mandatory (TЗ §13).
        if self.is_create and not cleaned.get("participant_orgs"):
            self.add_error("participant_orgs", "Добавьте хотя бы одну организацию-участника.")

        # The same INN must not repeat among the participants of one order
        # (branches with different КПП count as the same INN here). Sharing an
        # INN with the distributor / potential user is allowed.
        if not self.fields["participant_orgs"].disabled and hasattr(self.data, "getlist"):
            raw_ids = [v for v in self.data.getlist("participant_orgs") if v]
            if raw_ids:
                inn_by_id = dict(
                    Organization.objects.filter(pk__in=raw_ids).values_list("pk", "inn")
                )
                seen, dups = set(), set()
                for rid in raw_ids:
                    inn = inn_by_id.get(int(rid)) if rid.isdigit() else None
                    if inn is None:
                        continue
                    if inn in seen:
                        dups.add(inn)
                    seen.add(inn)
                if dups:
                    self.add_error(
                        "participant_orgs",
                        "Один и тот же ИНН нельзя добавить в участники несколько раз: "
                        + ", ".join(sorted(dups)) + ".",
                    )
        return cleaned
