"""Verifica que cabrero_context/restricciones-cabrero-import.json (el archivo que se
entrega al cliente para subir en Panel Interno > Restricciones > Importar JSON) es
válido de extremo a extremo: cada entrada crea una Restriction real y el motor la
evalúa sin explotar contra un plan con la forma de datos EAV descrita en
cabrero_context/manual-configuracion-cabrero.md (mismos nombres de campo/sección).
"""
import datetime as dt
import json
import os

import pytest

from apps.dynamic_fields.models import EntityField, EntityRecord, EntityType
from apps.restrictions import engine as rengine
from apps.restrictions.models import Restriction
from apps.shift_days.models import ShiftDay
from apps.shifts.models import Shift
from apps.workers.models import Worker

JSON_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "cabrero_context", "restricciones-cabrero-import.json",
)

MONDAY = dt.date(2026, 7, 6)


def _load_json():
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def day(date, **slots):
    d = {"date": date, "dayName": "", "rest": slots.pop("rest", [])}
    d.update(slots)
    return d


def asg(worker, areas=None):
    return {"workerId": worker.id, "workerName": worker.name, "areas": areas or []}


def week_of(monday, days_by_index=None):
    days_by_index = days_by_index or {}
    return [
        day((monday + dt.timedelta(days=i)).isoformat(), **days_by_index.get(i, {}))
        for i in range(7)
    ]


class TestJSONFileItself:
    def test_file_exists_and_parses(self):
        data = _load_json()
        assert isinstance(data, list) and len(data) > 5

    def test_all_entries_have_required_fields_and_valid_engine(self):
        valid_engines = {"count", "exclusion", "match", "condition", "closed_day"}
        for item in _load_json():
            assert item.get("name")
            assert item.get("engine") in valid_engines


@pytest.fixture
def minimal_cabrero(db):
    """Mismos EntityType/EntityField/valores que describe el manual paso a paso."""
    tienda_et = EntityType.objects.create(slug="tienda", name="Tienda", is_planning_scope=True, display_field="codigo")
    EntityField.objects.create(entity_type="tienda", key="codigo", label="Codigo", field_type="text")
    EntityField.objects.create(entity_type="tienda", key="zona", label="Zona", field_type="catalog_select")
    t01 = EntityRecord.objects.create(entity_type=tienda_et, data={"codigo": "T01", "zona": "huesca"})

    seccion_et = EntityType.objects.create(slug="seccion", name="Seccion", show_in_schedule=True, display_field="nombre")
    caja = EntityRecord.objects.create(entity_type=seccion_et, data={"nombre": "Caja"})
    encargado = EntityRecord.objects.create(entity_type=seccion_et, data={"nombre": "Encargado"})

    for key, ftype, target in [
        ("tienda", "entity_select", "tienda"), ("zona", "catalog_select", None),
        ("secciones", "multi_entity_select", "seccion"), ("tipo_contrato", "catalog_select", None),
        ("regimen", "select", None), ("rotacion", "select", None),
        ("jornada_reducida", "boolean", None), ("turnos_max_semana", "number", None),
        ("turno_base", "entity_select", "shift"), ("turno_alternativo", "entity_select", "shift"),
        ("turno_sabado", "entity_select", "shift"),
    ]:
        kw = {"target_entity": target} if target else {}
        EntityField.objects.create(entity_type="worker", key=key, label=key, field_type=ftype, **kw)

    sab_tarde = Shift.objects.create(name="Sabado Tarde", start_time=dt.time(16, 0), end_time=dt.time(21, 0))
    ShiftDay.objects.create(shift=sab_tarde, weekday=5)
    manana = Shift.objects.create(name="Manana", start_time=dt.time(7, 45), end_time=dt.time(14, 45))
    for wd in range(5):
        ShiftDay.objects.create(shift=manana, weekday=wd)

    cajera = Worker.objects.create(name="CAJERA UNO", custom_data={
        "tienda": t01.id, "zona": "huesca", "tipo_contrato": "plantilla", "regimen": "nuevo",
        "secciones": [{"value": caja.id, "priority": 1}], "turno_base": str(manana.id),
    })
    encargada = Worker.objects.create(name="ENCARGADA UNO", custom_data={
        "tienda": t01.id, "zona": "huesca", "tipo_contrato": "plantilla", "regimen": "antiguo",
        "secciones": [{"value": encargado.id, "priority": 1}], "turno_base": str(manana.id),
    })
    ett = Worker.objects.create(name="ETT UNO", custom_data={
        "zona": "huesca", "tipo_contrato": "ett", "regimen": "nuevo",
        "secciones": [{"value": caja.id, "priority": 1}], "turno_base": str(manana.id),
    })
    return {
        "t01": t01, "caja": caja, "encargado": encargado,
        "manana": manana, "sab_tarde": sab_tarde,
        "cajera": cajera, "encargada": encargada, "ett": ett,
    }


