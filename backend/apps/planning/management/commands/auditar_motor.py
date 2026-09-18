"""Audita si el plan GENERADO cumple cada restriccion, una por una.

No se fia del contador de violaciones: comprueba cada regla directamente sobre
las asignaciones producidas. Asi se detecta tanto que el motor incumpla algo como
que el evaluador no lo este mirando.

Solo lectura: genera en memoria, no guarda nada.

Uso:  python manage.py auditar_motor
      python manage.py auditar_motor --start 2026-08-10
"""
import datetime
from collections import defaultdict

from django.core.management.base import BaseCommand

from apps.dynamic_fields.models import EntityRecord, EntityType
from apps.planning.schedule_generator import (
    _field_values, _get_shift_slots, _norm_weekday, _thread_local,
    generate_schedule,
)
from apps.restrictions.models import Restriction
from apps.workers.models import Worker


def _limpiar():
    from apps.restrictions.engine import _cache
    if hasattr(_thread_local, 'gen_cache'):
        _thread_local.gen_cache = {}
    _cache.clear()


class Command(BaseCommand):
    help = 'Comprueba sobre el plan generado que cada restriccion se cumple.'

    def add_arguments(self, parser):
        parser.add_argument('--start', type=str, default='2026-08-03')
        parser.add_argument(
            '--ambito', type=str, default='todas',
            help="'todas' (15 tiendas) | 'zona:CODIGO' (p.ej. zona:huesca) "
                 "| 'tienda:ID'. Reproduce lo que hace cada boton de la app.",
        )

    def handle(self, *args, **opts):
        start = datetime.datetime.strptime(opts['start'], '%Y-%m-%d').date()
        # ── Ámbito: reproduce el botón correspondiente de la aplicación ──
        tiendas = list(EntityRecord.objects.filter(
            entity_type_id='tienda').order_by('id'))
        ambito = str(opts['ambito'] or 'todas').strip().lower()
        if ambito.startswith('zona:'):
            codigo = ambito.split(':', 1)[1]
            scopes = [r.id for r in tiendas
                      if str((r.data or {}).get('zona') or '').lower() == codigo]
            desc = f'ZONA {codigo} ({len(scopes)} tiendas)'
        elif ambito.startswith('tienda:'):
            scopes = [int(ambito.split(':', 1)[1])]
            desc = f'UNA TIENDA (scope {scopes[0]})'
        else:
            scopes = [r.id for r in tiendas]
            desc = f'TODAS ({len(scopes)} tiendas)'
        if not scopes:
            self.stdout.write(self.style.ERROR(
                f'el ambito {ambito!r} no casa con ninguna tienda'))
            return
        slots = _get_shift_slots()
        codes = [s['code'] for s in slots]
        labels = {s['code']: s['label'] for s in slots}

        areas = {r.id: str((r.data or {}).get('nombre') or '')
                 for r in EntityRecord.objects.all()}
        wcd = {w.id: (w.custom_data or {}) for w in Worker.objects.all()}
        wname = {w.id: w.name for w in Worker.objects.all()}

        # ── Generar las 15 tiendas EN BLOQUE ─────────────────────────────
        #
        # Igual que hace la aplicacion con "Generar todas": arrastrando busy_map
        # (quien ya tiene turno ese dia) y extra_hours (horas acumuladas) de una
        # tienda a la siguiente.
        #
        # Generarlas por separado, cada una con generate_schedule() a secas,
        # produce falsos positivos: cada llamada no sabe nada de las anteriores,
        # asi que los volantes salen asignados en varias tiendas y sus horas se
        # cuentan 8 veces. Eso NO es lo que hace el motor en produccion.
        _limpiar()
        planes = {}
        # Un ámbito PARCIAL (zona o una tienda) arranca reservando a quien ya
        # tiene turno guardado en las tiendas que NO se regeneran: es lo que hace
        # el endpoint con _busy_map_from_saved_plans. Sin esto la auditoría de
        # zona daría duplicados que en la aplicación no ocurren.
        from apps.planning.views import _busy_map_from_saved_plans
        busy_map: dict = {}
        if len(scopes) < len(tiendas):
            busy_map = {f: set(w) for f, w in _busy_map_from_saved_plans(
                start, exclude_scope_ids=scopes).items()}
            self.stdout.write(
                f'(reservados por planes guardados de otras tiendas: '
                f'{sum(len(v) for v in busy_map.values())} asignaciones)')
        # Copia ANTES de generar: `busy_map` se va rellenando con lo que produce
        # cada tienda, así que al comprobar ya contendría a todos los asignados y
        # el chequeo se acusaría a sí mismo.
        reservados_previos = {f: set(w) for f, w in busy_map.items()}
        extra_hours: dict = {}
        for s in scopes:
            r = generate_schedule(start, scope_entity_id=s,
                                  busy_map=busy_map, extra_hours=extra_hours)
            plan = r['plan']
            planes[s] = plan
            # Reservar a los asignados para las tiendas siguientes.
            for day in plan:
                fecha = day.get('date')
                for c in codes:
                    for e in (day.get(c) or []):
                        w = int((e or {}).get('workerId', 0) or 0)
                        if w <= 0:
                            continue
                        busy_map.setdefault(fecha, set()).add(w)
                        from apps.restrictions.engine import _assignment_hours
                        extra_hours[w] = extra_hours.get(w, 0.0) + (
                            _assignment_hours(e) or 0)

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
                for e in list(ejemplos)[:3]:
                    self.stdout.write(f'           {e}')

        self.stdout.write(f'AUDITORIA DEL MOTOR — semana {opts["start"]} — {desc}')
        self.stdout.write('=' * 72)

        # ── 1. Maximo 1 turno por dia por trabajador (error) ─────────────
        n = 0; ej = []
        for s, plan in planes.items():
            for day in plan:
                por_worker = defaultdict(int)
                for c in codes:
                    for e in (day.get(c) or []):
                        w = int((e or {}).get('workerId', 0) or 0)
                        if w > 0:
                            por_worker[w] += 1
                for w, k in por_worker.items():
                    if k > 1:
                        n += 1
                        ej.append(f'{wname.get(w, w)} · {day.get("date")} · {k} turnos')
        check('Maximo 1 turno por dia por trabajador', n, ej)

        # ── 2. Nadie en dos tiendas el mismo dia ─────────────────────────
        n = 0; ej = []
        por_dia = defaultdict(lambda: defaultdict(list))
        for s, plan in planes.items():
            for day in plan:
                for c in codes:
                    for e in (day.get(c) or []):
                        w = int((e or {}).get('workerId', 0) or 0)
                        if w > 0:
                            por_dia[day.get('date')][w].append(s)
        for fecha, ws in por_dia.items():
            for w, ts in ws.items():
                if len(set(ts)) > 1:
                    n += 1
                    ej.append(f'{wname.get(w, w)} · {fecha} · tiendas {set(ts)}')
        check('Nadie asignado en dos tiendas el mismo dia (dentro del ambito)',
              n, ej)

        # ── 2-bis. Ni choca con lo GUARDADO de las tiendas de fuera ──────
        n = 0; ej = []
        if reservados_previos:
            for s, plan in planes.items():
                for day in plan:
                    ocupados = reservados_previos.get(day.get('date'), set())
                    for c in codes:
                        for e in (day.get(c) or []):
                            w = int((e or {}).get('workerId', 0) or 0)
                            if w > 0 and w in ocupados:
                                n += 1
                                ej.append(f'{wname.get(w, w)} · {day.get("date")} '
                                          f'(ya trabajaba en otra tienda)')
        check('Ni choca con los planes guardados de otras tiendas', n, ej)

        # ── 3. La seccion esta en la polivalencia del trabajador ─────────
        n = 0; ej = []
        for s, plan in planes.items():
            for day in plan:
                for c in codes:
                    for e in (day.get(c) or []):
                        w = int((e or {}).get('workerId', 0) or 0)
                        if w <= 0:
                            continue
                        suyas = {areas.get(int(x['value']) if isinstance(x, dict) else int(x))
                                 for x in (wcd.get(w, {}).get('secciones') or []) if x}
                        for a in (e.get('areas') or []):
                            if suyas and str(a) not in suyas:
                                n += 1
                                ej.append(f'{wname.get(w, w)} en {a} '
                                          f'(sus secciones: {sorted(x for x in suyas if x)})')
        check('La seccion asignada esta en su polivalencia', n, ej)

        # ── 4. Nadie asignado en su dia libre fijo ───────────────────────
        n = 0; ej = []
        for s, plan in planes.items():
            for day in plan:
                fecha = day.get('date')
                wd = datetime.date.fromisoformat(fecha).weekday()
                for c in codes:
                    for e in (day.get(c) or []):
                        w = int((e or {}).get('workerId', 0) or 0)
                        if w <= 0:
                            continue
                        libres = {_norm_weekday(v) for v in
                                  _field_values(wcd.get(w, {}).get('dias_libres'))}
                        if wd in libres:
                            n += 1
                            ej.append(f'{wname.get(w, w)} · {fecha} (libra ese dia)')
        check('Nadie trabaja en su dia libre fijo', n, ej)

        # ── 5. Nadie asignado estando en descanso oficial ────────────────
        n = 0; ej = []
        for s, plan in planes.items():
            for day in plan:
                descansan = {int(x) for x in (day.get('rest') or [])
                             if str(x).isdigit()}
                for c in codes:
                    for e in (day.get(c) or []):
                        w = int((e or {}).get('workerId', 0) or 0)
                        if w > 0 and w in descansan:
                            n += 1
                            ej.append(f'{wname.get(w, w)} · {day.get("date")}')
        check('Nadie trabaja estando en descanso', n, ej)

        # ── 6. Topes por seccion (count / shift_area / lte) ──────────────
        topes = {}
        for r in Restriction.objects.filter(active=True, engine='count'):
            cfg = r.config or {}
            if cfg.get('groupBy') != 'shift_area' or cfg.get('operator') != 'lte':
                continue
            for nom in (cfg.get('filterAreaNames') or []):
                topes[str(nom)] = int(cfg['threshold'])
        n = 0; ej = []
        for s, plan in planes.items():
            for day in plan:
                for c in codes:
                    cuenta = defaultdict(int)
                    for e in (day.get(c) or []):
                        if int((e or {}).get('workerId', 0) or 0) > 0:
                            for a in (e.get('areas') or []):
                                cuenta[str(a)] += 1
                    for a, k in cuenta.items():
                        if a in topes and k > topes[a]:
                            n += 1
                            ej.append(f'{a}: {k} (max {topes[a]}) · '
                                      f'{day.get("date")} {labels.get(c, c)}')
        check(f'Topes por seccion respetados {topes or "(ninguno)"}', n, ej)

        # ── 7. Topes por campo de ficha (count / shift / filterField) ────
        fcaps = []
        for r in Restriction.objects.filter(active=True, engine='count'):
            cfg = r.config or {}
            if cfg.get('groupBy') != 'shift' or cfg.get('operator') != 'lte':
                continue
            if cfg.get('filterField'):
                fcaps.append((cfg['filterField'],
                              str(cfg.get('filterValue', '')).lower(),
                              int(cfg['threshold']), r.name))
        n = 0; ej = []
        for campo, valor, tope, nombre in fcaps:
            for s, plan in planes.items():
                for day in plan:
                    for c in codes:
                        k = sum(
                            1 for e in (day.get(c) or [])
                            if int((e or {}).get('workerId', 0) or 0) > 0
                            and str(wcd.get(int(e['workerId']), {})
                                    .get(campo, '')).lower() == valor)
                        if k > tope:
                            n += 1
                            ej.append(f'{nombre}: {k} (max {tope}) · '
                                      f'{day.get("date")} {labels.get(c, c)}')
        check(f'Topes por campo de ficha respetados '
              f'({len(fcaps)} regla(s))', n, ej)

        # ── 8. Parejas incompatibles nunca en el mismo turno ─────────────
        parejas = []
        for r in Restriction.objects.filter(active=True, engine='exclusion'):
            cfg = r.config or {}
            if cfg.get('exclusionType') == 'worker_pair':
                for p in (cfg.get('workerPairs') or []):
                    if len(p) == 2:
                        parejas.append((int(p[0]), int(p[1])))
        n = 0; ej = []
        for a, b in parejas:
            for s, plan in planes.items():
                for day in plan:
                    for c in codes:
                        ids = {int((e or {}).get('workerId', 0) or 0)
                               for e in (day.get(c) or [])}
                        if a in ids and b in ids:
                            n += 1
                            ej.append(f'{a}+{b} · {day.get("date")}')
        check(f'Parejas incompatibles separadas ({len(parejas)} pareja(s))', n, ej)

        # ── 9. Tope de horas semanales por contrato ──────────────────────
        from apps.restrictions.engine import _assignment_hours, _effective_threshold
        restr_h = Restriction.objects.filter(
            active=True, config__scope='per_week_worker_hours').first()
        n = 0; ej = []
        if restr_h:
            cfg = restr_h.config or {}
            plano = float(cfg.get('threshold', 0))
            campo = cfg.get('thresholdField', '') or ''
            offset = float(cfg.get('thresholdOffset', 0) or 0)
            horas = defaultdict(float)
            for s, plan in planes.items():
                for day in plan:
                    for c in codes:
                        for e in (day.get(c) or []):
                            w = int((e or {}).get('workerId', 0) or 0)
                            if w > 0:
                                horas[w] += _assignment_hours(e) or 0
            for w, h in horas.items():
                tope = _effective_threshold(wcd.get(w, {}), campo, plano, offset)
                if h > tope + 0.01:
                    n += 1
                    ej.append(f'{wname.get(w, w)}: {h:.1f} h (tope {tope})')
        check('Tope de horas semanales respetado', n, ej)

        # ── 10. Dias de cierre sin asignaciones ─────────────────────────
        # Un cierre puede ser GLOBAL (scope_entity_id = 0) o de una tienda
        # concreta: San Lorenzo, por ejemplo, solo cierra T02..T05 y T07. Comparar
        # solo la fecha daba 92 falsos positivos en las tiendas que ese dia SI
        # abren.
        from apps.planning.models import ClosedDay
        cierres_globales = set()
        cierres_tienda = defaultdict(set)     # scope -> {fechas}
        for c in ClosedDay.objects.all():
            if c.scope_entity_id:
                cierres_tienda[c.scope_entity_id].add(c.date.isoformat())
            else:
                cierres_globales.add(c.date.isoformat())
        total_cierres = len(cierres_globales) + sum(
            len(v) for v in cierres_tienda.values())
        n = 0; ej = []
        for s, plan in planes.items():
            cerrados = cierres_globales | cierres_tienda.get(s, set())
            for day in plan:
                if day.get('date') not in cerrados:
                    continue
                for c in codes:
                    for e in (day.get(c) or []):
                        if int((e or {}).get('workerId', 0) or 0) > 0:
                            n += 1
                            ej.append(
                                f'{day.get("date")} · scope {s} (dia de cierre)')
        check(f'Sin asignaciones en dias de cierre '
              f'({total_cierres} cierre(s) configurado(s))', n, ej)

        self.stdout.write('=' * 72)
        self.stdout.write(f'{ok} comprobaciones OK, {fail} con incumplimientos')
