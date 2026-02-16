from django import forms
from django.contrib.auth.models import User
from .models import Cliente, Membresia, Pago, RegistroEntrada
from datetime import datetime, timedelta

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'apellidos', 'telefono', 'email', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def save(self, commit=True):
        cliente = super().save(commit=False)
        if self.cleaned_data.get('password'):
            if not cliente.usuario:
                user = User.objects.create_user(
                    username=cliente.email,
                    email=cliente.email,
                    password=self.cleaned_data['password'],
                    first_name=cliente.nombre,
                    last_name=cliente.apellidos
                )
                cliente.usuario = user
            else:
                cliente.usuario.set_password(self.cleaned_data['password'])
                cliente.usuario.save()
        
        if commit:
            cliente.save()
        return cliente

class MembresiaForm(forms.ModelForm):
    class Meta:
        model = Membresia
        fields = ['cliente', 'tipo', 'fecha_inicio', 'costo']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'costo': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo')
        fecha_inicio = cleaned_data.get('fecha_inicio')
        
        if tipo and fecha_inicio:
            if tipo == 'mensual':
                fecha_fin = fecha_inicio + timedelta(days=30)
            elif tipo == 'anual':
                fecha_fin = fecha_inicio + timedelta(days=365)
            elif tipo == 'semanal':
                fecha_fin = fecha_inicio + timedelta(days=7)
            elif tipo == 'visita':
                fecha_fin = fecha_inicio  # Solo un día
            else:
                fecha_fin = fecha_inicio
            
            cleaned_data['fecha_fin'] = fecha_fin
        
        return cleaned_data
    
    def save(self, commit=True):
        membresia = super().save(commit=False)
        membresia.fecha_fin = self.cleaned_data['fecha_fin']
        if commit:
            membresia.save()
        return membresia

class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = ['membresia', 'monto', 'metodo', 'comprobante']
        widgets = {
            'membresia': forms.Select(attrs={'class': 'form-control'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control'}),
            'metodo': forms.Select(attrs={'class': 'form-control'}),
            'comprobante': forms.FileInput(attrs={'class': 'form-control'}),
        }

class RegistroEntradaForm(forms.Form):
    email = forms.EmailField(
        label='Email del cliente',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'cliente@email.com'})
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        
        try:
            # SOLO verificar que el cliente existe
            cliente = Cliente.objects.get(email=email)
            return cliente
        except Cliente.DoesNotExist:
            raise forms.ValidationError('Cliente no encontrado')
        