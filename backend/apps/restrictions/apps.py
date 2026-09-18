
from django.apps import AppConfig


class RestrictionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.restrictions'
    verbose_name = 'Restrictions'

    def ready(self):
        # Conecta las señales que invalidan la caché del engine de validación
        # cuando cambian los datos base (trabajadores, áreas, turnos, etc.).
        from .signals import register_cache_invalidation
        register_cache_invalidation()
