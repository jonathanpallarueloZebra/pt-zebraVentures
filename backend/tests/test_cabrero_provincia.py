"""Simulación Cabrero — fase 2/3: provincia con datos reales (Excels de jul-2026).

Fuentes: 'personal tiendas provincia para Zebra.xlsx' (cuadro por tienda),
'Vacaciones 26 para Zebra.xlsx' (9 grupos por localidad), y los ficheros nuevos
por tienda: 'T13/T14 - Barbastro.xls', 'T15..T18 HORARIO.xls', 'T19 - MONZON.xls',
'Tabla empleados Barbastro - Monzon.xls' y 'Trabajadores Jaca - Sabi.xls'
(maestro de provincia con código de empleado, NIF y categorías).

Mapeo REAL de códigos (confirmado cruzando los rosters de las tablas de
empleados con las columnas del cuadro de provincia):
    T13 = BTO-1 (Barbastro)  ·  T14 = BTO-2 (Barbastro)
    T15 = JACA-1             ·  T16 = JACA-2
    T17 = SABI-1 (Sabiñánigo)·  T18 = SABI-2 (Sabiñánigo)
    T19 = MONZÓN
(Huesca capital es T01..T08 = ALTOARAGON-1..8.)

Demuestra con configuración pura:
1. Zona compartida Jaca+Sabiñánigo (T15..T18): el personal COMÚN/ETT de la zona
   es elegible en las 4 tiendas; la plantilla fija solo en la suya.
2. Barbastro (T13/T14) y Monzón (T19) son zonas separadas: nadie cruza.
3. Grupos de vacaciones (grupo_vacaciones + ausencias de quincena): el grupo
   desaparece del plan y la bolsa COMÚN cubre.
4. Contratos por horas (30/35/40/45): per_week_worker_hours + thresholdField.
5. Horarios reales de los cuadros T13..T19: pescadería cerrada los lunes
   (turno sin ShiftDay de lunes), turno partido (2 franjas el mismo día con
   horas reales) y préstamo temporal dentro de la zona (el "cian" del cuadro:
   MARIN ALINA de T16 cubriendo carne en T15, LINCA LARISA en T17 y T18).
"""
import datetime as dt

import pytest

from apps.absences.models import AbsenceRequest, AbsenceType
from apps.catalog.models import Kind, KindValue
from apps.dynamic_fields.models import EntityField, EntityRecord, EntityType
from apps.planning.schedule_generator import generate_schedule
from apps.restrictions import engine as rengine
from apps.restrictions.models import Restriction
from apps.shift_days.models import ShiftDay
from apps.shifts.models import Shift
from apps.workers.models import Worker

MONDAY = dt.date(2026, 7, 6)


def asg_hours(worker, start="08:00", end="15:00", areas=None):
    return {"workerId": worker.id, "workerName": worker.name,
            "start": start, "end": end, "areas": areas or []}


def week_of(monday, days_by_index=None):
    days_by_index = days_by_index or {}
    week = []
    for i in range(7):
        d = {"date": (monday + dt.timedelta(days=i)).isoformat(), "dayName": "", "rest": []}
        d.update(days_by_index.get(i, {}))
        week.append(d)
    return week


def assigned_ids(plan, slot_codes):
    ids = set()
    for d in plan:
        for code in slot_codes:
            for a in d.get(code, []):
                if a.get("workerId", 0) > 0:
                    ids.add(a["workerId"])
    return ids


def days_assigned(plan, slot_codes, worker_id):
    out = []
    for i, d in enumerate(plan):
        for code in slot_codes:
            if any(a.get("workerId") == worker_id for a in d.get(code, [])):
                out.append(i)
                break
    return out


