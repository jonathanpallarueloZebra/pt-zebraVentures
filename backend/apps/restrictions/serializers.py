from rest_framework import serializers
from .models import Restriction


class RestrictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restriction
        fields = [
            'id', 'name', 'description', 'engine', 'config', 'severity',
            'active', 'message', 'scope_records', 'customizable', 'duplicated_from',
        ]
        read_only_fields = ['duplicated_from']
