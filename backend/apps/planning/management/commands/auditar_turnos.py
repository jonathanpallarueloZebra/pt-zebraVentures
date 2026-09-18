"""Audita la configuracion de TURNOS y que la planificacion la respete.

Comprueba, sobre datos reales:
  - coherencia de cada turno (horas, dias operativos, vigencia)
  - que el plan generado solo use turnos VIGENTES esa semana
  - que solo asigne en los DIAS OPERATIVOS de cada turno
  - que el turno de cada trabajador venga de su ficha (base/alternativo/sabado)
  - que las horas asignadas cuadren con el horario del turno o de la ficha

Solo lectura: genera en memoria, no guarda nada.

Uso:  python manage.py auditar_turnos
      python manage.py auditar_turnos --start 2026-12-21   (semana de campaña)
"""
import datetime
from collections import defaultdict

from django.core.management.base import BaseCommand

from apps.dynamic_fields.models import EntityRecord
from apps.planning.schedule_generator import (
    _get_shift_slots, _thread_local, generate_schedule,
)
from apps.shift_days.models import ShiftDay
from apps.shifts.models import Shift
from apps.workers.models import Worker

DIAS = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'DOM']


def _limpiar():
    from apps.restrictions.engine import _cache
    if hasattr(_thread_local, 'gen_cache'):
        _thread_local.gen_cache = {}
    _cache.clear()


def _horas(entry):
    try:
        h1, m1 = map(int, str(entry.get('start', '')).split(':')[:2])
        h2, m2 = map(int, str(entry.get('end', '')).split(':')[:2])
        return ((h2 * 60 + m2) - (h1 * 60 + m1)) / 60.0
    except Exception:
        return None


