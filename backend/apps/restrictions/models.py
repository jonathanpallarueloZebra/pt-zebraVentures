from django.db import models


class Restriction(models.Model):
    ENGINE_CHOICES = [
        ('count', 'Conteo'),
        ('exclusion', 'Exclusion'),
        ('match', 'Coincidencia'),
        ('condition', 'Condición'),
        ('closed_day', 'Día de cierre'),
    ]
    SEVERITY_CHOICES = [
        ('error', 'Error'),
        ('warning', 'Aviso'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    engine = models.CharField(
        max_length=20,
        choices=ENGINE_CHOICES,
        default='count',
        help_text='Motor de evaluacion de la restriccion',
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text='Configuracion estructurada del motor',
    )
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        default='error',
    )
    message = models.CharField(
        max_length=300,
        blank=True,
        default='',
        help_text='Mensaje personalizado. Placeholders: {worker}, {count}, {limit}, {area}, {shift}, {role}, {worker1}, {worker2}',
    )
    active = models.BooleanField(default=True)
    customizable = models.BooleanField(
        default=False,
        help_text=(
            'Si esta activo, el cliente puede editar sus parametros (valores, severidad, '
            'mensaje y ambito), duplicarla y asignarla a tiendas desde su panel. '
            'Si no, es una restriccion fija: solo se puede activar o desactivar.'
        ),
    )
    duplicated_from = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='duplicates',
        help_text='Restriccion de la que se duplico. Solo traza: la copia es independiente.',
    )
    scope_records = models.JSONField(
        default=list,
        blank=True,
        help_text='IDs de registros del scope de planificacion a los que aplica. Vacio = aplica a todos.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Restriccion'
        verbose_name_plural = 'Restricciones'

    def __str__(self):
        return self.name


class ValidationResult(models.Model):
    weekly_plan = models.ForeignKey(
        'planning.WeeklyPlan',
        on_delete=models.CASCADE,
        related_name='validations',
    )
    is_valid = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Validation {self.pk} - {"OK" if self.is_valid else "FAIL"}'


class RestrictionViolation(models.Model):
    SEVERITY_CHOICES = [('warning', 'Warning'), ('error', 'Error')]
    validation_result = models.ForeignKey(
        ValidationResult,
        on_delete=models.CASCADE,
        related_name='violations',
    )
    restriction = models.ForeignKey(
        Restriction,
        on_delete=models.CASCADE,
    )
    message = models.TextField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    day_date = models.DateField(null=True)
    shift_type = models.CharField(max_length=10, null=True)

    class Meta:
        ordering = ['day_date', 'shift_type']

    def __str__(self):
        return f'[{self.severity}] {self.message}'
