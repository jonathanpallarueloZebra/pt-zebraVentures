"""¿Regenerar tras cambiar un turno cambia REALMENTE el resultado?

Genera una tienda, cuenta las celdas vacias, cambia el turno de una persona,
vuelve a generar y compara. Sirve para saber si la regeneracion automatica
aporta algo o es humo.

No escribe nada: todo va dentro de una transaccion con rollback.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.dynamic_fields.models import EntityField, EntityType
from apps.planning.models import WeeklyPlan
from apps.planning.schedule_generator import (
    _worker_matches_scope, generate_schedule,
)
from apps.workers.models import Worker


def _vacias(plan, shift_codes):
    """Celdas de turno sin nadie asignado."""
    n = 0
    for day in plan:
        for code in shift_codes:
            entries = day.get(code) or []
            if not any(int((e or {}).get('workerId', 0) or 0) > 0 for e in entries):
                n += 1
    return n


def _asignaciones(plan, shift_codes):
    n = 0
    for day in plan:
        for code in shift_codes:
            for e in (day.get(code) or []):
                if int((e or {}).get('workerId', 0) or 0) > 0:
                    n += 1
    return n


class Command(BaseCommand):
    help = 'Mide el efecto de regenerar tras cambiar el turno de una ficha.'

    def add_arguments(self, parser):
        parser.add_argument('--scope', type=int, default=0)
        parser.add_argument('--start', type=str, default='')

    def handle(self, *args, **opts):
        from apps.planning.schedule_generator import _get_shift_slots

        plan_ref = WeeklyPlan.objects.filter(scope_entity_id__gt=0).order_by('-start_date').first()
        scope_id = opts['scope'] or (plan_ref.scope_entity_id if plan_ref else 0)
        start = opts['start'] or (plan_ref.start_date.strftime('%Y-%m-%d') if plan_ref else '')
        if not scope_id or not start:
            self.stdout.write('sin datos para probar')
            return

        codes = [s['code'] for s in _get_shift_slots()]
        self.stdout.write(f'tienda={scope_id} semana={start}\n')

        from datetime import datetime
        start_d = datetime.strptime(start, '%Y-%m-%d').date()
        r1 = generate_schedule(start_d, scope_entity_id=scope_id)
        p1 = r1['plan']
        v1, a1 = _vacias(p1, codes), _asignaciones(p1, codes)
        self.stdout.write(f'1) generacion inicial: {a1} asignaciones, {v1} celdas vacias')

        # Alguien de esa tienda con turno_base y turno_alternativo distintos.
        scope_et = EntityType.objects.filter(is_planning_scope=True).first()
        lf = EntityField.objects.filter(
            entity_type='worker',
            target_entity=scope_et.slug if scope_et else '',
            field_type__in=['entity_select', 'multi_entity_select'],
        ).first()
        # Se prueba con TODOS los candidatos de la tienda (base != alternativo) y
        # se queda el que mas mejora: buscar "un" trabajador al azar no dice si la
        # regeneracion sirve, solo si sirvio con ese.
        candidatos = []
        for w in Worker.objects.filter(active=True):
            cd = w.custom_data or {}
            if not _worker_matches_scope(cd, lf.key, scope_id):
                continue
            if cd.get('turno_base') and cd.get('turno_alternativo') \
                    and cd['turno_base'] != cd['turno_alternativo']:
                candidatos.append(w)
        if not candidatos:
            self.stdout.write('nadie con base != alternativo: no se puede probar el swap')
            return
        self.stdout.write(f'   ({len(candidatos)} candidatos con base != alternativo)')
        victima = candidatos[0]

        self.stdout.write('\n2) probando el swap base<->alt de cada candidato:')
        resultados = []
        for w in candidatos:
            cd0 = dict(w.custom_data or {})
            base, alt = cd0['turno_base'], cd0['turno_alternativo']
            try:
                with transaction.atomic():
                    cd = dict(cd0)
                    cd['turno_base'], cd['turno_alternativo'] = alt, base
                    w.custom_data = cd
                    w.save()

                    r2 = generate_schedule(start_d, scope_entity_id=scope_id)
                    v2 = _vacias(r2['plan'], codes)
                    a2 = _asignaciones(r2['plan'], codes)
                    resultados.append((v2 - v1, a2 - a1, w.name))
                    raise RuntimeError('rollback')
            except RuntimeError:
                pass
            w.refresh_from_db()
            assert (w.custom_data or {}).get('turno_base') == base, \
                f'la ficha de {w.name} NO se revirtio'

        resultados.sort()
        for dv, da, nombre in resultados:
            signo = 'MEJORA ' if dv < 0 else ('igual  ' if dv == 0 else 'empeora')
            self.stdout.write(f'   {signo} vacias {dv:+3d}  asign {da:+4d}  {nombre[:34]}')

        mejores = [r for r in resultados if r[0] < 0]
        self.stdout.write(
            f'\n=> {len(mejores)} de {len(resultados)} swaps reducen celdas vacias'
        )
        if mejores:
            dv, da, nombre = mejores[0]
            self.stdout.write(f'   el mejor: {nombre} ({dv:+d} vacias)')
        self.stdout.write('\nfichas revertidas (nada quedo escrito)')
