"""
Tests for the scopeMatch feature in the condition engine.

scopeMatch compares worker EAV fields against scope (tienda) records
using a rules array with OR logic. Supports:
- matchType "id": worker field == scope record PK
- field comparison: worker field == scope record's data field
- requireField/requireValue: extra boolean gate on the worker
"""
import pytest
from apps.restrictions import engine
from conftest import (
    ShiftFactory, WorkerFactory, RestrictionFactory,
    EntityTypeFactory, EntityRecordFactory, EntityFieldFactory,
    make_day, assignment,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def scope_setup(db):
    """Create tienda entity type with zona records, and matching workers."""
    tienda_et = EntityTypeFactory(
        slug="tienda", name="Tienda", is_planning_scope=True, display_field="nombre",
    )
    zona_et = EntityTypeFactory(slug="zona", name="Zona")

    t1 = EntityRecordFactory(entity_type=tienda_et, data={"nombre": "Tienda 1", "zona": 8})
    t2 = EntityRecordFactory(entity_type=tienda_et, data={"nombre": "Tienda 2", "zona": 9})
    t3 = EntityRecordFactory(entity_type=tienda_et, data={"nombre": "Tienda 3", "zona": 10})

    # Workers:
    # w_z8_t1_no_disp: zona=8, pref=T1, no travel
    # w_z8_t1_disp:    zona=8, pref=T1, travel available
    # w_z9_t2_no_disp: zona=9, pref=T2, no travel
    # w_z9_t2_disp:    zona=9, pref=T2, travel
    w_z8_t1_no = WorkerFactory(name="Ana Z8 NoDis", custom_data={
        "zona": 8, "tienda_de_preferencia": t1.id, "disponibilidad_de_traslado": False,
    })
    w_z8_t1_yes = WorkerFactory(name="Pedro Z8 Disp", custom_data={
        "zona": 8, "tienda_de_preferencia": t1.id, "disponibilidad_de_traslado": True,
    })
    w_z9_t2_no = WorkerFactory(name="Roberto Z9 NoDis", custom_data={
        "zona": 9, "tienda_de_preferencia": t2.id, "disponibilidad_de_traslado": False,
    })
    w_z9_t2_yes = WorkerFactory(name="Lucia Z9 Disp", custom_data={
        "zona": 9, "tienda_de_preferencia": t2.id, "disponibilidad_de_traslado": True,
    })

    return {
        "t1": t1, "t2": t2, "t3": t3,
        "w_z8_t1_no": w_z8_t1_no, "w_z8_t1_yes": w_z8_t1_yes,
        "w_z9_t2_no": w_z9_t2_no, "w_z9_t2_yes": w_z9_t2_yes,
    }


@pytest.fixture
def scope_restriction(db):
    """The zone restriction with multi-rule scopeMatch."""
    return RestrictionFactory(
        name="Zona tienda",
        engine="condition",
        severity="error",
        message="{worker} no puede trabajar en esta tienda",
        config={
            "scopeMatch": {
                "rules": [
                    {"workerField": "tienda_de_preferencia", "matchType": "id"},
                    {
                        "workerField": "zona", "scopeField": "zona",
                        "requireField": "disponibilidad_de_traslado",
                        "requireValue": True,
                    },
                ]
            }
        },
    )


class TestScopeMatchOwnTienda:
    """Rule 1: worker's tienda_de_preferencia == scope record ID → always OK."""

    def test_own_tienda_pass(self, shifts, scope_setup, scope_restriction):
        m, _, _ = shifts
        s = scope_setup
        plan = [make_day(**{str(m.id): [assignment(s["w_z8_t1_no"])]})]
        violations = engine.evaluate(scope_restriction, plan, scope_record_id=s["t1"].id)
        assert len(violations) == 0

    def test_own_tienda_pass_even_without_disp(self, shifts, scope_setup, scope_restriction):
        """Own tienda passes regardless of disponibilidad."""
        m, _, _ = shifts
        s = scope_setup
        plan = [make_day(**{str(m.id): [assignment(s["w_z8_t1_no"])]})]
        violations = engine.evaluate(scope_restriction, plan, scope_record_id=s["t1"].id)
        assert len(violations) == 0


class TestScopeMatchSameZona:
    """Rule 2: same zona + disponibilidad_de_traslado → OK, else FAIL."""

    def test_same_zona_with_disp_pass(self, shifts, scope_setup, scope_restriction):
        """Same zona + travel available → can work at another tienda in zona."""
        m, _, _ = shifts
        s = scope_setup
        # w_z8_t1_yes (zona=8, disp=true) at some other T in zona 8
        # Create another tienda in zona 8
        from conftest import EntityRecordFactory
        t4 = EntityRecordFactory(
            entity_type=s["t1"].entity_type,
            data={"nombre": "Tienda 4", "zona": 8},
        )
        plan = [make_day(**{str(m.id): [assignment(s["w_z8_t1_yes"])]})]
        violations = engine.evaluate(scope_restriction, plan, scope_record_id=t4.id)
        assert len(violations) == 0

    def test_same_zona_without_disp_fail(self, shifts, scope_setup, scope_restriction):
        """Same zona but no travel → cannot go to another tienda."""
        m, _, _ = shifts
        s = scope_setup
        from conftest import EntityRecordFactory
        t4 = EntityRecordFactory(
            entity_type=s["t1"].entity_type,
            data={"nombre": "Tienda 4", "zona": 8},
        )
        plan = [make_day(**{str(m.id): [assignment(s["w_z8_t1_no"])]})]
        violations = engine.evaluate(scope_restriction, plan, scope_record_id=t4.id)
        assert len(violations) == 1
        assert s["w_z8_t1_no"].name in violations[0]["message"]


class TestScopeMatchDifferentZona:
    """Different zona → always FAIL, regardless of disponibilidad."""

    def test_diff_zona_no_disp_fail(self, shifts, scope_setup, scope_restriction):
        m, _, _ = shifts
        s = scope_setup
        # w_z9 at tienda zona 8 → different zona → FAIL
        plan = [make_day(**{str(m.id): [assignment(s["w_z9_t2_no"])]})]
        violations = engine.evaluate(scope_restriction, plan, scope_record_id=s["t1"].id)
        assert len(violations) == 1

    def test_diff_zona_with_disp_still_fail(self, shifts, scope_setup, scope_restriction):
        """Even with travel, can't cross zones."""
        m, _, _ = shifts
        s = scope_setup
        plan = [make_day(**{str(m.id): [assignment(s["w_z9_t2_yes"])]})]
        violations = engine.evaluate(scope_restriction, plan, scope_record_id=s["t1"].id)
        assert len(violations) == 1

    def test_diff_zona_at_zona10(self, shifts, scope_setup, scope_restriction):
        m, _, _ = shifts
        s = scope_setup
        # w_z8 at tienda zona 10 → FAIL
        plan = [make_day(**{str(m.id): [assignment(s["w_z8_t1_yes"])]})]
        violations = engine.evaluate(scope_restriction, plan, scope_record_id=s["t3"].id)
        assert len(violations) == 1


class TestScopeMatchMultipleWorkers:
    """Multiple workers in same plan, mixed results."""

    def test_mixed_workers(self, shifts, scope_setup, scope_restriction):
        m, _, _ = shifts
        s = scope_setup
        from conftest import EntityRecordFactory
        t4 = EntityRecordFactory(
            entity_type=s["t1"].entity_type,
            data={"nombre": "Tienda 4", "zona": 8},
        )
        plan = [make_day(**{str(m.id): [
            assignment(s["w_z8_t1_yes"]),   # z8, disp → PASS (same zona + disp)
            assignment(s["w_z8_t1_no"]),    # z8, no disp, pref=T1 not T4 → FAIL
            assignment(s["w_z9_t2_yes"]),   # z9, disp → FAIL (diff zona)
        ]})]
        violations = engine.evaluate(scope_restriction, plan, scope_record_id=t4.id)
        assert len(violations) == 2
        names = {v["message"] for v in violations}
        assert any(s["w_z8_t1_no"].name in m for m in names)
        assert any(s["w_z9_t2_yes"].name in m for m in names)


class TestScopeMatchNoScopeId:
    """When no scope_record_id is passed, scopeMatch is skipped."""

    def test_no_scope_id_skips(self, shifts, scope_setup, scope_restriction):
        m, _, _ = shifts
        s = scope_setup
        plan = [make_day(**{str(m.id): [assignment(s["w_z9_t2_no"])]})]
        # No scope_record_id → scopeMatch not evaluated
        violations = engine.evaluate(scope_restriction, plan, scope_record_id=None)
        assert len(violations) == 0


class TestScopeMatchLegacyFormat:
    """Legacy single-field scopeMatch config (backward compatibility)."""

    def test_legacy_simple_field_match(self, shifts, scope_setup):
        m, _, _ = shifts
        s = scope_setup
        r = RestrictionFactory(
            engine="condition",
            config={"scopeMatch": {"workerField": "zona", "scopeField": "zona"}},
        )
        # w_z8 at T1 (zona=8) → match
        plan = [make_day(**{str(m.id): [assignment(s["w_z8_t1_no"])]})]
        violations = engine.evaluate(r, plan, scope_record_id=s["t1"].id)
        assert len(violations) == 0

    def test_legacy_mismatch(self, shifts, scope_setup):
        m, _, _ = shifts
        s = scope_setup
        r = RestrictionFactory(
            engine="condition",
            config={"scopeMatch": {"workerField": "zona", "scopeField": "zona"}},
        )
        # w_z9 at T1 (zona=8) → no match
        plan = [make_day(**{str(m.id): [assignment(s["w_z9_t2_no"])]})]
        violations = engine.evaluate(r, plan, scope_record_id=s["t1"].id)
        assert len(violations) == 1
