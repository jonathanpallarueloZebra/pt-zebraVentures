"""Tests de las mejoras genéricas de producto (motor + generador).

Cubren, para CUALQUIER empresa (no específico de un cliente):
1. ClosedDay + engine 'closed_day' (festivos locales / cierres por fecha y ámbito)
2. El generador no asigna en días de cierre
3. Regeneración PARCIAL: regenerar solo ciertos días congelando el resto
4. Topes semanales dinámicos por trabajador (thresholdField) en el generador
5. El generador respeta parejas incompatibles (exclusion worker_pair)
6. El motor count respeta ShiftDay (no falsos positivos en días sin turno)
7. match area_membership: la pill asignada debe estar en la polivalencia del worker
8. match area_role es multi-valor (no solo la sección principal)
9. count con filterAreaNames: filtra por el NOMBRE de la pill/área, no por ID,
   y reporta 0 cuando esa área no tiene a nadie asignado ese turno (clave para
   restricciones tipo "mínimo 1 de sección X por turno" sin depender de IDs).
10. condition per_week_worker_hours: tope de HORAS semanales (contratos 30/35/40h),
    sumando la duración real de cada asignación, con umbral dinámico por trabajador.
"""
import datetime as dt

import pytest

from apps.dynamic_fields.models import EntityField, EntityRecord, EntityType
from apps.planning.models import ClosedDay
from apps.planning.schedule_generator import generate_schedule
from apps.restrictions import engine as rengine
from apps.restrictions.models import Restriction
from apps.shift_days.models import ShiftDay
from apps.shifts.models import Shift
from apps.workers.models import Worker

MONDAY = dt.date(2026, 7, 6)


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


def mk_shift(name, start="08:00", end="15:00", weekdays=None):
    sh = Shift.objects.create(
        name=name,
        start_time=dt.time(*map(int, start.split(":"))),
        end_time=dt.time(*map(int, end.split(":"))),
    )
    for wd in (weekdays or []):
        ShiftDay.objects.create(shift=sh, weekday=wd)
    return sh


@pytest.fixture
def turno_field(db):
    """Campo worker→shift para que el generador bucketee por turno."""
    return EntityField.objects.create(
        entity_type="worker", key="turno_base", label="Turno",
        field_type="entity_select", target_entity="shift", order=1,
    )


def mk_worker(name, shift=None, **extra_cd):
    cd = dict(extra_cd)
    if shift is not None:
        cd["turno_base"] = str(shift.id)
    return Worker.objects.create(name=name, custom_data=cd)


# ────────────────────────────────────────────────────────────────────────────
# 1-2. ClosedDay: motor y generador
# ────────────────────────────────────────────────────────────────────────────

class TestClosedDay:
    def test_engine_detecta_asignacion_en_dia_cerrado(self, db):
        sh = mk_shift("Turno")
        w = mk_worker("Ana", sh)
        wednesday = MONDAY + dt.timedelta(days=2)
        ClosedDay.objects.create(date=wednesday, scope_entity_id=0, reason="Festivo")
        r = Restriction.objects.create(
            name="Cierres", engine="closed_day", severity="error", config={})
        plan = week_of(MONDAY, {2: {str(sh.id): [asg(w)]}})
        v = rengine.evaluate(r, plan, scope_record_id=None)
        assert len(v) == 1
        assert "cierre" in v[0]["message"]
        assert v[0]["dayDate"] == wednesday.isoformat()

    def test_cierre_de_otro_ambito_no_dispara(self, db):
        sh = mk_shift("Turno")
        w = mk_worker("Ana", sh)
        wednesday = MONDAY + dt.timedelta(days=2)
        ClosedDay.objects.create(date=wednesday, scope_entity_id=999, reason="Festivo local")
        r = Restriction.objects.create(
            name="Cierres", engine="closed_day", severity="error", config={})
        plan = week_of(MONDAY, {2: {str(sh.id): [asg(w)]}})
        assert rengine.evaluate(r, plan, scope_record_id=123) == []
        rengine.clear_cache()
        assert len(rengine.evaluate(r, plan, scope_record_id=999)) == 1

    def test_generador_no_asigna_en_dia_cerrado(self, db, turno_field):
        sh = mk_shift("Turno", weekdays=[0, 1, 2, 3, 4])
        workers = [mk_worker(f"W{i}", sh) for i in range(3)]
        wednesday = MONDAY + dt.timedelta(days=2)
        ClosedDay.objects.create(date=wednesday, scope_entity_id=0, reason="Festivo")
        result = generate_schedule(MONDAY, 0)
        plan = result["plan"]
        assert plan[2][str(sh.id)] == [], "el día cerrado no puede tener asignaciones"
        assert set(plan[2]["rest"]) >= {w.id for w in workers}
        assert plan[1][str(sh.id)], "los días abiertos siguen asignándose"
        assert any("cierre" in w.lower() for w in result["warnings"])


# ────────────────────────────────────────────────────────────────────────────
# 3. Regeneración parcial (días congelados)
# ────────────────────────────────────────────────────────────────────────────

