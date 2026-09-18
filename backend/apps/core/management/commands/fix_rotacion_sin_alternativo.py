"""Rellena el turno alternativo de quien esta marcado para rotar y no rota.

Un trabajador con rotacion 'semanal' pero sin turno_alternativo se queda en su
turno base para siempre: _apply_single_rule() no tiene destino al que moverlo y
devuelve el turno actual. La ficha dice que rota y en la practica es fijo.

Este comando le asigna el turno OPUESTO al base. Entre semana solo hay dos
turnos operativos (Manana / Tarde), asi que el opuesto es inequivoco.

Uso:
    python manage.py fix_rotacion_sin_alternativo --dry-run    # ver que haria
    python manage.py fix_rotacion_sin_alternativo              # aplicar
    python manage.py fix_rotacion_sin_alternativo --scope 54   # solo una tienda
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = ('Asigna turno_alternativo (el opuesto al base) a los trabajadores '
            'con rotacion semanal que no lo tienen.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Mostrar los cambios sin escribir en la BD.')
        parser.add_argument('--scope', type=int, default=0,
                            help='Limitar a un id de ambito (tienda). 0 = todas.')

    def handle(self, *args, **opts):
        from apps.assignments.models import AssignmentRule
        from apps.planning.schedule_generator import _rule_condition_matches
        from apps.shifts.models import Shift
        from apps.workers.models import Worker

        dry = opts['dry_run']
        scope = opts['scope']

        # ── Turnos operativos entre semana (los de sabado no rotan) ────────
        # Se excluyen los caducados (misma regla que los desplegables): un turno
        # extra de Navidad ya pasado no es candidato a ser el "opuesto".
        from datetime import date as _date

        from django.db.models import Q

        today = _date.today()
        weekday_shifts = [
            s for s in Shift.objects.filter(
                Q(valid_to__isnull=True) | Q(valid_to__gte=today))
            if 'sabado' not in s.name.lower() and 'sábado' not in s.name.lower()
        ]
        if len(weekday_shifts) != 2:
            self.stderr.write(self.style.ERROR(
                f'Se esperaban 2 turnos entre semana y hay {len(weekday_shifts)}: '
                + ', '.join(s.name for s in weekday_shifts)
                + '. El "opuesto" deja de ser inequivoco, revisalo a mano.'))
            return
        a, b = weekday_shifts
        opposite = {str(a.id): str(b.id), str(b.id): str(a.id)}
        names = {str(a.id): a.name, str(b.id): b.name}
        self.stdout.write(f'Turnos entre semana: {a.name} (id {a.id}) <-> {b.name} (id {b.id})')

        # ── Reglas de alternancia activas ──────────────────────────────────
        rules = [
            r for r in AssignmentRule.objects.filter(active=True)
            if (r.config or {}).get('pattern') in ('alternate_weekly', 'alternate_daily')
            and (r.config or {}).get('overrideField')
        ]
        if not rules:
            self.stdout.write(self.style.WARNING(
                'No hay reglas de alternancia activas: nada que arreglar.'))
            return

        scope_field = self._scope_field_key()
        pending, skipped = [], []

        for w in Worker.objects.filter(active=True).order_by('name'):
            cd = w.custom_data or {}
            if scope and scope_field and str(cd.get(scope_field, '')) != str(scope):
                continue
            for rule in rules:
                config = rule.config or {}
                field = config['overrideField']
                if not _rule_condition_matches(cd, config):
                    continue
                if str(cd.get(field, '') or ''):
                    continue                      # ya tiene alternativo
                base = str(cd.get('turno_base', '') or '')
                if base not in opposite:
                    # Sin turno base, o con un base que no es de entre semana:
                    # no se puede deducir el opuesto sin inventar.
                    skipped.append((w, base))
                    continue
                pending.append((w, field, base, opposite[base]))

        if not pending and not skipped:
            self.stdout.write(self.style.SUCCESS(
                'No hay trabajadores con rotacion sin turno alternativo.'))
            return

        prefix = '[DRY-RUN] ' if dry else ''
        self.stdout.write('')
        self.stdout.write(f'{prefix}{len(pending)} trabajador(es) a corregir:')
        for w, field, base, alt in pending:
            self.stdout.write(
                f'  {w.name[:34]:36} {names.get(base, base):9} -> {field} = {names.get(alt, alt)}')

        if skipped:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                f'{len(skipped)} sin corregir (turno base vacio o no es de entre semana), '
                'revisar a mano:'))
            for w, base in skipped:
                self.stdout.write(f'  {w.name[:34]:36} turno_base={base or "(vacio)"!r}')

        if dry:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'DRY-RUN: no se ha escrito nada. Repite sin --dry-run para aplicar.'))
            return

        with transaction.atomic():
            for w, field, _base, alt in pending:
                cd = w.custom_data or {}
                cd[field] = alt
                w.custom_data = cd
                w.save(update_fields=['custom_data'])

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Actualizados {len(pending)} trabajadores. Regenera la semana para '
            'que la rotacion surta efecto.'))

    def _scope_field_key(self):
        """Campo del worker que apunta al ambito de planificacion (p.ej. 'tienda')."""
        from apps.dynamic_fields.models import EntityField, EntityType
        et = EntityType.objects.filter(is_planning_scope=True).first()
        if not et:
            return None
        f = EntityField.objects.filter(
            entity_type='worker', target_entity=et.slug,
            field_type__in=['entity_select', 'multi_entity_select'],
        ).first()
        return f.key if f else None
