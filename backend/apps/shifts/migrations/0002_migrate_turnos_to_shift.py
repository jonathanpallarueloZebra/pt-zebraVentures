"""
Data migration: move turnos EntityRecords → Shift model rows.

For each EntityRecord(entity_type='turnos'):
  - Creates a Shift with matching ID, name, color, icon, start_time, end_time
  - Preserves the ID so plan_json references (shift IDs as keys) keep working

Then updates the EntityType slug 'turnos' → 'shift' and changes it to
point to the model instead of pure EAV.
"""
from django.db import migrations


def forward(apps, schema_editor):
    EntityRecord = apps.get_model('dynamic_fields', 'EntityRecord')
    EntityType = apps.get_model('dynamic_fields', 'EntityType')
    EntityField = apps.get_model('dynamic_fields', 'EntityField')
    Shift = apps.get_model('shifts', 'Shift')

    # Move each turnos record to the Shift table
    for r in EntityRecord.objects.filter(entity_type='turnos').order_by('id'):
        data = r.data or {}
        Shift.objects.get_or_create(
            id=r.id,
            defaults={
                'name': data.get('nombre', f'Turno {r.id}'),
                'color': data.get('color', '#628db4'),
                'icon': data.get('icon', ''),
                'start_time': data.get('hora_llegada', '00:00'),
                'end_time': data.get('hora_salida', '00:00'),
                'active': True,
                'custom_data': {
                    k: v for k, v in data.items()
                    if k not in ('nombre', 'color', 'icon', 'hora_llegada', 'hora_salida')
                },
            },
        )

    # Delete the old EntityRecords and EntityFields for turnos
    EntityRecord.objects.filter(entity_type='turnos').delete()
    EntityField.objects.filter(entity_type='turnos').delete()

    # Update the EntityType: turnos → shift
    EntityType.objects.filter(slug='turnos').update(
        slug='shift',
        name='Turnos',
        show_in_sidebar=False,
        is_system=True,
    )


def reverse(apps, schema_editor):
    # Reverse is not practical — would need to recreate EAV records
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('shifts', '0001_initial_shift_model'),
        ('dynamic_fields', '0006_create_system_entities'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
