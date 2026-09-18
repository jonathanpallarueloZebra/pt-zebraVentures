"""¿Se esta usando a todos los trabajadores? ¿Por que quedan celdas vacias?

Responde dos preguntas con datos, sin tocar nada (solo lectura):

  1. Cuantos trabajadores activos NO entran en ninguna planificacion, y por que.
  2. Cuantas de las celdas vacias son REALES (turno que ese dia opera y una
     seccion que ese dia abre) y cuantas son ruido de contar turno x dia x
     seccion a lo bruto.

Uso:
    python manage.py diagnostico_cobertura
    python manage.py diagnostico_cobertura --start 2026-08-10
"""
import datetime
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand

from apps.dynamic_fields.models import EntityRecord, EntityType
from apps.planning.schedule_generator import (
    _field_values, _get_shift_slots, _norm_weekday, _thread_local,
    generate_schedule,
)
from apps.workers.models import Worker


def _limpiar():
    from apps.restrictions.engine import _cache
    if hasattr(_thread_local, 'gen_cache'):
        _thread_local.gen_cache = {}
    _cache.clear()


class Command(BaseCommand):
    help = 'Diagnostico: trabajadores sin usar y celdas vacias reales.'

    def add_arguments(self, parser):
        parser.add_argument('--start', type=str, default='2026-08-03')

    def handle(self, *args, **opts):
        start_d = datetime.datetime.strptime(opts['start'], '%Y-%m-%d').date()
        scopes = list(range(54, 69))
        slots = _get_shift_slots()
        codes = [s['code'] for s in slots]
        labels = {s['code']: s['label'] for s in slots}

        areas_map = {r.id: str((r.data or {}).get('nombre') or '')
                     for r in EntityRecord.objects.all()}
        et = EntityType.objects.filter(show_in_schedule=True).first()
        secciones = [str((r.data or {}).get('nombre') or '')
                     for r in EntityRecord.objects.filter(entity_type=et)
                     if (r.data or {}).get('nombre')]

        _limpiar()
        planes = {}
        for s in scopes:
            planes[s] = generate_schedule(start_d, scope_entity_id=s)['plan']

        # ── 1. Trabajadores usados ──────────────────────────────────────
        usados = set()
        turnos_por_worker = Counter()
        for plan in planes.values():
            for day in plan:
                for c in codes:
                    for e in (day.get(c) or []):
                        wid = int((e or {}).get('workerId', 0) or 0)
                        if wid > 0:
                            usados.add(wid)
                            turnos_por_worker[wid] += 1

        activos = list(Worker.objects.filter(active=True))
        sin_usar = [w for w in activos if w.id not in usados]

        self.stdout.write('=' * 74)
        self.stdout.write(f'COBERTURA DE PLANTILLA  ({opts["start"]}, {len(scopes)} tiendas)')
        self.stdout.write('=' * 74)
        self.stdout.write(f'activos: {len(activos)} | usados: {len(usados)} '
                          f'| SIN USAR: {len(sin_usar)}')

        # Por que no se usan
        motivos = Counter()
        detalle = defaultdict(list)
        for w in sin_usar:
            cd = w.custom_data or {}
            if not cd:
                m = 'ficha vacia (sin datos)'
            elif not cd.get('secciones'):
                m = 'sin seccion asignada'
            elif not cd.get('turno_base'):
                m = 'sin turno base'
            elif not cd.get('tienda') and not cd.get('zona'):
                m = 'sin tienda NI zona (no es elegible en ningun sitio)'
            else:
                libres = {_norm_weekday(v) for v in _field_values(cd.get('dias_libres'))}
                libres.discard(None)
                m = ('libra toda la semana' if len(libres) >= 6
                     else 'elegible pero no le toco plaza')
            motivos[m] += 1
            detalle[m].append(w.name[:30])

        if sin_usar:
            self.stdout.write('')
            self.stdout.write('Por que no se usan:')
            for m, n in motivos.most_common():
                self.stdout.write(f'   {n:>3}  {m}')
                for nom in detalle[m][:4]:
                    self.stdout.write(f'         - {nom}')
                if len(detalle[m]) > 4:
                    self.stdout.write(f'         ... +{len(detalle[m]) - 4}')

        # Reparto de carga
        if turnos_por_worker:
            vals = sorted(turnos_por_worker.values())
            self.stdout.write('')
            self.stdout.write(f'Turnos por persona: min {vals[0]} · '
                              f'mediana {vals[len(vals) // 2]} · max {vals[-1]}')

        # ── 2. Celdas vacias: cuales son REALES ─────────────────────────
        # Un turno "opera" un dia si alguna tienda tiene gente ahi ese dia.
        opera = defaultdict(set)
        for plan in planes.values():
            for day in plan:
                f = day.get('date')
                for c in codes:
                    if any(int((e or {}).get('workerId', 0) or 0) > 0
                           for e in (day.get(c) or [])):
                        opera[f].add(c)

        # Una seccion "abre" un dia si alguna tienda la tiene cubierta ese dia.
        abre = defaultdict(set)
        for plan in planes.values():
            for day in plan:
                f = day.get('date')
                for c in codes:
                    for e in (day.get(c) or []):
                        if int((e or {}).get('workerId', 0) or 0) > 0:
                            for a in (e.get('areas') or []):
                                abre[f].add(str(a))

        bruto = reales = por_turno_cerrado = por_seccion_cerrada = 0
        huecos = Counter()
        for s, plan in planes.items():
            for day in plan:
                f = day.get('date')
                for c in codes:
                    cubiertas = {str(a)
                                 for e in (day.get(c) or [])
                                 if int((e or {}).get('workerId', 0) or 0) > 0
                                 for a in (e.get('areas') or [])}
                    for sec in secciones:
                        if sec in cubiertas:
                            continue
                        bruto += 1
                        if c not in opera.get(f, set()):
                            por_turno_cerrado += 1
                        elif sec not in abre.get(f, set()):
                            por_seccion_cerrada += 1
                        else:
                            reales += 1
                            huecos[f'{labels.get(c, c)} · {sec}'] += 1

        self.stdout.write('')
        self.stdout.write('=' * 74)
        self.stdout.write('CELDAS VACIAS')
        self.stdout.write('=' * 74)
        self.stdout.write(f'contando turno x dia x seccion a lo bruto : {bruto}')
        self.stdout.write(f'  - el turno no opera ese dia             : {por_turno_cerrado}')
        self.stdout.write(f'  - la seccion no abre ese dia            : {por_seccion_cerrada}')
        self.stdout.write(f'  = HUECOS REALES                         : {reales}')
        if huecos:
            self.stdout.write('')
            self.stdout.write('Los huecos reales, agrupados:')
            for k, n in huecos.most_common(12):
                self.stdout.write(f'   x{n:<4} {k}')