@pytest.fixture
def provincia(db):
    S = {}

    zona_kind = Kind.objects.create(code="zona_movilidad", name="Zona de movilidad")
    for code, label in [("huesca", "Huesca"), ("jaca_sabinanigo", "Jaca + Sabiñánigo"),
                        ("barbastro", "Barbastro"), ("monzon", "Monzón")]:
        KindValue.objects.create(kind=zona_kind, code=code, label=label)
    contrato_kind = Kind.objects.create(code="tipo_contrato", name="Tipo de contrato")
    for code in ["plantilla", "comun", "ett"]:
        KindValue.objects.create(kind=contrato_kind, code=code, label=code)

    tienda_et = EntityType.objects.create(
        slug="tienda", name="Tienda", is_planning_scope=True, display_field="codigo")
    tiendas = {}
    # Códigos REALES de los cuadros por tienda (jul-2026)
    for codigo, nombre, zona in [
        ("T15", "Jaca 1", "jaca_sabinanigo"), ("T16", "Jaca 2", "jaca_sabinanigo"),
        ("T17", "Sabiñánigo 1", "jaca_sabinanigo"), ("T18", "Sabiñánigo 2", "jaca_sabinanigo"),
        ("T13", "Barbastro 1", "barbastro"), ("T14", "Barbastro 2", "barbastro"),
        ("T19", "Monzón", "monzon"),
    ]:
        tiendas[codigo] = EntityRecord.objects.create(
            entity_type=tienda_et,
            data={"codigo": codigo, "nombre": nombre, "zona": zona, "active": True})
    S["tiendas"] = tiendas

    seccion_et = EntityType.objects.create(
        slug="seccion", name="Sección", show_in_schedule=True, display_field="nombre")
    secciones = {}
    # Catálogo ampliado por el cuadro provincia: incluye Repostería
    for nombre in ["Caja", "Carne", "Pescadería", "Panadería", "Repostería",
                   "Frutería", "Charcutería", "Encargado"]:
        secciones[nombre] = EntityRecord.objects.create(
            entity_type=seccion_et, data={"nombre": nombre})
    S["secciones"] = secciones

    jornada = Shift.objects.create(name="Jornada", start_time=dt.time(8, 0), end_time=dt.time(15, 0))
    for wd in range(5):
        ShiftDay.objects.create(shift=jornada, weekday=wd)
    S["jornada"] = jornada

    for key, ftype, extra, order in [
        ("tienda", "entity_select", {"target_entity": "tienda"}, 1),
        ("zona", "catalog_select", {"kind_code": "zona_movilidad"}, 2),
        ("secciones", "multi_entity_select", {"target_entity": "seccion", "allow_priority": True}, 3),
        ("tipo_contrato", "catalog_select", {"kind_code": "tipo_contrato"}, 4),
        ("grupo_vacaciones", "number", {}, 5),
        ("horas_semanales", "number", {}, 6),
        ("turno_base", "entity_select", {"target_entity": "shift"}, 10),
    ]:
        EntityField.objects.create(
            entity_type="worker", key=key, label=key.replace("_", " ").title(),
            field_type=ftype, order=order, **extra)

    def mk_worker(name, *, tienda=None, zona, secs=(), contrato="plantilla",
                  grupo=None, horas=40, turno=None):
        cd = {
            "zona": zona, "tipo_contrato": contrato, "horas_semanales": horas,
            "secciones": [{"value": secciones[s].id, "priority": i + 1} for i, s in enumerate(secs)],
            "turno_base": str((turno or jornada).id),
        }
        if tienda is not None:
            cd["tienda"] = tiendas[tienda].id
        if grupo is not None:
            cd["grupo_vacaciones"] = grupo
        return Worker.objects.create(name=name, custom_data=cd)

    W = {}
    # Personas REALES de las tablas de empleados de jul-2026 (T-código = su Centro)
    W["del_jesus"] = mk_worker("DEL JESUS EXPOSITO, MARIA", tienda="T15", zona="jaca_sabinanigo",
                               secs=("Encargado",), grupo=8)
    W["vilar"] = mk_worker("VILAR LARA, M.ISABEL", tienda="T15", zona="jaca_sabinanigo",
                           secs=("Caja",), grupo=1)
    W["ventura"] = mk_worker("VENTURA NAVARRO, PETRA", tienda="T15", zona="jaca_sabinanigo",
                             secs=("Charcutería",), grupo=2)
    W["saez"] = mk_worker("SAEZ SORIA, LAURA", tienda="T16", zona="jaca_sabinanigo",
                          secs=("Encargado",), grupo=7)
    W["marin"] = mk_worker("MARIN, ALINA", tienda="T16", zona="jaca_sabinanigo",
                           secs=("Carne",))
    W["sanz"] = mk_worker("SANZ LAFUENTE, NURIA", tienda="T17", zona="jaca_sabinanigo",
                          secs=("Encargado",), grupo=3)
    # LINCA, LARISA: el cuadro de T17 anota "EN LAS DOS TIENDAS" (T17+T18) y en el
    # cuadro de personal aparece sin negrita → bolsa de la zona (COMÚN)
    W["linca"] = mk_worker("LINCA, LARISA", tienda=None, zona="jaca_sabinanigo",
                           secs=("Caja",), contrato="comun")
    W["guerra"] = mk_worker("GUERRA ACEDO, SUSANA", tienda="T13", zona="barbastro",
                            secs=("Panadería", "Repostería"), grupo=5, horas=30)
    W["rodriguez"] = mk_worker("RODRIGUEZ RODRIGUEZ, ROSA", tienda="T13", zona="barbastro",
                               secs=("Pescadería",))
    W["sanguesa"] = mk_worker("SANGUESA ZANUY, MARIA ANGELES", tienda="T13", zona="barbastro",
                              secs=("Pescadería",))
    W["bardaji"] = mk_worker("BARDAJI BRUN, SILVIA", tienda="T14", zona="barbastro",
                             secs=("Encargado",), grupo=4)
    W["plana"] = mk_worker("PLANA RODRIGUEZ, M CARMEN", tienda="T19", zona="monzon",
                           secs=("Encargado",), grupo=5)
    W["adecco"] = mk_worker("ADECCO (ETT BARBASTRO)", tienda=None, zona="barbastro",
                            secs=("Caja",), contrato="ett")
    S["W"] = W

    R = {}
    R["elegibilidad"] = Restriction.objects.create(
        name="Elegibilidad por tienda y zona", engine="condition", severity="error",
        config={"scopeMatch": {"rules": [
            {"workerField": "tienda", "matchType": "id"},
            {"workerField": "zona", "scopeField": "zona", "matchType": "field",
             "requireField": "tipo_contrato", "requireValue": "comun"},
            {"workerField": "zona", "scopeField": "zona", "matchType": "field",
             "requireField": "tipo_contrato", "requireValue": "ett"},
        ]}},
        message="{worker} no puede trabajar en esta tienda")
    R["horas"] = Restriction.objects.create(
        name="Tope de horas semanales por contrato", engine="condition", severity="warning",
        config={"scope": "per_week_worker_hours", "operator": "lte",
                "threshold": 45, "thresholdField": "horas_semanales"},
        message="{worker}: {count}h esta semana (contrato: {limit}h)")
    S["R"] = R

    S["slot_codes"] = [str(s.id) for s in Shift.objects.order_by("id")]
    return S


