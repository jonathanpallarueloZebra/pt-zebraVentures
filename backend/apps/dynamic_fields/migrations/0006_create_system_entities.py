"""
Data migration: create system entity types and the 'dias' catalog.

Creates:
- Kind 'dias' + 7 KindValues (Lunes..Domingo)
- EntityType 'worker'  (is_system=True)
- EntityType 'turnos'  (is_system=True) + 6 EntityFields
"""
from django.db import migrations


def create_system_data(apps, schema_editor):
    Kind = apps.get_model('catalog', 'Kind')
    KindValue = apps.get_model('catalog', 'KindValue')
    EntityType = apps.get_model('dynamic_fields', 'EntityType')
    EntityField = apps.get_model('dynamic_fields', 'EntityField')

    # ── 1. Catalog: dias ───────────────────────────────────
    dias_kind, _ = Kind.objects.get_or_create(
        code='dias',
        defaults={
            'name': 'Dias de la semana',
            'description': 'Dias de la semana (lunes a domingo)',
            'icon': 'calendar_today',
            'editable': False,
            'active': True,
        },
    )
    DIAS = [
        ('lunes',     'Lunes',     1),
        ('martes',    'Martes',    2),
        ('miercoles', 'Miercoles', 3),
        ('jueves',    'Jueves',    4),
        ('viernes',   'Viernes',   5),
        ('sabado',    'Sabado',    6),
        ('domingo',   'Domingo',   7),
    ]
    for code, label, order in DIAS:
        KindValue.objects.get_or_create(
            kind=dias_kind,
            code=code,
            defaults={'label': label, 'order': order, 'active': True},
        )

    # ── 2. EntityType: worker ──────────────────────────────
    EntityType.objects.get_or_create(
        slug='worker',
        defaults={
            'name': 'Empleados',
            'icon': 'badge',
            'order': 0,
            'show_in_sidebar': False,
            'is_system': True,
            'display_field': 'name',
            'use_as_filter': False,
            'is_planning_scope': False,
            'show_in_schedule': False,
        },
    )

    # ── 3. EntityType: turnos ──────────────────────────────
    EntityType.objects.get_or_create(
        slug='turnos',
        defaults={
            'name': 'Turnos',
            'icon': 'schedule',
            'order': 1,
            'show_in_sidebar': True,
            'is_system': True,
            'display_field': 'nombre',
            'use_as_filter': False,
            'is_planning_scope': False,
            'show_in_schedule': False,
        },
    )

    TURNO_FIELDS = [
        {
            'key': 'nombre',
            'label': 'Nombre',
            'field_type': 'text',
            'required': True,
            'placeholder': 'Ej: Manana',
            'show_in_list': True,
            'order': 1,
        },
        {
            'key': 'color',
            'label': 'Color',
            'field_type': 'color',
            'required': False,
            'default_value': '#628db4',
            'show_in_list': True,
            'order': 2,
        },
        {
            'key': 'icon',
            'label': 'Icono',
            'field_type': 'text',
            'required': False,
            'placeholder': 'Ej: wb_sunny',
            'show_in_list': False,
            'order': 3,
        },
        {
            'key': 'hora_llegada',
            'label': 'Hora de entrada',
            'field_type': 'time',
            'required': True,
            'placeholder': '07:00',
            'show_in_list': True,
            'order': 4,
        },
        {
            'key': 'hora_salida',
            'label': 'Hora de salida',
            'field_type': 'time',
            'required': True,
            'placeholder': '15:00',
            'show_in_list': True,
            'order': 5,
        },
        {
            'key': 'dias',
            'label': 'Dias aplicables',
            'field_type': 'multi_catalog_select',
            'required': False,
            'kind_code': 'dias',
            'show_in_list': False,
            'order': 6,
        },
    ]

    for fdata in TURNO_FIELDS:
        EntityField.objects.get_or_create(
            entity_type='turnos',
            key=fdata['key'],
            defaults={
                'label': fdata['label'],
                'field_type': fdata['field_type'],
                'required': fdata.get('required', False),
                'default_value': fdata.get('default_value', ''),
                'placeholder': fdata.get('placeholder', ''),
                'kind_code': fdata.get('kind_code', ''),
                'show_in_list': fdata.get('show_in_list', False),
                'order': fdata['order'],
                'active': True,
            },
        )


def reverse(apps, schema_editor):
    EntityField = apps.get_model('dynamic_fields', 'EntityField')
    EntityType = apps.get_model('dynamic_fields', 'EntityType')
    KindValue = apps.get_model('catalog', 'KindValue')
    Kind = apps.get_model('catalog', 'Kind')

    EntityField.objects.filter(entity_type='turnos').delete()
    EntityType.objects.filter(slug__in=['worker', 'turnos']).delete()
    Kind.objects.filter(code='dias').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('dynamic_fields', '0005_add_show_in_schedule'),
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_system_data, reverse),
    ]