class Command(BaseCommand):
    help = 'Audita los turnos y que la planificacion los respete.'

    def add_arguments(self, parser):
        parser.add_argument('--start', type=str, default='2026-08-03')

    def handle(self, *args, **opts):
        start = datetime.datetime.strptime(opts['start'], '%Y-%m-%d').date()
        ok = fail = 0

        def check(nombre, incumple, ejemplos=()):
            nonlocal ok, fail
            if not incumple:
                ok += 1
                self.stdout.write(f'  OK    {nombre}')
            else:
                fail += 1
                self.stdout.write(self.style.ERROR(
                    f'  FALLO {nombre}: {incumple} casos'))
                for e in list(ejemplos)[:4]:
                    self.stdout.write(f'           {e}')

        turnos = list(Shift.objects.all().order_by('id'))
        dias_op = {}
        for s in turnos:
            d = sorted(ShiftDay.objects.filter(shift=s)
                       .values_list('weekday', flat=True))
            dias_op[str(s.id)] = set(d) if d else None   # None = todos

        # ── 1. Inventario ────────────────────────────────────────────────
        self.stdout.write(f'CONFIGURACION DE TURNOS — semana {opts["start"]}')
        self.stdout.write('=' * 74)
        for s in turnos:
            d = dias_op[str(s.id)]
            etq = ','.join(DIAS[x] for x in sorted(d)) if d else 'TODOS'
            vig = (f'{s.valid_from or "—"} a {s.valid_to or "—"}'
                   if (s.valid_from or s.valid_to) else 'siempre')
            activo = s.is_active_on(start) if hasattr(s, 'is_active_on') else True
            h = _horas({'start': str(s.start_time), 'end': str(s.end_time)})
            self.stdout.write(
                f'   {s.name[:26]:<28} {str(s.start_time)[:5]}-{str(s.end_time)[:5]} '
                f'({h:>5.2f} h) · {etq:<20} · {vig:<24} '
                f'{"VIGENTE" if activo else "no vigente"}')
        self.stdout.write('')

        # ── 2. Coherencia de la configuracion ────────────────────────────
        n = 0; ej = []
        for s in turnos:
            h = _horas({'start': str(s.start_time), 'end': str(s.end_time)})
            if h is None or h <= 0:
                n += 1
                ej.append(f'{s.name}: {s.start_time}-{s.end_time} -> {h} h')
        check('Todos los turnos tienen horario coherente (fin > inicio)', n, ej)

        n = 0; ej = []
        for s in turnos:
            if s.valid_from and s.valid_to and s.valid_from > s.valid_to:
                n += 1
                ej.append(f'{s.name}: {s.valid_from} > {s.valid_to}')
        check('Las vigencias no estan invertidas', n, ej)

        n = 0; ej = []
        for s in turnos:
            if dias_op[str(s.id)] == set():
                n += 1
                ej.append(f'{s.name}: sin ningun dia operativo')
        check('Ningun turno se queda sin dias operativos', n, ej)

        # ── 3. Generar y comprobar el plan ───────────────────────────────
        slots = _get_shift_slots()
        codes = [x['code'] for x in slots]
        labels = {x['code']: x['label'] for x in slots}
        tiendas = [r.id for r in EntityRecord.objects.filter(
            entity_type_id='tienda').order_by('id')]

        _limpiar()
        planes = {}
        busy: dict = {}
        extra: dict = {}
        from apps.restrictions.engine import _assignment_hours
        for s in tiendas:
            plan = generate_schedule(start, scope_entity_id=s,
                                     busy_map=busy, extra_hours=extra)['plan']
            planes[s] = plan
            for day in plan:
                for c in codes:
                    for e in (day.get(c) or []):
                        w = int((e or {}).get('workerId', 0) or 0)
                        if w > 0:
                            busy.setdefault(day.get('date'), set()).add(w)
                            extra[w] = extra.get(w, 0.0) + (_assignment_hours(e) or 0)

        self.stdout.write('PLANIFICACION GENERADA')
        self.stdout.write('=' * 74)

        # 3a. Solo turnos VIGENTES esa semana
        n = 0; ej = []
        for s, plan in planes.items():
            for day in plan:
                fecha = datetime.date.fromisoformat(day.get('date'))
                for c in codes:
                    tiene = any(int((e or {}).get('workerId', 0) or 0) > 0
                                for e in (day.get(c) or []))
                    if not tiene:
                        continue
                    sh = next((x for x in turnos if str(x.id) == str(c)), None)
                    if sh and hasattr(sh, 'is_active_on') and not sh.is_active_on(fecha):
                        n += 1
                        ej.append(f'{labels.get(c, c)} usado el {fecha} '
                                  f'(vigencia {sh.valid_from}..{sh.valid_to})')
        check('Solo se asignan turnos VIGENTES esa fecha', n, ej)

        # 3b. Solo en sus DIAS OPERATIVOS
        n = 0; ej = []
        for s, plan in planes.items():
            for day in plan:
                wd = datetime.date.fromisoformat(day.get('date')).weekday()
                for c in codes:
                    tiene = any(int((e or {}).get('workerId', 0) or 0) > 0
                                for e in (day.get(c) or []))
                    if not tiene:
                        continue
                    d = dias_op.get(str(c))
                    if d is not None and wd not in d:
                        n += 1
                        ej.append(f'{labels.get(c, c)} el {DIAS[wd]} '
                                  f'{day.get("date")} (opera {sorted(d)})')
        check('Solo se asigna en los DIAS OPERATIVOS del turno', n, ej)

        # 3c. El turno sale de la ficha del trabajador
        wcd = {w.id: (w.custom_data or {}) for w in Worker.objects.all()}
        wname = {w.id: w.name for w in Worker.objects.all()}
        n = 0; ej = []
        for s, plan in planes.items():
            for day in plan:
                for c in codes:
                    for e in (day.get(c) or []):
                        w = int((e or {}).get('workerId', 0) or 0)
                        if w <= 0:
                            continue
                        cd = wcd.get(w, {})
                        suyos = {str(cd.get(k)) for k in
                                 ('turno_base', 'turno_alternativo', 'turno_sabado')
                                 if cd.get(k)}
                        if suyos and str(c) not in suyos:
                            n += 1
                            ej.append(f'{wname.get(w, w)} en {labels.get(c, c)} '
                                      f'(su ficha: {sorted(suyos)})')
        check('El turno asignado esta en la ficha del trabajador', n, ej)

        # 3d. Las horas cuadran con el turno o con el horario propio
        n = 0; ej = []
        for s, plan in planes.items():
            for day in plan:
                for c in codes:
                    sh = next((x for x in turnos if str(x.id) == str(c)), None)
                    if not sh:
                        continue
                    hturno = _horas({'start': str(sh.start_time),
                                     'end': str(sh.end_time)})
                    for e in (day.get(c) or []):
                        if int((e or {}).get('workerId', 0) or 0) <= 0:
                            continue
                        h = _horas(e)
                        if h is None or h <= 0:
                            n += 1
                            ej.append(f'{labels.get(c, c)} · {day.get("date")}: '
                                      f'{e.get("start")}-{e.get("end")} -> {h}')
                        elif hturno and abs(h - hturno) > 3.0:
                            # Margen amplio: la ficha puede tener horario propio.
                            n += 1
                            ej.append(f'{wname.get(int(e["workerId"]), "?")}: '
                                      f'{h:.1f} h en un turno de {hturno:.1f} h')
        check('Las horas de cada asignacion son coherentes con su turno', n, ej)

        # ── 4. Uso real de cada turno ────────────────────────────────────
        uso = defaultdict(int)
        for s, plan in planes.items():
            for day in plan:
                for c in codes:
                    uso[c] += sum(1 for e in (day.get(c) or [])
                                  if int((e or {}).get('workerId', 0) or 0) > 0)
        self.stdout.write('')
        self.stdout.write('Asignaciones por turno:')
        for c in codes:
            sh = next((x for x in turnos if str(x.id) == str(c)), None)
            vig = (sh.is_active_on(start)
                   if sh and hasattr(sh, 'is_active_on') else True)
            nota = '' if vig else '  (no vigente esta semana)'
            self.stdout.write(f'   {labels.get(c, c)[:22]:<24} {uso[c]:>5}{nota}')

        self.stdout.write('=' * 74)
        self.stdout.write(f'{ok} comprobaciones OK, {fail} con incumplimientos')