def all_slot_codes():
    return [str(s.id) for s in Shift.objects.order_by("id")]


# ────────────────────────────────────────────────────────────────────────────
# 1. Zonas de la provincia (códigos reales T13..T19)
# ────────────────────────────────────────────────────────────────────────────

class TestZonasProvincia:
    def test_jaca_sabinanigo_comparten_bolsa_comun(self, provincia):
        """La zona Jaca+Sabiñánigo (T15..T18) es una sola bolsa para el COMÚN:
        LINCA, LARISA ('en las dos tiendas' según el cuadro de T17) es elegible
        tanto en Jaca como en Sabiñánigo."""
        W = provincia["W"]
        for codigo in ("T15", "T17"):
            plan = generate_schedule(MONDAY, provincia["tiendas"][codigo].id)["plan"]
            ids = assigned_ids(plan, provincia["slot_codes"])
            assert W["linca"].id in ids, f"la COMÚN de la zona debe ser elegible en {codigo}"

    def test_plantilla_fija_solo_su_tienda(self, provincia):
        """NURIA SANZ (plantilla T17) no aparece en T15 aunque compartan zona."""
        W = provincia["W"]
        plan = generate_schedule(MONDAY, provincia["tiendas"]["T15"].id)["plan"]
        ids = assigned_ids(plan, provincia["slot_codes"])
        assert W["sanz"].id not in ids
        assert W["del_jesus"].id in ids and W["vilar"].id in ids

    def test_barbastro_y_monzon_separados(self, provincia):
        """La ETT de Barbastro NO es elegible en Monzón (T19, zona propia)."""
        W = provincia["W"]
        plan = generate_schedule(MONDAY, provincia["tiendas"]["T19"].id)["plan"]
        ids = assigned_ids(plan, provincia["slot_codes"])
        assert ids == {W["plana"].id}, f"T19 solo tiene a Plana; obtuvo {ids}"
        plan_bto = generate_schedule(MONDAY, provincia["tiendas"]["T13"].id)["plan"]
        ids_bto = assigned_ids(plan_bto, provincia["slot_codes"])
        assert W["adecco"].id in ids_bto, "la ETT de la zona sí es elegible en T13"

    def test_validador_detecta_cruce_barbastro_monzon(self, provincia):
        """Meter a mano a alguien de Barbastro en Monzón dispara la restricción."""
        W = provincia["W"]
        plan = week_of(MONDAY, {0: {str(provincia["jornada"].id): [asg_hours(W["bardaji"])]}})
        rengine.clear_cache()
        v = rengine.evaluate(provincia["R"]["elegibilidad"], plan,
                             scope_record_id=provincia["tiendas"]["T19"].id)
        assert len(v) == 1 and "BARDAJI" in v[0]["message"]