class TestRegeneracionParcial:
    def test_dias_congelados_intactos_y_target_regenerado(self, db, turno_field):
        sh = mk_shift("Turno", weekdays=[0, 1, 2, 3, 4])
        workers = [mk_worker(f"W{i}", sh) for i in range(3)]
        base = week_of(MONDAY)
        # Lunes congelado con un marcador imposible de generar
        base[0][str(sh.id)] = [{"workerId": workers[0].id, "workerName": "MARCADOR CONGELADO",
                                "start": "23:00", "end": "23:59", "areas": ["X"]}]
        tuesday = (MONDAY + dt.timedelta(days=1)).isoformat()

        result = generate_schedule(MONDAY, 0, target_dates=[tuesday], base_plan=base)
        plan = result["plan"]

        frozen_monday = plan[0][str(sh.id)]
        assert len(frozen_monday) == 1
        assert frozen_monday[0]["workerName"] == "MARCADOR CONGELADO"
        assert frozen_monday[0]["start"] == "23:00", "el día congelado debe pasar intacto"

        regenerated_tuesday = plan[1][str(sh.id)]
        assert regenerated_tuesday, "el día objetivo debe regenerarse"
        assert all(e["workerName"] != "MARCADOR CONGELADO" for e in regenerated_tuesday)

        # Los días vacíos del base (miércoles...) también eran no-target → congelados vacíos
        assert plan[2][str(sh.id)] == [], "un día no-target no debe tocarse aunque esté vacío"

    def test_congelados_cuentan_para_el_tope_semanal(self, db, turno_field):
        sh = mk_shift("Turno", weekdays=[0, 1, 2, 3, 4])
        EntityField.objects.create(
            entity_type="worker", key="max_sem", label="Max semana",
            field_type="number", order=2)
        w = mk_worker("Limitada", sh, max_sem=1)
        Restriction.objects.create(
            name="Tope semanal", engine="condition", severity="warning",
            config={"scope": "per_week_worker", "operator": "lte",
                    "threshold": 5, "thresholdField": "max_sem"})
        base = week_of(MONDAY)
        base[0][str(sh.id)] = [asg(w)]  # lunes congelado: ya tiene su único turno

        targets = [(MONDAY + dt.timedelta(days=i)).isoformat() for i in range(1, 7)]
        plan = generate_schedule(MONDAY, 0, target_dates=targets, base_plan=base)["plan"]

        total = sum(
            1 for d in plan for e in d.get(str(sh.id), []) if e["workerId"] == w.id
        )
        assert total == 1, "el turno del día congelado debe contar para su tope (1)"


# ────────────────────────────────────────────────────────────────────────────
# 4. Tope semanal dinámico por trabajador en el generador
# ────────────────────────────────────────────────────────────────────────────

class TestTopeDinamicoGenerador:
    def test_generador_respeta_threshold_field(self, db, turno_field):
        sh = mk_shift("Turno", weekdays=[0, 1, 2, 3, 4, 5, 6])
        EntityField.objects.create(
            entity_type="worker", key="max_sem", label="Max semana",
            field_type="number", order=2)
        reducida = mk_worker("Reducida", sh, max_sem=2)
        completa = mk_worker("Completa", sh)  # sin campo → umbral estático 5
        Restriction.objects.create(
            name="Tope semanal", engine="condition", severity="warning",
            config={"scope": "per_week_worker", "operator": "lte",
                    "threshold": 5, "thresholdField": "max_sem"})

        plan = generate_schedule(MONDAY, 0)["plan"]

        def count(w):
            return sum(1 for d in plan for e in d.get(str(sh.id), []) if e["workerId"] == w.id)

        assert count(reducida) <= 2, "el generador debe respetar el tope individual"
        assert count(completa) <= 5
        assert count(completa) > 2, "la trabajadora sin límite individual usa el umbral estático"


# ────────────────────────────────────────────────────────────────────────────
# 5. Parejas incompatibles en el generador
# ────────────────────────────────────────────────────────────────────────────

class TestParejasGenerador:
    def test_generador_separa_pareja_incompatible(self, db, turno_field):
        sh = mk_shift("Turno", weekdays=[0, 1, 2, 3, 4])
        w1 = mk_worker("Uno", sh)
        w2 = mk_worker("Dos", sh)
        mk_worker("Tres", sh)
        Restriction.objects.create(
            name="Incompatibles", engine="exclusion", severity="error",
            config={"exclusionType": "worker_pair", "workerPairs": [[w1.id, w2.id]]})

        plan = generate_schedule(MONDAY, 0)["plan"]
        for d in plan:
            ids = {e["workerId"] for e in d.get(str(sh.id), [])}
            assert not ({w1.id, w2.id} <= ids), f"pareja incompatible junta el {d['date']}"


# ────────────────────────────────────────────────────────────────────────────
# 6. Motor count respeta ShiftDay
# ────────────────────────────────────────────────────────────────────────────

class TestCountShiftDay:
    def test_minimo_no_dispara_en_dias_inactivos(self, db):
        """Un turno que solo opera el lunes no genera 'mínimo incumplido' el resto."""
        sh = mk_shift("Solo Lunes", weekdays=[0])
        mk_worker("Ana", sh)
        r = Restriction.objects.create(
            name="Mínimo 1 por turno", engine="count", severity="error",
            config={"subject": "workers", "groupBy": "shift",
                    "operator": "gte", "threshold": 1})
        plan = week_of(MONDAY)  # semana vacía
        v = rengine.evaluate(r, plan)
        dates = sorted({x["dayDate"] for x in v})
        assert dates == [MONDAY.isoformat()], (
            f"solo el lunes (día activo) debe incumplir el mínimo; disparó en {dates}")


# ────────────────────────────────────────────────────────────────────────────
# 7-8. Match: area_membership y area_role multi-valor
# ────────────────────────────────────────────────────────────────────────────

