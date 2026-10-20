from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from basis.bootstrap.accounts import identity


class SignupForm(UserCreationForm[User]):
    email = forms.EmailField(label="Correo electrónico", max_length=150)
    name = forms.CharField(label="Nombre", max_length=100)
    adult = forms.BooleanField(label="Tengo 18 años o más")

    class Meta:
        model = get_user_model()
        fields = ["email", "name", "password1", "password2", "adult"]

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().lower()
        if identity().email_in_use(email):
            raise ValidationError(
                "Usa recuperación de acceso o contacta soporte si ya tienes un perfil."
            )
        return str(email)
