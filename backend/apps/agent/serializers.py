from rest_framework import serializers


class AgentMessageSerializer(serializers.Serializer):
    message = serializers.CharField()


class AgentResponseSerializer(serializers.Serializer):
    response = serializers.CharField()
