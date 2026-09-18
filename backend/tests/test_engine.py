"""
Tests for the restriction engine: count, exclusion, match, condition engines.

IMPORTANT: These tests create real Shift rows so that _get_shift_slots()
returns actual IDs, and plan_data uses those IDs as keys. This ensures
the engine iterates over the correct shift slots (unlike the old tests
that used "morning"/"night" strings which never matched real Shift IDs).
"""
import pytest
from apps.restrictions import engine
from conftest import (
    ShiftFactory, WorkerFactory, RestrictionFactory,
    EntityTypeFactory, EntityRecordFactory, EntityFieldFactory,
    make_day, assignment,
)

pytestmark = pytest.mark.django_db


# ═══════════════════════════════════════════════════════════════════════════
# COUNT ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class TestCountEngine:
    """Count engine: count entities per scope and compare against threshold."""

    def test_max_workers_per_shift_pass(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory()
        w2 = WorkerFactory()
        r = RestrictionFactory(
            engine="count",
            config={"subject": "workers", "groupBy": "shift", "operator": "lte", "threshold": 3},
        )
        plan = [make_day(**{str(m.id): [assignment(w1), assignment(w2)]})]
        assert engine.evaluate(r, plan) == []

    def test_max_workers_per_shift_fail(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory()
        w2 = WorkerFactory()
        r = RestrictionFactory(
            engine="count",
            config={"subject": "workers", "groupBy": "shift", "operator": "lte", "threshold": 1},
        )
        plan = [make_day(**{str(m.id): [assignment(w1), assignment(w2)]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) == 1
        assert "2" in violations[0]["message"]

    def test_min_workers_per_shift_fail(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(
            engine="count",
            config={"subject": "workers", "groupBy": "shift", "operator": "gte", "threshold": 2},
        )
        plan = [make_day(**{str(m.id): [assignment(w1)]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) >= 1

    def test_max_shifts_per_day_worker_fail(self, shifts):
        m, _, n = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(
            engine="count",
            config={"subject": "shifts", "groupBy": "day_worker", "operator": "lte", "threshold": 1},
        )
        plan = [make_day(**{str(m.id): [assignment(w1)], str(n.id): [assignment(w1)]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) == 1
        assert w1.name in violations[0]["message"]

    def test_max_shifts_per_day_worker_pass(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(
            engine="count",
            config={"subject": "shifts", "groupBy": "day_worker", "operator": "lte", "threshold": 1},
        )
        plan = [make_day(**{str(m.id): [assignment(w1)]})]
        assert engine.evaluate(r, plan) == []

    def test_count_per_shift_area_fail(self, shifts):
        m, _, _ = shifts
        w1, w2, w3 = WorkerFactory(), WorkerFactory(), WorkerFactory()
        r = RestrictionFactory(
            engine="count",
            config={"subject": "workers", "groupBy": "shift_area", "operator": "lte", "threshold": 2},
        )
        plan = [make_day(**{str(m.id): [
            assignment(w1, areas=["Farm"]),
            assignment(w2, areas=["Farm"]),
            assignment(w3, areas=["Farm"]),
        ]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) == 1
        assert "Farm" in violations[0]["message"]

    def test_count_per_shift_worker_areas(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(
            engine="count",
            config={"subject": "areas", "groupBy": "shift_worker", "operator": "lte", "threshold": 2},
        )
        plan = [make_day(**{str(m.id): [assignment(w1, areas=["A", "B", "C"])]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) == 1

    def test_ignores_zero_worker_id(self, shifts):
        m, _, _ = shifts
        r = RestrictionFactory(
            engine="count",
            config={"subject": "workers", "groupBy": "shift", "operator": "lte", "threshold": 5},
        )
        plan = [make_day(**{str(m.id): [{"workerId": 0, "areas": []}]})]
        assert engine.evaluate(r, plan) == []

    def test_count_with_worker_field_filter(self, shifts):
        """Filter by EAV field: only count workers whose role == 1."""
        m, _, _ = shifts
        w1 = WorkerFactory(custom_data={"role": 1})
        w2 = WorkerFactory(custom_data={"role": 2})
        r = RestrictionFactory(
            engine="count",
            config={
                "subject": "workers", "groupBy": "shift",
                "operator": "gte", "threshold": 1,
                "filterField": "role", "filterRecordId": 1,
            },
        )
        # Only w2 (role=2) assigned → 0 workers with role=1 → violation
        plan = [make_day(**{str(m.id): [assignment(w2)]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) >= 1

    def test_empty_plan_no_violations(self, shifts):
        r = RestrictionFactory(
            engine="count",
            config={"subject": "workers", "groupBy": "shift", "operator": "lte", "threshold": 5},
        )
        assert engine.evaluate(r, []) == []

    def test_multiple_days(self, shifts):
        m, _, _ = shifts
        w1, w2, w3 = WorkerFactory(), WorkerFactory(), WorkerFactory()
        r = RestrictionFactory(
            engine="count",
            config={"subject": "workers", "groupBy": "shift", "operator": "lte", "threshold": 1},
        )
        plan = [
            make_day("2026-05-11", **{str(m.id): [assignment(w1), assignment(w2)]}),
            make_day("2026-05-12", **{str(m.id): [assignment(w3)]}),
        ]
        violations = engine.evaluate(r, plan)
        # Day 1 violates (2 > 1), day 2 OK
        assert len(violations) == 1
        assert violations[0]["dayDate"] == "2026-05-11"


# ═══════════════════════════════════════════════════════════════════════════
# EXCLUSION ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class TestExclusionEngine:

    def test_consecutive_shifts_violation(self, shifts):
        m, _, n = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(
            engine="exclusion",
            config={
                "exclusionType": "consecutive_shifts",
                "shiftA": str(n.id), "shiftB": str(m.id),
            },
        )
        plan = [
            make_day("2026-05-11", **{str(n.id): [assignment(w1)]}),
            make_day("2026-05-12", **{str(m.id): [assignment(w1)]}),
        ]
        violations = engine.evaluate(r, plan)
        assert len(violations) == 1
        assert w1.name in violations[0]["message"]

    def test_consecutive_shifts_different_worker_ok(self, shifts):
        m, _, n = shifts
        w1, w2 = WorkerFactory(), WorkerFactory()
        r = RestrictionFactory(
            engine="exclusion",
            config={
                "exclusionType": "consecutive_shifts",
                "shiftA": str(n.id), "shiftB": str(m.id),
            },
        )
        plan = [
            make_day("2026-05-11", **{str(n.id): [assignment(w1)]}),
            make_day("2026-05-12", **{str(m.id): [assignment(w2)]}),
        ]
        assert engine.evaluate(r, plan) == []

    def test_worker_pair_violation(self, shifts):
        m, _, _ = shifts
        w1, w2 = WorkerFactory(), WorkerFactory()
        r = RestrictionFactory(
            engine="exclusion",
            config={"exclusionType": "worker_pair", "workerPairs": [[w1.id, w2.id]]},
        )
        plan = [make_day(**{str(m.id): [assignment(w1), assignment(w2)]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) == 1
        assert "incompatibles" in violations[0]["message"]

    def test_worker_pair_different_shifts_ok(self, shifts):
        m, _, n = shifts
        w1, w2 = WorkerFactory(), WorkerFactory()
        r = RestrictionFactory(
            engine="exclusion",
            config={"exclusionType": "worker_pair", "workerPairs": [[w1.id, w2.id]]},
        )
        plan = [make_day(**{str(m.id): [assignment(w1)], str(n.id): [assignment(w2)]})]
        assert engine.evaluate(r, plan) == []

    def test_rest_conflict_int_format(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(
            engine="exclusion",
            config={"exclusionType": "rest_conflict"},
        )
        plan = [make_day(rest=[w1.id], **{str(m.id): [assignment(w1)]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) == 1
        assert "descanso" in violations[0]["message"].lower()

    def test_rest_conflict_dict_format(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(
            engine="exclusion",
            config={"exclusionType": "rest_conflict"},
        )
        plan = [make_day(rest=[{"workerId": w1.id}], **{str(m.id): [assignment(w1)]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) == 1

    def test_rest_no_conflict(self, shifts):
        m, _, _ = shifts
        w1, w2 = WorkerFactory(), WorkerFactory()
        r = RestrictionFactory(
            engine="exclusion",
            config={"exclusionType": "rest_conflict"},
        )
        plan = [make_day(rest=[w2.id], **{str(m.id): [assignment(w1)]})]
        assert engine.evaluate(r, plan) == []

    def test_empty_pairs_list(self):
        r = RestrictionFactory(
            engine="exclusion",
            config={"exclusionType": "worker_pair", "workerPairs": []},
        )
        assert engine.evaluate(r, [make_day()]) == []


# ═══════════════════════════════════════════════════════════════════════════
# MATCH ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class TestMatchEngine:

    def test_preference_violation(self, shifts):
        m, _, n = shifts
        from apps.workers.models import WorkerPreference
        w1 = WorkerFactory()
        WorkerPreference.objects.create(worker=w1, shift_type=str(m.id))
        r = RestrictionFactory(
            engine="match",
            config={"matchType": "worker_preference"},
        )
        # w1 prefers morning but assigned to night
        plan = [make_day(**{str(n.id): [assignment(w1)]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) == 1
        assert "no preferido" in violations[0]["message"]

    def test_preference_match_ok(self, shifts):
        m, _, _ = shifts
        from apps.workers.models import WorkerPreference
        w1 = WorkerFactory()
        WorkerPreference.objects.create(worker=w1, shift_type=str(m.id))
        r = RestrictionFactory(engine="match", config={"matchType": "worker_preference"})
        plan = [make_day(**{str(m.id): [assignment(w1)]})]
        assert engine.evaluate(r, plan) == []

    def test_no_prefs_no_violation(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(engine="match", config={"matchType": "worker_preference"})
        plan = [make_day(**{str(m.id): [assignment(w1)]})]
        assert engine.evaluate(r, plan) == []

    def test_area_role_violation(self, shifts):
        m, _, _ = shifts
        role_et = EntityTypeFactory(slug="role", name="Rol")
        area_et = EntityTypeFactory(slug="area", name="Area")
        role_rec = EntityRecordFactory(entity_type=role_et, data={"nombre": "Farmaceutico"})
        EntityRecordFactory(
            entity_type=area_et,
            data={"nombre": "Farmacia", "name": "Farmacia", "required_role": role_rec.id},
        )
        w2 = WorkerFactory(custom_data={"role": 999})  # wrong role
        r = RestrictionFactory(engine="match", config={"matchType": "area_role"})
        plan = [make_day(**{str(m.id): [assignment(w2, areas=["Farmacia"])]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# CONDITION ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class TestConditionEngine:
    """Condition engine: advanced filter+threshold with AND/OR/NOT on EAV fields."""

    def test_per_shift_threshold(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory(custom_data={"tipo": "ett"})
        w2 = WorkerFactory(custom_data={"tipo": "ett"})
        r = RestrictionFactory(
            engine="condition",
            config={
                "scope": "per_shift",
                "filter": {"field": "tipo", "op": "eq", "value": "ett"},
                "operator": "lte", "threshold": 1,
            },
        )
        plan = [make_day(**{str(m.id): [assignment(w1), assignment(w2)]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) >= 1

    def test_per_shift_pass(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory(custom_data={"tipo": "ett"})
        r = RestrictionFactory(
            engine="condition",
            config={
                "scope": "per_shift",
                "filter": {"field": "tipo", "op": "eq", "value": "ett"},
                "operator": "lte", "threshold": 1,
            },
        )
        plan = [make_day(**{str(m.id): [assignment(w1)]})]
        assert engine.evaluate(r, plan) == []

    def test_per_week_worker(self, shifts):
        m, a, n = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(
            engine="condition",
            config={"scope": "per_week_worker", "operator": "lte", "threshold": 2},
        )
        plan = [
            make_day("2026-05-11", **{str(m.id): [assignment(w1)]}),
            make_day("2026-05-12", **{str(a.id): [assignment(w1)]}),
            make_day("2026-05-13", **{str(n.id): [assignment(w1)]}),
        ]
        violations = engine.evaluate(r, plan)
        assert len(violations) == 1
        assert w1.name in violations[0]["message"]

    def test_per_week_worker_pass(self, shifts):
        m, a, _ = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(
            engine="condition",
            config={"scope": "per_week_worker", "operator": "lte", "threshold": 5},
        )
        plan = [
            make_day("2026-05-11", **{str(m.id): [assignment(w1)]}),
            make_day("2026-05-12", **{str(a.id): [assignment(w1)]}),
        ]
        assert engine.evaluate(r, plan) == []

    def test_filter_and(self, shifts):
        """AND condition: tipo=ett AND zona=8."""
        m, _, _ = shifts
        w1 = WorkerFactory(custom_data={"tipo": "ett", "zona": 8})
        w2 = WorkerFactory(custom_data={"tipo": "ett", "zona": 9})
        r = RestrictionFactory(
            engine="condition",
            config={
                "scope": "per_shift",
                "filter": {"and": [
                    {"field": "tipo", "op": "eq", "value": "ett"},
                    {"field": "zona", "op": "eq", "value": 8},
                ]},
                "operator": "lte", "threshold": 0,
            },
        )
        plan = [make_day(**{str(m.id): [assignment(w1), assignment(w2)]})]
        violations = engine.evaluate(r, plan)
        # w1 passes filter (ett + zona=8) → count=1 > 0 → violation
        # w2 fails filter (zona=9) → not counted
        assert len(violations) >= 1

    def test_filter_or(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory(custom_data={"zona": 8})
        w2 = WorkerFactory(custom_data={"zona": 9})
        w3 = WorkerFactory(custom_data={"zona": 10})
        r = RestrictionFactory(
            engine="condition",
            config={
                "scope": "per_shift",
                "filter": {"or": [
                    {"field": "zona", "op": "eq", "value": 8},
                    {"field": "zona", "op": "eq", "value": 9},
                ]},
                "operator": "gte", "threshold": 2,
            },
        )
        # All 3 workers in morning shift: w1 (z8) and w2 (z9) pass filter → count=2 >=2 → OK for that shift
        # But other shifts (afternoon, night) have 0 workers → 0 < 2 → violations
        # So let's put workers in all shifts to avoid false failures
        plan = [make_day(**{
            str(m.id): [assignment(w1), assignment(w2), assignment(w3)],
            str(shifts[1].id): [assignment(w1), assignment(w2)],
            str(shifts[2].id): [assignment(w1), assignment(w2)],
        })]
        assert engine.evaluate(r, plan) == []

    def test_filter_not(self, shifts):
        m, a, n = shifts
        w1 = WorkerFactory(custom_data={"tipo": "ett"})
        w2 = WorkerFactory(custom_data={"tipo": "fijo"})
        r = RestrictionFactory(
            engine="condition",
            config={
                "scope": "per_shift",
                "filter": {"not": {"field": "tipo", "op": "eq", "value": "ett"}},
                "operator": "gte", "threshold": 1,
            },
        )
        # NOT ett = fijo workers only → need at least 1 per shift
        # Put w2 (fijo) in all shifts so all pass
        plan = [make_day(**{
            str(m.id): [assignment(w1), assignment(w2)],
            str(a.id): [assignment(w2)],
            str(n.id): [assignment(w2)],
        })]
        assert engine.evaluate(r, plan) == []

    def test_filter_in_multi_entity(self, shifts):
        """Use 'in' op for multi_entity_select fields."""
        m, a, n = shifts
        w1 = WorkerFactory(custom_data={"rol": [{"value": 4, "priority": 1}]})
        w2 = WorkerFactory(custom_data={"rol": [{"value": 1, "priority": 1}]})
        r = RestrictionFactory(
            engine="condition",
            config={
                "scope": "per_shift",
                "filter": {"field": "rol", "op": "in", "value": [4]},
                "operator": "gte", "threshold": 1,
            },
        )
        # w1 has rol=4 in all shifts → passes filter → count >=1 per shift → OK
        plan = [make_day(**{
            str(m.id): [assignment(w1), assignment(w2)],
            str(a.id): [assignment(w1)],
            str(n.id): [assignment(w1)],
        })]
        assert engine.evaluate(r, plan) == []

    def test_filter_boolean_field(self, shifts):
        m, a, n = shifts
        w1 = WorkerFactory(custom_data={"disponibilidad": True})
        w2 = WorkerFactory(custom_data={"disponibilidad": False})
        r = RestrictionFactory(
            engine="condition",
            config={
                "scope": "per_shift",
                "filter": {"field": "disponibilidad", "op": "eq", "value": True},
                "operator": "gte", "threshold": 1,
            },
        )
        # Only w2 assigned to morning → 0 with disponibilidad=true in morning → violation
        # Put w1 in other shifts to avoid extra violations
        plan = [make_day(**{
            str(m.id): [assignment(w2)],
            str(a.id): [assignment(w1)],
            str(n.id): [assignment(w1)],
        })]
        violations = engine.evaluate(r, plan)
        # Only morning shift should violate
        assert len(violations) == 1

    def test_per_day_worker_scope(self, shifts):
        m, a, _ = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(
            engine="condition",
            config={"scope": "per_day_worker", "operator": "lte", "threshold": 1},
        )
        plan = [make_day(**{str(m.id): [assignment(w1)], str(a.id): [assignment(w1)]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) == 1

    def test_day_of_week_filter(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(
            engine="condition",
            config={
                "scope": "per_shift", "operator": "lte", "threshold": 0,
                "dayOfWeek": 0,  # Monday
            },
        )
        # 2026-05-11 is a Monday
        plan = [make_day("2026-05-11", **{str(m.id): [assignment(w1)]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) >= 1

    def test_day_of_week_no_match(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(
            engine="condition",
            config={
                "scope": "per_shift", "operator": "lte", "threshold": 0,
                "dayOfWeek": 6,  # Sunday
            },
        )
        # 2026-05-11 is Monday, not Sunday → skip
        plan = [make_day("2026-05-11", **{str(m.id): [assignment(w1)]})]
        assert engine.evaluate(r, plan) == []


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES & DISPATCH
# ═══════════════════════════════════════════════════════════════════════════

class TestEngineEdgeCases:

    def test_unknown_engine(self):
        r = RestrictionFactory(engine="magic", config={})
        assert engine.evaluate(r, []) == []

    def test_unknown_exclusion_type(self):
        r = RestrictionFactory(engine="exclusion", config={"exclusionType": "unicorn"})
        assert engine.evaluate(r, []) == []

    def test_unknown_match_type(self):
        r = RestrictionFactory(engine="match", config={"matchType": "teleport"})
        assert engine.evaluate(r, []) == []

    def test_violation_structure(self, shifts):
        m, _, _ = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(
            name="Test Structure", engine="count", severity="warning",
            config={"subject": "shifts", "groupBy": "day_worker", "operator": "lte", "threshold": 0},
        )
        plan = [make_day(**{str(m.id): [assignment(w1)]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) >= 1
        v = violations[0]
        assert v["restrictionId"] == r.id
        assert v["restrictionName"] == "Test Structure"
        assert v["severity"] == "warning"
        assert "dayDate" in v
        assert "message" in v
        assert "shift" in v

    def test_custom_message_placeholder(self, shifts):
        m, _, n = shifts
        w1 = WorkerFactory()
        r = RestrictionFactory(
            engine="count", severity="error",
            config={"subject": "shifts", "groupBy": "day_worker", "operator": "lte", "threshold": 1},
            message="{worker} tiene demasiados turnos",
        )
        plan = [make_day(**{str(m.id): [assignment(w1)], str(n.id): [assignment(w1)]})]
        violations = engine.evaluate(r, plan)
        assert len(violations) == 1
        assert w1.name in violations[0]["message"]
        assert "demasiados turnos" in violations[0]["message"]