class TestMatchPolivalencia:
    @pytest.fixture
    def pills(self, db):
        et = EntityType.objects.create(
            slug="rol", name="Rol", show_in_schedule=True, display_field="nombre")
        caja = EntityRecord.objects.create(entity_type=et, data={"nombre": "Caja"})
        carne = EntityRecord.objects.create(entity_type=et, data={"nombre": "Carne"})
        EntityField.objects.create(
            entity_type="worker", key="roles", label="Roles",
            field_type="multi_entity_select", target_entity="rol",
            allow_priority=True, order=1)
        return {"et": et, "caja": caja, "carne": carne}

    def test_area_membership_valida_polivalencia(self, db, pills):
        sh = mk_shift("Turno")
        w = mk_worker("Ana", None, roles=[{"value": pills["caja"].id, "priority": 1}])
        r = Restriction.objects.create(
            name="Pill dentro de polivalencia", engine="match", severity="error",
            config={"matchType": "area_membership", "workerField": "roles"})
        # Pill que NO tiene → violación
        plan = week_of(MONDAY, {0: {str(sh.id): [asg(w, areas=["Carne"])]}})
        v = rengine.evaluate(r, plan)
        assert len(v) == 1 and "Carne" in v[0]["message"]
        # Pill que SÍ tiene → sin violación
        rengine.clear_cache()
        plan_ok = week_of(MONDAY, {0: {str(sh.id): [asg(w, areas=["Caja"])]}})
        assert rengine.evaluate(r, plan_ok) == []

    def test_area_role_acepta_roles_secundarios(self, db, pills):
        """area_role era solo-principal; ahora cualquier valor del multi cuenta."""
        sh = mk_shift("Turno")
        area_et = EntityType.objects.create(slug="area", name="Área")
        EntityRecord.objects.create(
            entity_type=area_et,
            data={"nombre": "Mostrador Carne", "required_role": pills["carne"].id})
        # Carne es su rol SECUNDARIO (antes: violación falsa; ahora: pasa)
        w = mk_worker("Ana", None, roles=[
            {"value": pills["caja"].id, "priority": 1},
            {"value": pills["carne"].id, "priority": 2},
        ])
        r = Restriction.objects.create(
            name="Rol requerido por área", engine="match", severity="error",
            config={"matchType": "area_role", "areaEntityType": "area",
                    "roleEntityType": "rol", "workerRoleField": "roles"})
        plan = week_of(MONDAY, {0: {str(sh.id): [asg(w, areas=["Mostrador Carne"])]}})
        assert rengine.evaluate(r, plan) == [], "un rol secundario debe satisfacer el área"

        # Y sigue detectando cuando NO tiene el rol en absoluto
        rengine.clear_cache()
        w2 = mk_worker("Sin Rol", None, roles=[{"value": pills["caja"].id, "priority": 1}])
        plan_bad = week_of(MONDAY, {0: {str(sh.id): [asg(w2, areas=["Mostrador Carne"])]}})
        assert len(rengine.evaluate(r, plan_bad)) == 1


# ────────────────────────────────────────────────────────────────────────────
# 9. count con filterAreaNames: min/max por sección sin depender de IDs
# ────────────────────────────────────────────────────────────────────────────

class TestFilterAreaNames:
    def test_minimo_por_nombre_de_area_reporta_cero_si_ausente(self, db):
        sh = mk_shift("Turno")
        w = mk_worker("Cajera", sh)
        plan = week_of(MONDAY, {0: {str(sh.id): [asg(w, areas=["Caja"])]}})
        r = Restriction.objects.create(
            name="Min Caja", engine="count", severity="warning",
            config={"subject": "workers", "groupBy": "shift_area", "operator": "gte",
                    "threshold": 1, "filterAreaNames": ["Caja"]})
        v = rengine.evaluate(r, plan)
        flagged = {x["dayDate"] for x in v}
        assert MONDAY.isoformat() not in flagged, "el lunes SÍ tiene Caja asignada, no debe violar"
        assert (MONDAY + dt.timedelta(days=1)).isoformat() in flagged, (
            "el martes no tiene a nadie de Caja: debe reportarse como 0, aunque nadie trabaje ese día")

    def test_maximo_por_nombre_de_area_no_dispara_si_nadie_la_tiene(self, db):
        sh = mk_shift("Turno")
        mk_worker("Cajera", sh)  # sin pill "Encargado" en absoluto esta semana
        plan = week_of(MONDAY)
        r = Restriction.objects.create(
            name="Max Encargado", engine="count", severity="warning",
            config={"subject": "workers", "groupBy": "shift_area", "operator": "lte",
                    "threshold": 1, "filterAreaNames": ["Encargado"]})
        assert rengine.evaluate(r, plan) == []


# ────────────────────────────────────────────────────────────────────────────
# 10. condition per_week_worker_hours: tope de HORAS semanales por contrato
# ────────────────────────────────────────────────────────────────────────────

