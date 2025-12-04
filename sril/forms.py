# sril/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import Usuario, Puntuacion, PreferenciaUsuario, HistorialLectura

class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'tu@email.com'
        })
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Contraseña'
        })
    )

class RegistroForm(UserCreationForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'tu@email.com'
        })
    )
    nombre = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tu nombre completo'
        })
    )
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Contraseña'
        })
    )
    password2 = forms.CharField(
        label='Confirmar Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repite tu contraseña'
        })
    )

    class Meta:
        model = Usuario
        fields = ['email', 'nombre', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.nombre = self.cleaned_data['nombre']
        if commit:
            user.save()
        return user


class PuntuacionForm(forms.ModelForm):
    class Meta:
        model = Puntuacion
        fields = ['puntuacion', 'comentario']
        widgets = {
            'puntuacion': forms.NumberInput(attrs={
                'min': '1', 
                'max': '5', 
                'step': '0.5',
                'class': 'form-control'
            }),
            'comentario': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Escribe tu reseña...'
            })
        }

class PreferenciaUsuarioForm(forms.ModelForm):
    class Meta:
        model = PreferenciaUsuario
        fields = ['categoria', 'nivel_interes']
        widgets = {
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'nivel_interes': forms.NumberInput(attrs={
                'min': '1',
                'max': '5',
                'class': 'form-control'
            })
        }

class HistorialLecturaForm(forms.ModelForm):
    class Meta:
        model = HistorialLectura
        fields = ['estado', 'paginas_leidas']
        widgets = {
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'paginas_leidas': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            })
        }