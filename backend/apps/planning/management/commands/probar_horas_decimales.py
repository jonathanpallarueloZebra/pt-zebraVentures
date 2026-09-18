"""Demuestra que las horas semanales DECIMALES afectan a la planificacion.

Prueba de extremo a extremo: pone 37,5 h a un trabajador, genera y comprueba que
el motor le respeta ese tope con la parte fraccionaria (y no 37 ni 38).

Todo va dentro de una transaccion con rollback: no deja nada escrito.

Uso:
    python manage.py probar_horas_decimales
    python manage.py probar_horas_decimales --scope 54
"""
import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.dynamic_fields.models import EntityField
from apps.planning.schedule_generator import (
    _get_shift_slots, _thread_local, generate_schedule,
)
from apps.restrictions.engine import _effective_threshold
from apps.workers.models import Worker


def _limpiar():
    from apps.restrictions.engine import _cache
    if hasattr(_thread_local, 'gen_cache'):
        _thread_local.gen_cache = {}
    _cache.clear()


def _horas(entry):
    """Horas de una asignacion a partir de start/end (HH:MM)."""
    try:
        h1, m1 = map(int, str(entry.get('start', '')).split(':')[:2])
        h2, m2 = map(int, str(entry.get('end', '')).split(':')[:2])
        return ((h2 * 60 + m2) - (h1 * 60 + m1)) / 60.0
    except Exception:
        return 0.0


class Command(BaseCommand):
    help = 'Comprueba que un tope de horas con decimales se respeta al generar.'

    def add_arguments(self, parser):
        parser.add_argument('--scope', type=int, default=54)
        parser.add_argument('--start', type=str, default='2026-08-03')

    def handle(self, *args, **opts):
        ok = fail = 0

        def check(nombre, cond, detalle=''):
            nonlocal ok, fail
            if cond:
                ok += 1
                self.stdout.write(f'  OK    {nombre} {detalle}')
            else:
                fail += 1
                self.stdout.write(self.style.ERROR(f'  FALLO {nombre} {detalle}'))

        scope = opts['scope']
        start = datetime.datetime.strptime(opts['start'], '%Y-%m-%d').date()

        # ── 1. El campo esta declarado como decimal ──────────────────────
        self.stdout.write('1) El campo de horas es de tipo decimal')
        f = EntityField.objects.filter(
            entity_type='worker', key='horas_semanales').first()
        check('horas_semanales existe', f is not None)
        if f is None:
            return
        check("su tipo es 'float'", f.field_type == 'float',
              f'(es {f.field_type!r})')

        # ── 2. El motor lee el decimal sin redondear ─────────────────────
        self.stdout.write('\n2) El motor lee 37,5 sin perder el decimal')
        for valor, etiqueta in [(37.5, 'numero 37.5'), ('37,5', 'texto "37,5"'),
                                ('37.5', 'texto "37.5"')]:
            v = _effective_threshold({'horas_semanales': valor},
                                     'horas_semanales', 45, 5.0)
            check(f'{etiqueta} + 5 de margen = 42.5', abs(v - 42.5) < 0.001,
                  f'-> {v}')

        # ── 3. Efecto REAL sobre la planificacion ────────────────────────
        self.stdout.write('\n3) Efecto en la planificacion de una tienda')
        codes = [s['code'] for s in _get_shift_slots()]

        # Un trabajador de esa tienda que trabaje varios dias.
        _limpiar()
        plan0 = generate_schedule(start, scope_entity_id=scope)['plan']
        horas0 = {}
        for day in plan0:
            for c in codes:
                for e in (day.get(c) or []):
                    wid = int((e or {}).get('workerId', 0) or 0)
                    if wid > 0:
                        horas0[wid] = horas0.get(wid, 0.0) + _horas(e)
        if not horas0:
            self.stdout.write('   (la tienda no genera asignaciones)')
            return

        # El que mas horas acumula: es donde un tope bajo se nota.
        wid = max(horas0, key=lambda k: horas0[k])
        w = Worker.objects.filter(pk=wid).first()
        antes = horas0[wid]
        self.stdout.write(
            f'   Cobaya: {w.name[:32]} — {antes:.1f} h esta semana')

        original = dict(w.custom_data or {})
        try:
            with transaction.atomic():
                # Tope MUY bajo y con decimal: 12,5 h. Si el motor lo respeta,
                # sus horas deben quedar por debajo de 12,5 + 5 de margen.
                cd = dict(original)
                cd['horas_semanales'] = 12.5
                w.custom_data = cd
                w.save()

                _limpiar()
                plan1 = generate_schedule(start, scope_entity_id=scope)['plan']
                despues = 0.0
                for day in plan1:
                    for c in codes:
                        for e in (day.get(c) or []):
                            if int((e or {}).get('workerId', 0) or 0) == wid:
                                despues += _horas(e)

                tope = 12.5 + 5      # contrato + margen de empresa
                self.stdout.write(
                    f'   Con horas_semanales = 12,5 -> {despues:.1f} h '
                    f'(tope efectivo {tope})')
                check('sus horas bajan respecto al plan original',
                      despues < antes, f'({antes:.1f} -> {despues:.1f})')
                check('no supera el tope decimal', despues <= tope + 0.01,
                      f'({despues:.1f} <= {tope})')

                raise RuntimeError('rollback')
        except RuntimeError:
            pass

        # ── 4. Nada quedo escrito ────────────────────────────────────────
        w.refresh_from_db()
        check('la ficha vuelve a su valor original',
              (w.custom_data or {}).get('horas_semanales')
              == original.get('horas_semanales'),
              f"({(w.custom_data or {}).get('horas_semanales')})")

        _limpiar()
        self.stdout.write(f'\n{ok} OK, {fail} fallos')
