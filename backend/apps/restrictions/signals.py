"""Invalidación de la caché del engine de validación.

El engine (engine.py) mantiene en memoria una caché de datos base (trabajadores,
áreas, campos, preferencias, turnos, catálogos, días cerrados). Antes se vaciaba
al inicio de cada validación, lo que hacía cada validación lenta (recargaba toda
la BD por cada movimiento del planificador). Ahora la caché persiste entre
validaciones y solo se invalida cuando cambian los modelos de los que depende.

Estas señales cubren las escrituras vía ORM (admin, DRF, management commands).
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from . import engine
from .models import Restriction


def _invalidate(*args, **kwargs):
    engine.invalidate_cache()


def register_cache_invalidation():
    """Conecta las señales. Se llama desde AppConfig.ready().

    Importamos los modelos aquí (no a nivel de módulo) para no romper el arranque
    si el registro de apps aún no está listo cuando se importa este módulo.
    """
    from apps.workers.models import Worker, WorkerPreference
    from apps.dynamic_fields.models import EntityType, EntityRecord
    from apps.shifts.models import Shift
    from apps.shift_days.models import ShiftDay
    from apps.planning.models import ClosedDay

    models = [
        Worker, WorkerPreference,
        EntityType, EntityRecord,
        Shift, ShiftDay,
        ClosedDay,
        Restriction,
    ]
    for model in models:
        # dispatch_uid evita conexiones duplicadas si ready() se llama dos veces.
        uid = f'restrictions_cache_invalidate_{model.__name__}'
        post_save.connect(_invalidate, sender=model, dispatch_uid=f'{uid}_save', weak=False)
        post_delete.connect(_invalidate, sender=model, dispatch_uid=f'{uid}_del', weak=False)
