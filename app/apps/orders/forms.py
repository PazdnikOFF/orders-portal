"""
Order card form. Organization fields are entered as INN and resolved to
Organization records on save (TЗ §12). Field availability is gated by the
stage/role matrix — non-editable fields are rendered disabled.
"""
import json

from django import forms
from django.urls import reverse_lazy

from apps.directories.models import Employee, EmployeeType

from . import matrix
from .models import Status

# Fire the lookup automatically once a full INN (10 or 12 digits) is entered —
# no button click. `event.target` is the input in both keyup and change filters.
_INN_VALID_LEN = "event.target.value.length==10||event.target.value.length==12"


def _inn_widget(input_id: str, field_key: str, target_id: str) -> forms.TextInput:
    return forms.TextInput(attrs={
        "class": "input inn-input",
        "inputmode": "numeric",
        "autocomplete": "off",
        "hx-post": reverse_lazy("directories:org_lookup"),
        "hx-trigger": f"keyup[{_INN_VALID_LEN}] changed delay:500ms, change[{_INN_VALID_LEN}]",
        "hx-vals": f'js:{{inn: document.getElementById("{input_id}").value, field:"{field_key}"}}',
        "hx-target": f"#{target_id}",
        "hx-swap": "innerHTML",
    })


class OrderForm(forms.Form):
    manager = forms.ModelChoiceField(
        label="Менеджер",
        queryset=Employee.objects.filter(type=EmployeeType.MANAGER, is_active=True),
        widget=forms.Select(attrs={"class": "input"}),
        empty_label="— выберите менеджера —",
    )
    distributor_inn = forms.CharField(
        label="Дистрибьютор (ИНН)", max_length=12,
        widget=_inn_widget("id_distributor_inn", "distributor", "lk-distributor"),
    )
    potential_user_inn = forms.CharField(
        label="Потенциальный пользователь (ИНН)", max_length=12,
        widget=_inn_widget("id_potential_user_inn", "potential_user", "lk-potential"),
    )
    # Hidden JSON array of participant INNs, managed by the Alpine widget.
    participant_inns = forms.CharField(
        label="Участники проекта", required=False, widget=forms.HiddenInput()
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
        "distributor_inn": "distributor",
        "potential_user_inn": "potential_user",
        "participant_inns": "participants",
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

    def _clean_inn(self, value):
        value = (value or "").strip()
        if value and (not value.isdigit() or len(value) not in (10, 12)):
            raise forms.ValidationError("ИНН должен содержать 10 или 12 цифр.")
        return value

    def clean_distributor_inn(self):
        return self._clean_inn(self.cleaned_data.get("distributor_inn"))

    def clean_potential_user_inn(self):
        return self._clean_inn(self.cleaned_data.get("potential_user_inn"))

    def clean_participant_inns(self):
        raw = (self.cleaned_data.get("participant_inns") or "").strip()
        if not raw:
            return []
        try:
            items = json.loads(raw) if raw.startswith("[") else [x for x in raw.replace(",", "\n").split("\n")]
        except json.JSONDecodeError:
            raise forms.ValidationError("Некорректный список участников.")
        inns = []
        for item in items:
            inn = self._clean_inn(str(item))
            if inn:
                inns.append(inn)
        return inns

    def clean(self):
        cleaned = super().clean()
        # At creation all listed fields are mandatory (TЗ §13).
        if self.is_create:
            if not cleaned.get("participant_inns"):
                self.add_error("participant_inns", "Добавьте хотя бы одну организацию-участника.")
        return cleaned
