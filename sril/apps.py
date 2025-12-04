from django.apps import AppConfig

class SrilConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sril'
    verbose_name = 'Sistema de Recomendación de Libros'
    
    def ready(self):
        import sril.signals  # Importar las señales