# ────────────────────────────────────────────────────────────────────────────
# 2. Grupos de vacaciones (cuadro anual por quincenas)
# ────────────────────────────────────────────────────────────────────────────

class TestGruposVacaciones:
    def test_quincena_del_grupo_bloquea_y_la_comun_cubre(self, provincia):
        """Cuando toca la quincena del grupo 1 (VILAR, T15), ella desaparece del
        plan de T15 y la bolsa COMÚN de la zona (LINCA) la cubre — el flujo del
        cuadro 'Vacaciones 26': vacacionista → sustituta."""
        W = provincia["W"]
        tipo = AbsenceType.objects.create(name="Vacaciones")
        # Quincena completa del grupo 1 empezando este lunes
        for w in Worker.objects.filter(active=True):
            if (w.custom_data or {}).get("grupo_vacaciones") == 1:
                AbsenceRequest.objects.create(
                    worker=w, type=tipo, status="approved",
                    start_date=MONDAY, end_date=MONDAY + dt.timedelta(days=13))
        plan = generate_schedule(MONDAY, provincia["tiendas"]["T15"].id)["plan"]
        ids = assigned_ids(plan, provincia["slot_codes"])
        assert W["vilar"].id not in ids, "la trabajadora del grupo de vacaciones no puede tener turnos"
        for d in plan[:5]:
            assert W["vilar"].id in d["rest"], f"debe estar en descanso el {d['date']}"
        assert W["linca"].id in ids, "la sustituta COMÚN debe cubrir la quincena"

    def test_restriccion_de_descanso_detecta_asignacion_en_vacaciones(self, provincia):
        """Editar a mano y asignar a alguien de vacaciones → rest_conflict."""
        W = provincia["W"]
        r = Restriction.objects.create(
            name="Descanso en turno", engine="exclusion", severity="error",
            config={"exclusionType": "rest_conflict"})
        sc = str(provincia["jornada"].id)
        plan = week_of(MONDAY, {0: {sc: [asg_hours(W["vilar"])], "rest": [W["vilar"].id]}})
        rengine.clear_cache()
        assert len(rengine.evaluate(r, plan)) == 1


