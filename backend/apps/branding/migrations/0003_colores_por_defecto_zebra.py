"""Los colores por defecto pasan a ser los de Zebra.

El defecto anterior era un rojo (#EF4444) que no corresponde a ninguna marca:
una instalacion sin configurar salia con un color arbitrario. Ahora arranca con
el amarillo de Zebra y su variante oscura, los mismos `--p-brand-300` y
`--p-brand-500` que usa el frontend.

Solo cambia el valor por defecto de la columna. Las instalaciones que ya tengan
un color configurado conservan el suyo: esta migracion no toca las filas.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('branding', '0002_branding_date_picker_mode'),
    ]

    operations = [
        migrations.AlterField(
            model_name='branding',
            name='primary_color',
            field=models.CharField(default='#FCCF3F', help_text='Color principal (hex, ej: #FCCF3F)', max_length=20),
        ),
        migrations.AlterField(
            model_name='branding',
            name='primary_dark',
            field=models.CharField(default='#D8AB29', help_text='Variante oscura del color principal', max_length=20),
        ),
        migrations.AlterField(
            model_name='branding',
            name='company_name',
            field=models.CharField(default='Planificador de Turnos', max_length=200),
        ),
    ]
