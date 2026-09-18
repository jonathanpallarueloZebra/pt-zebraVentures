from rest_framework import serializers
from .models import AssignmentRule


class AssignmentRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignmentRule
        fields = ['id', 'name', 'description', 'config', 'active', 'priority', 'scope_records']