# ────────────────────────────────────────────────────────────────────────────
# 3. Contratos por horas (30/35/40/45 del cuadro)
# ────────────────────────────────────────────────────────────────────────────

class TestContratosPorHoras:
    def test_susana_guerra_30h_viola_con_35h_trabajadas(self, provincia):
        """SUSANA GUERRA (30) con 5 jornadas de 7h = 35h → supera su contrato;
        una compañera de 40h con las mismas 35h no."""
        W = provincia["W"]
        sc = str(provincia["jornada"].id)
        plan = week_of(MONDAY, {
            i: {sc: [asg_hours(W["guerra"]), asg_hours(W["bardaji"])]} for i in range(5)
        })
        rengine.clear_cache()
        v = rengine.evaluate(provincia["R"]["horas"], plan)
        assert len(v) == 1, f"solo la de contrato 30h debe violar: {v}"
        assert "GUERRA" in v[0]["message"]
        assert "35" in v[0]["message"] and "30" in v[0]["message"]

    def test_plan_generado_respeta_contratos(self, provincia):
        """El plan generado de T13 no produce errores de elegibilidad ni de horas."""
        result = generate_schedule(MONDAY, provincia["tiendas"]["T13"].id)
        from apps.planning.schedule_generator import _collect_violations
        violations = _collect_violations(result["plan"], scope_record_id=provincia["tiendas"]["T13"].id)
        errors = [v for v in violations if v["severity"] == "error"]
        assert errors == [], f"el plan generado tiene errores: {errors}"


# ────────────────────────────────────────────────────────────────────────────
# 4. Horarios reales de los cuadros por tienda T13..T19 (jul-2026)
# ────────────────────────────────────────────────────────────────────────────

