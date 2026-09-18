from django.db import models


class Branding(models.Model):
    """
    Single-row table — one record per deployed instance.
    Stores the client-specific look & feel: name, logo, colors.
    """
    company_name = models.CharField(max_length=200, default='Planificador de Turnos')
    tagline = models.CharField(max_length=300, blank=True)
    logo = models.ImageField(
        upload_to='branding/',
        blank=True,
        null=True,
        help_text='Logo de la empresa (PNG/SVG recomendado, fondo transparente)',
    )
    favicon = models.ImageField(
        upload_to='branding/',
        blank=True,
        null=True,
        help_text='Icono de la pestana del navegador (32x32 px)',
    )
    primary_color = models.CharField(
        max_length=20, default='#EF4444',
        help_text='Color principal (hex, ej: #EF4444)',
    )
    primary_dark = models.CharField(
        max_length=20, default='#B91C1C',
        help_text='Variante oscura del color principal',
    )

    # ── Comportamiento del selector de fechas ────────────────────────────
    # La unidad de trabajo cambia segun el proyecto: en Cabrero siempre se
    # planifica la semana completa, pero otros planificadores necesitan elegir
    # un rango libre. Se configura aqui para no tocar codigo por proyecto.
    DATE_PICKER_WEEK = 'week'
    DATE_PICKER_RANGE = 'range'
    DATE_PICKER_MODES = [
        (DATE_PICKER_WEEK, 'Por semanas'),
        (DATE_PICKER_RANGE, 'Por rango de fechas'),
    ]
    date_picker_mode = models.CharField(
        max_length=10,
        choices=DATE_PICKER_MODES,
        # 'range' por defecto: es el comportamiento que ya tenian los proyectos
        # existentes, asi que ninguno cambia de conducta al desplegar esto.
        default=DATE_PICKER_RANGE,
        help_text=(
            'Por semanas: al pulsar un dia se selecciona su semana completa. '
            'Por rango: el usuario elige fecha de inicio y de fin.'
        ),
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuracion de marca'
        verbose_name_plural = 'Configuracion de marca'

    def __str__(self):
        return self.company_name

    def save(self, *args, **kwargs):
        # Enforce single-row: always use pk=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
