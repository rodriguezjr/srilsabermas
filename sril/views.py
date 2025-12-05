# sril/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Count
from .models import Usuario, Libro, Categoria, Puntuacion, PreferenciaUsuario, HistorialLectura
from .forms import PuntuacionForm, PreferenciaUsuarioForm, HistorialLecturaForm

from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from .forms import LoginForm, RegistroForm

from django.http import FileResponse, Http404
from django.utils.text import slugify
import os

# Vistas de autenticación
def registro_view(request):
    """Vista para registro de nuevos usuarios"""
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'¡Bienvenido {user.nombre}! Tu cuenta ha sido creada exitosamente.')
            return redirect('sril:home')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = RegistroForm()
    
    context = {'form': form}
    return render(request, 'sril/usuarios/registro.html', context)

class CustomLoginView(LoginView):
    """Vista personalizada para login"""
    form_class = LoginForm
    template_name = 'sril/usuarios/login.html'
    
    def form_valid(self, form):
        messages.success(self.request, f'¡Bienvenido de nuevo {form.get_user().nombre}!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Email o contraseña incorrectos. Intenta nuevamente.')
        return super().form_invalid(form)

@login_required
def logout_view(request):
    """Vista para cerrar sesión"""
    logout(request)
    messages.success(request, 'Has cerrado sesión exitosamente.')
    return redirect('sril:home')

def get_usuario_actual(request):
    """Helper function to get the correct Usuario instance"""
    if request.user.is_authenticated:
        try:
            return Usuario.objects.get(id=request.user.id)
        except Usuario.DoesNotExist:
            return None
    return None

def home(request):
    """Página principal con libros destacados"""
    libros_destacados = Libro.objects.annotate(
        avg_rating=Avg('puntuaciones__puntuacion'),
        num_ratings=Count('puntuaciones')
    ).filter(activo=True).order_by('-avg_rating')[:8]
    
    context = {
        'libros_destacados': libros_destacados,
    }
    return render(request, 'sril/home.html', context)

def lista_libros(request):
    """Lista todos los libros con filtros"""
    libros = Libro.objects.filter(activo=True)
    
    # Filtros
    categoria_id = request.GET.get('categoria')
    if categoria_id:
        libros = libros.filter(categorias__id=categoria_id)
    
    query = request.GET.get('q')
    if query:
        libros = libros.filter(
            Q(titulo__icontains=query) |
            Q(autor__icontains=query) |
            Q(isbn__icontains=query)
        )
    
    categorias = Categoria.objects.all()
    
    context = {
        'libros': libros,
        'categorias': categorias,
    }
    return render(request, 'sril/libros/lista_libros.html', context)

def detalle_libro(request, libro_id):
    """Detalle de un libro específico"""
    libro = get_object_or_404(Libro, id=libro_id, activo=True)
    puntuacion_usuario = None
    historial_usuario = None
    
    usuario_actual = get_usuario_actual(request)
    if usuario_actual:
        puntuacion_usuario = Puntuacion.objects.filter(
            usuario=usuario_actual, 
            libro=libro
        ).first()
        
        historial_usuario = HistorialLectura.objects.filter(
            usuario=usuario_actual,
            libro=libro
        ).first()
    
    # Puntuaciones recientes
    puntuaciones_recientes = libro.puntuaciones.select_related('usuario').order_by('-fecha_puntuacion')[:5]
    
    # Libros similares (misma categoría)
    libros_similares = Libro.objects.filter(
        categorias__in=libro.categorias.all(),
        activo=True
    ).exclude(
        id=libro.id
    ).distinct().annotate(
        avg_rating=Avg('puntuaciones__puntuacion'),
        num_ratings=Count('puntuaciones')
    ).order_by('-avg_rating')[:4]
    
    context = {
        'libro': libro,
        'puntuacion_usuario': puntuacion_usuario,
        'historial_usuario': historial_usuario,
        'puntuaciones_recientes': puntuaciones_recientes,
        'libros_similares': libros_similares,
    }
    return render(request, 'sril/libros/detalle_libro.html', context)

