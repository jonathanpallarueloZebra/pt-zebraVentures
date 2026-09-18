from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('restrictions', '0004_alter_restriction_engine'),
    ]

    operations = [
        migrations.AddField(
            model_name='restriction',
            name='customizable',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Si esta activo, el cliente puede editar sus parametros (valores, severidad, '
                    'mensaje y ambito), duplicarla y asignarla a tiendas desde su panel. '
                    'Si no, es una restriccion fija: solo se puede activar o desactivar.'
                ),
            ),
        ),
        migrations.AddField(
            model_name='restriction',
            name='duplicated_from',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='duplicates',
                to='restrictions.restriction',
                help_text='Restriccion de la que se duplico. Solo traza: la copia es independiente.',
            ),
        ),
    ]
