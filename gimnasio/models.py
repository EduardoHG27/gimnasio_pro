import logging
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

logger = logging.getLogger(__name__)

class Cliente(models.Model):
    TIPO_MEMBRESIA = [
        ('mensual', 'Mensual'),
        ('anual', 'Anual'),
        ('semanal', 'Semanal'),
        ('visita', 'Visita'),
    ]
    
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    nombre = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    telefono = models.CharField(max_length=15)
    email = models.EmailField(unique=True)
    fecha_registro = models.DateTimeField(default=timezone.now)
    activo = models.BooleanField(default=True)
    contraseña = models.CharField(max_length=20, blank=True, editable=False) 
    
    def get_membresia_activa(self):
        """Retorna la membresía activa del cliente si existe"""
        hoy = timezone.now().date()
        logger.debug(f"Buscando membresía activa para cliente {self.id} - Fecha actual: {hoy}")
        
        membresia = self.membresias.filter(
            fecha_inicio__lte=hoy,
            fecha_fin__gte=hoy,
            pagado=True
        ).first()
        
        if membresia:
            logger.debug(f"Membresía activa encontrada: ID={membresia.id}, del {membresia.fecha_inicio} al {membresia.fecha_fin}")
        else:
            logger.debug("No se encontró membresía activa")
            
            # DEBUG: Mostrar todas las membresías del cliente para verificar
            todas = self.membresias.all()
            logger.debug(f"Total membresías del cliente: {todas.count()}")
            for m in todas:
                logger.debug(f"  - Membresía ID={m.id}: {m.fecha_inicio} a {m.fecha_fin}, pagado={m.pagado}, activa hoy={m.fecha_inicio <= hoy <= m.fecha_fin and m.pagado}")
        
        return membresia
    
    def tiene_membresia_activa(self):
        """Verifica si el cliente tiene una membresía activa"""
        resultado = self.get_membresia_activa() is not None
        logger.debug(f"Cliente {self.id} - ¿Tiene membresía activa?: {resultado}")
        return resultado
    
    def actualizar_estado_activo(self):
        """Actualiza el campo activo basado en si tiene membresía activa"""
        estado_anterior = self.activo
        self.activo = self.tiene_membresia_activa()
        
        if estado_anterior != self.activo:
            logger.debug(f"Cliente {self.id} - Estado cambiado: {estado_anterior} -> {self.activo}")
            self.save(update_fields=['activo'])
        else:
            logger.debug(f"Cliente {self.id} - Estado sin cambios: {self.activo}")

        
    def generar_contraseña(self):
        """Genera una contraseña con formato: últimos 2 dígitos del año + últimos 3 dígitos del teléfono"""
        from datetime import datetime
        
        # Obtener últimos 2 dígitos del año actual
        año_actual = datetime.now().year
        ultimos_2_año = str(año_actual)[-2:]
        
        # Obtener últimos 3 dígitos del teléfono (limpiando el número)
        telefono_limpio = ''.join(filter(str.isdigit, self.telefono))
        if len(telefono_limpio) >= 3:
            ultimos_3_telefono = telefono_limpio[-3:]
        else:
            # Si el teléfono tiene menos de 3 dígitos, rellenar con ceros
            ultimos_3_telefono = telefono_limpio.zfill(3)
        
        # Generar contraseña
        self.contraseña = f"{ultimos_2_año}{ultimos_3_telefono}"
        return self.contraseña
    
    def save(self, *args, **kwargs):
        # Si es un nuevo cliente y no tiene contraseña, generarla automáticamente
        if not self.pk and not self.contraseña:
            self.generar_contraseña()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} {self.apellidos}"
    
    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

class Membresia(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='membresias')
    tipo = models.CharField(max_length=20, choices=Cliente.TIPO_MEMBRESIA)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    costo = models.DecimalField(max_digits=10, decimal_places=2)
    pagado = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.cliente} - {self.tipo} ({self.fecha_inicio} a {self.fecha_fin})"
    
    @property
    def dias_restantes(self):
        hoy = timezone.now().date()
        if self.fecha_fin and self.fecha_fin >= hoy:
            dias = (self.fecha_fin - hoy).days
            logger.debug(f"Membresía {self.id} - Días restantes: {dias}")
            return dias
        logger.debug(f"Membresía {self.id} - Días restantes: 0 (vencida)")
        return 0
    
    @property
    def esta_activa(self):
        hoy = timezone.now().date()
        activa = self.pagado and self.fecha_inicio <= hoy <= self.fecha_fin
        logger.debug(f"Membresía {self.id} - ¿Está activa?: {activa}")
        return activa
    
    @property
    def esta_vencida(self):
        """Verifica si la membresía está vencida"""
        hoy = timezone.now().date()
        return self.fecha_fin < hoy
    
    def save(self, *args, **kwargs):
        """Sobrescribimos save para actualizar el estado del cliente"""
        super().save(*args, **kwargs)
        # Actualizar el estado activo del cliente
        self.cliente.actualizar_estado_activo()
    
    class Meta:
        verbose_name = "Membresía"
        verbose_name_plural = "Membresías"

class Pago(models.Model):
    METODO_PAGO = [
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta'),
        ('transferencia', 'Transferencia'),
    ]
    
    membresia = models.ForeignKey(Membresia, on_delete=models.CASCADE, related_name='pagos')
    fecha_pago = models.DateTimeField(default=timezone.now)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=20, choices=METODO_PAGO)
    comprobante = models.FileField(upload_to='comprobantes/', null=True, blank=True)
    
    def __str__(self):
        return f"Pago {self.membresia} - {self.monto}"
    
    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"

class RegistroEntrada(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='entradas')
    fecha_entrada = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.cliente} - {self.fecha_entrada.strftime('%Y-%m-%d %H:%M')}"
    
    class Meta:
        verbose_name = "Registro de Entrada"
        verbose_name_plural = "Registros de Entrada"
        ordering = ['-fecha_entrada']