class TestImportedRestrictionsAgainstPlan:
    def test_import_creates_restrictions_and_engine_evaluates_cleanly(self, minimal_cabrero):
        data = _load_json()
        created = []
        for item in data:
            if not item.get("name") or not item.get("engine"):
                continue
            clean_config = {k: v for k, v in (item.get("config") or {}).items() if not k.startswith("_DOC")}
            created.append(Restriction.objects.create(
                name=item["name"], description=item.get("description", ""),
                message=item.get("message", ""), engine=item["engine"],
                config=clean_config, severity=item.get("severity", "error"),
                active=item.get("active", True),
            ))
        assert len(created) == len(data)

        m = minimal_cabrero
        plan = week_of(MONDAY, {
            0: {str(m["manana"].id): [
                asg(m["cajera"], areas=["Caja"]),
                asg(m["encargada"], areas=["Encargado"]),
                asg(m["ett"], areas=["Caja"]),
            ]},
            # martes CON gente pero sin nadie de Caja → el mínimo debe avisar
            1: {str(m["manana"].id): [
                asg(m["encargada"], areas=["Encargado"]),
            ]},
        })

        rengine.clear_cache()
        all_violations = []
        for r in Restriction.objects.filter(active=True):
            all_violations.extend(rengine.evaluate(r, plan, scope_record_id=m["t01"].id))
        # No debe reventar, y no debe haber violaciones espurias el lunes
        # (caja cubierta, 1 encargado, elegibilidad correcta, ETT dentro del tope).
        monday_violations = [v for v in all_violations if v.get("dayDate") == MONDAY.isoformat()]
        assert monday_violations == [], f"violaciones inesperadas el lunes bien cubierto: {monday_violations}"

        # El martes hay gente pero nadie de Caja: el mínimo debe dispararse (por nombre, sin ID).
        # El resto de la semana está vacía y con skipEmptyShifts NO debe avisar
        # (los ~31 turnos especiales de Cabrero dispararían "Caja: 0" a diario si no).
        rengine.clear_cache()
        caja_violations = []
        for r in Restriction.objects.filter(active=True, name="Mínimo 1 persona de Caja por turno"):
            caja_violations.extend(rengine.evaluate(r, plan, scope_record_id=m["t01"].id))
        flagged_dates = {v["dayDate"] for v in caja_violations}
        assert flagged_dates == {(MONDAY + dt.timedelta(days=1)).isoformat()},             f"solo el martes (con gente y sin caja) debe avisar: {flagged_dates}"

    def test_elegibilidad_bloquea_trabajador_fuera_de_ambito(self, minimal_cabrero):
        data = _load_json()
        elig = next(i for i in data if i["name"].startswith("Elegibilidad"))
        clean_config = {k: v for k, v in elig["config"].items() if not k.startswith("_DOC")}
        r = Restriction.objects.create(
            name=elig["name"], engine=elig["engine"], severity=elig["severity"],
            config=clean_config, active=True,
        )
        m = minimal_cabrero
        otra_tienda = EntityRecord.objects.create(entity_type=m["t01"].entity_type, data={"codigo": "T99", "zona": "barbastro"})
        forastero = Worker.objects.create(name="FORASTERO", custom_data={
            "tienda": otra_tienda.id, "zona": "barbastro", "tipo_contrato": "plantilla",
            "secciones": [{"value": m["caja"].id, "priority": 1}], "turno_base": str(m["manana"].id),
        })
        plan = week_of(MONDAY, {0: {str(m["manana"].id): [asg(forastero, areas=["Caja"])]}})
        rengine.clear_cache()
        violations = rengine.evaluate(r, plan, scope_record_id=m["t01"].id)
        assert len(violations) == 1
        assert "FORASTERO" in violations[0]["message"]
