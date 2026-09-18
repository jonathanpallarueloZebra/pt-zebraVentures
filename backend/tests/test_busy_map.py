"""
Tests de la reserva de trabajadores entre tiendas (_busy_map_from_saved_plans).

Nadie puede estar en dos tiendas a la vez. El personal "volante" (sin tienda
fija) es elegible en TODAS las tiendas de su zona, así que al generar cada
tienda por separado acababa asignado en todas — 3 tiendas × 40h = 120h/semana
en el dashboard de horas extra.

La generación en bloque ya arrastraba un busy_map en memoria, pero la
generación de UNA tienda no miraba los planes guardados de las demás.
"""
import pytest

from apps.planning.models import WeeklyPlan
from apps.planning.views import _busy_map_from_saved_plans

pytestmark = pytest.mark.django_db

START = '2026-07-27'
SHIFT = '153'  # código de turno real usado en los planes de Cabrero


def make_plan(scope_entity_id, worker_ids, dates=(START,), shift=SHIFT):
    """Crea un WeeklyPlan con esos trabajadores asignados en cada fecha."""
    plan_json = [
        {'date': d, 'dayName': 'lunes', 'rest': [],
         shift: [{'workerId': w, 'start': '07:45', 'end': '14:45'} for w in worker_ids]}
        for d in dates
    ]
    return WeeklyPlan.objects.create(
        start_date=START, scope_entity_id=scope_entity_id, plan_json=plan_json,
    )


@pytest.fixture
def shift_row(db):
    """El busy_map recorre los códigos de turno reales (_get_shift_slots)."""
    from apps.shifts.models import Shift
    from datetime import time
    from apps.planning.schedule_generator import _get_gen_cache
    _get_gen_cache().clear()
    return Shift.objects.create(id=int(SHIFT), name='Mañana',
                                start_time=time(7, 45), end_time=time(14, 45))


class TestBusyMap:

    def test_sin_planes_no_reserva_a_nadie(self, shift_row):
        assert _busy_map_from_saved_plans(START) == {}

    def test_recoge_los_asignados_de_otra_tienda(self, shift_row):
        make_plan(scope_entity_id=54, worker_ids=[545, 546])
        busy = _busy_map_from_saved_plans(START, exclude_scope_ids=[55])
        assert busy == {START: {545, 546}}

    def test_agrega_varias_tiendas(self, shift_row):
        make_plan(scope_entity_id=54, worker_ids=[545])
        make_plan(scope_entity_id=55, worker_ids=[546])
        busy = _busy_map_from_saved_plans(START, exclude_scope_ids=[57])
        assert busy == {START: {545, 546}}

    def test_excluye_el_ambito_que_se_regenera(self, shift_row):
        """Al regenerar T01 su propia gente debe quedar libre; si no,
        regenerar dos veces vaciaría la tienda."""
        make_plan(scope_entity_id=54, worker_ids=[545])
        make_plan(scope_entity_id=55, worker_ids=[546])

        busy = _busy_map_from_saved_plans(START, exclude_scope_ids=[54])
        assert busy == {START: {546}}, 'la gente de T54 debe quedar libre'

    def test_excluye_varios_ambitos_en_bloque(self, shift_row):
        make_plan(scope_entity_id=54, worker_ids=[545])
        make_plan(scope_entity_id=55, worker_ids=[546])
        make_plan(scope_entity_id=57, worker_ids=[547])

        busy = _busy_map_from_saved_plans(START, exclude_scope_ids=[54, 55])
        assert busy == {START: {547}}

    def test_el_bloqueo_es_por_dia(self, shift_row):
        """Cada día se reserva por separado: trabajar el lunes en otra tienda
        no impide que se le asigne el martes aquí."""
        d1, d2 = '2026-07-27', '2026-07-28'
        make_plan(scope_entity_id=54, worker_ids=[545], dates=(d1,))
        make_plan(scope_entity_id=55, worker_ids=[546], dates=(d2,))

        busy = _busy_map_from_saved_plans(START, exclude_scope_ids=[57])
        assert busy == {d1: {545}, d2: {546}}

    def test_ignora_planes_de_otras_semanas(self, shift_row):
        make_plan(scope_entity_id=54, worker_ids=[545])
        WeeklyPlan.objects.create(
            start_date='2026-08-03', scope_entity_id=55,
            plan_json=[{'date': '2026-08-03', SHIFT: [{'workerId': 999,
                                                       'start': '07:45', 'end': '14:45'}]}],
        )
        busy = _busy_map_from_saved_plans(START, exclude_scope_ids=[57])
        assert busy == {START: {545}}, 'solo la semana pedida'

    def test_ignora_descansos_y_metadatos(self, shift_row):
        """'rest' no es un turno y date/dayName no son listas de asignaciones."""
        WeeklyPlan.objects.create(
            start_date=START, scope_entity_id=54,
            plan_json=[{'date': START, 'dayName': 'lunes', 'rest': [777],
                        SHIFT: [{'workerId': 545, 'start': '07:45', 'end': '14:45'}]}],
        )
        busy = _busy_map_from_saved_plans(START, exclude_scope_ids=[55])
        assert busy == {START: {545}}, '777 descansa, no ocupa turno'

    def test_tolera_planes_vacios_o_malformados(self, shift_row):
        WeeklyPlan.objects.create(start_date=START, scope_entity_id=54, plan_json=[])
        WeeklyPlan.objects.create(start_date=START, scope_entity_id=55, plan_json=None)
        WeeklyPlan.objects.create(start_date=START, scope_entity_id=56,
                                  plan_json=['basura', {'sin_fecha': True}])
        assert _busy_map_from_saved_plans(START) == {}

    def test_ignora_workerid_cero_o_ausente(self, shift_row):
        """Los huecos sin cubrir se guardan como workerId 0 / entradas vacías."""
        WeeklyPlan.objects.create(
            start_date=START, scope_entity_id=54,
            plan_json=[{'date': START, SHIFT: [
                {'workerId': 0, 'start': '07:45', 'end': '14:45'},
                {'start': '07:45', 'end': '14:45'},
                {'workerId': 545, 'start': '07:45', 'end': '14:45'},
            ]}],
        )
        busy = _busy_map_from_saved_plans(START, exclude_scope_ids=[55])
        assert busy == {START: {545}}


class TestEscenarioReal:
    """El caso de las 120h: YANIRE (volante) en T54, T55 y T57."""

    def test_la_volante_queda_reservada_tras_la_primera_tienda(self, shift_row):
        yanire = 545
        make_plan(scope_entity_id=54, worker_ids=[yanire],
                  dates=('2026-07-27', '2026-07-28', '2026-07-29'))

        # Al generar T55 ahora se la ve ocupada los 3 días → no se la duplica.
        busy = _busy_map_from_saved_plans(START, exclude_scope_ids=[55])
        assert all(yanire in busy[d] for d in
                   ('2026-07-27', '2026-07-28', '2026-07-29'))

    def test_sin_exclusion_se_reservaria_a_si_misma(self, shift_row):
        """Comprobación del contrario: sin excluir el propio ámbito, el plan
        guardado de T54 bloquearía a su propia gente al regenerarse."""
        make_plan(scope_entity_id=54, worker_ids=[545])
        assert _busy_map_from_saved_plans(START) == {START: {545}}
        assert _busy_map_from_saved_plans(START, exclude_scope_ids=[54]) == {}