class TestWeeklyHours:
    def _hours_asg(self, worker, start, end):
        return {"workerId": worker.id, "workerName": worker.name,
                "start": start, "end": end, "areas": []}

    def test_suma_horas_con_umbral_dinamico_por_contrato(self, db):
        """Contratos de 30h vs 40h: mismas 35h trabajadas, solo la de 30h viola."""
        sh = mk_shift("Jornada", start="08:00", end="15:00")  # 7h
        EntityField.objects.create(
            entity_type="worker", key="horas_semanales", label="Horas semanales",
            field_type="number", order=1)
        reducida = mk_worker("Contrato30", None, horas_semanales=30)
        completa = mk_worker("Contrato40", None, horas_semanales=40)
        r = Restriction.objects.create(
            name="Tope de horas semanales", engine="condition", severity="warning",
            config={"scope": "per_week_worker_hours", "operator": "lte",
                    "threshold": 45, "thresholdField": "horas_semanales"})
        # 5 días × 7h = 35h para ambas
        plan = week_of(MONDAY, {
            i: {str(sh.id): [self._hours_asg(reducida, "08:00", "15:00"),
                             self._hours_asg(completa, "08:00", "15:00")]}
            for i in range(5)
        })
        v = rengine.evaluate(r, plan)
        assert len(v) == 1, f"solo la de contrato 30h debe violar: {v}"
        assert "Contrato30" in v[0]["message"]
        assert "35" in v[0]["message"] and "30" in v[0]["message"]

    def test_turno_nocturno_cruza_medianoche(self, db):
        """22:00-06:00 son 8 horas, no negativas."""
        sh = mk_shift("Noche", start="22:00", end="06:00")
        w = mk_worker("Nocturna", None)
        r = Restriction.objects.create(
            name="Máx 7h semanales", engine="condition", severity="warning",
            config={"scope": "per_week_worker_hours", "operator": "lte", "threshold": 7})
        plan = week_of(MONDAY, {0: {str(sh.id): [self._hours_asg(w, "22:00", "06:00")]}})
        v = rengine.evaluate(r, plan)
        assert len(v) == 1
        assert "8" in v[0]["message"], f"8h esperadas en el mensaje: {v[0]['message']}"

    def test_umbral_estatico_sin_campo(self, db):
        sh = mk_shift("Jornada", start="08:00", end="16:00")  # 8h
        w = mk_worker("SinCampo", None)
        r = Restriction.objects.create(
            name="Máx 20h", engine="condition", severity="warning",
            config={"scope": "per_week_worker_hours", "operator": "lte", "threshold": 20})
        plan = week_of(MONDAY, {
            i: {str(sh.id): [self._hours_asg(w, "08:00", "16:00")]} for i in range(3)
        })  # 24h > 20h
        v = rengine.evaluate(r, plan)
        assert len(v) == 1 and "24" in v[0]["message"]


class TestSkipEmptyShifts:
    """Mejora jul-2026: `skipEmptyShifts` en el motor count — los mínimos
    (gte) no se exigen a turnos que el ámbito no usa ese día. Motivado por
    la demo VESTIA y por Cabrero (~31 turnos especiales que disparaban
    «Caja: 0 (mín 1)» en cada turno vacío)."""

    def _asg(self, worker, areas):
        return {"workerId": worker.id, "workerName": worker.name, "areas": areas}

    def test_minimo_ignora_turnos_vacios(self, db):
        usado = mk_shift("Apertura", start="09:30", end="16:30")
        vacio = mk_shift("Inventario", start="22:00", end="02:00")
        w = mk_worker("Cajera", None)
        r = Restriction.objects.create(
            name="Mínimo 1 Caja por turno", engine="count", severity="warning",
            config={"subject": "workers", "groupBy": "shift_area", "operator": "gte",
                    "threshold": 1, "filterAreaNames": ["Caja"], "skipEmptyShifts": True})
        plan = week_of(MONDAY, {0: {str(usado.id): [self._asg(w, ["Caja"])],
                                    str(vacio.id): []}})
        rengine.clear_cache()
        assert rengine.evaluate(r, plan) == [], \
            "el turno vacío no debe exigir mínimo de Caja"

    def test_minimo_sigue_saltando_en_turno_usado_sin_el_area(self, db):
        usado = mk_shift("Cierre", start="15:30", end="22:30")
        w = mk_worker("Dependienta", None)
        r = Restriction.objects.create(
            name="Mínimo 1 Caja por turno", engine="count", severity="warning",
            config={"subject": "workers", "groupBy": "shift_area", "operator": "gte",
                    "threshold": 1, "filterAreaNames": ["Caja"], "skipEmptyShifts": True})
        # turno CON gente pero sin nadie de Caja → sí debe avisar
        plan = week_of(MONDAY, {0: {str(usado.id): [self._asg(w, ["Probadores"])]}})
        rengine.clear_cache()
        v = rengine.evaluate(r, plan)
        assert len(v) == 1 and "Caja" in v[0]["message"]

    def test_sin_flag_conserva_comportamiento_anterior(self, db):
        usado = mk_shift("Apertura", start="09:30", end="16:30")
        vacio = mk_shift("Inventario", start="22:00", end="02:00")
        w = mk_worker("Cajera", None)
        r = Restriction.objects.create(
            name="Mínimo 1 Caja por turno", engine="count", severity="warning",
            config={"subject": "workers", "groupBy": "shift_area", "operator": "gte",
                    "threshold": 1, "filterAreaNames": ["Caja"]})
        plan = week_of(MONDAY, {0: {str(usado.id): [self._asg(w, ["Caja"])],
                                    str(vacio.id): []}})
        rengine.clear_cache()
        v = rengine.evaluate(r, plan)
        # compat: sin el flag, el turno vacío SÍ avisa (en cada día operativo)
        lunes_vacio = [x for x in v if x["dayDate"] == MONDAY.isoformat()]
        assert lunes_vacio, f"sin el flag, el turno vacío debe seguir avisando: {v[:2]}"


# ────────────────────────────────────────────────────────────────────────────
# 12. El GENERADOR respeta el tope de horas semanales (no solo lo valida)
# ────────────────────────────────────────────────────────────────────────────

