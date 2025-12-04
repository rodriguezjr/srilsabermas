from django.contrib import admin
from django.db.models import Avg, Count
from django.urls import path
from django.shortcuts import render
from django.http import HttpResponseRedirect
from .models import Usuario, Libro, Puntuacion, Categoria, PreferenciaUsuario, HistorialLectura

class MiBibliotecaAdminSite(admin.AdminSite):
    site_header = "Administración de SaberMas"
    site_title = "SaberMas Admin"
    index_title = "Panel de Control - Estadísticas del Sistema"
    
    def get_urls(self):
        urls = super().get_urls()
        # Hacer que la página principal sea estadísticas
        custom_urls = [
            path('', self.admin_view(self.estadisticas_view), name='index'),
            path('estadisticas/', self.admin_view(self.estadisticas_view), name='estadisticas'),
            path('admin-original/', self.admin_view(self.original_index_view), name='admin_original'),
        ]
        return custom_urls + urls
    
    def estadisticas_view(self, request):
        """Vista de estadísticas - ahora es la página principal"""
        # Calcular estadísticas principales
        total_usuarios = Usuario.objects.count()
        total_libros = Libro.objects.count()
        
        # Promedio de todas las puntuaciones
        promedio_puntuaciones = Puntuacion.objects.aggregate(
            avg_puntuacion=Avg('puntuacion')
        )['avg_puntuacion'] or 0
        
        # Libros sin puntuación
        libros_sin_puntuacion = Libro.objects.annotate(
            num_puntuaciones=Count('puntuaciones')
        ).filter(num_puntuaciones=0).count()
        
        # Libros mejor puntuados (top 10)
        libros_mejor_puntuados = Libro.objects.annotate(
            avg_rating=Avg('puntuaciones__puntuacion'),
            num_ratings=Count('puntuaciones')
        ).filter(num_ratings__gte=1).order_by('-avg_rating')[:10]
        
        # Usuarios más activos (más puntuaciones)
        usuarios_activos = Usuario.objects.annotate(
            num_puntuaciones=Count('puntuaciones')
        ).order_by('-num_puntuaciones')[:10]
        
        # Categorías más populares
        categorias_populares = Categoria.objects.annotate(
            num_libros=Count('librocategoria'),
            num_preferencias=Count('preferenciausuario')
        ).order_by('-num_preferencias', '-num_libros')[:10]
        
        # Estadísticas de lectura
        libros_leyendo = HistorialLectura.objects.filter(estado='LEYENDO').count()
        libros_terminados = HistorialLectura.objects.filter(estado='TERMINADO').count()
        
        context = {
            # Estadísticas principales
            'total_usuarios': total_usuarios,
            'total_libros': total_libros,
            'promedio_puntuaciones': promedio_puntuaciones,
            'libros_sin_puntuacion': libros_sin_puntuacion,
            
            # Listas detalladas
            'libros_mejor_puntuados': libros_mejor_puntuados,
            'usuarios_activos': usuarios_activos,
            'categorias_populares': categorias_populares,
            
            # Estadísticas de lectura
            'libros_leyendo': libros_leyendo,
            'libros_terminados': libros_terminados,
            
            **self.each_context(request),
            'title': 'Estadísticas del Sistema',
            'is_estadisticas': True,
        }
        
        return render(request, 'admin/estadisticas_index.html', context)
    
    def original_index_view(self, request):
        """Vista original del admin (accesible desde /admin/admin-original/)"""
        return super().index(request)

# Crear instancia del admin site personalizado
mi_biblioteca_admin = MiBibliotecaAdminSite(name='mi_biblioteca_admin')