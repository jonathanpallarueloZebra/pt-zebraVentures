"""Schema-only placeholder — data seeding removed from migrations.

This migration ORIGINALLY created Cabrero-specific worker EntityFields
(jornada_reducida, horas_semanales, horario_especial, turno_sabado).

Per the deploy-per-client model, migrations must NOT seed company data into a
fresh deployment. Those fields are now created by the OPTIONAL management
command `python manage.py seed_cabrero` (run by hand only on a Cabrero install),
never automatically on `migrate`.

It is intentionally a NO-OP (not deleted) so that:
- existing Cabrero DBs — where it was already applied — keep their fields untouched;
- new-company deployments run `migrate` and get a clean, UI-configurable schema.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dynamic_fields', '0010_add_show_as_filter'),
    ]

    operations = []
