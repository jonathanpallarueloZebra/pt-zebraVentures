"""
Tests for the EAV system: EntityType, EntityField, EntityRecord,
DynamicFieldsMixin, and Worker custom_data integration.
"""
import pytest
from conftest import (
    EntityTypeFactory, EntityFieldFactory, EntityRecordFactory,
    WorkerFactory,
)

pytestmark = pytest.mark.django_db


# ═══════════════════════════════════════════════════════════════════════════
# EntityType
# ═══════════════════════════════════════════════════════════════════════════

class TestEntityType:
    def test_create_entity_type(self):
        et = EntityTypeFactory(slug="zona", name="Zona")
        assert et.slug == "zona"
        assert et.name == "Zona"
        assert str(et) == "Zona"

    def test_slug_unique(self):
        from apps.dynamic_fields.models import EntityType
        EntityType.objects.create(slug="unique_slug", name="A")
        with pytest.raises(Exception):
            EntityType.objects.create(slug="unique_slug", name="B")

    def test_default_flags(self):
        et = EntityTypeFactory()
        assert et.is_system is False
        assert et.is_planning_scope is False
        assert et.show_in_schedule is False
        assert et.show_in_sidebar is True

    def test_display_field_default(self):
        et = EntityTypeFactory()
        assert et.display_field == "name"


# ═══════════════════════════════════════════════════════════════════════════
# EntityField
# ═══════════════════════════════════════════════════════════════════════════

class TestEntityField:
    def test_create_field(self):
        f = EntityFieldFactory(
            entity_type="worker", key="zona", label="Zona",
            field_type="entity_select", target_entity="zona",
        )
        assert f.key == "zona"
        assert f.field_type == "entity_select"
        assert str(f) == "worker → Zona"

    def test_field_unique_per_entity(self):
        from apps.dynamic_fields.models import EntityField
        EntityField.objects.create(entity_type="worker", key="dup_key", label="A", field_type="text")
        with pytest.raises(Exception):
            EntityField.objects.create(entity_type="worker", key="dup_key", label="B", field_type="text")

    def test_same_key_different_entity(self):
        """Same key is allowed for different entity types."""
        EntityFieldFactory(entity_type="worker", key="name")
        f2 = EntityFieldFactory(entity_type="tienda", key="name")
        assert f2.pk is not None

    def test_all_field_types_valid(self):
        from apps.dynamic_fields.models import EntityField
        valid = {c[0] for c in EntityField.FIELD_TYPES}
        expected = {
            "text", "number", "boolean", "color", "time", "select",
            "textarea", "catalog_select", "multi_catalog_select",
            "entity_select", "multi_entity_select",
        }
        assert valid == expected

    def test_depends_on_fields(self):
        f = EntityFieldFactory(
            entity_type="worker", key="tienda_pref",
            field_type="entity_select", target_entity="tienda",
            depends_on="zona", depends_on_field="zona",
        )
        assert f.depends_on == "zona"
        assert f.depends_on_field == "zona"

    def test_allow_priority(self):
        f = EntityFieldFactory(
            entity_type="worker", key="roles",
            field_type="multi_entity_select", allow_priority=True,
        )
        assert f.allow_priority is True


# ═══════════════════════════════════════════════════════════════════════════
# EntityRecord (JSONB data)
# ═══════════════════════════════════════════════════════════════════════════

class TestEntityRecord:
    def test_create_record(self, tienda_et):
        rec = EntityRecordFactory(
            entity_type=tienda_et,
            data={"nombre": "Tienda 1", "zona": 8},
        )
        assert rec.data["nombre"] == "Tienda 1"
        assert rec.data["zona"] == 8

    def test_record_str(self, tienda_et):
        rec = EntityRecordFactory(
            entity_type=tienda_et,
            data={"name": "Test"},
        )
        assert "tienda" in str(rec)

    def test_empty_data_allowed(self, tienda_et):
        rec = EntityRecordFactory(entity_type=tienda_et, data={})
        assert rec.data == {}

    def test_nested_jsonb(self, tienda_et):
        """JSONB supports nested structures."""
        rec = EntityRecordFactory(
            entity_type=tienda_et,
            data={"meta": {"geo": [41.65, -0.88], "active": True}},
        )
        assert rec.data["meta"]["geo"] == [41.65, -0.88]

    def test_jsonb_query_filter(self, tienda_et):
        """Can filter records by JSONB field values."""
        from apps.dynamic_fields.models import EntityRecord
        EntityRecordFactory(entity_type=tienda_et, data={"zona": 8})
        EntityRecordFactory(entity_type=tienda_et, data={"zona": 9})
        EntityRecordFactory(entity_type=tienda_et, data={"zona": 8})
        assert EntityRecord.objects.filter(data__zona=8).count() == 2

    def test_jsonb_contains_filter(self, tienda_et):
        from apps.dynamic_fields.models import EntityRecord
        EntityRecordFactory(
            entity_type=tienda_et,
            data={"nombre": "T1", "zona": 8, "active": True},
        )
        qs = EntityRecord.objects.filter(data__contains={"zona": 8, "active": True})
        assert qs.count() == 1


# ═══════════════════════════════════════════════════════════════════════════
# DynamicFieldsMixin (Worker integration)
# ═══════════════════════════════════════════════════════════════════════════

