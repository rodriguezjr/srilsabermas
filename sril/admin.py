from django.contrib import admin
from .admin_site import mi_biblioteca_admin
from .models import Usuario, Categoria, Libro, PreferenciaUsuario, Puntuacion, HistorialLectura, LibroCategoria
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm

admin.site.site_header = '📚 SaberMas'
admin.site.index_title = 'Panel de control'
admin.site.site_title = 'Panel de adminsitracion'


# Registrar todos los modelos con el admin site personalizado
class UsuarioAdmin(UserAdmin):
    list_display = ('email', 'nombre', 'fecha_registro', 'es_administrador', 'activo')
    list_filter = ('es_administrador', 'activo', 'fecha_registro')
    search_fields = ('email', 'nombre')
    ordering = ('email',)
    readonly_fields = ('fecha_registro', 'fecha_ultimo_login')
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Información Personal', {'fields': ('nombre',)}),
        ('Permisos', {'fields': ('es_administrador', 'activo')}),
        ('Fechas importantes', {'fields': ('fecha_ultimo_login', 'fecha_registro')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nombre', 'password1', 'password2', 'es_administrador', 'activo')}
        ),
    )
    change_password_form = AdminPasswordChangeForm

class LibroCategoriaInline(admin.TabularInline):
    model = LibroCategoria
    extra = 1

class LibroAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'autor', 'numero_paginas', 'disponible_descarga', 'tiene_archivo', 'tiene_portada', 'activo')
    list_filter = ('activo', 'disponible_descarga', 'categorias', 'fecha_publicacion')
    search_fields = ('titulo', 'autor', 'isbn')
    inlines = [LibroCategoriaInline]
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion', 'info_archivo', 'vista_previa_portada')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('titulo', 'autor', 'isbn', 'sinopsis')
        }),
        ('Archivos', {
            'fields': ('archivo_pdf', 'disponible_descarga', 'portada', 'vista_previa_portada', 'info_archivo')
        }),
        ('Detalles', {
            'fields': ('fecha_publicacion', 'editorial')
        }),
        ('Metadata', {
            'fields': ('activo', 'fecha_creacion', 'fecha_actualizacion')
        }),
    )
    
    actions = ['regenerar_portadas', 'activar_descargas', 'desactivar_descargas']
    
    def tiene_archivo(self, obj):
        return "✅" if obj.archivo_pdf else "❌"
    tiene_archivo.short_description = 'PDF'
    
    def tiene_portada(self, obj):
        return "✅" if obj.portada else "❌"
    tiene_portada.short_description = 'Portada'
    
    def info_archivo(self, obj):
        """Información del archivo PDF"""
        if obj.archivo_pdf:
            try:
                import os
                tamaño_mb = round(obj.archivo_pdf.size / (1024 * 1024), 2)
                nombre = os.path.basename(obj.archivo_pdf.name)
                return f" {nombre} - {tamaño_mb} MB"
            except:
                return "📄 Archivo disponible"
        return "❌ Sin archivo"
    info_archivo.short_description = 'Información del archivo'
    info_archivo.allow_tags = True
    
    def vista_previa_portada(self, obj):
        if obj.portada:
            try:
                # Usar la URL correcta para el admin
                from django.conf import settings
                portada_url = obj.portada.url
                
                return format_html(
                    '''
                    <div style="text-align: center; border: 2px solid #ddd; padding: 10px; border-radius: 8px; background: #f8f9fa;">
                        <img src="{}" 
                             style="max-width: 200px; max-height: 300px; object-fit: contain;" 
                             onerror="this.style.display='none'" />
                        <div style="margin-top: 10px;">
                            <small style="color: #666;">{}<br>Tamaño: {} KB</small>
                        </div>
                    </div>
                    ''',
                    portada_url,
                    obj.portada.name,
                    obj.portada.size // 1024 if obj.portada.size else 0
                )
            except Exception as e:
                return format_html(
                    '<div style="color: #dc3545; padding: 10px; border: 1px solid #dc3545; border-radius: 4px;">'
                    'Error cargando imagen: {}'
                    '</div>',
                    str(e)
                )
        else:
            return format_html(
                '''
                <div style="text-align: center; padding: 40px; background: #f8f9fa; border: 2px dashed #dee2e6; border-radius: 8px;">
                    <div style="font-size: 48px; color: #6c757d;">📚</div>
                    <div style="color: #6c757d; margin-top: 16px;">
                        <strong>Portada no generada</strong><br>
                        <small>Se creará automáticamente al guardar con un PDF</small>
                    </div>
                </div>
                '''
            )
    vista_previa_portada.short_description = 'Vista Previa de Portada'
    
    def regenerar_portadas(self, request, queryset):
        """Acción para regenerar portadas de libros seleccionados"""
        count = 0
        for libro in queryset:
            if libro.archivo_pdf:
                try:
                    # Lógica simple de regeneración - eliminar portada existente
                    if libro.portada:
                        libro.portada.delete(save=False)
                    # La portada se regenerará automáticamente al guardar
                    libro.save()
                    count += 1
                    self.message_user(request, f"Portada regenerada para: {libro.titulo}")
                except Exception as e:
                    self.message_user(request, f"Error con {libro.titulo}: {str(e)}", level='ERROR')
            else:
                self.message_user(request, f"{libro.titulo} no tiene PDF", level='WARNING')
        
        self.message_user(request, f"Procesadas {count} portadas")
    
    regenerar_portadas.short_description = " Regenerar portadas desde PDF"
    
    def activar_descargas(self, request, queryset):
        """Activar descargas para libros seleccionados"""
        updated = queryset.update(disponible_descarga=True)
        self.message_user(request, f" Activadas descargas para {updated} libros")
    
    activar_descargas.short_description = " Activar descargas"
    
    def desactivar_descargas(self, request, queryset):
        """Desactivar descargas para libros seleccionados"""
        updated = queryset.update(disponible_descarga=False)
        self.message_user(request, f" Desactivadas descargas para {updated} libros")
    
    desactivar_descargas.short_description = " Desactivar descargas"
    
    def save_model(self, request, obj, form, change):
        """Manejar el guardado del modelo"""
        # Guardar primero el objeto
        super().save_model(request, obj, form, change)
        
        # Generar portada si hay PDF pero no portada
        if obj.archivo_pdf and not obj.portada:
            self.message_user(request, "Generando portada desde PDF...")
            try:
                obj.generar_portada_desde_pdf()
                obj.save()
                self.message_user(request, "Portada generada exitosamente")
            except Exception as e:
                self.message_user(request, f"Error generando portada: {str(e)}", level='ERROR')

