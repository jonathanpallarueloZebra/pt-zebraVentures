"""Comprueba la deteccion de plan desactualizado (_stale_info).

Solo lectura salvo --touch-scope, que simula la edicion de una ficha (guarda un
trabajador sin cambiar sus datos, solo para mover updated_at). Sirve para probar
que el aviso salta en SU tienda y no en las demas.
"""
from django.core.management.base import BaseCommand

from apps.planning.models import WeeklyPlan
from apps.planning.serializers import _stale_info
from apps.workers.models import Worker


class Command(BaseCommand):
    help = 'Muestra si los planes guardados estan desactualizados respecto a las fichas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--touch-scope', type=int, default=0,
            help='Toca updated_at de un trabajador de esta tienda (prueba).',
        )

    def handle(self, *args, **opts):
        scope = opts['touch_scope']
        if scope:
            self._touch(scope)

        total = WeeklyPlan.objects.count()
        con_scope = WeeklyPlan.objects.filter(scope_entity_id__gt=0).count()
        self.stdout.write(
            f'planes={total} con-scope={con_scope} workers={Worker.objects.count()}'
        )
        qs = WeeklyPlan.objects.filter(scope_entity_id__gt=0).order_by('-start_date')[:8]
        if not qs:
            qs = WeeklyPlan.objects.order_by('-start_date')[:8]
        for p in qs:
            i = _stale_info(p)
            quien = ', '.join(i['stale_workers'][:3]) or '-'
            self.stdout.write(
                f"scope={p.scope_entity_id} {p.start_date} "
                f"upd={p.updated_at:%m-%d %H:%M} stale={i['stale']} quien={quien}"
            )

    def _touch(self, scope_id):
        from apps.dynamic_fields.models import EntityType, EntityField
        from apps.planning.schedule_generator import _worker_matches_scope

        scope_et = EntityType.objects.filter(is_planning_scope=True).first()
        lf = EntityField.objects.filter(
            entity_type='worker',
            target_entity=scope_et.slug if scope_et else '',
            field_type__in=['entity_select', 'multi_entity_select'],
        ).first()
        if not lf:
            self.stdout.write('sin campo de enlace: no se puede tocar')
            return
        for w in Worker.objects.all():
            if _worker_matches_scope(w.custom_data or {}, lf.key, scope_id):
                w.save(update_fields=['updated_at'])
                self.stdout.write(f'tocado: {w.name} (scope {scope_id})')
                return
        self.stdout.write(f'ningun trabajador en scope {scope_id}')
