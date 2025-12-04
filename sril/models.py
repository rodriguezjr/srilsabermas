import os
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from pdf2image import convert_from_path
from PIL import Image, ImageDraw, ImageFont
import tempfile
from io import BytesIO
from django.core.files.base import ContentFile

class UsuarioManager(BaseUserManager):
    def create_user(self, email, nombre, password=None, **extra_fields):
        if not email:
            raise ValueError('El usuario debe tener un email')
        email = self.normalize_email(email)
        user = self.model(email=email, nombre=nombre, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, nombre, password=None, **extra_fields):
        extra_fields.setdefault('es_administrador', True)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, nombre, password, **extra_fields)

class Usuario(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, max_length=150)
    nombre = models.CharField(max_length=100)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_ultimo_login = models.DateTimeField(auto_now=True)
    es_administrador = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    # Agregar related_name personalizado para evitar conflictos
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='usuario_set',  # Cambiado para evitar conflicto
        related_query_name='usuario',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='usuario_set',  # Cambiado para evitar conflicto
        related_query_name='usuario',
    )
    
    objects = UsuarioManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nombre']
    
    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
    
    def __str__(self):
        return f"{self.nombre} ({self.email})"
    
    def has_perm(self, perm, obj=None):
        return self.es_administrador
    
    def has_module_perms(self, app_label):
        return self.es_administrador

class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
    
    def __str__(self):
        return self.nombre

