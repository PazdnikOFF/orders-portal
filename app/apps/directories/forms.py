from django import forms

from .models import Employee


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["last_name", "first_name", "middle_name", "type", "is_active"]
        widgets = {
            "last_name": forms.TextInput(attrs={"class": "input"}),
            "first_name": forms.TextInput(attrs={"class": "input"}),
            "middle_name": forms.TextInput(attrs={"class": "input"}),
            "type": forms.Select(attrs={"class": "input"}),
        }
