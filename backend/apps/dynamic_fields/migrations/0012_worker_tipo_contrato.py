"""
Data migration: create the stable 'tipo_contrato' catalog + worker field.

Antes esto solo existía en el seed de demostración (seed_demo). Se promueve a
migración estable para que llegue a producción con `migrate` y el widget
"Empleados ETT" del dashboard tenga el dato real (workers con
custom_data.tipo_contrato == 'ett').

Creates:
- Kind 'tipo_contrato' (editable: el usuario puede añadir más valores)
- KindValues: plantilla, volante, ett
- EntityField worker.tipo_contrato (catalog_select)

Idempotente (get_or_create): seguro de re-ejecutar y compatible con entornos
que ya tengan estos datos por haber corrido seed_demo.
"""
from django.db import migrations


CONTRATOS = [
    ('plantilla', 'Plantilla fija', 1),
    ('volante', 'Volante (cubre su zona)', 2),
    ('ett', 'ETT', 3),
]


def create_tipo_contrato(apps, schema_editor):
    Kind = apps.get_model('catalog', 'Kind')
    KindValue = apps.get_model('catalog', 'KindValue')
    EntityField = apps.get_model('dynamic_fields', 'EntityField')

    kind, _ = Kind.objects.get_or_create(
        code='tipo_contrato',
        defaults={
            'name': 'Tipo de contrato',
            'description': 'Clasificación del trabajador (plantilla, volante, ETT)',
            'icon': 'badge',
            'editable': True,
            'active': True,
        },
    )

    for code, label, order in CONTRATOS:
        KindValue.objects.get_or_create(
            kind=kind,
            code=code,
            defaults={'label': label, 'order': order, 'active': True},
        )

    EntityField.objects.get_or_create(
        entity_type='worker',
        key='tipo_contrato',
        defaults={
            'label': 'Tipo de contrato',
            'field_type': 'catalog_select',
            'kind_code': 'tipo_contrato',
            'required': False,
            'show_in_list': True,
            'show_as_filter': True,
            'order': 4,
            'active': True,
        },
    )


def reverse(apps, schema_editor):
    Kind = apps.get_model('catalog', 'Kind')
    EntityField = apps.get_model('dynamic_fields', 'EntityField')

    EntityField.objects.filter(entity_type='worker', key='tipo_contrato').delete()
    # Elimina el Kind y sus KindValues (cascade). No borra custom_data de los
    # workers ya guardados: ese JSON permanece intacto.
    Kind.objects.filter(code='tipo_contrato').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('dynamic_fields', '0011_add_worker_schedule_fields'),
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_tipo_contrato, reverse),
    ]
