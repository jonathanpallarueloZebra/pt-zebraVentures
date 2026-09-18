from django.db import models
from django.conf import settings


class Worker(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='worker_profile',
    )
    name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)
    custom_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Trabajador'
        verbose_name_plural = 'Trabajadores'

    def __str__(self):
        return self.name


class WorkerPreference(models.Model):
    worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
        related_name='preferences',
    )
    shift_type = models.CharField(
        max_length=50,
        help_text='Code from catalog kind "shift_slot"',
    )

    class Meta:
        unique_together = ['worker', 'shift_type']
        verbose_name = 'Preferencia de turno'
        verbose_name_plural = 'Preferencias de turno'

    def __str__(self):
        return f'{self.worker.name} - {self.shift_type}'