class TestDynamicFieldsMixin:
    def test_defaults_applied_on_create(self):
        EntityFieldFactory(
            entity_type="worker", key="turno",
            field_type="text", default_value="morning",
        )
        from apps.dynamic_fields.mixins import invalidate_fields_cache
        invalidate_fields_cache("worker")

        from rest_framework.test import APIClient
        client = APIClient()
        resp = client.post("/api/workers/", {
            "name": "DefaultTest",
            "custom_data": {},
            "preferredShifts": [],
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["custom_data"]["turno"] == "morning"
        invalidate_fields_cache("worker")

    def test_merge_on_update(self):
        EntityFieldFactory(entity_type="worker", key="nota", field_type="text")
        from apps.dynamic_fields.mixins import invalidate_fields_cache
        invalidate_fields_cache("worker")

        w = WorkerFactory(custom_data={"nota": "old", "extra": "keep"})
        from rest_framework.test import APIClient
        client = APIClient()
        resp = client.patch(f"/api/workers/{w.id}/", {
            "custom_data": {"nota": "new"},
            "preferredShifts": [],
        }, format="json")
        assert resp.status_code == 200
        assert resp.data["custom_data"]["nota"] == "new"
        assert resp.data["custom_data"]["extra"] == "keep"
        invalidate_fields_cache("worker")

    def test_field_schema_includes_dependencies(self):
        EntityFieldFactory(
            entity_type="worker", key="zona_dep",
            field_type="entity_select", target_entity="zona",
            display_key="nombre", depends_on="region", depends_on_field="region",
        )
        from apps.dynamic_fields.mixins import invalidate_fields_cache
        invalidate_fields_cache("worker")

        w = WorkerFactory()
        from apps.workers.serializers import WorkerSerializer
        ser = WorkerSerializer(w)
        schema = ser.data["field_schema"]
        matching = [f for f in schema if f["key"] == "zona_dep"]
        assert len(matching) == 1
        f = matching[0]
        assert f["target_entity"] == "zona"
        assert f["display_key"] == "nombre"
        assert f["depends_on"] == "region"
        assert f["depends_on_field"] == "region"
        invalidate_fields_cache("worker")


# ═══════════════════════════════════════════════════════════════════════════
# Worker model
# ═══════════════════════════════════════════════════════════════════════════

class TestWorkerModel:
    def test_create_worker(self):
        w = WorkerFactory(name="Juan", custom_data={"zona": 8})
        assert w.name == "Juan"
        assert w.custom_data["zona"] == 8

    def test_worker_custom_data_is_jsonb(self):
        """Verify custom_data supports complex structures."""
        w = WorkerFactory(custom_data={
            "zona": 10,
            "rol": [{"value": 4, "priority": 1}, {"value": 1, "priority": 2}],
            "disponibilidad_de_traslado": True,
            "tienda_de_preferencia": 13,
        })
        assert w.custom_data["zona"] == 10
        assert len(w.custom_data["rol"]) == 2
        assert w.custom_data["disponibilidad_de_traslado"] is True

    def test_worker_preference(self):
        from apps.workers.models import WorkerPreference
        w = WorkerFactory()
        WorkerPreference.objects.create(worker=w, shift_type="3")
        assert w.preferences.count() == 1

    def test_preference_unique_constraint(self):
        from apps.workers.models import WorkerPreference
        w = WorkerFactory()
        WorkerPreference.objects.create(worker=w, shift_type="3")
        with pytest.raises(Exception):
            WorkerPreference.objects.create(worker=w, shift_type="3")


# ═══════════════════════════════════════════════════════════════════════════
# _extract_field_values (EAV value extraction)
# ═══════════════════════════════════════════════════════════════════════════

class TestExtractFieldValues:
    """Test the engine's EAV value extractor with all formats."""

    def test_scalar_int(self):
        from apps.restrictions.engine import _extract_field_values
        assert _extract_field_values({"zona": 10}, "zona") == [10]

    def test_scalar_string(self):
        from apps.restrictions.engine import _extract_field_values
        assert _extract_field_values({"tipo": "ett"}, "tipo") == ["ett"]

    def test_scalar_bool(self):
        from apps.restrictions.engine import _extract_field_values
        assert _extract_field_values({"disp": True}, "disp") == [True]

    def test_simple_list(self):
        from apps.restrictions.engine import _extract_field_values
        assert _extract_field_values({"zonas": [8, 9, 10]}, "zonas") == [8, 9, 10]

    def test_priority_value_format(self):
        """Frontend sends {value: id, priority: N}."""
        from apps.restrictions.engine import _extract_field_values
        data = {"rol": [{"value": 4, "priority": 1}, {"value": 1, "priority": 2}]}
        result = _extract_field_values(data, "rol")
        assert result == [4, 1]

    def test_entity_id_format(self):
        from apps.restrictions.engine import _extract_field_values
        data = {"rol": [{"entity_id": 4, "priority": 1}]}
        result = _extract_field_values(data, "rol")
        assert result == [4]

    def test_id_format(self):
        from apps.restrictions.engine import _extract_field_values
        data = {"rol": [{"id": 4}]}
        result = _extract_field_values(data, "rol")
        assert result == [4]

    def test_priority_not_leaked(self):
        """Priority numbers must NOT appear as values."""
        from apps.restrictions.engine import _extract_field_values
        data = {"rol": [{"value": 4, "priority": 1}]}
        result = _extract_field_values(data, "rol")
        assert 1 not in result
        assert result == [4]

    def test_missing_field_returns_empty(self):
        from apps.restrictions.engine import _extract_field_values
        assert _extract_field_values({"a": 1}, "b") == []

    def test_none_value_returns_empty(self):
        from apps.restrictions.engine import _extract_field_values
        assert _extract_field_values({"a": None}, "a") == []
