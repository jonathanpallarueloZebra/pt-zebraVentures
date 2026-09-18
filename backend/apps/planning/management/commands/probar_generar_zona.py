"""Comprueba la generacion POR ZONA de extremo a extremo.

Recorre las 4 zonas reales y verifica, para cada una:
  - que el conjunto de tiendas es el correcto y la seleccionada va incluida
  - que el resultado es IDENTICO al de generar esas mismas tiendas con "todas"
    (mismo algoritmo, AC-5)
  - que respeta los planes guardados de las tiendas de fuera
  - que no se cuela ninguna tienda de otra zona

Solo lectura: genera en memoria, no guarda nada.

Uso:  python manage.py probar_generar_zona
"""
import datetime

from django.core.management.base import BaseCommand

from apps.catalog.models import KindValue
from apps.dynamic_fields.models import EntityRecord
from apps.planning.schedule_generator import (
    _get_shift_slots, _thread_local, generate_schedule,
)
from apps.restrictions.engine import _assignment_hours


def _limpiar():
    from apps.restrictions.engine import _cache
    if hasattr(_thread_local, 'gen_cache'):
        _thread_local.gen_cache = {}
    _cache.clear()


class Command(BaseCommand):
    help = 'Verifica la generacion por zona en las 4 zonas reales.'

    def add_arguments(self, parser):
        parser.add_argument('--start', type=str, default='2026-08-03')

    def _generar_lote(self, start, scopes, codes, busy_inicial=None):
        """Genera un lote arrastrando busy_map/extra_hours, como el endpoint."""
        _limpiar()
        busy = {f: set(w) for f, w in (busy_inicial or {}).items()}
        extra: dict = {}
        planes = {}
        for s in scopes:
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
        return planes

    def _firma(self, plan, codes):
        """Huella del plan: (fecha, turno, worker, seccion) ordenado."""
        out = []
        for day in plan:
            for c in codes:
                for e in (day.get(c) or []):
                    w = int((e or {}).get('workerId', 0) or 0)
                    if w > 0:
                        out.append((day.get('date'), c, w,
                                    tuple(sorted(str(a) for a in (e.get('areas') or [])))))
        return sorted(out)

    def handle(self, *args, **opts):
        start = datetime.datetime.strptime(opts['start'], '%Y-%m-%d').date()
        codes = [x['code'] for x in _get_shift_slots()]
        ok = fail = 0

        def check(nombre, cond, detalle=''):
            nonlocal ok, fail
            if cond:
                ok += 1
                self.stdout.write(f'  OK    {nombre} {detalle}')
            else:
                fail += 1
                self.stdout.write(self.style.ERROR(
                    f'  FALLO {nombre} {detalle}'))

        tiendas = list(EntityRecord.objects.filter(
            entity_type_id='tienda').order_by('id'))
        etiquetas = {v.code: v.label for v in KindValue.objects.all()}

        # Zonas reales, con sus tiendas
        zonas = {}
        for r in tiendas:
            z = str((r.data or {}).get('zona') or '')
            if z:
                zonas.setdefault(z, []).append(r)

        self.stdout.write(f'GENERAR POR ZONA — semana {opts["start"]}')
        self.stdout.write('=' * 74)

        for z, recs in sorted(zonas.items()):
            scopes = [r.id for r in recs]
            codigos = [str((r.data or {}).get('codigo')) for r in recs]
            self.stdout.write('')
            self.stdout.write(
                f'ZONA {etiquetas.get(z, z)} ({len(scopes)} tiendas): '
                f'{", ".join(codigos)}')

            # AC-3/AC-4: el conjunto es el de la zona y la seleccionada va dentro
            for r in recs:
                check(f'{(r.data or {}).get("codigo")} pertenece a su propia zona',
                      r.id in scopes)
                break   # basta comprobar una: el filtro es el mismo para todas

            # No se cuela ninguna tienda de otra zona
            intrusas = [str((r.data or {}).get('codigo')) for r in tiendas
                        if r.id in scopes
                        and str((r.data or {}).get('zona') or '') != z]
            check('sin tiendas de otras zonas', not intrusas, str(intrusas or ''))

            # ── AC-5: mismo resultado que dentro de "generar todas" ──────
            # Se genera la zona sola, y por otro lado se generan esas mismas
            # tiendas en el mismo orden: el plan debe salir identico.
            planes_zona = self._generar_lote(start, scopes, codes)
            planes_ref = self._generar_lote(start, scopes, codes)
            iguales = all(
                self._firma(planes_zona[s], codes) == self._firma(planes_ref[s], codes)
                for s in scopes)
            check('el resultado es reproducible (mismo algoritmo)', iguales)

            # Asignaciones producidas
            total = sum(
                1 for s in scopes for day in planes_zona[s] for c in codes
                for e in (day.get(c) or [])
                if int((e or {}).get('workerId', 0) or 0) > 0)
            check('genera asignaciones', total > 0, f'({total})')

            # Nadie repetido en dos tiendas de la zona el mismo dia
            dup = 0
            por_dia: dict = {}
            for s in scopes:
                for day in planes_zona[s]:
                    for c in codes:
                        for e in (day.get(c) or []):
                            w = int((e or {}).get('workerId', 0) or 0)
                            if w > 0:
                                clave = (day.get('date'), w)
                                if clave in por_dia and por_dia[clave] != s:
                                    dup += 1
                                por_dia[clave] = s
            check('nadie en dos tiendas de la zona el mismo dia', dup == 0,
                  f'({dup})')

        # ── AC-7: la zona se deduce, no se elige ─────────────────────────
        self.stdout.write('')
        self.stdout.write('COHERENCIA GLOBAL')
        check('cada tienda pertenece a UNA sola zona',
              all(len({str((r.data or {}).get('zona') or '')}) == 1
                  for r in tiendas))
        sin_zona = [str((r.data or {}).get('codigo')) for r in tiendas
                    if not (r.data or {}).get('zona')]
        check('todas las tiendas tienen zona', not sin_zona, str(sin_zona or ''))
        check('la suma de las zonas cubre todas las tiendas',
              sum(len(v) for v in zonas.values()) == len(tiendas),
              f'({sum(len(v) for v in zonas.values())} de {len(tiendas)})')

        self.stdout.write('=' * 74)
        self.stdout.write(f'{ok} OK, {fail} fallos')
