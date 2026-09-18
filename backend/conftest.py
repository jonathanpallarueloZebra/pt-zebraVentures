"""
Root conftest.py – shared fixtures and factories for all tests.

Provides:
- Shift fixtures (creates real Shift rows so _get_shift_slots() works)
- EntityType / EntityField / EntityRecord factories
- Worker factory with EAV custom_data
- Restriction factory
- Plan-building helpers
"""
import pytest
import factory
from factory.django import DjangoModelFactory


# ── Factories ──────────────────────────────────────────────────────────────

class ShiftFactory(DjangoModelFactory):
    class Meta:
        model = "shifts.Shift"

    name = factory.Sequence(lambda n: f"Turno {n}")
    start_time = factory.LazyFunction(lambda: __import__('datetime').time(7, 0))
    end_time = factory.LazyFunction(lambda: __import__('datetime').time(15, 0))


class EntityTypeFactory(DjangoModelFactory):
    class Meta:
        model = "dynamic_fields.EntityType"
        django_get_or_create = ("slug",)

    slug = factory.Sequence(lambda n: f"type_{n}")
    name = factory.LazyAttribute(lambda o: o.slug.replace("_", " ").title())
    icon = "category"
    order = 0


class EntityFieldFactory(DjangoModelFactory):
    class Meta:
        model = "dynamic_fields.EntityField"
        django_get_or_create = ("entity_type", "key")

    entity_type = "worker"
    key = factory.Sequence(lambda n: f"field_{n}")
    label = factory.LazyAttribute(lambda o: o.key.replace("_", " ").title())
    field_type = "text"
    order = 0
    active = True


class EntityRecordFactory(DjangoModelFactory):
    class Meta:
        model = "dynamic_fields.EntityRecord"

    entity_type = factory.LazyAttribute(lambda o: EntityTypeFactory())
    data = factory.LazyFunction(dict)


class WorkerFactory(DjangoModelFactory):
    class Meta:
        model = "workers.Worker"

    name = factory.Sequence(lambda n: f"Worker {n}")
    active = True
    custom_data = factory.LazyFunction(dict)


class RestrictionFactory(DjangoModelFactory):
    class Meta:
        model = "restrictions.Restriction"

    name = factory.Sequence(lambda n: f"Restriction {n}")
    engine = "count"
    config = factory.LazyFunction(dict)
    severity = "error"
    active = True


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def shift_morning(db):
    """A root shift (Mañana) – its str(id) is used as plan_data key."""
    return ShiftFactory(name="Mañana")


@pytest.fixture
def shift_afternoon(db):
    return ShiftFactory(name="Tarde")


@pytest.fixture
def shift_night(db):
    return ShiftFactory(name="Noche")


@pytest.fixture
def shifts(shift_morning, shift_afternoon, shift_night):
    """Returns (morning, afternoon, night) shift objects."""
    return shift_morning, shift_afternoon, shift_night


@pytest.fixture
def tienda_et(db):
    """EntityType for tienda (planning scope)."""
    return EntityTypeFactory(
        slug="tienda", name="Tienda",
        is_planning_scope=True, display_field="nombre",
    )


@pytest.fixture
def zona_et(db):
    """EntityType for zona."""
    return EntityTypeFactory(slug="zona", name="Zona")


@pytest.fixture
def role_et(db):
    """EntityType for role (show_in_schedule)."""
    return EntityTypeFactory(
        slug="rol", name="Rol",
        show_in_schedule=True, display_field="nombre",
    )


@pytest.fixture(autouse=True)
def _clear_engine_cache():
    """Clear the restriction engine cache and the generator's thread-local
    cache before each test (shifts/shift-days cached by one test leaked into
    the next when calling normalize_week/_fallback_round_robin directly)."""
    from apps.restrictions import engine
    from apps.planning import schedule_generator
    engine.clear_cache()
    schedule_generator._get_gen_cache().clear()
    yield
    engine.clear_cache()
    schedule_generator._get_gen_cache().clear()


@pytest.fixture(autouse=True)
def _no_openai(monkeypatch):
    """Tests must be deterministic and offline: never call OpenAI from the generator."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


# ── Helpers ────────────────────────────────────────────────────────────────

def make_day(date="2026-05-11", **shifts_data):
    """Build a plan day dict.

    Usage:
        make_day("2026-05-11", **{str(shift.id): [assignment(w)]})
    """
    d = {"date": date, "dayName": "Lunes", "rest": shifts_data.pop("rest", [])}
    d.update(shifts_data)
    return d


def assignment(worker, areas=None):
    """Build an assignment dict for plan_data."""
    return {
        "workerId": worker.id,
        "workerName": worker.name,
        "areas": areas or [],
    }
