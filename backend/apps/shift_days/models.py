
from django.db import models


WEEKDAY_CHOICES = [
    (0, 'Lunes'),
    (1, 'Martes'),
    (2, 'Miércoles'),
    (3, 'Jueves'),
    (4, 'Viernes'),
    (5, 'Sábado'),
    (6, 'Domingo'),
]


class ShiftDay(models.Model):
    """Relación turno ↔ día de la semana. Indica en qué días opera cada turno."""
    shift = models.ForeignKey(
        'shifts.Shift',
        on_delete=models.CASCADE,
        related_name='operating_days',
    )
    weekday = models.IntegerField(
        choices=WEEKDAY_CHOICES,
        help_text='0 = Lunes, 6 = Domingo (coincide con Python weekday())',
    )

    class Meta:
        unique_together = ('shift', 'weekday')
        ordering = ['shift', 'weekday']
        verbose_name = 'Día de turno'
        verbose_name_plural = 'Días de turno'

    def __str__(self):
        return f'{self.shift.name} – {self.get_weekday_display()}'
