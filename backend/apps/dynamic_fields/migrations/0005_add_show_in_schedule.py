from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dynamic_fields', '0004_add_is_planning_scope'),
    ]

    operations = [
        migrations.AddField(
            model_name='entitytype',
            name='show_in_schedule',
            field=models.BooleanField(
                default=False,
                help_text='Si es True, los registros de esta entidad aparecen como pills asignables dentro de cada asignación del horario (ej: roles, secciones). Independiente del ámbito de planificación.',
            ),
        ),
    ]
