from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import datetime, timedelta
import pandas as pd

from .models import Cliente, Membresia, Pago, RegistroEntrada
from .forms import ClienteForm, MembresiaForm, PagoForm, RegistroEntradaForm

# Vistas de clientes
@login_required
def lista_clientes(request):
    # Opcional: actualizar todos los clientes al cargar la lista
    for cliente in Cliente.objects.all():
        cliente.actualizar_estado_activo()
    
    clientes = Cliente.objects.all().order_by('-fecha_registro')
    
    # Marcar en la lista quiénes tienen membresía activa y su fecha de vencimiento
    for cliente in clientes:
        # Obtener membresía activa si existe
        membresia_activa = cliente.get_membresia_activa()
        cliente.tiene_membresia_activa = membresia_activa is not None
        
        if membresia_activa:
            # Si tiene membresía activa, mostrar su fecha de vencimiento
            cliente.fecha_vencimiento = membresia_activa.fecha_fin
            cliente.dias_restantes = membresia_activa.dias_restantes
            cliente.tipo_membresia = membresia_activa.get_tipo_display()
            cliente.es_activa = True
        else:
            # Si no tiene membresía activa, buscar la última membresía (aunque esté vencida)
            ultima_membresia = cliente.membresias.filter(pagado=True).order_by('-fecha_fin').first()
            if ultima_membresia:
                cliente.fecha_vencimiento = ultima_membresia.fecha_fin
                cliente.tipo_membresia = ultima_membresia.get_tipo_display()
                cliente.dias_restantes = 0
                cliente.es_activa = False
                
                # Calcular días desde que venció
                hoy = timezone.now().date()
                if ultima_membresia.fecha_fin < hoy:
                    cliente.dias_vencida = (hoy - ultima_membresia.fecha_fin).days
            else:
                cliente.fecha_vencimiento = None
                cliente.tipo_membresia = None
                cliente.es_activa = False
                cliente.dias_vencida = None
    
    return render(request, 'gimnasio/clientes/lista.html', {'clientes': clientes})

@login_required
def detalle_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    
    # Verificar y actualizar el estado del cliente basado en sus membresías
    estado_anterior = cliente.activo
    cliente.actualizar_estado_activo()
    
    # Si cambió el estado, mostrar un mensaje
    if estado_anterior != cliente.activo:
        if cliente.activo:
            messages.info(request, f'✨ El cliente {cliente.nombre} ha sido reactivado automáticamente (tiene membresía activa)')
        else:
            messages.warning(request, f'⚠️ El cliente {cliente.nombre} ha sido desactivado automáticamente (su membresía expiró)')
    
    membresias = cliente.membresias.all().order_by('-fecha_inicio')
    entradas = cliente.entradas.all()[:10]  # Últimas 10 entradas
    
    # ✅ ELIMINA ESTA LÍNEA PROBLEMÁTICA:
    # for membresia in membresias:
    #     membresia.esta_activa = membresia.esta_activa  # ← ¡NO HACER!
    
    return render(request, 'gimnasio/clientes/detalle.html', {
        'cliente': cliente,
        'membresias': membresias,
        'entradas': entradas
    })

@login_required
def nuevo_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_clientes')
    else:
        form = ClienteForm()
    
    return render(request, 'gimnasio/clientes/form.html', {
        'form': form,
        'accion': 'Nuevo'
    })

@login_required
def editar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente actualizado exitosamente')
            return redirect('detalle_cliente', pk=cliente.pk)
    else:
        form = ClienteForm(instance=cliente)
    
    return render(request, 'gimnasio/clientes/form.html', {'form': form, 'accion': 'Editar'})

# Vistas de membresías
@login_required
def nueva_membresia(request, cliente_pk=None):
    cliente = None
    if cliente_pk:
        cliente = get_object_or_404(Cliente, pk=cliente_pk)
    
    if request.method == 'POST':
        form = MembresiaForm(request.POST)
        if form.is_valid():
            membresia = form.save()
            messages.success(request, 'Membresía registrada exitosamente')
            return redirect('detalle_cliente', pk=membresia.cliente.pk)
    else:
        initial = {}
        if cliente:
            initial['cliente'] = cliente
        form = MembresiaForm(initial=initial)
    
    return render(request, 'gimnasio/membresias/form.html', {'form': form, 'accion': 'Nueva'})

