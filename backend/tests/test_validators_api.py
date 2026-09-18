"""
Tests for plan validation, scope_records filtering,
and restriction API endpoints.
"""
import pytest
from rest_framework.test import APIClient
from apps.restrictions import engine
from apps.restrictions.validators import validate_plan
from conftest import (
    ShiftFactory, WorkerFactory, RestrictionFactory,
    EntityTypeFactory, EntityRecordFactory,
    make_day, assignment,
)

pytestmark = pytest.mark.django_db


# ═══════════════════════════════════════════════════════════════════════════
# validate_plan
# ═══════════════════════════════════════════════════════════════════════════

class TestValidatePlan:

    def test_aggregates_all_restrictions(self, shifts):
        m, _, n = shifts
        w1 = WorkerFactory()
        RestrictionFactory(
            name="Max 1 shift/day", engine="count",
            config={"subject": "shifts", "groupBy": "day_worker", "operator": "lte", "threshold": 1},
        )
        RestrictionFactory(
            name="Descanso", engine="exclusion",
            config={"exclusionType": "rest_conflict"},
        )
        plan = [make_day(rest=[w1.id], **{
            str(m.id): [assignment(w1)],
            str(n.id): [assignment(w1)],
        })]
        violations = validate_plan(plan)
        names = {v["restrictionName"] for v in violations}
        assert "Max 1 shift/day" in names
        assert "Descanso" in names

    def test_inactive_ignored(self, shifts):
        m, _, n = shifts
        w1 = WorkerFactory()
        RestrictionFactory(
            name="Inactive", engine="count", active=False,
            config={"subject": "shifts", "groupBy": "day_worker", "operator": "lte", "threshold": 1},
        )
        plan = [make_day(**{str(m.id): [assignment(w1)], str(n.id): [assignment(w1)]})]
        assert validate_plan(plan) == []


# ═══════════════════════════════════════════════════════════════════════════
# scope_records filtering
# ═══════════════════════════════════════════════════════════════════════════

