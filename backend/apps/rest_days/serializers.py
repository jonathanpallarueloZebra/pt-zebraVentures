from rest_framework import serializers
from .models import RestDay
from apps.workers.models import Worker


class RestDaySerializer(serializers.ModelSerializer):
    workerId = serializers.PrimaryKeyRelatedField(
        source='worker', queryset=Worker.objects.all(),
    )
    worker_name = serializers.CharField(source='worker.name', read_only=True)

    class Meta:
        model = RestDay
        fields = ['id', 'workerId', 'worker_name', 'date', 'reason']