class TestGeneradorTopeHoras:
    """Antes el generador razonaba solo en nº de turnos: producía planes que se
    pasaban de horas y el exceso se veía después, como aviso. Ahora frena al
    asignar."""

    @pytest.fixture
    def horas_field(self, db):
        return EntityField.objects.create(
            entity_type="worker", key="horas_semanales", label="Horas semanales",
            field_type="number", order=2)

    def _tope_horas(self, threshold=45, field="horas_semanales", offset=None):
        cfg = {"scope": "per_week_worker_hours", "operator": "lte",
               "threshold": threshold, "thresholdField": field}
        if offset is not None:
            cfg["thresholdOffset"] = offset
        return Restriction.objects.create(
            name="Tope de horas semanales por contrato", engine="condition",
            severity="warning", config=cfg)

    def _horas_por_worker(self, plan, shift_id):
        from apps.restrictions.engine import _assignment_hours
        total = {}
        for d in plan:
            for e in d.get(str(shift_id), []):
                wid = e.get("workerId", 0)
                if wid > 0:
                    total[wid] = total.get(wid, 0.0) + _assignment_hours(e)
        return total

    def test_no_asigna_por_encima_del_contrato(self, db, turno_field, horas_field):
        """Contrato de 20h con turnos de 8h: máximo 2 turnos (16h), no 5."""
        sh = mk_shift("Jornada", start="08:00", end="16:00")  # 8h
        parcial = mk_worker("Parcial20", sh, horas_semanales=20)
        self._tope_horas()
        plan = generate_schedule(MONDAY, 0)["plan"]
        horas = self._horas_por_worker(plan, sh.id)
        asignadas = horas.get(parcial.id, 0.0)
        assert asignadas <= 20, f"se pasó del contrato de 20h: {asignadas}h"
        assert asignadas == 16, f"debería caber 2 turnos de 8h = 16h, dio {asignadas}h"

    def test_contrato_completo_no_se_recorta(self, db, turno_field, horas_field):
        """Un contrato de 40h no debe verse afectado por el tope."""
        sh = mk_shift("Jornada", start="08:00", end="16:00")  # 8h
        completa = mk_worker("Completa40", sh, horas_semanales=40)
        self._tope_horas()
        plan = generate_schedule(MONDAY, 0)["plan"]
        horas = self._horas_por_worker(plan, sh.id)
        assert horas.get(completa.id, 0.0) == 40, "40h de contrato = 5 turnos de 8h"

    def test_margen_de_horas_extra_amplia_el_tope(self, db, turno_field, horas_field):
        """thresholdOffset = horas extra permitidas sobre el contrato."""
        sh = mk_shift("Jornada", start="08:00", end="16:00")  # 8h
        w = mk_worker("ConMargen", sh, horas_semanales=16)
        self._tope_horas(offset=8)  # 16 + 8 = 24h → 3 turnos
        plan = generate_schedule(MONDAY, 0)["plan"]
        horas = self._horas_por_worker(plan, sh.id)
        assert horas.get(w.id, 0.0) == 24, "con margen de 8h el tope es 24h"

    def test_sin_restriccion_de_horas_no_cambia_nada(self, db, turno_field, horas_field):
        """Sin la restricción activa, el generador se comporta como antes.

        El turno opera los 7 días, así que se asignan 7×8h = 56h aunque el
        contrato diga 8: sin regla que lo limite, el campo del trabajador no
        pinta nada (el tope vive en la restricción, no en la ficha).
        """
        sh = mk_shift("Jornada", start="08:00", end="16:00")
        w = mk_worker("SinTope", sh, horas_semanales=8)
        plan = generate_schedule(MONDAY, 0)["plan"]
        horas = self._horas_por_worker(plan, sh.id)
        assert horas.get(w.id, 0.0) == 56, "sin restricción no se aplica ningún tope"

    def test_contrato_vacio_usa_umbral_plano(self, db, turno_field, horas_field):
        """Los 272 trabajadores tienen el campo vacío: cae al umbral de la regla."""
        sh = mk_shift("Jornada", start="08:00", end="16:00")  # 8h
        w = mk_worker("SinContrato", sh, horas_semanales="")
        self._tope_horas(threshold=24)  # sin campo válido → 24h para todos
        plan = generate_schedule(MONDAY, 0)["plan"]
        horas = self._horas_por_worker(plan, sh.id)
        assert horas.get(w.id, 0.0) == 24, "campo vacío debe usar el umbral plano"

    def test_plan_generado_no_viola_la_restriccion(self, db, turno_field, horas_field):
        """Integración: lo que genera el generador ya no lo tumba el validador."""
        sh = mk_shift("Jornada", start="08:00", end="16:00")
        mk_worker("Parcial20", sh, horas_semanales=20)
        mk_worker("Media30", sh, horas_semanales=30)
        mk_worker("Completa40", sh, horas_semanales=40)
        r = self._tope_horas()
        plan = generate_schedule(MONDAY, 0)["plan"]
        rengine.clear_cache()
        violaciones = rengine.evaluate(r, plan)
        assert violaciones == [], f"el plan generado no debe violar el tope: {violaciones}"


# ────────────────────────────────────────────────────────────────────────────
# 13. Varias restricciones per_week_worker: gana la más restrictiva
# ────────────────────────────────────────────────────────────────────────────

