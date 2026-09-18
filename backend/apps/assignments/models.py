from django.db import models


class AssignmentRule(models.Model):
    PATTERN_CHOICES = [
        ('always', 'Siempre (override directo)'),
        ('alternate_weekly', 'Alternar por semanas'),
        ('alternate_daily', 'Alternar por dias'),
        ('weekday', 'Solo en un dia de la semana'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text='Configuracion: conditionField, conditionValue, overrideField, pattern, frequencyField/frequencyValue',
    )
    active = models.BooleanField(default=True)
    priority = models.IntegerField(
        default=0,
        help_text='Prioridad de aplicacion (menor = se aplica primero)',
    )
    scope_records = models.JSONField(
        default=list,
        blank=True,
        help_text='IDs de registros del scope de planificacion a los que aplica. Vacio = aplica a todos.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority', 'name']
        verbose_name = 'Regla de asignacion'
        verbose_name_plural = 'Reglas de asignacion'

    def __str__(self):
        return self.name
