from django.db import models


class Kind(models.Model):
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text='Nombre de icono Material')
    editable = models.BooleanField(default=True, help_text='Si es False los usuarios no pueden añadir ni eliminar valores')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Tipo de catalogo'
        verbose_name_plural = 'Tipos de catalogo'

    def __str__(self):
        return self.name


FIELD_TYPE_CHOICES = [
    ('text', 'Texto'),
    ('number', 'Numero'),
    ('float', 'Decimal'),   # p.ej. 37,5 horas semanales
    ('time', 'Hora'),
    ('color', 'Color'),
    ('boolean', 'Si/No'),
    ('textarea', 'Texto largo'),
]


class KindAttribute(models.Model):
    """
    Define un campo extra tipado que todos los valores de un Kind pueden tener.
    Ej: el Kind 'shift_slot' tiene atributos start_time (Hora) y end_time (Hora).
    """
    kind = models.ForeignKey(Kind, on_delete=models.CASCADE, related_name='attributes')
    key = models.CharField(max_length=50, help_text='Clave interna, ej: start_time')
    label = models.CharField(max_length=100, help_text='Texto visible al usuario, ej: Hora inicio')
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='text')
    required = models.BooleanField(default=False)
    default_value = models.CharField(max_length=500, blank=True)
    placeholder = models.CharField(max_length=200, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ['kind', 'key']
        verbose_name = 'Atributo de tipo'
        verbose_name_plural = 'Atributos de tipo'

    def __str__(self):
        return f'{self.kind.code}/{self.key} ({self.get_field_type_display()})'


class KindValue(models.Model):
    kind = models.ForeignKey(Kind, on_delete=models.CASCADE, related_name='values')
    code = models.CharField(max_length=50, db_index=True)
    label = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=20, blank=True, help_text='Color CSS, ej: #FF0000')
    order = models.IntegerField(default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'label']
        unique_together = ['kind', 'code']
        verbose_name = 'Valor de catalogo'
        verbose_name_plural = 'Valores de catalogo'

    def __str__(self):
        return f'{self.kind.code}/{self.code}: {self.label}'


class KindValueAttribute(models.Model):
    """
    Almacena el valor de un atributo tipado para un KindValue concreto.
    Ej: el valor 'morning' tiene start_time='07:00' y end_time='15:00'.
    """
    kind_value = models.ForeignKey(KindValue, on_delete=models.CASCADE, related_name='attributes')
    attribute = models.ForeignKey(KindAttribute, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(max_length=500, blank=True)

    class Meta:
        unique_together = ['kind_value', 'attribute']
        verbose_name = 'Valor de atributo'
        verbose_name_plural = 'Valores de atributo'

    def __str__(self):
        return f'{self.kind_value} | {self.attribute.key}={self.value}'
