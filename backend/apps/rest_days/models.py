from django.db import models


class RestDay(models.Model):
    worker = models.ForeignKey(
        'workers.Worker',
        on_delete=models.CASCADE,
        related_name='rest_days',
    )
    date = models.DateField()
    reason = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['worker', 'date']
        ordering = ['date']
        verbose_name = 'Dia de descanso'
        verbose_name_plural = 'Dias de descanso'

    def __str__(self):
        return f'{self.worker.name} - {self.date}'
