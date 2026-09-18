from django.conf import settings
from django.db import models


class AbsenceType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    requires_approval = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Tipo de ausencia'
        verbose_name_plural = 'Tipos de ausencia'

    def __str__(self):
        return self.name


class AbsenceRequest(models.Model):
    worker = models.ForeignKey(
        'workers.Worker',
        on_delete=models.CASCADE,
        related_name='absence_requests',
    )
    type = models.ForeignKey(
        AbsenceType,
        on_delete=models.PROTECT,
        related_name='requests',
    )
    start_date = models.DateField()
    # end_date es opcional cuando la ausencia es "indefinida" (baja sin fecha
    # de reincorporación conocida). Si indefinite=False debe venir informada.
    end_date = models.DateField(null=True, blank=True)
    indefinite = models.BooleanField(
        default=False,
        help_text='Ausencia sin fecha de fin conocida. Mientras esté activa '
                  '(sin end_date), el empleado no se planifica.',
    )
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        default='pending',
        help_text='Code from catalog kind "absence_status"',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_absences',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Campos configurables desde AdminZebra (EntityType 'absence'), igual que en
    # Worker. Los campos de arriba siguen siendo COLUMNAS FIJAS a proposito: el
    # planificador lee worker, start_date, end_date e indefinite directamente
    # (ver covers() y _absences_map), asi que no pueden dejar de existir ni
    # volverse opcionales desde la configuracion.
    custom_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Solicitud de ausencia'
        verbose_name_plural = 'Solicitudes de ausencia'

    def __str__(self):
        return f'{self.worker.name} - {self.type.name} ({self.status})'

    @property
    def is_open_ended(self):
        """Ausencia indefinida aún sin fecha de fin: bloquea planificación
        desde start_date en adelante, sin límite superior (AC-4)."""
        return self.indefinite and self.end_date is None

    def covers(self, day):
        """¿La ausencia cubre la fecha `day`? Una indefinida sin fin cubre
        cualquier día >= start_date; una normal, dentro de [start, end]."""
        if day < self.start_date:
            return False
        if self.is_open_ended:
            return True
        return self.end_date is not None and day <= self.end_date
