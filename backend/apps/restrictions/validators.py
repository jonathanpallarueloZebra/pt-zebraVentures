"""
Plan validation entry point.

Delegates all evaluation to the engine module which interprets
restriction configurations stored in the database.
"""
from .models import Restriction
from . import engine


def validate_plan(plan_data, scope_record_id=None):
    """Validate plan data against active restrictions.

    If scope_record_id is given, only apply restrictions that are
    global (scope_records=[]) OR include this specific record ID.
    """
    # NO limpiamos la caché aquí. Antes se hacía engine.clear_cache() en cada
    # validación, forzando recargar toda la BD por movimiento (lento). Ahora la
    # caché persiste y se invalida por señales cuando cambian los datos base
    # (ver apps/restrictions/signals.py).
    restrictions = Restriction.objects.filter(active=True)
    violations = []
    for restriction in restrictions:
        scoped = restriction.scope_records or []
        if scope_record_id and scoped and scope_record_id not in scoped:
            continue
        violations.extend(engine.evaluate(restriction, plan_data, scope_record_id=scope_record_id))
    return violations
