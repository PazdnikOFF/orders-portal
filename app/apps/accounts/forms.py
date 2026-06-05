from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Role, User


class LoginForm(AuthenticationForm):
    """Login by username + password (TЗ §2.1)."""

    username = forms.CharField(
        label="Логин",
        widget=forms.TextInput(attrs={"autofocus": True, "class": "input"}),
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"class": "input"}),
    )

    error_messages = {
        "invalid_login": "Неверный логин или пароль.",
        "inactive": "Учётная запись заблокирована.",
    }


class UserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput(attrs={"class": "input"}))
    password2 = forms.CharField(
        label="Повтор пароля", widget=forms.PasswordInput(attrs={"class": "input"})
    )

    class Meta:
        model = User
        fields = ["username", "full_name", "role", "employee", "is_active"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "input"}),
            "full_name": forms.TextInput(attrs={"class": "input"}),
            "role": forms.Select(attrs={"class": "input"}),
            "employee": forms.Select(attrs={"class": "input"}),
        }

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Пароли не совпадают.")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    """Admin edits profile/role/block status and may set a new password."""

    new_password = forms.CharField(
        label="Новый пароль",
        required=False,
        help_text="Оставьте оба поля пустыми, чтобы не менять пароль.",
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "new-password"}),
    )
    new_password2 = forms.CharField(
        label="Повтор нового пароля",
        required=False,
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ["full_name", "role", "employee", "is_active"]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "input"}),
            "role": forms.Select(attrs={"class": "input"}),
            "employee": forms.Select(attrs={"class": "input"}),
        }

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("new_password")
        p2 = cleaned.get("new_password2")
        if (p1 or p2) and p1 != p2:
            self.add_error("new_password2", "Пароли не совпадают.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        pwd = self.cleaned_data.get("new_password")
        if pwd:
            user.set_password(pwd)
        if commit:
            user.save()
        return user