class TestHorariosProvinciaReales:
    def test_pescaderia_cerrada_los_lunes(self, provincia):
        """En T13..T19 la pescadería marca el lunes como FESTIVO: se modela con
        un turno propio SIN ShiftDay de lunes. El generador nunca asigna a la
        pescadera en lunes (descansa) pero sí el resto de la semana."""
        W = provincia["W"]
        pesca = Shift.objects.create(name="Pescadería T13",
                                     start_time=dt.time(8, 0), end_time=dt.time(14, 30))
        for wd in range(1, 6):  # martes..sábado; lunes NO opera
            ShiftDay.objects.create(shift=pesca, weekday=wd)
        for key in ("rodriguez", "sanguesa"):
            w = W[key]
            w.custom_data["turno_base"] = str(pesca.id)
            w.save()

        plan = generate_schedule(MONDAY, provincia["tiendas"]["T13"].id)["plan"]
        codes = all_slot_codes()
        for key in ("rodriguez", "sanguesa"):
            wid = W[key].id
            dias = days_assigned(plan, codes, wid)
            assert 0 not in dias, "la pescadería no abre los lunes (FESTIVO en el cuadro)"
            assert W[key].id in plan[0]["rest"], "el lunes debe constar como descanso"
            assert dias, "el resto de la semana sí debe tener turnos de pescadería"

    def test_turno_partido_suma_horas_reales(self, provincia):
        """PESCADERIA PARTIDO de T13 (p. ej. 9:30-13 + 16-21): se modela con un
        turno por franja. El tope de horas semanales suma la duración REAL de
        cada franja: 5 días × (3.5h + 5h) = 42.5h > 40h de contrato → aviso;
        la compañera en intensiva (7h × 5 = 35h) no."""
        W = provincia["W"]
        franja_m = Shift.objects.create(name="Pesc. partido mañana T13",
                                        start_time=dt.time(9, 30), end_time=dt.time(13, 0))
        franja_t = Shift.objects.create(name="Pesc. partido tarde T13",
                                        start_time=dt.time(16, 0), end_time=dt.time(21, 0))
        for wd in range(1, 6):
            ShiftDay.objects.create(shift=franja_m, weekday=wd)
            ShiftDay.objects.create(shift=franja_t, weekday=wd)
        cm, ct = str(franja_m.id), str(franja_t.id)
        plan = week_of(MONDAY, {
            i: {cm: [asg_hours(W["rodriguez"], "09:30", "13:00")],
                ct: [asg_hours(W["rodriguez"], "16:00", "21:00")],
                str(provincia["jornada"].id): [asg_hours(W["sanguesa"])]}
            for i in range(5)
        })
        rengine.clear_cache()
        v = rengine.evaluate(provincia["R"]["horas"], plan)
        assert len(v) == 1, f"solo la del partido debe pasarse de horas: {v}"
        assert "RODRIGUEZ" in v[0]["message"]

    def test_turno_partido_y_maximo_turnos_por_dia(self, provincia):
        """El partido son 2 turnos el mismo día: la regla 'máx 1 turno/día'
        genérica lo marcaría. La receta para tiendas con partido es umbral 2
        (sigue cazando un triple turno)."""
        W = provincia["W"]
        franja_m = Shift.objects.create(name="Franja mañana",
                                        start_time=dt.time(9, 30), end_time=dt.time(13, 0))
        franja_t = Shift.objects.create(name="Franja tarde",
                                        start_time=dt.time(16, 0), end_time=dt.time(21, 0))
        cm, ct = str(franja_m.id), str(franja_t.id)
        sc = str(provincia["jornada"].id)
        plan = week_of(MONDAY, {0: {
            cm: [asg_hours(W["rodriguez"], "09:30", "13:00")],
            ct: [asg_hours(W["rodriguez"], "16:00", "21:00")],
        }})
        max1 = Restriction.objects.create(
            name="Máx 1 turno/día", engine="count", severity="error",
            config={"subject": "shifts", "groupBy": "day_worker", "operator": "lte", "threshold": 1},
            message="{worker}: {count} turnos el mismo día (máx {limit})")
        max2 = Restriction.objects.create(
            name="Máx 2 turnos/día (tiendas con partido)", engine="count", severity="error",
            config={"subject": "shifts", "groupBy": "day_worker", "operator": "lte", "threshold": 2},
            message="{worker}: {count} turnos el mismo día (máx {limit})")
        rengine.clear_cache()
        assert len(rengine.evaluate(max1, plan)) == 1, "con umbral 1 el partido saltaría"
        assert rengine.evaluate(max2, plan) == [], "con umbral 2 el partido es válido"
        plan3 = week_of(MONDAY, {0: {
            cm: [asg_hours(W["rodriguez"], "09:30", "13:00")],
            ct: [asg_hours(W["rodriguez"], "16:00", "21:00")],
            sc: [asg_hours(W["rodriguez"])],
        }})
        rengine.clear_cache()
        assert len(rengine.evaluate(max2, plan3)) == 1, "un triple turno sí debe saltar"

    def test_prestamo_temporal_dentro_de_zona(self, provincia):
        """MARIN, ALINA es plantilla de T16 pero el cuadro de T15 la anota
        cubriendo CARNE CONTINUO ('MARIN, ALINA (T16)'). Como plantilla queda
        fuera de ámbito en T15 (el validador avisa); el flujo del cuadro de
        colorines (cian = desplazada) es marcarla tipo_contrato=comun mientras
        dure el préstamo → elegible en toda su zona."""
        W = provincia["W"]
        plan = week_of(MONDAY, {0: {str(provincia["jornada"].id): [asg_hours(W["marin"])]}})
        rengine.clear_cache()
        v = rengine.evaluate(provincia["R"]["elegibilidad"], plan,
                             scope_record_id=provincia["tiendas"]["T15"].id)
        assert len(v) == 1 and "MARIN" in v[0]["message"], \
            "plantilla de T16 asignada en T15 debe avisar"
        marin = W["marin"]
        marin.custom_data["tipo_contrato"] = "comun"
        marin.save()
        rengine.clear_cache()
        v2 = rengine.evaluate(provincia["R"]["elegibilidad"], plan,
                              scope_record_id=provincia["tiendas"]["T15"].id)
        assert v2 == [], "marcada como desplazada (comun) ya es elegible en su zona"
