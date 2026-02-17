from django import forms
from .models import Cliente, Membresia, Pago, RegistroEntrada
from datetime import datetime, timedelta

class ClienteForm(forms.ModelForm):
    # Campo opcional para mostrar la contraseña generada (solo lectura)
    contraseña_generada = forms.CharField(
        label='Contraseña generada',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': 'readonly',
            'placeholder': 'Se generará automáticamente'
        })
    )
    
    class Meta:
        model = Cliente
        fields = ['nombre', 'apellidos', 'telefono', 'email', 'activo', 'contraseña_generada']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si estamos editando un cliente existente, mostrar su contraseña actual
        if self.instance and self.instance.pk and self.instance.contraseña:
            self.fields['contraseña_generada'].initial = self.instance.contraseña
        elif self.instance and not self.instance.pk:
            # Para clientes nuevos, generar una contraseña de ejemplo
            self.fields['contraseña_generada'].initial = self._generar_contraseña_ejemplo()
    
    def _generar_contraseña_ejemplo(self):
        """Genera un ejemplo de contraseña basado en el año actual"""
        año_actual = datetime.now().year
        ultimos_2_año = str(año_actual)[-2:]
        return f"{ultimos_2_año}123"  # Ejemplo con 123 como últimos dígitos
    
    def save(self, commit=True):
        cliente = super().save(commit=False)
        
        # Si es un cliente nuevo, generar contraseña automáticamente
        if not cliente.pk:
            cliente.generar_contraseña()
        # Si se modificó el teléfono, regenerar contraseña
        elif 'telefono' in self.changed_data:
            cliente.generar_contraseña()
        
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
    contraseña = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese la contraseña del cliente',
            'autocomplete': 'off'
        }),
        label='Contraseña'
    )
    
    def clean_contraseña(self):
        contraseña = self.cleaned_data['contraseña']
        try:
            cliente = Cliente.objects.get(contraseña=contraseña)
            return cliente
        except Cliente.DoesNotExist:
            raise forms.ValidationError('No existe un cliente con esa contraseña')