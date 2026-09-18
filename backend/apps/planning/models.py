from django.db import models


class ShiftAssignment(models.Model):
    worker = models.ForeignKey(
        'workers.Worker',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Asignacion de turno'
        verbose_name_plural = 'Asignaciones de turno'

    def __str__(self):
        name = self.worker.name if self.worker else 'Sin asignar'
        return f'{name} ({self.start_time:%H:%M}-{self.end_time:%H:%M})'


class AreaAssignment(models.Model):
    shift_assignment = models.ForeignKey(
        ShiftAssignment,
        on_delete=models.CASCADE,
        related_name='areas',
    )
    area_record_id = models.PositiveIntegerField(
        help_text='EntityRecord ID of the area',
    )

    class Meta:
        unique_together = ['shift_assignment', 'area_record_id']
        verbose_name = 'Asignacion de area'
        verbose_name_plural = 'Asignaciones de area'


class DayPlan(models.Model):
    date = models.DateField(unique=True)
    day_name = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date']
        verbose_name = 'Plan diario'
        verbose_name_plural = 'Planes diarios'

    def __str__(self):
        return f'{self.day_name} {self.date}'


class DayPlanShift(models.Model):
    day_plan = models.ForeignKey(
        DayPlan,
        on_delete=models.CASCADE,
        related_name='shifts',
    )
    shift_type = models.CharField(
        max_length=20,
        help_text='Code from catalog kind "shift_slot"',
    )
    shift_assignment = models.ForeignKey(
        ShiftAssignment,
        on_delete=models.CASCADE,
    )

    class Meta:
        unique_together = ['day_plan', 'shift_type', 'shift_assignment']


class WeeklyPlan(models.Model):
    start_date = models.DateField()  # not unique alone — unique per (start_date, scope_entity_id)
    scope_entity_id = models.IntegerField(
        default=0,
        help_text='EntityRecord ID del ámbito de planificación (0 = sin ámbito / legado)',
    )
    plan_json = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('start_date', 'scope_entity_id')]
        ordering = ['-start_date']
        verbose_name = 'Plan semanal'
        verbose_name_plural = 'Planes semanales'

    def __str__(self):
        return f'Semana {self.start_date} (scope={self.scope_entity_id})'


class ClosedDay(models.Model):
    """Día de cierre (festivo local, cierre puntual) por fecha y ámbito.

    scope_entity_id = 0 → aplica a todos los ámbitos (cierre global).
    El generador no asigna turnos en días cerrados y el motor de
    restricciones (engine 'closed_day') marca como violación cualquier
    asignación existente en esas fechas.
    """
    date = models.DateField()
    scope_entity_id = models.IntegerField(
        default=0,
        help_text='EntityRecord ID del ámbito al que aplica el cierre (0 = todos)',
    )
    reason = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('date', 'scope_entity_id')]
        ordering = ['date']
        verbose_name = 'Día de cierre'
        verbose_name_plural = 'Días de cierre'

    def __str__(self):
        scope = 'global' if not self.scope_entity_id else f'scope {self.scope_entity_id}'
        return f'{self.date} ({scope}) {self.reason}'.strip()


class WeeklyPlanDay(models.Model):
    weekly_plan = models.ForeignKey(
        WeeklyPlan,
        on_delete=models.CASCADE,
        related_name='days',
    )
    day_plan = models.ForeignKey(
        DayPlan,
        on_delete=models.CASCADE,
    )
    day_order = models.IntegerField()

    class Meta:
        unique_together = ['weekly_plan', 'day_order']
        ordering = ['day_order']
