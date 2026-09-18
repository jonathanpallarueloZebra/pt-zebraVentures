
from django.db import models


class Shift(models.Model):
    name = models.CharField(max_length=100)
    start_time = models.TimeField(help_text='Hora de inicio del turno')
    end_time = models.TimeField(help_text='Hora de fin del turno')
    # ── Vigencia por rango de fechas ─────────────────────────────────────
    # Turno "normal": valid_from = valid_to = NULL → siempre operativo.
    # Turno "extra": con rango de fechas → solo operativo dentro de [from, to]
    # (refuerzos puntuales: Navidad, puentes, fiestas locales…). Los extremos
    # son inclusivos y cualquiera de los dos puede ir suelto (solo inicio =
    # activo indefinidamente a partir de esa fecha; solo fin = activo hasta
    # esa fecha).
    valid_from = models.DateField(
        null=True, blank=True,
        help_text='Inicio de vigencia (inclusive). Vacío = sin límite inferior.',
    )
    valid_to = models.DateField(
        null=True, blank=True,
        help_text='Fin de vigencia (inclusive). Vacío = sin límite superior.',
    )
    custom_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Turno'
        verbose_name_plural = 'Turnos'

    def __str__(self):
        return self.name

    # ── Helpers de vigencia ──────────────────────────────────────────────
    @property
    def has_validity(self):
        """True si el turno tiene algún límite de vigencia (turno 'extra')."""
        return self.valid_from is not None or self.valid_to is not None

    def is_active_on(self, day):
        """¿El turno está vigente en la fecha `day` (datetime.date)?

        Un turno sin rango (normal) está siempre vigente. Con rango, la fecha
        debe caer dentro de [valid_from, valid_to] (extremos inclusivos).
        """
        if self.valid_from is not None and day < self.valid_from:
            return False
        if self.valid_to is not None and day > self.valid_to:
            return False
        return True

    def is_expired(self, today):
        """True si la vigencia del turno ya finalizó respecto a `today`.

        Se usa para bloquear NUEVAS asignaciones (AC-5) sin borrar el turno,
        que permanece como registro histórico.
        """
        return self.valid_to is not None and self.valid_to < today
