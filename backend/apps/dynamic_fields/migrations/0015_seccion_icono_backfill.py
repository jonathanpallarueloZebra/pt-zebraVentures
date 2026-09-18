"""
Data migration: rellena el campo `icono` de las secciones YA existentes.

El planificador ya asociaba un SVG a cada sección por su NOMBRE (mapa
`sectionIcon()` en el front). Aquí aplicamos el MISMO mapeo por nombre para
poblar `data['icono']` de cada EntityRecord de la entidad 'seccion' que aún no
tenga icono, de modo que las secciones existentes aparezcan con su icono en la
tabla/dropdown sin tener que asignarlo a mano una por una.

Los valores guardados coinciden con los ficheros de public/icons/sections/.
Idempotente: solo escribe si el registro no tiene ya un `icono` con valor.
Reversible: borra la clave `icono` que esta migración haya podido poner.
"""
from django.db import migrations

ENTITY_SLUG = 'seccion'
FIELD_KEY = 'icono'

# Mismo criterio que sectionIcon() del front: (substring del nombre normalizado) → fichero SVG.
# El orden importa poco porque los substrings no solapan.
NAME_MAP = [
    ('encarg', 'encargada'),
    ('caja', 'caja'),
    ('panad', 'panaderia'),
    ('pescad', 'pescaderia'),
    ('frut', 'fruteria'),
    ('carn', 'carniceria'),   # carne / carnicería
    ('charc', 'charcuteria'),
]


def _normalize(s):
    """Minúsculas + sin acentos + trim (equivalente a normalizeSection del front)."""
    import unicodedata
    s = (s or '').lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


def _icon_for(name):
    n = _normalize(name)
    for needle, file in NAME_MAP:
        if needle in n:
            return file
    return None


def backfill(apps, schema_editor):
    EntityRecord = apps.get_model('dynamic_fields', 'EntityRecord')
    for rec in EntityRecord.objects.filter(entity_type=ENTITY_SLUG):
        data = rec.data or {}
        if data.get(FIELD_KEY):          # ya tiene icono → respetar
            continue
        icon = _icon_for(data.get('nombre') or data.get('name') or '')
        if not icon:                     # sin match (p.ej. Repostería) → dejar vacío
            continue
        data[FIELD_KEY] = icon
        rec.data = data
        rec.save(update_fields=['data'])


def unbackfill(apps, schema_editor):
    EntityRecord = apps.get_model('dynamic_fields', 'EntityRecord')
    known = {f for _, f in NAME_MAP}
    for rec in EntityRecord.objects.filter(entity_type=ENTITY_SLUG):
        data = rec.data or {}
        # Solo quitamos si el valor es uno de los que pusimos nosotros.
        if data.get(FIELD_KEY) in known:
            data.pop(FIELD_KEY, None)
            rec.data = data
            rec.save(update_fields=['data'])


class Migration(migrations.Migration):

    dependencies = [
        ('dynamic_fields', '0014_seccion_icono_field'),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