class Libro(models.Model):
    # Campos básicos
    titulo = models.CharField(max_length=255, verbose_name="Título")
    autor = models.CharField(max_length=255, verbose_name="Autor")
    isbn = models.CharField(
        max_length=20, 
        unique=True, 
        blank=True, 
        null=True,
        verbose_name="ISBN"
    )
    sinopsis = models.TextField(blank=True, null=True, verbose_name="Sinopsis")
    numero_paginas = models.PositiveIntegerField(
        default=0,
        verbose_name="Número de páginas"
    )
    tiempo_lectura_promedio = models.PositiveIntegerField(
        default=0,
        help_text="Tiempo promedio de lectura en minutos",
        verbose_name="Tiempo de lectura"
    )
    fecha_publicacion = models.DateField(
        blank=True, 
        null=True,
        verbose_name="Fecha de publicación"
    )
    editorial = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        verbose_name="Editorial"
    )
    
    # Campos para archivos
    archivo_pdf = models.FileField(
        upload_to='libros/pdfs/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        help_text="Subir archivo PDF del libro",
        verbose_name="Archivo PDF"
    )
    portada = models.ImageField(
        upload_to='libros/portadas/',
        blank=True,
        null=True,
        help_text="Portada generada automáticamente desde el PDF",
        verbose_name="Portada"
    )
    disponible_descarga = models.BooleanField(
        default=False,
        help_text="¿Está disponible para descarga?",
        verbose_name="Disponible para descarga"
    )
    
    # Relaciones
    categorias = models.ManyToManyField(
        'Categoria', 
        through='LibroCategoria',
        verbose_name="Categorías"
    )
    
    # Metadata
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")
    
    class Meta:
        verbose_name = 'Libro'
        verbose_name_plural = 'Libros'
        ordering = ['titulo']
        indexes = [
            models.Index(fields=['titulo']),
            models.Index(fields=['autor']),
            models.Index(fields=['fecha_publicacion']),
        ]
    
    def __str__(self):
        return f"{self.titulo} - {self.autor}"
    
    def save(self, *args, **kwargs):
        """
        Sobrescribir save para extraer metadatos del PDF automáticamente
        """
        # Verificar si es un nuevo libro o el PDF cambió
        es_nuevo = not self.pk
        pdf_cambiado = False
        
        if not es_nuevo:
            try:
                libro_original = Libro.objects.get(pk=self.pk)
                pdf_cambiado = (libro_original.archivo_pdf != self.archivo_pdf)
            except Libro.DoesNotExist:
                pass
        
        # Guardar el objeto primero (necesario para tener self.id)
        super().save(*args, **kwargs)
        
        cambios_realizados = False
        
        # Extraer número de páginas si el PDF es nuevo o cambió
        if (es_nuevo or pdf_cambiado) and self.archivo_pdf:
            print(f"📄 Extrayendo metadatos para: {self.titulo}")
            if self.extraer_metadatos_pdf():
                cambios_realizados = True
        
        # Generar portada si es necesario
        if (pdf_cambiado or not self.portada) and self.archivo_pdf:
            print(f"🔄 Generando portada para: {self.titulo}")
            if self.generar_portada_desde_pdf():
                cambios_realizados = True
        
        # Guardar nuevamente si hubo cambios en los campos
        if cambios_realizados:
            update_fields = []
            if hasattr(self, '_numero_paginas_actualizado'):
                update_fields.append('numero_paginas')
            if hasattr(self, '_tiempo_lectura_actualizado'):
                update_fields.append('tiempo_lectura_promedio')
            if self.portada:
                update_fields.append('portada')
            
            if update_fields:
                super().save(update_fields=update_fields)
    
    def extraer_metadatos_pdf(self):
        """
        Extraer metadatos del PDF: número de páginas y calcular tiempo de lectura
        """
        try:
            if not self.archivo_pdf or not os.path.exists(self.archivo_pdf.path):
                return False
            
            # Extraer número de páginas
            num_paginas = self._extraer_numero_paginas()
            if num_paginas > 0:
                self.numero_paginas = num_paginas
                self._numero_paginas_actualizado = True
                print(f"   ✅ Páginas extraídas: {num_paginas}")
            else:
                print("   ⚠️ No se pudo extraer el número de páginas")
            
            # Calcular tiempo de lectura estimado
            tiempo_lectura = self._calcular_tiempo_lectura()
            if tiempo_lectura > 0:
                self.tiempo_lectura_promedio = tiempo_lectura
                self._tiempo_lectura_actualizado = True
                print(f"   ⏱️ Tiempo lectura calculado: {tiempo_lectura} min")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error extrayendo metadatos: {str(e)}")
            return False
    
    def _extraer_numero_paginas(self):
        """
        Extraer número de páginas usando múltiples métodos
        """
        # Intentar con PyPDF2 primero (más eficiente)
        paginas = self._extraer_paginas_pypdf2()
        if paginas > 0:
            return paginas
        
        # Intentar con pdfplumber (más preciso)
        paginas = self._extraer_paginas_pdfplumber()
        if paginas > 0:
            return paginas
        
        # Estimación por tamaño como último recurso
        paginas = self._estimar_paginas_por_tamaño()
        return paginas
    
    def _extraer_paginas_pypdf2(self):
        """Extraer páginas usando PyPDF2"""
        try:
            import PyPDF2
            
            with open(self.archivo_pdf.path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                return len(pdf_reader.pages)
                
        except ImportError:
            print("   📚 PyPDF2 no está instalado")
            return 0
        except Exception as e:
            print(f"   ❌ Error con PyPDF2: {str(e)}")
            return 0
    
    def _extraer_paginas_pdfplumber(self):
        """Extraer páginas usando pdfplumber"""
        try:
            import pdfplumber
            
            with pdfplumber.open(self.archivo_pdf.path) as pdf:
                return len(pdf.pages)
                
        except ImportError:
            print("   📚 pdfplumber no está instalado")
            return 0
        except Exception as e:
            print(f"   ❌ Error con pdfplumber: {str(e)}")
            return 0
    
    def _estimar_paginas_por_tamaño(self):
        """Estimar páginas basado en el tamaño del archivo"""
        try:
            if not self.archivo_pdf:
                return 0
            
            tamaño_bytes = self.archivo_pdf.size
            
            # Estimación más precisa basada en el tipo de contenido
            # PDFs con imágenes: ~100KB por página
            # PDFs de texto: ~50KB por página
            # Usamos una estimación conservadora de 75KB por página
            paginas_estimadas = max(1, round(tamaño_bytes / (75 * 1024)))
            
            print(f"   📏 Páginas estimadas por tamaño: {paginas_estimadas}")
            return paginas_estimadas
            
        except:
            return 1  # Mínimo 1 página
    
    def _calcular_tiempo_lectura(self):
        """
        Calcular tiempo de lectura estimado basado en número de páginas
        """
        if self.numero_paginas <= 0:
            return 0
        
        # Tiempo promedio de lectura por página (en minutos)
        # Basado en estudios de velocidad de lectura
        tiempo_por_pagina = 2.0  # 2 minutos por página en promedio
        
        tiempo_total = self.numero_paginas * tiempo_por_pagina
        
        # Ajustar para libros muy largos (la gente lee más lento en libros largos)
        if self.numero_paginas > 500:
            tiempo_total *= 1.2  # 20% más de tiempo para libros muy largos
        elif self.numero_paginas < 50:
            tiempo_total *= 0.8  # 20% menos para libros cortos
        
        return max(5, round(tiempo_total))  # Mínimo 5 minutos
    
    def generar_portada_desde_pdf(self):
        """
        Generar portada desde PDF usando pdf2image o crear placeholder
        """
        # Primero intentar con pdf2image
        if self._generar_portada_con_pdf2image():
            return True
        
        # Si falla, crear placeholder
        return self._crear_portada_placeholder()
    
    def _generar_portada_con_pdf2image(self):
        """Intentar generar portada usando pdf2image"""
        try:
            from pdf2image import convert_from_path
            
            if not self.archivo_pdf or not os.path.exists(self.archivo_pdf.path):
                return False
            
            print(f"   📄 Procesando PDF: {self.archivo_pdf.path}")
            
            # Convertir primera página a imagen
            images = convert_from_path(
                self.archivo_pdf.path, 
                first_page=1, 
                last_page=1, 
                dpi=100,
                use_pdftocairo=True
            )
            
            if not images:
                return False
            
            portada_image = images[0]
            
            # Redimensionar a tamaño óptimo
            max_size = (400, 600)
            portada_image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Convertir a JPEG en memoria
            buffer = BytesIO()
            portada_image.save(buffer, format='JPEG', quality=85)
            buffer.seek(0)
            
            # Crear nombre de archivo
            nombre_base = os.path.splitext(os.path.basename(self.archivo_pdf.name))[0]
            portada_filename = f"portada_{self.id}_{nombre_base}.jpg"
            
            # Eliminar portada existente si la hay
            if self.portada:
                try:
                    self.portada.delete(save=False)
                except:
                    pass
            
            # Guardar nueva portada
            self.portada.save(portada_filename, ContentFile(buffer.read()), save=False)
            
            print(f"   ✅ Portada generada desde PDF")
            return True
            
        except ImportError:
            print("   📚 pdf2image no está instalado")
        except Exception as e:
            print(f"   ❌ Error con pdf2image: {str(e)}")
        
        return False
    
    def _crear_portada_placeholder(self):
        """Crear una portada placeholder elegante"""
        try:
            # Dimensiones de la portada
            width, height = 400, 600
            
            # Colores (azul profesional)
            background_color = (41, 128, 185)  # Azul
            title_color = (255, 255, 255)      # Blanco
            author_color = (236, 240, 241)     # Gris claro
            accent_color = (52, 152, 219)      # Azul claro
            
            # Crear imagen base
            image = Image.new('RGB', (width, height), background_color)
            draw = ImageDraw.Draw(image)
            
            # Intentar cargar fuentes
            title_font = self._obtener_fuente(24, True)
            author_font = self._obtener_fuente(16)
            info_font = self._obtener_fuente(12)
            
            # Dibujar elementos decorativos
            self._dibujar_elementos_decorativos(draw, width, height, accent_color)
            
            # Preparar texto del título (dividir en líneas)
            lineas_titulo = self._dividir_texto(self.titulo, 25)
            
            # Calcular posición vertical para centrar
            total_text_height = len(lineas_titulo) * 30 + 40
            y_start = (height - total_text_height) // 2
            
            # Dibujar título
            for i, linea in enumerate(lineas_titulo):
                bbox = draw.textbbox((0, 0), linea, font=title_font)
                text_width = bbox[2] - bbox[0]
                x = (width - text_width) // 2
                y = y_start + (i * 30)
                
                # Sombra del texto
                draw.text((x+1, y+1), linea, fill=(31, 97, 141), font=title_font)
                # Texto principal
                draw.text((x, y), linea, fill=title_color, font=title_font)
            
            # Dibujar autor
            autor_y = y_start + len(lineas_titulo) * 30 + 10
            autor_text = f"por {self.autor}"
            bbox = draw.textbbox((0, 0), autor_text, font=author_font)
            autor_width = bbox[2] - bbox[0]
            autor_x = (width - autor_width) // 2
            
            draw.text((autor_x, autor_y), autor_text, fill=author_color, font=author_font)
            
            # Pie de página informativo
            pie_text = "SaberMas - Sistema de Recomendación Inteligente de Lectura"
            bbox = draw.textbbox((0, 0), pie_text, font=info_font)
            pie_width = bbox[2] - bbox[0]
            pie_x = (width - pie_width) // 2
            pie_y = height - 30
            
            draw.text((pie_x, pie_y), pie_text, fill=author_color, font=info_font)
            
            # Guardar imagen
            buffer = BytesIO()
            image.save(buffer, format='JPEG', quality=90)
            buffer.seek(0)
            
            # Crear nombre de archivo
            portada_filename = f"portada_placeholder_{self.id}.jpg"
            
            # Eliminar portada existente si la hay
            if self.portada:
                try:
                    self.portada.delete(save=False)
                except:
                    pass
            
            # Guardar portada
            self.portada.save(portada_filename, ContentFile(buffer.read()), save=False)
            
            print(f"   ✅ Portada placeholder creada")
            return True
            
        except Exception as e:
            print(f"   ❌ Error creando placeholder: {str(e)}")
            return False
    
    def _obtener_fuente(self, size, bold=False):
        """Obtener la mejor fuente disponible"""
        try:
            if os.name == 'nt':  # Windows
                font_name = "arialbd.ttf" if bold else "arial.ttf"
                return ImageFont.truetype(font_name, size)
            else:  # Linux/Mac
                font_name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
                return ImageFont.truetype(font_name, size)
        except:
            # Fuente por defecto
            return ImageFont.load_default()
    
    def _dividir_texto(self, texto, max_caracteres):
        """Dividir texto en líneas que no excedan max_caracteres"""
        if not texto:
            return ["Sin título"]
            
        palabras = texto.split()
        lineas = []
        linea_actual = []
        
        for palabra in palabras:
            if len(' '.join(linea_actual + [palabra])) <= max_caracteres:
                linea_actual.append(palabra)
            else:
                if linea_actual:
                    lineas.append(' '.join(linea_actual))
                linea_actual = [palabra]
        
        if linea_actual:
            lineas.append(' '.join(linea_actual))
        
        return lineas if lineas else [texto[:max_caracteres] + "..."]
    
    def _dibujar_elementos_decorativos(self, draw, width, height, color):
        """Dibujar elementos decorativos en la portada"""
        # Línea decorativa superior
        draw.rectangle([0, 0, width, 10], fill=color)
        
        # Línea decorativa inferior
        draw.rectangle([0, height-10, width, height], fill=color)
        
        # Elementos de esquina
        corner_size = 50
        # Esquina superior izquierda
        draw.pieslice([-corner_size, -corner_size, corner_size, corner_size], 180, 270, fill=color)
        # Esquina superior derecha
        draw.pieslice([width-corner_size, -corner_size, width+corner_size, corner_size], 270, 360, fill=color)
    
    def regenerar_portada(self):
        """Regenerar la portada manualmente"""
        try:
            # Eliminar portada existente
            if self.portada:
                self.portada.delete(save=False)
            
            # Generar nueva portada
            return self.generar_portada_desde_pdf()
            
        except Exception as e:
            print(f"❌ Error regenerando portada: {str(e)}")
            return False
    
    def regenerar_metadatos(self):
        """Regenerar todos los metadatos del PDF"""
        try:
            if not self.archivo_pdf:
                return False
            
            print(f"🔄 Regenerando metadatos para: {self.titulo}")
            return self.extraer_metadatos_pdf()
            
        except Exception as e:
            print(f"❌ Error regenerando metadatos: {str(e)}")
            return False
    
    # Propiedades calculadas
    @property
    def rating_promedio(self):
        """Calcula el rating promedio del libro"""
        from django.db.models import Avg
        try:
            resultado = self.puntuaciones.aggregate(promedio=Avg('puntuacion'))
            promedio = resultado['promedio']
            return round(promedio, 2) if promedio else 0.0
        except:
            return 0.0
    
    @property
    def nombre_archivo(self):
        """Obtener el nombre del archivo sin la ruta"""
        if self.archivo_pdf:
            return os.path.basename(self.archivo_pdf.name)
        return None
    
    @property
    def tamaño_archivo(self):
        """Obtener el tamaño del archivo en MB"""
        if self.archivo_pdf and self.archivo_pdf.size:
            return round(self.archivo_pdf.size / (1024 * 1024), 2)
        return 0
    
    @property
    def tiempo_lectura_formateado(self):
        """Tiempo de lectura formateado para mostrar"""
        if self.tiempo_lectura_promedio <= 0:
            return "No disponible"
        
        horas = self.tiempo_lectura_promedio // 60
        minutos = self.tiempo_lectura_promedio % 60
        
        if horas > 0:
            return f"{horas}h {minutos}min"
        else:
            return f"{minutos} min"
    
    @property
    def tiene_contenido_digital(self):
        """Verificar si el libro tiene contenido digital"""
        return bool(self.archivo_pdf)
    
    @property
    def puede_visualizar(self):
        """Verificar si el libro puede ser visualizado"""
        return self.tiene_contenido_digital and self.disponible_descarga
    
    def puede_descargar(self, usuario):
        """Verificar si un usuario puede descargar el libro"""
        if not self.disponible_descarga or not self.archivo_pdf:
            return False
        return usuario.is_authenticated
    
    def obtener_estadisticas_descarga(self):
        """Obtener estadísticas de descarga (para futura implementación)"""
        return {
            'tiene_pdf': self.tiene_contenido_digital,
            'disponible': self.disponible_descarga,
            'tamaño_mb': self.tamaño_archivo,
            'paginas': self.numero_paginas,
            'tiempo_lectura': self.tiempo_lectura_formateado,
        }
    
    class Meta:
        verbose_name = 'Libro'
        verbose_name_plural = 'Libros'
        ordering = ['titulo']
        indexes = [
            models.Index(fields=['titulo']),
            models.Index(fields=['autor']),
            models.Index(fields=['fecha_publicacion']),
        ]

class LibroCategoria(models.Model):
    libro = models.ForeignKey(Libro, on_delete=models.CASCADE)
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    fecha_agregado = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'biblioteca_libro_categorias'
        unique_together = ['libro', 'categoria']
        verbose_name = 'Libro por Categoría'
        verbose_name_plural = 'Libros por Categoría'
    
    def __str__(self):
        return f"{self.libro.titulo} - {self.categoria.nombre}"

class PreferenciaUsuario(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='preferencias')
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    nivel_interes = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Nivel de interés de 1 (poco) a 5 (mucho)"
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['usuario', 'categoria']
        verbose_name = 'Preferencia de Usuario'
        verbose_name_plural = 'Preferencias de Usuarios'
    
    def __str__(self):
        return f"{self.usuario.nombre} - {self.categoria.nombre} ({self.nivel_interes})"

class Puntuacion(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='puntuaciones')
    libro = models.ForeignKey(Libro, on_delete=models.CASCADE, related_name='puntuaciones')
    puntuacion = models.DecimalField(
        max_digits=3, 
        decimal_places=2,
        validators=[MinValueValidator(1.0), MaxValueValidator(5.0)],
        help_text="Puntuación de 1.0 a 5.0"
    )
    comentario = models.TextField(blank=True, null=True)
    fecha_puntuacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['usuario', 'libro']
        verbose_name = 'Puntuación'
        verbose_name_plural = 'Puntuaciones'
    
    def __str__(self):
        return f"{self.usuario.nombre} - {self.libro.titulo}: {self.puntuacion}"

class HistorialLectura(models.Model):
    ESTADO_CHOICES = [
        ('POR_LEER', 'Por leer'),
        ('LEYENDO', 'Leyendo'),
        ('TERMINADO', 'Terminado'),
        ('ABANDONADO', 'Abandonado'),
    ]
    
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='historial_lectura')
    libro = models.ForeignKey(Libro, on_delete=models.CASCADE, related_name='historial_lectura')
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='POR_LEER')
    paginas_leidas = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ['usuario', 'libro']
        verbose_name = 'Historial de Lectura'
        verbose_name_plural = 'Historiales de Lectura'
    
    def __str__(self):
        return f"{self.usuario.nombre} - {self.libro.titulo} ({self.estado})"
    
    def porcentaje_lectura(self):
        """Calcula el porcentaje de lectura basado en páginas leídas"""
        if self.libro.numero_paginas > 0:
            return (self.paginas_leidas / self.libro.numero_paginas) * 100
        return 0