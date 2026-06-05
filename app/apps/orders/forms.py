"""
Order card form. Organization fields (distributor, potential user, participants)
are comboboxes: the user types an INN, picks an organization from the dropdown,
and the chosen Organization is submitted by id. Field availability is gated by
the stage/role matrix — non-editable fields are rendered read-only.
"""
from django import forms

from apps.directories.models import Employee, EmployeeType, Organization

from . import matrix
from .models import Status


class OrderForm(forms.Form):
    manager = forms.ModelChoiceField(
        label="Менеджер",
        queryset=Employee.objects.filter(type=EmployeeType.MANAGER, is_active=True),
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
    participant_orgs = forms.ModelMultipleChoiceField(
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
        return cleaned
