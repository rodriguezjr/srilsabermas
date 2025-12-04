from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Libro

@receiver(post_save, sender=Libro)
def generar_portada_despues_de_guardar(sender, instance, created, **kwargs):
    """Generar portada después de guardar el libro"""
    if instance.archivo_pdf and (created or not instance.portada):
        print(f"🚀 Señal: Generando portada para {instance.titulo}")
        instance.generar_portada_desde_pdf()
        # Guardar solo si se generó la portada
        if instance.portada:
            instance.save()