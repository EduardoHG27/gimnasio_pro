from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Autenticación
    path('login/', auth_views.LoginView.as_view(template_name='gimnasio/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # Clientes
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('clientes/nuevo/', views.nuevo_cliente, name='nuevo_cliente'),
    path('clientes/<int:pk>/', views.detalle_cliente, name='detalle_cliente'),
    path('clientes/<int:pk>/editar/', views.editar_cliente, name='editar_cliente'),
    path('clientes/<int:pk>/regenerar-contraseña/', views.regenerar_contraseña, name='regenerar_contraseña'), 
    
    # Membresías
    path('membresias/nueva/', views.nueva_membresia, name='nueva_membresia'),
    path('membresias/nueva/<int:cliente_pk>/', views.nueva_membresia, name='nueva_membresia_cliente'),
    
    # Pagos
    path('pagos/nuevo/', views.nuevo_pago, name='nuevo_pago'),
    path('pagos/nuevo/<int:membresia_pk>/', views.nuevo_pago, name='nuevo_pago_membresia'),
    
    # Registro de entradas
    path('entradas/', views.registro_entrada, name='registro_entrada'),
    path('entradas/historial/', views.historial_entradas, name='historial_entradas'),
    
    # Exportar
    path('exportar/clientes/', views.exportar_clientes, name='exportar_clientes'),
]