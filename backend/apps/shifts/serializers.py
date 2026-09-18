
from rest_framework import serializers
from apps.dynamic_fields.mixins import DynamicFieldsMixin
from apps.shift_days.models import ShiftDay, WEEKDAY_CHOICES
from .models import Shift


class ShiftSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    _entity_type = 'shift'
    operating_days = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
        write_only=True,
    )

    class Meta:
        model = Shift
        fields = [
            'id', 'name', 'start_time', 'end_time',
            'valid_from', 'valid_to', 'custom_data', 'operating_days',
        ]

    def validate(self, attrs):
        # super() = DynamicFieldsMixin.validate (campos obligatorios al crear).
        attrs = super().validate(attrs)

        # El inicio de vigencia no puede ser posterior al fin (AC-1).
        # En un PATCH parcial toma el valor entrante o, si no viene, el actual.
        instance = getattr(self, 'instance', None)
        valid_from = attrs.get('valid_from', getattr(instance, 'valid_from', None))
        valid_to = attrs.get('valid_to', getattr(instance, 'valid_to', None))
        if valid_from and valid_to and valid_from > valid_to:
            raise serializers.ValidationError({
                'valid_to': 'La fecha de fin de vigencia no puede ser anterior a la de inicio.',
            })

        # La hora de fin no puede ser anterior o igual a la de inicio.
        #
        # Sin esto se pudo guardar un turno 15:36-13:40, es decir -1,93 horas.
        # No es cosmetico: las horas de cada asignacion se calculan como
        # fin - inicio, asi que un turno invertido resta horas al contador
        # semanal y el tope por contrato deja de cuadrar. Un turno de 0 horas
        # tampoco tiene sentido.
        start = attrs.get('start_time', getattr(instance, 'start_time', None))
        end = attrs.get('end_time', getattr(instance, 'end_time', None))
        if start and end and end <= start:
            raise serializers.ValidationError({
                'end_time': (
                    'La hora de fin debe ser posterior a la de inicio '
                    f'(recibido {start:%H:%M}-{end:%H:%M}). Un turno que cruza '
                    'medianoche no está soportado.'
                ),
            })
        return attrs

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['operating_days'] = sorted(
            instance.operating_days.values_list('weekday', flat=True)
        )
        return ret

    def create(self, validated_data):
        days = validated_data.pop('operating_days', None)
        shift = super().create(validated_data)
        if days is not None:
            self._sync_days(shift, days)
        return shift

    def update(self, instance, validated_data):
        days = validated_data.pop('operating_days', None)
        shift = super().update(instance, validated_data)
        if days is not None:
            self._sync_days(shift, days)
        return shift

    def _sync_days(self, shift, weekday_list):
        """Replace the shift's operating days with the given list of weekday ints."""
        shift.operating_days.all().delete()
        ShiftDay.objects.bulk_create([
            ShiftDay(shift=shift, weekday=d) for d in set(weekday_list)
        ])
