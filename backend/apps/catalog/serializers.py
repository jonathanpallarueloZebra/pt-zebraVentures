from rest_framework import serializers
from .models import Kind, KindAttribute, KindValue, KindValueAttribute


class KindAttributeSerializer(serializers.ModelSerializer):
    field_type_display = serializers.CharField(source='get_field_type_display', read_only=True)

    class Meta:
        model = KindAttribute
        fields = [
            'id', 'kind', 'key', 'label', 'field_type', 'field_type_display',
            'required', 'default_value', 'placeholder', 'order',
        ]


class KindValueAttributeSerializer(serializers.ModelSerializer):
    attribute_key = serializers.CharField(source='attribute.key', read_only=True)
    attribute_label = serializers.CharField(source='attribute.label', read_only=True)
    attribute_field_type = serializers.CharField(source='attribute.field_type', read_only=True)

    class Meta:
        model = KindValueAttribute
        fields = [
            'id', 'kind_value', 'attribute', 'attribute_key',
            'attribute_label', 'attribute_field_type', 'value',
        ]


class KindValueSerializer(serializers.ModelSerializer):
    kind_code = serializers.CharField(source='kind.code', read_only=True)
    attributes = KindValueAttributeSerializer(many=True, read_only=True)

    class Meta:
        model = KindValue
        fields = [
            'id', 'kind', 'kind_code', 'code', 'label',
            'description', 'icon', 'color', 'order',
            'active', 'attributes',
        ]


class KindSerializer(serializers.ModelSerializer):
    values = KindValueSerializer(many=True, read_only=True)
    attributes = KindAttributeSerializer(many=True, read_only=True)

    class Meta:
        model = Kind
        fields = [
            'id', 'code', 'name', 'description', 'icon',
            'editable', 'active', 'attributes', 'values',
        ]


class KindListSerializer(serializers.ModelSerializer):
    value_count = serializers.IntegerField(source='values.count', read_only=True)

    class Meta:
        model = Kind
        fields = ['id', 'code', 'name', 'description', 'icon', 'editable', 'active', 'value_count']
