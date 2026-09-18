"""Optional, EXPLICIT seed of Cabrero-specific configuration.

This is NOT run by `migrate` (migrations are schema-only — they must never seed
company data into a fresh deployment). Run it by hand, only on a Cabrero install:

    python manage.py seed_cabrero            # create what's missing
    python manage.py seed_cabrero --dry-run  # show what it would create

Creates Cabrero's worker EntityFields and the Saturday assignment rule.
Idempotent: safe to re-run. A brand-new company simply never runs this and
starts from a clean, fully UI-configurable schema.
"""
from django.core.management.base import BaseCommand


WORKER_FIELDS = [
    {'key': 'jornada_reducida', 'label': 'Jornada reducida', 'field_type': 'boolean',
     'default_value': 'false', 'show_in_list': True, 'order': 100},
    {'key': 'horas_semanales', 'label': 'Horas semanales', 'field_type': 'number',
     'default_value': '40', 'placeholder': '40', 'show_in_list': False, 'order': 101,
     'help_text': 'Horas contractuales por semana. Se usa como umbral dinámico en restricciones de tipo per_week_worker.'},
    {'key': 'horario_especial', 'label': 'Horario especial', 'field_type': 'boolean',
     'default_value': 'false', 'show_in_list': True, 'order': 102,
     'help_text': 'Marca que este trabajador tiene un horario individual fijo. El generador no le aplica reglas de rotación automáticas.'},
    {'key': 'turno_sabado', 'label': 'Turno sábado', 'field_type': 'entity_select',
     'target_entity': 'shift', 'show_in_list': False, 'order': 103,
     'help_text': 'Turno asignado los sábados. Si se especifica, sobreescribe el turno normal únicamente el sábado.'},
]

SATURDAY_RULE = {
    'name': 'Turno de sabado',
    'description': 'En sabado, los trabajadores con turno_sabado definido pasan a ese turno.',
    'config': {'conditionField': '', 'conditionValue': '',
               'overrideField': 'turno_sabado', 'pattern': 'weekday', 'weekday': 5},
    'active': True, 'priority': 100, 'scope_records': [],
}


class Command(BaseCommand):
    help = 'Seed Cabrero-specific config (worker fields + Saturday rule). NOT run by migrate.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Mostrar lo que se crearía sin escribir en la BD.')

    def handle(self, *args, **opts):
        from apps.dynamic_fields.models import EntityField
        from apps.assignments.models import AssignmentRule
        dry = opts['dry_run']
        prefix = '[DRY-RUN] crearía: ' if dry else 'creado: '
        created = 0

        for f in WORKER_FIELDS:
            if EntityField.objects.filter(entity_type='worker', key=f['key']).exists():
                self.stdout.write(f"= campo worker '{f['key']}' ya existe")
                continue
            created += 1
            self.stdout.write(self.style.SUCCESS(f"{prefix}campo worker '{f['key']}'"))
            if not dry:
                EntityField.objects.create(
                    entity_type='worker', key=f['key'], label=f['label'],
                    field_type=f['field_type'], required=f.get('required', False),
                    default_value=f.get('default_value', ''), placeholder=f.get('placeholder', ''),
                    kind_code=f.get('kind_code', ''), target_entity=f.get('target_entity', ''),
                    show_in_list=f.get('show_in_list', False), help_text=f.get('help_text', ''),
                    order=f['order'], active=True,
                )

        rule_exists = any(
            (r.config or {}).get('pattern') == 'weekday'
            and str((r.config or {}).get('weekday')) == '5'
            and (r.config or {}).get('overrideField') == 'turno_sabado'
            for r in AssignmentRule.objects.all()
        )
        if rule_exists:
            self.stdout.write('= regla de sábado ya existe')
        else:
            created += 1
            self.stdout.write(self.style.SUCCESS(f"{prefix}regla de asignación 'Turno de sabado'"))
            if not dry:
                AssignmentRule.objects.create(**SATURDAY_RULE)

        self.stdout.write(self.style.WARNING(
            f"\nTotal {'a crear' if dry else 'creado'}: {created}. "
            'Recuerda: este comando es OPCIONAL y específico de Cabrero; una empresa nueva no lo ejecuta.'
        ))
