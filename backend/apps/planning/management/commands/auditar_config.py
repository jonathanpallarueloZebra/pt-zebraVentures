"""Audita la COHERENCIA de las configuraciones que alimentan al motor.

Busca datos que el sistema deja guardar pero que hacen que la planificacion
salga mal o que una regla no se aplique. Solo lectura.

Uso:  python manage.py auditar_config
"""
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand

from apps.assignments.models import AssignmentRule
from apps.catalog.models import KindValue
from apps.dynamic_fields.models import EntityField, EntityRecord, EntityType
from apps.planning.models import ClosedDay
from apps.restrictions.models import Restriction
from apps.shift_days.models import ShiftDay
from apps.shifts.models import Shift
from apps.workers.models import Worker


class Command(BaseCommand):
    help = 'Revisa la coherencia de turnos, restricciones, reglas y fichas.'

    def handle(self, *args, **opts):
        ok = avisos = 0

        def check(nombre, problemas, ejemplos=(), critico=True):
            """critico=False -> se reporta como AVISO, no como fallo."""
            nonlocal ok, avisos
            if not problemas:
                ok += 1
                self.stdout.write(f'  OK      {nombre}')
                return
            avisos += 1
            etq = 'CRITICO' if critico else 'AVISO  '
            estilo = self.style.ERROR if critico else self.style.WARNING
            self.stdout.write(estilo(f'  {etq} {nombre}: {problemas}'))
            for e in list(ejemplos)[:4]:
                self.stdout.write(f'             {e}')

        # ── TURNOS ───────────────────────────────────────────────────────
        self.stdout.write('TURNOS')
        self.stdout.write('-' * 74)
        turnos = list(Shift.objects.all())

        mal = [f'{s.name}: {s.start_time}-{s.end_time}' for s in turnos
               if s.end_time <= s.start_time]
        check('Hora de fin posterior a la de inicio', len(mal), mal)

        inv = [f'{s.name}: {s.valid_from} > {s.valid_to}' for s in turnos
               if s.valid_from and s.valid_to and s.valid_from > s.valid_to]
        check('Vigencias en orden', len(inv), inv)

        sin_dias = [s.name for s in turnos
                    if not ShiftDay.objects.filter(shift=s).exists()]
        check('Todos declaran dias operativos '
              '(sin dias = opera todos, puede ser intencionado)',
              len(sin_dias), sin_dias, critico=False)

        caducados = [f'{s.name} (hasta {s.valid_to})' for s in turnos
                     if s.valid_to and str(s.valid_to) < '2026-08-01']
        check('Sin turnos caducados arrastrandose',
              len(caducados), caducados, critico=False)

        # ── RESTRICCIONES ────────────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write('RESTRICCIONES')
        self.stdout.write('-' * 74)
        activas = list(Restriction.objects.filter(active=True))

        # Umbral ausente o no numerico en las de conteo
        malas = []
        for r in activas:
            cfg = r.config or {}
            if r.engine == 'count':
                try:
                    int(cfg.get('threshold'))
                except (TypeError, ValueError):
                    malas.append(f'{r.name}: threshold={cfg.get("threshold")!r}')
        check('Las de conteo tienen umbral numerico', len(malas), malas)

        # thresholdField que apunta a un campo que no existe
        claves = set(EntityField.objects.filter(entity_type='worker')
                     .values_list('key', flat=True))
        huerfanas = []
        for r in activas:
            cfg = r.config or {}
            campo = cfg.get('thresholdField')
            if campo and campo not in claves:
                huerfanas.append(f'{r.name}: thresholdField={campo!r} no existe')
        check('Los thresholdField apuntan a campos existentes',
              len(huerfanas), huerfanas)

        # filterAreaNames que no casan con ninguna seccion
        et = EntityType.objects.filter(show_in_schedule=True).first()
        secciones = {str((r.data or {}).get('nombre') or '')
                     for r in EntityRecord.objects.filter(entity_type=et)} if et else set()
        malas_areas = []
        for r in activas:
            for nom in ((r.config or {}).get('filterAreaNames') or []):
                if secciones and str(nom) not in secciones:
                    malas_areas.append(f'{r.name}: area {nom!r} no existe')
        check('Los filterAreaNames casan con secciones reales',
              len(malas_areas), malas_areas)

        # Parejas incompatibles con trabajadores inexistentes
        ids = set(Worker.objects.values_list('id', flat=True))
        malas_parejas = []
        for r in activas:
            cfg = r.config or {}
            if cfg.get('exclusionType') == 'worker_pair':
                for p in (cfg.get('workerPairs') or []):
                    fuera = [x for x in p if int(x) not in ids]
                    if fuera:
                        malas_parejas.append(
                            f'{r.name}: los IDs {fuera} no existen -> la regla no hace nada')
        check('Las parejas incompatibles apuntan a trabajadores reales',
              len(malas_parejas), malas_parejas, critico=False)

        # ── REGLAS DE ASIGNACION ─────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write('REGLAS DE ASIGNACION')
        self.stdout.write('-' * 74)
        reglas = list(AssignmentRule.objects.filter(active=True))

        sin_campo = []
        for r in reglas:
            cfg = r.config or {}
            tipo = cfg.get('overrideType')
            if tipo == 'times' and not (cfg.get('startField') or cfg.get('startValue')):
                sin_campo.append(f'{r.name}: overrideType times sin origen de horas')
            if tipo == 'day_off' and not cfg.get('daysField'):
                sin_campo.append(f'{r.name}: day_off sin daysField')
            if cfg.get('pattern') in ('alternate_weekly', 'alternate_daily') \
                    and not cfg.get('overrideField'):
                sin_campo.append(f'{r.name}: rotacion sin overrideField')
        check('Cada regla tiene los campos que su patron necesita',
              len(sin_campo), sin_campo)

        campos_ref = []
        for r in reglas:
            cfg = r.config or {}
            for k in ('overrideField', 'startField', 'endField', 'daysField',
                      'conditionField'):
                v = cfg.get(k)
                if v and v not in claves:
                    campos_ref.append(f'{r.name}: {k}={v!r} no existe en la ficha')
        check('Las reglas referencian campos de ficha existentes',
              len(campos_ref), campos_ref)

        # ── FICHAS DE TRABAJADOR ─────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write('FICHAS DE TRABAJADOR')
        self.stdout.write('-' * 74)
        activos = list(Worker.objects.filter(active=True))
        codigos_turno = {str(s.id) for s in turnos}

        sin_sec = [w.name for w in activos
                   if not (w.custom_data or {}).get('secciones')]
        check('Todos tienen seccion asignada', len(sin_sec), sin_sec,
              critico=False)

        sin_base = [w.name for w in activos
                    if not (w.custom_data or {}).get('turno_base')]
        check('Todos tienen turno base', len(sin_base), sin_base, critico=False)

        turno_malo = []
        for w in activos:
            cd = w.custom_data or {}
            for k in ('turno_base', 'turno_alternativo', 'turno_sabado'):
                v = cd.get(k)
                if v and str(v) not in codigos_turno:
                    turno_malo.append(f'{w.name}: {k}={v} (turno inexistente)')
        check('Los turnos de las fichas existen', len(turno_malo), turno_malo)

        sin_tienda = [w.name for w in activos
                      if not (w.custom_data or {}).get('tienda')]
        check('Todos tienen tienda asignada '
              '(sin ella entran por zona en TODAS las de su zona)',
              len(sin_tienda), sin_tienda, critico=False)

        # Rotacion declarada sin turno alternativo -> en la practica es fija
        rot = []
        for w in activos:
            cd = w.custom_data or {}
            if str(cd.get('rotacion', '')).lower() == 'semanal' \
                    and not cd.get('turno_alternativo'):
                rot.append(w.name)
        check('Quien rota tiene turno alternativo', len(rot), rot)

        # ── DIAS DE CIERRE ───────────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write('DIAS DE CIERRE')
        self.stdout.write('-' * 74)
        scopes = set(EntityRecord.objects.filter(
            entity_type_id='tienda').values_list('id', flat=True))
        malos = [f'{c.date} scope {c.scope_entity_id} (tienda inexistente)'
                 for c in ClosedDay.objects.all()
                 if c.scope_entity_id and c.scope_entity_id not in scopes]
        check('Los cierres por tienda apuntan a tiendas reales', len(malos), malos)

        dup = Counter((c.date, c.scope_entity_id) for c in ClosedDay.objects.all())
        repes = [f'{d} scope {s}' for (d, s), n in dup.items() if n > 1]
        check('Sin cierres duplicados', len(repes), repes)

        self.stdout.write('')
        self.stdout.write('=' * 74)
        self.stdout.write(f'{ok} comprobaciones OK, {avisos} con hallazgos')
