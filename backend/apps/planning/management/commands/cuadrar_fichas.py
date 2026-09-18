"""Rellena huecos DEDUCIBLES en las fichas para que la generación cuadre mejor.

Solo toca lo que se deduce sin ambigüedad de los datos que ya existen. NO decide
nada que dependa del cliente (a quién se contrata, quién pasa a turno de tarde,
qué secciones cubre cada uno): eso se queda como aviso en la planificación.

Dos arreglos:

1. `turno_sabado` vacío  →  el turno de sábado que corresponde a su turno base
   (base Mañana → Sábado Mañana, base Tarde → Sábado Tarde). Quien trabaja de
   mañana L-V lo normal es que el sábado también sea de mañana.

2. Secciones donde TODO el personal rota igual (mismo turno base y mismo
   alternativo)  →  se invierten base/alternativo en UNA persona para que vayan
   desfasadas. Si no, rotan en bloque y en semanas alternas ese turno se queda
   sin nadie. Se elige a quien menos secciones cubre (para no descolocar a los
   comodines) y se respeta su `turno_sabado` (no se toca).

Por defecto SIMULA: no escribe nada. Con --apply guarda los cambios.

    python manage.py cuadrar_fichas               # simulación
    python manage.py cuadrar_fichas --apply       # aplica
    python manage.py cuadrar_fichas --only sabado # solo el arreglo 1
"""
import collections

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.dynamic_fields.models import EntityRecord, EntityType
from apps.shifts.models import Shift
from apps.shift_days.models import ShiftDay
from apps.workers.models import Worker


class Command(BaseCommand):
    help = 'Rellena turno_sabado y desincroniza rotaciones en bloque (deducible, sin decidir personal)'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Escribe los cambios. Sin este flag solo simula.')
        parser.add_argument('--only', choices=['sabado', 'rotacion'],
                            help='Aplicar solo uno de los dos arreglos.')

    def handle(self, *args, **opts):
        apply_changes = opts['apply']
        only = opts.get('only')

        shifts = {str(s.id): s for s in Shift.objects.all()}
        # Turnos que operan el sábado, separados por franja.
        sat_ids = {str(sd.shift_id) for sd in ShiftDay.objects.filter(weekday=5)}
        sat_morning = next((i for i in sat_ids if 'tarde' not in shifts[i].name.lower()), None)
        sat_evening = next((i for i in sat_ids if 'tarde' in shifts[i].name.lower()), None)

        sec_type = EntityType.objects.filter(slug='seccion').first()
        sec_names = {}
        if sec_type:
            sec_names = {
                r.id: (r.data.get('nombre') or r.data.get('name'))
                for r in EntityRecord.objects.filter(entity_type=sec_type)
            }

        workers = list(Worker.objects.filter(active=True))
        cambios = []   # (worker, {campo: (antes, despues)}, motivo)

        if only != 'rotacion':
            cambios += self._fill_saturday(workers, shifts, sat_morning, sat_evening)
        if only != 'sabado':
            cambios += self._desync_rotation(workers, shifts, sec_names)

        self._report(cambios, shifts)

        if not cambios:
            self.stdout.write(self.style.SUCCESS('\nNada que cambiar.'))
            return
        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                f'\nSIMULACION: no se ha escrito nada. Repite con --apply para '
                f'aplicar estos {len(cambios)} cambios.'))
            return

        with transaction.atomic():
            for worker, campos, _motivo in cambios:
                data = dict(worker.custom_data or {})
                for campo, (_antes, despues) in campos.items():
                    data[campo] = despues
                worker.custom_data = data
                worker.save(update_fields=['custom_data'])
        self.stdout.write(self.style.SUCCESS(
            f'\nAplicados {len(cambios)} cambios. Hay que REGENERAR las semanas '
            f'ya guardadas: los planes no se recalculan solos.'))

    # ── Arreglo 1: turno de sábado ──────────────────────────────────────
    def _fill_saturday(self, workers, shifts, sat_morning, sat_evening):
        if not sat_morning and not sat_evening:
            self.stdout.write(self.style.WARNING(
                'No hay turnos que operen el sábado: se omite el arreglo de turno_sabado.'))
            return []
        out = []
        for w in workers:
            cd = w.custom_data or {}
            if cd.get('turno_sabado'):
                continue
            base = shifts.get(str(cd.get('turno_base') or ''))
            if not base:
                continue          # sin turno base no hay nada que replicar
            destino = sat_evening if 'tarde' in base.name.lower() else sat_morning
            if not destino:
                continue
            out.append((w, {'turno_sabado': (None, int(destino))},
                        f'turno base {base.name} -> {shifts[destino].name}'))
        return out

    # ── Arreglo 2: desincronizar rotaciones en bloque ────────────────────
    def _desync_rotation(self, workers, shifts, sec_names):
        # Agrupa por (tienda, sección) solo a quien rota de verdad.
        grupos = collections.defaultdict(list)
        for w in workers:
            cd = w.custom_data or {}
            tienda = cd.get('tienda')
            base = str(cd.get('turno_base') or '')
            alt = str(cd.get('turno_alternativo') or '')
            if not tienda or not base or not alt or base == alt:
                continue
            if str(cd.get('rotacion') or '') != 'semanal':
                continue
            for x in (cd.get('secciones') or []):
                if isinstance(x, dict):
                    nombre = sec_names.get(x.get('value'))
                    if nombre:
                        grupos[(int(tienda), nombre)].append(w)

        out = []
        ya_tocados = set()     # una persona solo se invierte una vez
        for (tienda, seccion), pool in sorted(grupos.items(), key=lambda kv: str(kv[0])):
            if len(pool) < 2:
                continue       # con una sola no hay nada que desfasar
            firmas = {
                f"{(w.custom_data or {}).get('turno_base')}|"
                f"{(w.custom_data or {}).get('turno_alternativo')}"
                for w in pool
            }
            if len(firmas) > 1:
                continue       # ya están desfasadas
            # Se invierte a quien menos secciones cubra (menos impacto).
            candidatos = sorted(
                pool, key=lambda w: (len((w.custom_data or {}).get('secciones') or []), w.id))
            elegido = next((w for w in candidatos if w.id not in ya_tocados), None)
            if not elegido:
                continue
            ya_tocados.add(elegido.id)
            cd = elegido.custom_data or {}
            base, alt = cd.get('turno_base'), cd.get('turno_alternativo')
            out.append((elegido,
                        {'turno_base': (base, alt), 'turno_alternativo': (alt, base)},
                        f'{seccion} en tienda {tienda}: {len(pool)} personas rotaban en bloque'))
        return out

    # ── Informe ─────────────────────────────────────────────────────────
    def _report(self, cambios, shifts):
        def nombre(v):
            s = shifts.get(str(v))
            return s.name if s else str(v)

        por_campo = collections.Counter()
        self.stdout.write('=' * 74)
        self.stdout.write('CAMBIOS PROPUESTOS')
        self.stdout.write('=' * 74)
        for w, campos, motivo in cambios:
            detalle = ' · '.join(
                f'{k}: {nombre(a) if a else "(vacio)"} -> {nombre(b)}'
                for k, (a, b) in campos.items())
            self.stdout.write(f'  {w.name[:30]:30} {detalle}')
            self.stdout.write(f'  {"":30} ({motivo})')
            for k in campos:
                por_campo[k] += 1
        self.stdout.write('\n--- resumen ---')
        for k, v in por_campo.most_common():
            self.stdout.write(f'  {k:20} {v} fichas')
        self.stdout.write(f'  {"TOTAL":20} {len(cambios)} fichas')