class TestTopeSemanalMasRestrictivo:
    def test_dos_restricciones_gana_la_menor(self, db, turno_field):
        """Antes se aplicaba la PRIMERA (break); la segunda se ignoraba."""
        sh = mk_shift("Jornada", start="08:00", end="16:00")
        w = mk_worker("Ana", sh)
        Restriction.objects.create(
            name="Tope 6", engine="condition", severity="warning",
            config={"scope": "per_week_worker", "operator": "lte", "threshold": 6})
        Restriction.objects.create(
            name="Tope 3", engine="condition", severity="warning",
            config={"scope": "per_week_worker", "operator": "lte", "threshold": 3})
        plan = generate_schedule(MONDAY, 0)["plan"]
        turnos = sum(1 for d in plan for e in d.get(str(sh.id), [])
                     if e.get("workerId") == w.id)
        assert turnos <= 3, f"debe ganar el tope más restrictivo (3), dio {turnos}"


# ────────────────────────────────────────────────────────────────────────────
# 14. Reglas de asignación con overrideType 'times': el horario de la ficha
#     del trabajador manda sobre el horario genérico del turno.
# ────────────────────────────────────────────────────────────────────────────

class TestHorarioPropioDelTrabajador:
    """`overrideType: 'times'` estaba configurado en BD pero sin implementar.

    _apply_single_rule() salía por `if not override_field` y devolvía el turno
    tal cual, así que ~75 trabajadores con hora_entrada/hora_salida propias
    acababan con el horario genérico del turno (p.ej. ficha 09:30-14:30 →
    plan 07:45-14:45).
    """

    def _rule(self, **config):
        from apps.assignments.models import AssignmentRule
        base = {"overrideType": "times", "weekdays": [0, 1, 2, 3, 4]}
        base.update(config)
        return AssignmentRule.objects.create(
            name=config.pop("_name", "Horario personal"), config=base,
            active=True, priority=30,
        )

    def _times_of(self, plan, shift, worker, day_index=0):
        entries = [e for e in plan[day_index].get(str(shift.id), [])
                   if e.get("workerId") == worker.id]
        assert entries, f"{worker.name} no fue asignado el día {day_index}"
        return entries[0]["start"], entries[0]["end"]

    def test_horario_de_la_ficha_pisa_el_del_turno(self, db, turno_field):
        sh = mk_shift("Mañana", start="07:45", end="14:45")
        w = mk_worker("Jessica", sh, hora_entrada="09:30", hora_salida="14:30")
        self._rule(startField="hora_entrada", endField="hora_salida")
        plan = generate_schedule(MONDAY, 0)["plan"]
        assert self._times_of(plan, sh, w) == ("09:30", "14:30")

    def test_horario_que_excede_el_turno_tambien_se_respeta(self, db, turno_field):
        """08:00-15:00 sobre un turno 07:45-14:45 es un horario real, no una errata."""
        sh = mk_shift("Mañana", start="07:45", end="14:45")
        w = mk_worker("Inma", sh, hora_entrada="08:00", hora_salida="15:00")
        self._rule(startField="hora_entrada", endField="hora_salida")
        plan = generate_schedule(MONDAY, 0)["plan"]
        assert self._times_of(plan, sh, w) == ("08:00", "15:00")

    def test_sin_horario_propio_se_queda_el_del_turno(self, db, turno_field):
        sh = mk_shift("Mañana", start="07:45", end="14:45")
        w = mk_worker("Begoña", sh)
        self._rule(startField="hora_entrada", endField="hora_salida")
        plan = generate_schedule(MONDAY, 0)["plan"]
        assert self._times_of(plan, sh, w) == ("07:45", "14:45")

    def test_weekdays_limita_los_dias(self, db, turno_field):
        """Regla solo para el sábado: el lunes no debe tocar el horario."""
        sh = mk_shift("Turno", start="08:00", end="15:00")
        w = mk_worker("Carla", sh,
                      hora_entrada_sabado="08:00", hora_salida_sabado="13:00")
        self._rule(_name="Horario sábado", weekdays=[5],
                   startField="hora_entrada_sabado", endField="hora_salida_sabado")
        plan = generate_schedule(MONDAY, 0)["plan"]
        assert self._times_of(plan, sh, w, day_index=0) == ("08:00", "15:00")
        assert self._times_of(plan, sh, w, day_index=5) == ("08:00", "13:00")

    def test_condicion_multivalor_secciones(self, db, turno_field):
        """`secciones` es [{'value': 76, ...}]: la condición debe mirar el 'value'.

        Comparar contra el repr de la lista no casaba nunca, así que las reglas
        de encargadas no se aplicaban a nadie.
        """
        sh = mk_shift("Mañana", start="07:45", end="14:45")
        enc = mk_worker("Encargada", sh, secciones=[{"value": 76, "priority": 1}])
        otra = mk_worker("Charcutera", sh, secciones=[{"value": 70, "priority": 1}])
        self._rule(_name="Horario encargadas", conditionField="secciones",
                   conditionValue="76", startValue="07:45", endValue="14:30")
        plan = generate_schedule(MONDAY, 0)["plan"]
        assert self._times_of(plan, sh, enc) == ("07:45", "14:30")
        assert self._times_of(plan, sh, otra) == ("07:45", "14:45")

    def test_apply_shift_distingue_reglas_del_mismo_dia(self, db, turno_field):
        """Dos reglas con misma condición y weekdays, una por turno (applyShift).

        Es el caso de las encargadas: "semana de mañana" (turno 153) y "semana
        de tarde" (154). Sin comprobar applyShift ganaba siempre la última y
        todas acababan con horario de tarde.
        """
        from apps.assignments.models import AssignmentRule
        manana = mk_shift("Mañana", start="07:45", end="14:45")
        tarde = mk_shift("Tarde", start="14:15", end="21:15")
        w_m = mk_worker("EncMañana", manana, secciones=[{"value": 76, "priority": 1}])
        w_t = mk_worker("EncTarde", tarde, secciones=[{"value": 76, "priority": 1}])
        for prio, sh_obj, start, end in ((25, manana, "07:45", "14:30"),
                                         (26, tarde, "14:25", "21:15")):
            AssignmentRule.objects.create(
                name=f"Encargadas {sh_obj.name}", active=True, priority=prio,
                config={"overrideType": "times", "weekdays": [0, 1, 2, 3, 4],
                        "conditionField": "secciones", "conditionValue": "76",
                        "applyShift": str(sh_obj.id),
                        "startValue": start, "endValue": end},
            )
        plan = generate_schedule(MONDAY, 0)["plan"]
        assert self._times_of(plan, manana, w_m) == ("07:45", "14:30")
        assert self._times_of(plan, tarde, w_t) == ("14:25", "21:15")

    def test_horas_semanales_cuentan_el_horario_real(self, db, turno_field):
        """El tope de horas debe medir el horario propio, no el del turno."""
        sh = mk_shift("Jornada", start="08:00", end="16:00")  # 8h de turno
        w = mk_worker("Media", sh, hora_entrada="08:00", hora_salida="12:00")  # 4h real
        self._rule(startField="hora_entrada", endField="hora_salida")
        Restriction.objects.create(
            name="Max 20h", engine="condition", severity="error",
            config={"scope": "per_week_worker_hours", "operator": "lte",
                    "threshold": 20})
        plan = generate_schedule(MONDAY, 0)["plan"]
        turnos = sum(1 for d in plan for e in d.get(str(sh.id), [])
                     if e.get("workerId") == w.id)
        # Con 4h reales caben 5 días; si contara las 8h del turno solo caberían 2.
        assert turnos >= 4, f"debe contar 4h/día (no 8h del turno), dio {turnos} días"

    def test_horario_de_manana_no_se_aplica_en_turno_de_tarde(self, db, turno_field):
        """Red de seguridad: el horario personal es uno solo para L-V.

        Quien rota mañana/tarde tiene un único hora_entrada, así que le sirve
        para una semana y no para la otra. Si no solapa la mitad del turno se
        descarta: mejor el horario genérico del turno que uno imposible
        (turno de Tarde con horas de mañana).
        """
        manana = mk_shift("Mañana", start="07:45", end="14:45")
        tarde = mk_shift("Tarde", start="14:15", end="21:15")
        w = mk_worker("Marcos", manana, rotacion="semanal",
                      turno_alternativo=str(tarde.id),
                      hora_entrada="08:30", hora_salida="12:30")
        from apps.assignments.models import AssignmentRule
        AssignmentRule.objects.create(
            name="Rotación semanal", active=True, priority=10,
            config={"pattern": "alternate_weekly", "overrideField": "turno_alternativo",
                    "conditionField": "rotacion", "conditionValue": "semanal"})
        self._rule(startField="hora_entrada", endField="hora_salida")

        # Semana par (ISO 32): turno Mañana → su horario sí encaja.
        par = generate_schedule(dt.date(2026, 8, 3), 0)["plan"]
        assert self._times_of(par, manana, w) == ("08:30", "12:30")

        # Semana impar (ISO 33): turno Tarde → 08:30-12:30 no solapa nada,
        # así que se usan las horas del turno.
        impar = generate_schedule(dt.date(2026, 8, 10), 0)["plan"]
        assert self._times_of(impar, tarde, w) == ("14:15", "21:15")

    def test_horario_que_solapa_lo_suficiente_si_se_respeta(self, db, turno_field):
        """08:00-15:00 sobre turno 07:45-14:45 excede el turno pero es real."""
        sh = mk_shift("Mañana", start="07:45", end="14:45")
        w = mk_worker("Inma", sh, hora_entrada="08:00", hora_salida="15:00")
        self._rule(startField="hora_entrada", endField="hora_salida")
        plan = generate_schedule(MONDAY, 0)["plan"]
        assert self._times_of(plan, sh, w) == ("08:00", "15:00")