@login_required
def puntuar_libro(request, libro_id):
    """Permite al usuario puntuar un libro"""
    libro = get_object_or_404(Libro, id=libro_id, activo=True)
    usuario_actual = get_usuario_actual(request)
    
    if not usuario_actual:
        messages.error(request, 'Error de autenticación')
        return redirect('sril:login')
    
    puntuacion_existente = Puntuacion.objects.filter(usuario=usuario_actual, libro=libro).first()
    
    if request.method == 'POST':
        form = PuntuacionForm(request.POST, instance=puntuacion_existente)
        if form.is_valid():
            puntuacion = form.save(commit=False)
            puntuacion.usuario = usuario_actual
            puntuacion.libro = libro
            puntuacion.save()
            messages.success(request, '¡Gracias por tu puntuación!')
            return redirect('sril:detalle_libro', libro_id=libro.id)
    else:
        form = PuntuacionForm(instance=puntuacion_existente)
    
    context = {
        'form': form,
        'libro': libro,
        'puntuacion_existente': puntuacion_existente,
    }
    return render(request, 'sril/libros/puntuar_libro.html', context)

@login_required
def gestionar_historial(request, libro_id):
    """Gestiona el historial de lectura de un usuario"""
    libro = get_object_or_404(Libro, id=libro_id, activo=True)
    usuario_actual = get_usuario_actual(request)
    
    if not usuario_actual:
        messages.error(request, 'Error de autenticación')
        return redirect('sril:login')
    
    historial_existente = HistorialLectura.objects.filter(usuario=usuario_actual, libro=libro).first()
    
    if request.method == 'POST':
        form = HistorialLecturaForm(request.POST, instance=historial_existente)
        if form.is_valid():
            historial = form.save(commit=False)
            historial.usuario = usuario_actual
            historial.libro = libro
            historial.save()
            messages.success(request, 'Historial actualizado correctamente')
            return redirect('sril:detalle_libro', libro_id=libro.id)
    else:
        form = HistorialLecturaForm(instance=historial_existente)
    
    context = {
        'form': form,
        'libro': libro,
        'historial_existente': historial_existente,
    }
    return render(request, 'sril/libros/gestionar_historial.html', context)

@login_required
def mis_preferencias(request):
    """Permite al usuario gestionar sus preferencias"""
    usuario_actual = get_usuario_actual(request)
    
    if not usuario_actual:
        messages.error(request, 'Error de autenticación')
        return redirect('sril:login')
    
    preferencias = PreferenciaUsuario.objects.filter(usuario=usuario_actual)
    categorias = Categoria.objects.all()
    
    if request.method == 'POST':
        # Manejar eliminación
        eliminar_id = request.POST.get('eliminar_id')
        if eliminar_id:
            preferencia = get_object_or_404(PreferenciaUsuario, id=eliminar_id, usuario=usuario_actual)
            preferencia.delete()
            messages.success(request, 'Preferencia eliminada correctamente')
            return redirect('sril:mis_preferencias')
        
        # Manejar creación
        form = PreferenciaUsuarioForm(request.POST)
        if form.is_valid():
            preferencia = form.save(commit=False)
            preferencia.usuario = usuario_actual
            
            # Verificar si ya existe
            existe = PreferenciaUsuario.objects.filter(
                usuario=usuario_actual, 
                categoria=preferencia.categoria
            ).exists()
            
            if not existe:
                preferencia.save()
                messages.success(request, 'Preferencia agregada correctamente')
            else:
                messages.error(request, 'Ya tienes una preferencia para esta categoría')
            
            return redirect('sril:mis_preferencias')
    else:
        form = PreferenciaUsuarioForm()
    
    context = {
        'preferencias': preferencias,
        'categorias': categorias,
        'form': form,
    }
    return render(request, 'sril/usuarios/mis_preferencias.html', context)

