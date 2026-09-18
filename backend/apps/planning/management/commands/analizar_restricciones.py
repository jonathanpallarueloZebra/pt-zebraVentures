"""Analiza el efecto de CADA restriccion por separado sobre la planificacion.

Metodo: se desactivan todas, se genera para tener una linea base, y despues se
activa UNA sola cada vez midiendo que cambia (asignaciones, huecos, violaciones,
tiempo). Al terminar se restaura el estado original de todas.

Sirve para responder: ¿esta restriccion hace algo al generar, o solo avisa
despues? ¿cuanto cuesta? ¿deja gente sin asignar?

Uso:
    python manage.py analizar_restricciones                # todas las tiendas
    python manage.py analizar_restricciones --scope 54     # una tienda
    python manage.py analizar_restricciones --md salida.md # ademas escribe MD

Solo lectura sobre los planes: nunca guarda un WeeklyPlan. Toca el campo
`active` de las restricciones y lo deja como estaba (incluso si falla, por el
try/finally).
"""
import time
from collections import Counter

from django.core.management.base import BaseCommand

from apps.planning.schedule_generator import (
    _collect_violations, _get_shift_slots, _thread_local, generate_schedule,
)
from apps.restrictions.models import Restriction


def _limpiar_caches():
    """Sin esto, la 2ª generacion reutiliza las restricciones de la 1ª."""
    from apps.restrictions.engine import _cache
    if hasattr(_thread_local, 'gen_cache'):
        _thread_local.gen_cache = {}
    _cache.clear()


class Command(BaseCommand):
    help = 'Mide el efecto de cada restriccion activandolas de una en una.'

    def add_arguments(self, parser):
        parser.add_argument('--scope', type=int, default=0,
                            help='Solo esta tienda (0 = todas).')
        parser.add_argument('--start', type=str, default='2026-08-03')
        parser.add_argument('--md', type=str, default='',
                            help='Ruta de un .md donde volcar el informe.')

    # ── helpers ─────────────────────────────────────────────────────────
    def _metricas(self, scopes, start_d, codes):
        """Genera y devuelve (asignaciones, celdas_vacias, violaciones, seg)."""
        _limpiar_caches()
        t0 = time.time()
        asign = vacias = 0
        viol = Counter()
        sin_asignar = set()
        for scope in scopes:
            r = generate_schedule(start_d, scope_entity_id=scope)
            plan = r['plan']
            for day in plan:
                for code in codes:
                    ents = [e for e in (day.get(code) or [])
                            if int((e or {}).get('workerId', 0) or 0) > 0]
                    if ents:
                        asign += len(ents)
                    else:
                        vacias += 1
            for v in _collect_violations(plan, scope_record_id=scope):
                viol[f"{v['severity'][:4]}|{v['restrictionName'][:34]}"] += 1
            # Gente que no entro en ningun turno de su tienda
            asignados = {int(e['workerId'])
                         for day in plan for code in codes
                         for e in (day.get(code) or [])
                         if int((e or {}).get('workerId', 0) or 0) > 0}
            for day in plan:
                for wid in (day.get('rest') or []):
                    if wid not in asignados:
                        sin_asignar.add(wid)
        return asign, vacias, viol, time.time() - t0, len(sin_asignar)

    # ── comando ─────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        from datetime import datetime

        start_d = datetime.strptime(opts['start'], '%Y-%m-%d').date()
        scopes = [opts['scope']] if opts['scope'] else list(range(54, 69))
        codes = [s['code'] for s in _get_shift_slots()]

        todas = list(Restriction.objects.all().order_by('id'))
        original = {r.id: r.active for r in todas}
        activas = [r for r in todas if original[r.id]]

        lineas = []

        def out(txt=''):
            self.stdout.write(txt)
            lineas.append(txt)

        out(f'Semana {opts["start"]} · {len(scopes)} tienda(s) · '
            f'{len(activas)} restricciones activas')
        out('=' * 78)

        try:
            # ── Linea base: TODAS desactivadas ──────────────────────────
            Restriction.objects.filter(active=True).update(active=False)
            b_as, b_vac, b_viol, b_seg, b_sin = self._metricas(
                scopes, start_d, codes)
            out('')
            out(f'BASE (todas desactivadas): {b_as} asignaciones · '
                f'{b_vac} celdas vacias · {b_sin} sin asignar · {b_seg:.1f}s')
            out('')
            out(f'{"RESTRICCION":<44}{"ASIGN":>7}{"VACIAS":>8}'
                f'{"S/ASIG":>8}{"VIOL":>6}{"SEG":>7}')
            out('-' * 78)

            resultados = []
            for r in activas:
                Restriction.objects.filter(active=True).update(active=False)
                Restriction.objects.filter(id=r.id).update(active=True)
                a, v, vi, seg, sa = self._metricas(scopes, start_d, codes)
                resultados.append((r, a, v, vi, seg, sa))
                out(f'{r.name[:43]:<44}{a:>7}{v:>8}{sa:>8}'
                    f'{sum(vi.values()):>6}{seg:>6.1f}s')

            # ── Todas juntas ────────────────────────────────────────────
            Restriction.objects.filter(active=False).update(active=False)
            for rid, was in original.items():
                Restriction.objects.filter(id=rid).update(active=was)
            t_as, t_vac, t_viol, t_seg, t_sin = self._metricas(
                scopes, start_d, codes)
            out('-' * 78)
            out(f'{"TODAS ACTIVAS (estado real)":<44}{t_as:>7}{t_vac:>8}'
                f'{t_sin:>8}{sum(t_viol.values()):>6}{t_seg:>6.1f}s')

            # ── Lectura de los resultados ───────────────────────────────
            out('')
            out('ANALISIS')
            out('=' * 78)

            sin_efecto = [r.name for (r, a, v, vi, seg, sa) in resultados
                          if a == b_as and v == b_vac]
            con_efecto = [(r.name, a - b_as, v - b_vac)
                          for (r, a, v, vi, seg, sa) in resultados
                          if a != b_as or v != b_vac]

            out('')
            out(f'Cambian el reparto ({len(con_efecto)}):')
            for n, da, dv in sorted(con_efecto, key=lambda x: x[1]):
                out(f'   {n[:46]:<48} asign {da:+5d}   vacias {dv:+5d}')
            out('')
            out(f'NO cambian el reparto ({len(sin_efecto)}):')
            for n in sin_efecto:
                out(f'   {n[:60]}')
            out('   -> o no aplican a estos datos, o solo se validan despues.')

            # Violaciones que quedan con todo activo
            out('')
            if t_viol:
                out('Violaciones con TODAS activas:')
                for k, n in t_viol.most_common():
                    out(f'   x{n:<4} {k}')
            else:
                out('Sin violaciones con todas activas.')

            # Coste en tiempo
            out('')
            caras = sorted(resultados, key=lambda x: -x[4])[:3]
            out(f'Mas lentas (base {b_seg:.1f}s):')
            for r, a, v, vi, seg, sa in caras:
                out(f'   {seg:>6.1f}s  ({seg - b_seg:+.1f}s)  {r.name[:44]}')

        finally:
            # Restaurar SIEMPRE el estado original
            for rid, was in original.items():
                Restriction.objects.filter(id=rid).update(active=was)
            _limpiar_caches()
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(
                'Estado original de las restricciones restaurado.'))

        if opts['md']:
            with open(opts['md'], 'w', encoding='utf-8') as fh:
                fh.write('# Analisis de restricciones\n\n```\n')
                fh.write('\n'.join(lineas))
                fh.write('\n```\n')
            self.stdout.write(f'Informe escrito en {opts["md"]}')
