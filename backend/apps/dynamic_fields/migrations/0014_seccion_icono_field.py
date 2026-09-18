"""
Data migration: añade a la entidad 'seccion' un campo de tipo `icon`.

Permite asignar un icono a cada sección desde /entities/seccion (crear/editar),
que luego se mostrará a la izquierda del nombre en el planificador.
Ticket "[BE] Crear tipo de campo icono" (AC-4).

Idempotente: usa get_or_create sobre (entity_type, key), que es unique_together.
Solo crea el campo si la entidad 'seccion' existe.
"""
from django.db import migrations


ENTITY_SLUG = 'seccion'
FIELD_KEY = 'icono'


def add_icono_field(apps, schema_editor):
    EntityType = apps.get_model('dynamic_fields', 'EntityType')
    EntityField = apps.get_model('dynamic_fields', 'EntityField')

    # Solo si existe la entidad 'seccion' (no romper en instalaciones sin ella).
    if not EntityType.objects.filter(slug=ENTITY_SLUG).exists():
        return

    # Orden: detrás del último campo existente de la entidad.
    last = (
        EntityField.objects.filter(entity_type=ENTITY_SLUG)
        .order_by('-order')
        .first()
    )
    next_order = (last.order + 1) if last else 0

    EntityField.objects.get_or_create(
        entity_type=ENTITY_SLUG,
        key=FIELD_KEY,
        defaults={
            'label': 'Icono',
            'field_type': 'icon',
            'required': False,
            'help_text': 'Icono que se mostrará junto al nombre de la sección.',
            'show_in_list': True,
            'order': next_order,
            'active': True,
        },
    )


def remove_icono_field(apps, schema_editor):
    EntityField = apps.get_model('dynamic_fields', 'EntityField')
    EntityField.objects.filter(entity_type=ENTITY_SLUG, key=FIELD_KEY).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('dynamic_fields', '0013_alter_entityfield_field_type'),
    ]

    operations = [
        migrations.RunPython(add_icono_field, remove_icono_field),
    ]