class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'total_libros', 'descripcion_corta')
    search_fields = ('nombre', 'descripcion')
    
    def total_libros(self, obj):
        return obj.librocategoria_set.count()
    total_libros.short_description = 'Libros'
    
    def descripcion_corta(self, obj):
        return obj.descripcion[:50] + "..." if obj.descripcion and len(obj.descripcion) > 50 else obj.descripcion
    descripcion_corta.short_description = 'Descripción'

class PuntuacionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'libro', 'puntuacion', 'fecha_puntuacion')
    list_filter = ('puntuacion', 'fecha_puntuacion')
    search_fields = ('usuario__nombre', 'libro__titulo')

class PreferenciaUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'categoria', 'nivel_interes', 'fecha_actualizacion')
    list_filter = ('nivel_interes', 'categoria')
    search_fields = ('usuario__nombre', 'categoria__nombre')

class HistorialLecturaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'libro', 'estado', 'porcentaje_lectura', 'fecha_inicio')
    list_filter = ('estado', 'fecha_inicio')
    search_fields = ('usuario__nombre', 'libro__titulo')
    
    def porcentaje_lectura(self, obj):
        return f"{obj.porcentaje_lectura():.1f}%"
    porcentaje_lectura.short_description = 'Progreso'

# Registrar modelos con el admin site personalizado
mi_biblioteca_admin.register(Usuario, UsuarioAdmin)
mi_biblioteca_admin.register(Libro, LibroAdmin)
mi_biblioteca_admin.register(Categoria, CategoriaAdmin)
mi_biblioteca_admin.register(Puntuacion, PuntuacionAdmin)
mi_biblioteca_admin.register(PreferenciaUsuario, PreferenciaUsuarioAdmin)
mi_biblioteca_admin.register(HistorialLectura, HistorialLecturaAdmin)