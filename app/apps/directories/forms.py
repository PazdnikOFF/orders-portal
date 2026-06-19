"""Forms for the admin-managed Distributor directory.

Organization data is still entered via the order card combobox (no standalone
form). Distributors are added by INN (name pulled from DaData) and edited here.
"""
from django import forms

from .models import Distributor


class DistributorAddForm(forms.Form):
    """Add a distributor by INN — the name is fetched from the provider."""

    inn = forms.CharField(
        label="ИНН",
        max_length=12,
        widget=forms.TextInput(attrs={
            "class": "input", "inputmode": "numeric", "autocomplete": "off",
            "placeholder": "10 или 12 цифр",
        }),
        help_text="Наименование подтянется автоматически из DaData по ИНН.",
    )

    def clean_inn(self):
        inn = (self.cleaned_data["inn"] or "").strip()
        if not inn.isdigit() or len(inn) not in (10, 12):
            raise forms.ValidationError("ИНН должен содержать 10 или 12 цифр.")
        if Distributor.objects.filter(inn=inn).exists():
            raise forms.ValidationError("Дистрибьютор с таким ИНН уже есть в справочнике.")
        return inn


class DistributorEditForm(forms.ModelForm):
    """Edit a distributor's display name (ИНН is immutable)."""

    class Meta:
        model = Distributor
        fields = ["name", "full_name"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input"}),
            "full_name": forms.TextInput(attrs={"class": "input"}),
        }
        help_texts = {
            "name": "Короткое наименование, как показывается в заказах.",
        }
