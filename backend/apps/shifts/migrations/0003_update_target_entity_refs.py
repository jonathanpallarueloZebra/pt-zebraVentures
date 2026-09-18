"""
Update EntityField.target_entity from 'turnos' to 'shift' to match the new slug.
"""
from django.db import migrations


def forwards(apps, schema_editor):
    EntityField = apps.get_model('dynamic_fields', 'EntityField')
    EntityField.objects.filter(target_entity='turnos').update(target_entity='shift')


def backwards(apps, schema_editor):
    EntityField = apps.get_model('dynamic_fields', 'EntityField')
    EntityField.objects.filter(target_entity='shift').update(target_entity='turnos')


class Migration(migrations.Migration):
    dependencies = [
        ('shifts', '0002_migrate_turnos_to_shift'),
        ('dynamic_fields', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