# Vistas de pagos
@login_required
def nuevo_pago(request, membresia_pk=None):
    membresia = None
    if membresia_pk:
        membresia = get_object_or_404(Membresia, pk=membresia_pk)
    
    if request.method == 'POST':
        form = PagoForm(request.POST, request.FILES)
        if form.is_valid():
            pago = form.save()
            # Marcar membresía como pagada
            membresia = pago.membresia
            membresia.pagado = True
            membresia.save()
            
            messages.success(request, 'Pago registrado exitosamente')
            return redirect('detalle_cliente', pk=membresia.cliente.pk)
    else:
        initial = {}
        if membresia:
            initial['membresia'] = membresia
            initial['monto'] = membresia.costo
        form = PagoForm(initial=initial)
    
    return render(request, 'gimnasio/pagos/form.html', {'form': form, 'accion': 'Nuevo'})

# Vistas de registro de entrada
def registro_entrada(request):
    cliente_info = None
    email_buscado = None
    
    if request.method == 'POST':
        form = RegistroEntradaForm(request.POST)
        if form.is_valid():
            cliente = form.cleaned_data['email']
            email_buscado = cliente.email
            
            # Actualizar estado del cliente
            estado_anterior = cliente.activo
            cliente.actualizar_estado_activo()
            
            # Verificar membresía activa
            membresia_activa = cliente.get_membresia_activa()
            
            if membresia_activa:
                # Cliente con membresía activa - REGISTRAR ENTRADA
                if not estado_anterior and cliente.activo:
                    messages.info(request, f'✨ {cliente.nombre} ha sido reactivado automáticamente')
                
                dias_restantes = membresia_activa.dias_restantes
                
                # Registrar la entrada
                entrada = RegistroEntrada.objects.create(cliente=cliente)
                
                messages.success(
                    request, 
                    f'✅ Entrada registrada para {cliente.nombre} {cliente.apellidos}<br>'
                    f'📅 Membresía vigente por {dias_restantes} días más '
                    f'(vence: {membresia_activa.fecha_fin.strftime("%d/%m/%Y")})'
                )
                
                cliente_info = {
                    'nombre': f'{cliente.nombre} {cliente.apellidos}',
                    'tipo_membresia': membresia_activa.get_tipo_display(),
                    'fecha_inicio': membresia_activa.fecha_inicio,
                    'fecha_fin': membresia_activa.fecha_fin,
                    'dias_restantes': dias_restantes,
                    'tiene_membresia_activa': True,
                    'cliente_id': cliente.id
                }
            else:
                # Cliente sin membresía activa - NO REGISTRAR ENTRADA
                if cliente.activo:
                    cliente.activo = False
                    cliente.save(update_fields=['activo'])
                    messages.warning(
                        request,
                        f'⚠️ {cliente.nombre} {cliente.apellidos} ha sido desactivado automáticamente (sin membresía activa)'
                    )
                
                # Buscar información de membresías anteriores
                ultima_membresia = Membresia.objects.filter(
                    cliente=cliente
                ).order_by('-fecha_fin').first()
                
                # Preparar información detallada del cliente inactivo
                cliente_info = {
                    'nombre': f'{cliente.nombre} {cliente.apellidos}',
                    'tiene_membresia_activa': False,
                    'cliente_id': cliente.id,
                    'email': cliente.email,
                    'telefono': cliente.telefono
                }
                
                if ultima_membresia:
                    cliente_info['ultima_membresia'] = ultima_membresia
                    cliente_info['tipo_membresia'] = ultima_membresia.get_tipo_display()
                    cliente_info['fecha_fin'] = ultima_membresia.fecha_fin
                    
                    if not ultima_membresia.pagado:
                        cliente_info['motivo'] = 'membresía pendiente de pago'
                        cliente_info['membresia_pendiente'] = ultima_membresia
                    elif ultima_membresia.fecha_fin < timezone.now().date():
                        cliente_info['motivo'] = 'membresía vencida'
                        cliente_info['dias_vencida'] = (timezone.now().date() - ultima_membresia.fecha_fin).days
                else:
                    cliente_info['motivo'] = 'sin membresía registrada'
                
                # Mensaje de advertencia
                messages.warning(
                    request,
                    f'⚠️ {cliente.nombre} {cliente.apellidos} no tiene una membresía activa.<br>'
                    f'Motivo: {cliente_info["motivo"]}'
                )
    else:
        form = RegistroEntradaForm()
    
    # Obtener últimos registros (el resto del código permanece igual)
    ultimos_registros = RegistroEntrada.objects.all().select_related('cliente')[:10]
    
    for registro in ultimos_registros:
        membresia_en_momento = Membresia.objects.filter(
            cliente=registro.cliente,
            fecha_inicio__lte=registro.fecha_entrada.date(),
            fecha_fin__gte=registro.fecha_entrada.date(),
            pagado=True
        ).first()
        
        registro.membresia_activa = membresia_en_momento is not None
    
    return render(request, 'gimnasio/registro_entrada.html', {
        'form': form,
        'ultimos_registros': ultimos_registros,
        'cliente_info': cliente_info,
        'email_buscado': email_buscado
    })