# ────────────────────────────────────────────────────────────────────────────
# 15. El tope de HORAS es del contrato de la persona, no de la tienda:
#     debe contar lo que ya trabaja esa semana en OTROS ámbitos.
# ────────────────────────────────────────────────────────────────────────────

class TestTopeHorasEntreTiendas:
    """Antes el tope se evaluaba por tienda: alguien con 35h de contrato podía
    hacer 5 días en una tienda y el sábado en otra (42,5h) sin que ninguna de
    las dos superase el límite por separado.
    """

    def _cap_35h(self):
        Restriction.objects.create(
            name="Tope horas", engine="condition", severity="warning",
            config={"scope": "per_week_worker_hours", "operator": "lte",
                    "threshold": 40, "thresholdField": "horas_semanales"})

    def _hours_of(self, plan, shift, worker):
        def mins(t):
            h, m = str(t).split(":")[:2]
            return int(h) * 60 + int(m)
        total = 0.0
        for d in plan:
            for e in d.get(str(shift.id), []):
                if e.get("workerId") == worker.id:
                    total += (mins(e["end"]) - mins(e["start"])) / 60
        return total

    def test_prior_hours_de_otra_tienda_consumen_contrato(self, db, turno_field):
        from apps.planning.models import WeeklyPlan
        sh = mk_shift("Jornada", start="08:00", end="15:00")   # 7h
        w = mk_worker("Ainhoa", sh, horas_semanales=14)         # solo 2 turnos
        self._cap_35h()
        # Plan YA GUARDADO de otra tienda: 7h el lunes.
        WeeklyPlan.objects.create(
            start_date=MONDAY, scope_entity_id=99,
            plan_json=[{"date": MONDAY.isoformat(), "dayName": "", "rest": [],
                        str(sh.id): [{"workerId": w.id, "workerName": w.name,
                                      "start": "08:00", "end": "15:00", "areas": []}]}],
        )
        plan = generate_schedule(MONDAY, 0)["plan"]
        horas = self._hours_of(plan, sh, w)
        # 14h de contrato − 7h ya hechas en la tienda 99 → como mucho 7h aquí.
        assert horas <= 7.0, f"debe descontar las 7h de la otra tienda, dio {horas}h"

    def test_extra_hours_en_generacion_en_bloque(self, db, turno_field):
        """En bloque los planes aún no están en BD: las horas llegan por parámetro."""
        sh = mk_shift("Jornada", start="08:00", end="15:00")
        w = mk_worker("Erika", sh, horas_semanales=14)
        self._cap_35h()
        plan = generate_schedule(MONDAY, 0, extra_hours={w.id: 7.0})["plan"]
        horas = self._hours_of(plan, sh, w)
        assert horas <= 7.0, f"debe respetar extra_hours, dio {horas}h"

    def test_sin_horas_previas_se_usa_el_contrato_completo(self, db, turno_field):
        sh = mk_shift("Jornada", start="08:00", end="15:00")
        w = mk_worker("Nueva", sh, horas_semanales=14)
        self._cap_35h()
        plan = generate_schedule(MONDAY, 0)["plan"]
        horas = self._hours_of(plan, sh, w)
        assert horas >= 14.0, f"sin horas previas debe llegar a su contrato, dio {horas}h"


