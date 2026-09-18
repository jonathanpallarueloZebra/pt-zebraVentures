
from rest_framework import serializers
from .models import ShiftDay


class ShiftDaySerializer(serializers.ModelSerializer):
    weekday_label = serializers.CharField(source='get_weekday_display', read_only=True)

    class Meta:
        model = ShiftDay
        fields = ['id', 'shift', 'weekday', 'weekday_label']
