# sril/urls.py
from django.urls import path
from . import views
from .views import CustomLoginView

app_name = 'sril'

urlpatterns = [
    path('', views.home, name='home'),
    path('libros/', views.lista_libros, name='lista_libros'),
    path('libros/<int:libro_id>/', views.detalle_libro, name='detalle_libro'),
    path('libros/<int:libro_id>/puntuar/', views.puntuar_libro, name='puntuar_libro'),
    path('libros/<int:libro_id>/historial/', views.gestionar_historial, name='gestionar_historial'),
    path('libros/<int:libro_id>/descargar/', views.descargar_libro, name='descargar_libro'),
    path('libros/<int:libro_id>/ver/', views.ver_libro, name='ver_libro'),
    path('libros/<int:libro_id>/info-descarga/', views.info_descarga, name='info_descarga'),
    path('mis-preferencias/', views.mis_preferencias, name='mis_preferencias'),
    path('recomendaciones/', views.recomendaciones, name='recomendaciones'),
    
    # URLs de autenticación
    path('login/', CustomLoginView.as_view(), name='login'),
    path('registro/', views.registro_view, name='registro'),
    path('logout/', views.logout_view, name='logout'),
]