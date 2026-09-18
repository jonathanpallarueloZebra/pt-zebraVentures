from rest_framework import serializers
from .models import EntityField, EntityType, EntityRecord
from .mixins import _get_fields_cached


class EntityTypeSerializer(serializers.ModelSerializer):
    record_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = EntityType
        fields = ['id', 'slug', 'name', 'icon', 'order', 'show_in_sidebar', 'is_system', 'display_field', 'use_as_filter', 'is_planning_scope', 'show_in_schedule', 'record_count']
        read_only_fields = ['is_system']


class EntityRecordSerializer(serializers.ModelSerializer):
    entity_type_slug = serializers.CharField(source='entity_type.slug', read_only=True)
    field_schema = serializers.SerializerMethodField()

    class Meta:
        model = EntityRecord
        fields = ['id', 'entity_type', 'entity_type_slug', 'data', 'field_schema', 'created_at', 'updated_at']

    def get_field_schema(self, obj):
        fields = _get_fields_cached(obj.entity_type.slug)
        return [
            {
                'key': f.key,
                'label': f.label,
                'field_type': f.field_type,
                'required': f.required,
                'default_value': f.default_value,
                'placeholder': f.placeholder,
                'options': f.options,
                'show_in_list': f.show_in_list,
                'show_as_filter': f.show_as_filter,
                'allow_unassigned_filter': f.allow_unassigned_filter,
                'order': f.order,
                'kind_code': f.kind_code,
                'target_entity': f.target_entity,
                'display_key': f.display_key,
                'depends_on': f.depends_on,
                'depends_on_field': f.depends_on_field,
                'visible_when_field': f.visible_when_field,
                'visible_when_value': f.visible_when_value,
            }
            for f in fields
        ]


class EntityFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntityField
        fields = [
            'id', 'entity_type', 'key', 'label', 'field_type',
            'required', 'default_value', 'placeholder', 'options',
            'kind_code', 'target_entity', 'display_key',
            'depends_on', 'depends_on_field',
            'visible_when_field', 'visible_when_value',
            'allow_priority', 'help_text',
            'show_in_list', 'show_as_filter', 'allow_unassigned_filter',
            'order', 'active',
        ]