class TestScopeRecordsFiltering:
    """Restrictions with scope_records should only apply to those scopes."""

    def test_scoped_restriction_applies_to_matching_scope(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(
            engine="count",
            config={"subject": "workers", "groupBy": "shift", "operator": "lte", "threshold": 0},
            scope_records=[11],
        )
        plan = [make_day(**{str(m.id): [assignment(w1)]})]
        violations = validate_plan(plan, scope_record_id=11)
        assert len(violations) >= 1

    def test_scoped_restriction_skipped_for_other_scope(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory()
        RestrictionFactory(
            engine="count",
            config={"subject": "workers", "groupBy": "shift", "operator": "lte", "threshold": 0},
            scope_records=[11],
        )
        plan = [make_day(**{str(m.id): [assignment(w1)]})]
        violations = validate_plan(plan, scope_record_id=99)
        assert len(violations) == 0

    def test_global_restriction_always_applies(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory()
        RestrictionFactory(
            engine="count",
            config={"subject": "workers", "groupBy": "shift", "operator": "lte", "threshold": 0},
            scope_records=[],  # empty = global
        )
        plan = [make_day(**{str(m.id): [assignment(w1)]})]
        violations = validate_plan(plan, scope_record_id=42)
        assert len(violations) >= 1

    def test_schedule_generator_respects_scope_records(self, shifts):
        """_collect_violations in schedule_generator also filters by scope_records."""
        from apps.planning.schedule_generator import _collect_violations
        m, _, _ = shifts
        w1 = WorkerFactory()
        RestrictionFactory(
            engine="count",
            config={"subject": "workers", "groupBy": "shift", "operator": "lte", "threshold": 0},
            scope_records=[11],
        )
        plan = [make_day(**{str(m.id): [assignment(w1)]})]
        # scope_record_id=99 → restriction scoped to [11] → skipped
        violations = _collect_violations(plan, scope_record_id=99)
        assert len(violations) == 0
        # scope_record_id=11 → applies
        violations = _collect_violations(plan, scope_record_id=11)
        assert len(violations) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# API endpoint tests
# ═══════════════════════════════════════════════════════════════════════════

class TestRestrictionAPI:

    @pytest.fixture(autouse=True)
    def setup_client(self):
        self.client = APIClient()

    def test_crud_create(self):
        resp = self.client.post("/api/restrictions/", {
            "name": "Test Restriction",
            "engine": "count",
            "config": {"subject": "workers", "groupBy": "shift", "operator": "lte", "threshold": 5},
            "severity": "warning",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["name"] == "Test Restriction"

    def test_crud_read(self):
        r = RestrictionFactory(name="Read Me")
        resp = self.client.get(f"/api/restrictions/{r.id}/")
        assert resp.status_code == 200
        assert resp.data["name"] == "Read Me"

    def test_crud_update(self):
        r = RestrictionFactory(name="Old Name")
        resp = self.client.patch(f"/api/restrictions/{r.id}/", {"name": "New Name"}, format="json")
        assert resp.status_code == 200
        r.refresh_from_db()
        assert r.name == "New Name"

    def test_crud_delete(self):
        r = RestrictionFactory(name="Delete Me")
        resp = self.client.delete(f"/api/restrictions/{r.id}/")
        assert resp.status_code == 204

    def test_validate_valid(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory()
        RestrictionFactory(
            engine="count",
            config={"subject": "workers", "groupBy": "shift", "operator": "lte", "threshold": 5},
        )
        plan = [make_day(**{str(m.id): [assignment(w1)]})]
        resp = self.client.post("/api/restrictions/validate/", {"plan": plan}, format="json")
        assert resp.status_code == 200
        assert resp.data["isValid"] is True

    def test_validate_with_violations(self, shifts):
        m, _, _ = shifts
        w1, w2 = WorkerFactory(), WorkerFactory()
        RestrictionFactory(
            engine="count",
            config={"subject": "workers", "groupBy": "shift", "operator": "lte", "threshold": 1},
        )
        plan = [make_day(**{str(m.id): [assignment(w1), assignment(w2)]})]
        resp = self.client.post("/api/restrictions/validate/", {"plan": plan}, format="json")
        assert resp.status_code == 200
        assert resp.data["isValid"] is False
        assert len(resp.data["violations"]) > 0

    def test_validate_empty_plan_400(self):
        resp = self.client.post("/api/restrictions/validate/", {"plan": []}, format="json")
        assert resp.status_code == 400

    def test_validate_no_body_400(self):
        resp = self.client.post("/api/restrictions/validate/", {}, format="json")
        assert resp.status_code == 400

    def test_engine_schema(self):
        resp = self.client.get("/api/restrictions/engine_schema/")
        assert resp.status_code == 200
        assert "count" in resp.data
        assert "exclusion" in resp.data
        assert "match" in resp.data
        assert "condition" in resp.data
        # Condition engine should have scopeMatch field
        cond_fields = resp.data["condition"]["fields"]
        keys = [f["key"] for f in cond_fields]
        assert "scopeMatch" in keys

    def test_constraints(self):
        RestrictionFactory(engine="count")
        resp = self.client.get("/api/restrictions/constraints/")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# EAV entity API
# ═══════════════════════════════════════════════════════════════════════════

class TestEntityAPI:

    @pytest.fixture(autouse=True)
    def setup_client(self):
        self.client = APIClient()

    def test_entity_type_crud(self):
        resp = self.client.post("/api/entity-types/", {
            "slug": "vehiculo", "name": "Vehiculo", "icon": "directions_car",
        }, format="json")
        assert resp.status_code == 201
        slug = resp.data["slug"]

        resp = self.client.get(f"/api/entity-types/{slug}/")
        assert resp.status_code == 200
        assert resp.data["name"] == "Vehiculo"

    def test_entity_record_crud(self):
        et = EntityTypeFactory(slug="area_test")
        resp = self.client.post("/api/entity-records/", {
            "entity_type": et.slug,
            "data": {"nombre": "Area 1", "color": "#FF0000"},
        }, format="json")
        assert resp.status_code == 201
        rid = resp.data["id"]

        resp = self.client.get(f"/api/entity-records/{rid}/")
        assert resp.status_code == 200
        assert resp.data["data"]["nombre"] == "Area 1"

    def test_entity_record_filter_by_type(self):
        et1 = EntityTypeFactory(slug="type_a")
        et2 = EntityTypeFactory(slug="type_b")
        EntityRecordFactory(entity_type=et1, data={"name": "A1"})
        EntityRecordFactory(entity_type=et1, data={"name": "A2"})
        EntityRecordFactory(entity_type=et2, data={"name": "B1"})

        resp = self.client.get("/api/entity-records/", {"entity_type": "type_a"})
        assert resp.status_code == 200
        assert len(resp.data) == 2

    def test_system_entity_cannot_be_deleted(self):
        et = EntityTypeFactory(slug="system_et", is_system=True)
        resp = self.client.delete(f"/api/entity-types/{et.slug}/")
        assert resp.status_code == 400

    def test_worker_api_includes_field_schema(self):
        """Worker API response must include field_schema and custom_data."""
        from apps.dynamic_fields.mixins import invalidate_fields_cache
        from apps.dynamic_fields.models import EntityField
        EntityField.objects.create(
            entity_type="worker", key="testfield", label="Test",
            field_type="text", order=0, active=True,
        )
        invalidate_fields_cache("worker")

        w = WorkerFactory(name="Schema Test")
        resp = self.client.get(f"/api/workers/{w.id}/")
        assert resp.status_code == 200
        assert "field_schema" in resp.data
        assert "custom_data" in resp.data
        keys = [f["key"] for f in resp.data["field_schema"]]
        assert "testfield" in keys
        invalidate_fields_cache("worker")