@login_required
def recomendaciones(request):
    """Sistema de recomendación basado en preferencias del usuario"""
    usuario_actual = get_usuario_actual(request)
    
    if not usuario_actual:
        messages.error(request, 'Error de autenticación')
        return redirect('sril:login')
    
    # Obtener preferencias del usuario
    preferencias_usuario = PreferenciaUsuario.objects.filter(
        usuario=usuario_actual, 
        nivel_interes__gte=3  # Solo categorías con interés >= 3
    ).values_list('categoria_id', flat=True)
    
    # Libros recomendados basados en preferencias
    libros_recomendados = Libro.objects.filter(
        categorias__id__in=preferencias_usuario,
        activo=True
    ).distinct().annotate(
        avg_rating=Avg('puntuaciones__puntuacion'),
        num_ratings=Count('puntuaciones')
    ).order_by('-avg_rating')[:8]
    
    # Libros sugeridos (populares/general)
    libros_sugeridos = Libro.objects.filter(
        activo=True
    ).annotate(
        avg_rating=Avg('puntuaciones__puntuacion'),
        num_ratings=Count('puntuaciones')
    ).exclude(
        id__in=[libro.id for libro in libros_recomendados]
    ).order_by('-avg_rating')[:12]
    
    context = {
        'libros_recomendados': libros_recomendados,
        'libros_sugeridos': libros_sugeridos,
    }
    return render(request, 'sril/recomendaciones.html', context)

@login_required
def descargar_libro(request, libro_id):
    """Vista para descargar un libro PDF"""
    libro = get_object_or_404(Libro, id=libro_id, activo=True)
    
    # Verificar permisos
    if not libro.puede_descargar(request.user):
        messages.error(request, 'No tienes permisos para descargar este libro o no está disponible.')
        return redirect('sril:detalle_libro', libro_id=libro.id)
    
    if not libro.archivo_pdf:
        messages.error(request, 'Este libro no tiene archivo disponible para descarga.')
        return redirect('sril:detalle_libro', libro_id=libro.id)
    
    try:
        # Crear nombre de archivo amigable
        titulo_slug = slugify(libro.titulo)
        autor_slug = slugify(libro.autor)
        nombre_archivo = f"{titulo_slug}_{autor_slug}.pdf"
        
        # Registrar descarga en el historial
        usuario_actual = get_usuario_actual(request)
        historial, created = HistorialLectura.objects.get_or_create(
            usuario=usuario_actual,
            libro=libro,
            defaults={'estado': 'LEYENDO'}
        )
        
        # Servir el archivo con nombre personalizado
        response = FileResponse(
            libro.archivo_pdf.open(),
            as_attachment=True,
            filename=nombre_archivo
        )
        
        # Agregar headers para mejor experiencia de descarga
        response['Content-Type'] = 'application/pdf'
        response['Content-Length'] = libro.archivo_pdf.size
        
        # Estadísticas de descarga (podrías agregar un campo para esto después)
        messages.success(request, f'✅ Libro "{libro.titulo}" descargado exitosamente!')
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error al descargar el libro: {str(e)}')
        return redirect('sril:detalle_libro', libro_id=libro.id)

@login_required
def ver_libro(request, libro_id):
    """Vista para ver un libro PDF en el navegador"""
    libro = get_object_or_404(Libro, id=libro_id, activo=True)
    
    if not libro.puede_descargar(request.user):
        messages.error(request, 'No tienes permisos para ver este libro.')
        return redirect('sril:detalle_libro', libro_id=libro.id)
    
    if not libro.archivo_pdf:
        messages.error(request, 'Este libro no tiene archivo disponible.')
        return redirect('sril:detalle_libro', libro_id=libro.id)
    
    try:
        # Registrar visualización
        usuario_actual = get_usuario_actual(request)
        historial, created = HistorialLectura.objects.get_or_create(
            usuario=usuario_actual,
            libro=libro,
            defaults={'estado': 'LEYENDO'}
        )
        
        # Servir el archivo para visualización en el navegador
        response = FileResponse(
            libro.archivo_pdf.open(),
            content_type='application/pdf'
        )
        
        # Configurar para visualización en línea
        response['Content-Disposition'] = f'inline; filename="{libro.nombre_archivo}"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error al abrir el libro: {str(e)}')
        return redirect('sril:detalle_libro', libro_id=libro.id)

@login_required
def info_descarga(request, libro_id):
    """Vista con información detallada de descarga"""
    libro = get_object_or_404(Libro, id=libro_id, activo=True)
    
    context = {
        'libro': libro,
        'puede_descargar': libro.puede_descargar(request.user),
    }
    
    return render(request, 'sril/libros/info_descarga.html', context)