# ────────────────────────────────────────────────────────────────────────────
# 16. Días libres FIJOS por contrato (overrideType 'day_off').
#     Caso real: pescadería libra los lunes (no hay lonja en domingo).
# ────────────────────────────────────────────────────────────────────────────

class TestDiasLibresFijos:
    """`overrideType: 'day_off'` estaba configurado en BD pero sin implementar.

    26 trabajadores de pescadería tienen 'lunes' en `dias_libres` y el generador
    los asignaba igualmente: la regla estaba activa pero el motor no entendía
    ese overrideType (mismo patrón que 'times').
    """

    def _rule(self, days_field="dias_libres", **extra):
        from apps.assignments.models import AssignmentRule
        cfg = {"overrideType": "day_off", "daysField": days_field}
        cfg.update(extra)
        return AssignmentRule.objects.create(
            name="Días libres personales", config=cfg, active=True, priority=5)

    def _days_worked(self, plan, shift, worker):
        out = []
        for i, d in enumerate(plan):
            if any(e.get("workerId") == worker.id for e in d.get(str(shift.id), [])):
                out.append(dt.date.fromisoformat(d["date"]).weekday())
        return out

    def test_no_se_asigna_en_su_dia_libre(self, db, turno_field):
        sh = mk_shift("Mañana", start="08:00", end="15:00")
        w = mk_worker("Pescadera", sh, dias_libres=["lunes"])
        self._rule()
        plan = generate_schedule(MONDAY, 0)["plan"]
        dias = self._days_worked(plan, sh, w)
        assert 0 not in dias, f"no debe trabajar el lunes (weekday 0), dio {dias}"
        assert dias, "debe trabajar el resto de días"

    def test_varios_dias_libres(self, db, turno_field):
        sh = mk_shift("Mañana", start="08:00", end="15:00")
        w = mk_worker("Multi", sh, dias_libres=["lunes", "miercoles", "sabado"])
        self._rule()
        plan = generate_schedule(MONDAY, 0)["plan"]
        dias = self._days_worked(plan, sh, w)
        for libre in (0, 2, 5):
            assert libre not in dias, f"weekday {libre} es libre, dio {dias}"

    def test_acentos_y_mayusculas(self, db, turno_field):
        """Los códigos del catálogo van sin acentos, pero se aceptan ambos."""
        sh = mk_shift("Mañana", start="08:00", end="15:00")
        w = mk_worker("Acentos", sh, dias_libres=["Miércoles"])
        self._rule()
        plan = generate_schedule(MONDAY, 0)["plan"]
        assert 2 not in self._days_worked(plan, sh, w)

    def test_sin_dias_libres_trabaja_todos(self, db, turno_field):
        sh = mk_shift("Mañana", start="08:00", end="15:00")
        w = mk_worker("Normal", sh)
        self._rule()
        plan = generate_schedule(MONDAY, 0)["plan"]
        assert 0 in self._days_worked(plan, sh, w), "sin días libres debe trabajar el lunes"

    def test_condicion_limita_a_quien_aplica(self, db, turno_field):
        """Con conditionField, la regla solo afecta a quien la cumple."""
        sh = mk_shift("Mañana", start="08:00", end="15:00")
        afectado = mk_worker("ConRegimen", sh, dias_libres=["lunes"], regimen="antiguo")
        otro = mk_worker("SinRegimen", sh, dias_libres=["lunes"], regimen="nuevo")
        self._rule(conditionField="regimen", conditionValue="antiguo")
        plan = generate_schedule(MONDAY, 0)["plan"]
        assert 0 not in self._days_worked(plan, sh, afectado)
        assert 0 in self._days_worked(plan, sh, otro), "no cumple la condición: sí trabaja"
