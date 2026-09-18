"""
Mixin for entity serializers that adds dynamic field support.
"""
from django.core.cache import cache as django_cache
from rest_framework import serializers

from apps.dynamic_fields.models import EntityField

# Module-level cache: entity_type -> list of EntityField objects
# Invalidated when fields are created/updated/deleted via the API
_fields_cache: dict = {}


def _get_fields_cached(entity_type: str):
    if entity_type not in _fields_cache:
        _fields_cache[entity_type] = list(
            EntityField.objects.filter(entity_type=entity_type, active=True).order_by('order')
        )
    return _fields_cache[entity_type]


def invalidate_fields_cache(entity_type: str | None = None):
    """Call this after any EntityField create/update/delete."""
    if entity_type:
        _fields_cache.pop(entity_type, None)
    else:
        _fields_cache.clear()


class DynamicFieldsMixin:
    """Add custom_data + field_schema to serialized entity."""

    _entity_type = None

    def _get_entity_type(self):
        if self._entity_type:
            return self._entity_type
        model = self.Meta.model
        return model.__name__.lower()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        etype = self._get_entity_type()
        fields = _get_fields_cached(etype)
        schema = []
        for f in fields:
            field_def = {
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
                'allow_priority': f.allow_priority,
                'help_text': f.help_text,
            }
            if f.field_type in ('catalog_select', 'multi_catalog_select') and f.kind_code:
                field_def['kind_code'] = f.kind_code
            if f.field_type in ('entity_select', 'multi_entity_select') and f.target_entity:
                field_def['target_entity'] = f.target_entity
                if f.display_key:
                    field_def['display_key'] = f.display_key
            if f.depends_on:
                field_def['depends_on'] = f.depends_on
            if f.depends_on_field:
                field_def['depends_on_field'] = f.depends_on_field
            if f.visible_when_field:
                field_def['visible_when_field'] = f.visible_when_field
                field_def['visible_when_value'] = f.visible_when_value
            schema.append(field_def)
        custom = getattr(instance, 'custom_data', None) or {}
        for f in fields:
            if f.key not in custom:
                custom[f.key] = f.default_value
        data['custom_data'] = custom
        data['field_schema'] = schema
        return data

    def _missing_required(self, custom_data):
        """Claves obligatorias (EntityField.required) que llegan sin valor.

        La lista de obligatorios NO se duplica aquí: sale de la misma
        configuración que el front recibe en `field_schema`, así que marcar o
        desmarcar un campo en Admin Zebra cambia las dos validaciones a la vez.

        Se consideran vacíos None, '' y las listas/objetos vacíos (los
        multi_*_select guardan listas). El 0 y el False SÍ son valores válidos:
        un "Turnos máx./semana = 0" o un boolean en false están rellenos.
        """
        etype = self._get_entity_type()
        cd = custom_data or {}
        faltan = []
        for f in _get_fields_cached(etype):
            if not f.required:
                continue
            # Un default en la config rellena el campo solo, así que no falta.
            if str(f.default_value or ''):
                continue
            v = cd.get(f.key)
            if v is None or v == '' or v == [] or v == {}:
                faltan.append(f)
        return faltan

    def _validate_required(self, custom_data):
        """Corta la creación si falta algún obligatorio (mismo error por campo
        que usa DRF, para que el front lo pinte en el campo que toca)."""
        faltan = self._missing_required(custom_data)
        if not faltan:
            return
        raise serializers.ValidationError({
            'custom_data': {f.key: f'"{f.label}" es obligatorio.' for f in faltan},
        })

    def _apply_defaults(self, custom_data):
        etype = self._get_entity_type()
        fields = _get_fields_cached(etype)
        result = dict(custom_data) if custom_data else {}
        for f in fields:
            if f.key not in result:
                result[f.key] = f.default_value
        return result

    def validate(self, attrs):
        """Exige los campos obligatorios de la configuración AL CREAR.

        Va en validate() y no en create() a propósito: los serializers concretos
        (Worker, Shift) sobreescriben create() sin llamar a super(), así que un
        create() aquí no se ejecutaría. validate() lo corre DRF siempre.

        Solo al crear (`self.instance is None`). En la edición no se exige: hay
        fichas cargadas de antes con obligatorios vacíos (p.ej. 103 empleados
        sin 'regimen') y bloquearlas aquí impediría editarles cualquier otro
        dato, que no es lo que pide la tarea.
        """
        attrs = super().validate(attrs)
        if self.instance is None:
            self._validate_required(attrs.get('custom_data'))
        return attrs

    def create(self, validated_data):
        cd = validated_data.get('custom_data') or {}
        validated_data['custom_data'] = self._apply_defaults(cd)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'custom_data' in validated_data:
            existing = getattr(instance, 'custom_data', None) or {}
            incoming = validated_data['custom_data'] or {}
            merged = {**existing, **incoming}
            validated_data['custom_data'] = self._apply_defaults(merged)
        return super().update(instance, validated_data)