@login_required
def historial_entradas(request):
    entradas = RegistroEntrada.objects.all()
    
    # Filtros
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    cliente_id = request.GET.get('cliente')
    
    if fecha_inicio:
        entradas = entradas.filter(fecha_entrada__date__gte=fecha_inicio)
    if fecha_fin:
        entradas = entradas.filter(fecha_entrada__date__lte=fecha_fin)
    if cliente_id:
        entradas = entradas.filter(cliente_id=cliente_id)
    
    return render(request, 'gimnasio/historial_entradas.html', {
        'entradas': entradas,
        'clientes': Cliente.objects.filter(activo=True)
    })

# Dashboard / Reportes
@login_required
def dashboard(request):
    hoy = timezone.now().date()
    
    # Estadísticas generales
    total_clientes = Cliente.objects.count()
    clientes_activos = Cliente.objects.filter(activo=True).count()
    
    # Membresías activas hoy
    membresias_activas = Membresia.objects.filter(
        fecha_inicio__lte=hoy,
        fecha_fin__gte=hoy,
        pagado=True
    ).count()
    
    # Ingresos del mes
    ingresos_mes = Pago.objects.filter(
        fecha_pago__month=hoy.month,
        fecha_pago__year=hoy.year
    ).aggregate(total=Sum('monto'))['total'] or 0
    
    # Entradas hoy
    entradas_hoy = RegistroEntrada.objects.filter(
        fecha_entrada__date=hoy
    ).count()
    
    # Próximas membresías a vencer (próximos 7 días)
    proximas_vencer = Membresia.objects.filter(
        fecha_fin__gte=hoy,
        fecha_fin__lte=hoy + timedelta(days=7),
        pagado=True
    ).select_related('cliente')
    
    # 🔴 NUEVO: Membresías vencidas (últimos 30 días)
    membresias_vencidas = Membresia.objects.filter(
        fecha_fin__lt=hoy,
        fecha_fin__gte=hoy - timedelta(days=30),
        pagado=True
    ).select_related('cliente').order_by('-fecha_fin')
    
    # Calcular días de vencimiento para cada una
    for membresia in membresias_vencidas:
        membresia.dias_vencida = (hoy - membresia.fecha_fin).days
    
    context = {
        'total_clientes': total_clientes,
        'clientes_activos': clientes_activos,
        'membresias_activas': membresias_activas,
        'ingresos_mes': ingresos_mes,
        'entradas_hoy': entradas_hoy,
        'proximas_vencer': proximas_vencer,
        'membresias_vencidas': membresias_vencidas,  # 🔴 NUEVO
    }
    
    return render(request, 'gimnasio/dashboard.html', context)

# Exportar datos
@login_required
def exportar_clientes(request):
    clientes = Cliente.objects.all().values(
        'nombre', 'apellidos', 'telefono', 'email', 
        'fecha_registro', 'activo'
    )
    df = pd.DataFrame(list(clientes))
    
    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename="clientes.xlsx"'
    
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Clientes', index=False)
    
    return response
