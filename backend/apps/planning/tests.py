from datetime import date, time, timedelta

from django.test import TestCase
from rest_framework.test import APIClient
from apps.workers.models import Worker
from apps.shifts.models import Shift
from .models import WeeklyPlan
from .serializers import empty_week


class EmptyWeekTest(TestCase):
    def test_generates_7_days(self):
        week = empty_week('2026-04-13')
        self.assertEqual(len(week), 7)

    def test_dates_sequential(self):
        week = empty_week('2026-04-13')
        self.assertEqual(week[0]['date'], '2026-04-13')
        self.assertEqual(week[6]['date'], '2026-04-19')

    def test_each_day_has_rest(self):
        week = empty_week(date(2026, 4, 13))
        for day in week:
            self.assertIn('rest', day)
            self.assertEqual(day['rest'], [])


class WeeklyPlanAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/planning/weekly-plan/'

    def test_list_requires_start(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 400)

    def test_list_nonexistent_returns_empty_week(self):
        resp = self.client.get(f'{self.url}?start=2026-04-13')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['plan']), 7)

    def test_create_and_retrieve(self):
        plan_data = empty_week('2026-04-13')
        # Add an assignment to the first day
        plan_data[0]['morning'] = [{'workerId': 999, 'workerName': 'Test', 'start': '07:00', 'end': '15:00', 'areas': []}]
        resp = self.client.post(self.url, {'start': '2026-04-13', 'plan': plan_data}, format='json')
        self.assertEqual(resp.status_code, 201)

        # Retrieve by start date
        resp = self.client.get(f'{self.url}?start=2026-04-13')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['start'], '2026-04-13')

    def test_retrieve_by_pk_date(self):
        WeeklyPlan.objects.create(start_date='2026-04-13', plan_json=[])
        resp = self.client.get(f'{self.url}2026-04-13/')
        self.assertEqual(resp.status_code, 200)

    def test_retrieve_nonexistent_date(self):
        resp = self.client.get(f'{self.url}2030-01-01/')
        self.assertEqual(resp.status_code, 200)
        # Returns empty week template
        self.assertEqual(len(resp.data['plan']), 7)

    def test_update_existing(self):
        """Creating with same start date updates existing."""
        self.client.post(self.url, {'start': '2026-04-13', 'plan': empty_week('2026-04-13')}, format='json')
        resp = self.client.post(self.url, {'start': '2026-04-13', 'plan': empty_week('2026-04-13')}, format='json')
        self.assertEqual(resp.status_code, 201)
        # Should still be one plan
        self.assertEqual(WeeklyPlan.objects.filter(start_date='2026-04-13').count(), 1)

    def test_invalid_date_format(self):
        resp = self.client.get(f'{self.url}?start=not-a-date')
        self.assertEqual(resp.status_code, 400)


class ScheduleGeneratorNormalizeTest(TestCase):
    """Test normalize_week from schedule_generator."""

    def setUp(self):
        self.s_morning = Shift.objects.create(
            name='Mañana', start_time=time(7, 0), end_time=time(15, 0))
        self.M = str(self.s_morning.id)

    def test_normalize_empty(self):
        from .schedule_generator import normalize_week
        result = normalize_week([], date(2026, 4, 13))
        self.assertEqual(len(result), 7)
        self.assertEqual(result[0]['date'], '2026-04-13')

    def test_normalize_short_week(self):
        from .schedule_generator import normalize_week
        result = normalize_week([{'date': '2026-04-13'}], date(2026, 4, 13))
        self.assertEqual(len(result), 7)

    def test_normalize_rest_formats(self):
        from .schedule_generator import normalize_week
        input_data = [
            {'date': '2026-04-13', 'rest': [1, {'workerId': 2}]},
        ]
        result = normalize_week(input_data, date(2026, 4, 13))
        self.assertEqual(result[0]['rest'], [1, 2])

    def test_normalize_assignment_formats(self):
        from .schedule_generator import normalize_week
        input_data = [
            {
                'date': '2026-04-13',
                self.M: [
                    {'workerId': 1, 'workerName': 'Ana'},
                    {'worker_id': 2, 'worker_name': 'Carlos'},
                ],
            },
        ]
        result = normalize_week(input_data, date(2026, 4, 13))
        self.assertEqual(result[0][self.M][0]['workerId'], 1)
        self.assertEqual(result[0][self.M][1]['workerId'], 2)

    def test_fallback_round_robin(self):
        from .schedule_generator import _fallback_round_robin
        Worker.objects.create(name='W1')
        Worker.objects.create(name='W2')
        result = _fallback_round_robin(date(2026, 4, 13), [
            {'id': 1, 'name': 'W1'},
            {'id': 2, 'name': 'W2'},
        ])
        self.assertEqual(len(result), 7)
        # Each day should have at least one shift with an assignment
        for day in result:
            has_assignment = False
            for key in day:
                if key not in ('date', 'dayName', 'rest') and isinstance(day[key], list) and len(day[key]) > 0:
                    has_assignment = True
                    break
            self.assertTrue(has_assignment, f"Day {day['date']} has no assignments")


class TestShiftValidityGenerator(TestCase):
    """Vigencia de turnos en el generador de planificación (AC-2, AC-4)."""

    def setUp(self):
        # Limpia el cache thread-local del generador entre tests.
        from .schedule_generator import _thread_local
        if hasattr(_thread_local, 'gen_cache'):
            _thread_local.gen_cache = {}
        self.normal = Shift.objects.create(
            name='Normal', start_time=time(9, 0), end_time=time(15, 0))
        self.extra = Shift.objects.create(
            name='Extra Navidad', start_time=time(9, 0), end_time=time(21, 0),
            valid_from=date(2026, 12, 21), valid_to=date(2026, 12, 27))
        self.N = str(self.normal.id)
        self.E = str(self.extra.id)

    def test_operates_on_combines_weekday_and_validity(self):  # AC-2/AC-4
        from .schedule_generator import (
            _get_shift_active_days, _get_shift_validity, _shift_operates_on)
        active = _get_shift_active_days()
        validity = _get_shift_validity()

        # Turno normal: opera cualquier fecha (sin ShiftDay = todos los días).
        self.assertTrue(_shift_operates_on(self.N, date(2026, 7, 20), active, validity))
        self.assertTrue(_shift_operates_on(self.N, date(2026, 12, 25), active, validity))

        # Turno extra: solo dentro de su rango de vigencia.
        self.assertFalse(_shift_operates_on(self.E, date(2026, 12, 20), active, validity))  # antes
        self.assertTrue(_shift_operates_on(self.E, date(2026, 12, 21), active, validity))   # inicio
        self.assertTrue(_shift_operates_on(self.E, date(2026, 12, 25), active, validity))   # dentro
        self.assertTrue(_shift_operates_on(self.E, date(2026, 12, 27), active, validity))   # fin
        self.assertFalse(_shift_operates_on(self.E, date(2026, 12, 28), active, validity))  # después

    def test_extra_shift_empty_outside_range(self):  # AC-2
        """Fuera del rango, la clave del turno extra sale vacía en toda la semana."""
        from .schedule_generator import _fallback_round_robin
        Worker.objects.create(name='W1')
        week = _fallback_round_robin(date(2026, 7, 13), [{'id': 1, 'name': 'W1'}])
        for day in week:
            self.assertEqual(day.get(self.E, []), [],
                             f"El turno extra no debería operar el {day['date']}")

    def test_normal_and_extra_coexist(self):  # AC-4
        """Dentro del rango del extra, el turno normal sigue presente ese día
        (conviven sin pisarse)."""
        from .schedule_generator import (
            _get_shift_active_days, _get_shift_validity, _shift_operates_on)
        active = _get_shift_active_days()
        validity = _get_shift_validity()
        d = date(2026, 12, 25)
        self.assertTrue(_shift_operates_on(self.N, d, active, validity))
        self.assertTrue(_shift_operates_on(self.E, d, active, validity))


class TestShiftValidityPlanSave(TestCase):
    """Bloqueo de asignaciones a turnos fuera de vigencia al guardar (AC-5)."""

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/planning/weekly-plan/'
        self.normal = Shift.objects.create(
            name='Normal', start_time=time(9, 0), end_time=time(15, 0))
        self.expired = Shift.objects.create(
            name='Caducado', start_time=time(9, 0), end_time=time(15, 0),
            valid_from=date(2025, 1, 1), valid_to=date(2025, 1, 10))
        self.N = str(self.normal.id)
        self.X = str(self.expired.id)

    def _week(self, extra_entries_on_day0=None):
        week = empty_week('2026-07-13')
        week[0][self.N] = [{'workerId': 1, 'start': '09:00', 'end': '15:00'}]
        if extra_entries_on_day0 is not None:
            week[0][self.X] = extra_entries_on_day0
        return week

    def test_allows_plan_without_expired_assignments(self):
        resp = self.client.post(self.url, {
            'start': '2026-07-13', 'scope': 0, 'plan': self._week(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_rejects_assignment_to_expired_shift(self):  # AC-5
        resp = self.client.post(self.url, {
            'start': '2026-07-13', 'scope': 0,
            'plan': self._week(extra_entries_on_day0=[
                {'workerId': 1, 'start': '09:00', 'end': '15:00'}]),
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_empty_expired_shift_slot_is_ok(self):
        """Una clave de turno caducado presente pero sin asignación no bloquea."""
        resp = self.client.post(self.url, {
            'start': '2026-07-13', 'scope': 0,
            'plan': self._week(extra_entries_on_day0=[]),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


class TestRotacionSinTurnoAlternativo(TestCase):
    """Una rotación sin turno alternativo no rota: se detecta y se avisa.

    Antes fallaba en silencio: _apply_single_rule() devolvía el turno base y ni
    el generador ni el guardado del empleado decían nada, así que la ficha ponía
    "rotación semanal" y en la práctica era un turno fijo.
    """

    def setUp(self):
        from apps.assignments.models import AssignmentRule
        from .schedule_generator import _thread_local
        if hasattr(_thread_local, 'gen_cache'):
            _thread_local.gen_cache = {}
        self.manana = Shift.objects.create(
            name='Mañana', start_time=time(7, 45), end_time=time(14, 45))
        self.tarde = Shift.objects.create(
            name='Tarde', start_time=time(14, 15), end_time=time(21, 15))
        self.rule = AssignmentRule.objects.create(
            name='Rotación semanal mañana/tarde', active=True, priority=10,
            config={
                'pattern': 'alternate_weekly',
                'overrideField': 'turno_alternativo',
                'conditionField': 'rotacion',
                'conditionValue': 'semanal',
            },
        )

    def _cd(self, **kw):
        base = {'rotacion': 'semanal', 'turno_base': str(self.manana.id)}
        base.update(kw)
        return base

    # ── Detección en el generador ────────────────────────────────────────
    def test_detecta_rotacion_sin_alternativo(self):
        from .schedule_generator import _find_unrotated_workers
        workers = [
            {'id': 1, 'name': 'SIN ALTERNATIVO', 'customData': self._cd()},
            {'id': 2, 'name': 'CORRECTO',
             'customData': self._cd(turno_alternativo=str(self.tarde.id))},
        ]
        out = _find_unrotated_workers(workers, [self.rule])
        self.assertIn(self.rule.name, out)
        self.assertEqual(out[self.rule.name], ['SIN ALTERNATIVO'])

    def test_fijo_sin_alternativo_no_se_avisa(self):
        """Un turno FIJO sin alternativo es correcto, no una incoherencia."""
        from .schedule_generator import _find_unrotated_workers
        workers = [{'id': 1, 'name': 'FIJO', 'customData': self._cd(rotacion='fijo')}]
        self.assertEqual(_find_unrotated_workers(workers, [self.rule]), {})

    def test_patron_weekday_sin_override_no_se_avisa(self):
        """Falta de turno de sábado no es una rotación rota."""
        from apps.assignments.models import AssignmentRule
        from .schedule_generator import _find_unrotated_workers
        sabado = AssignmentRule.objects.create(
            name='Turno de sábado', active=True, priority=20,
            config={'pattern': 'weekday', 'weekday': 5,
                    'overrideField': 'turno_sabado', 'conditionField': ''},
        )
        workers = [{'id': 1, 'name': 'X', 'customData': self._cd()}]
        self.assertEqual(_find_unrotated_workers(workers, [sabado]), {})

    def test_sin_alternativo_el_turno_no_cambia_entre_semanas(self):
        """Confirma el efecto: mismo turno en semana par e impar."""
        from .schedule_generator import _resolve_worker_shift_code
        cd = self._cd()
        par = _resolve_worker_shift_code(cd, 'turno_base', [self.rule], 0)
        impar = _resolve_worker_shift_code(cd, 'turno_base', [self.rule], 1)
        self.assertEqual(par, impar)
        # Con alternativo sí rota.
        cd2 = self._cd(turno_alternativo=str(self.tarde.id))
        self.assertNotEqual(
            _resolve_worker_shift_code(cd2, 'turno_base', [self.rule], 0),
            _resolve_worker_shift_code(cd2, 'turno_base', [self.rule], 1),
        )

    # ── Validación al guardar el empleado ────────────────────────────────
    def test_api_rechaza_guardar_semanal_sin_alternativo(self):
        client = APIClient()
        resp = client.post('/api/workers/', {
            'name': 'Nuevo Rotativo', 'custom_data': self._cd(),
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('turno_alternativo', resp.data)

    def test_api_acepta_semanal_con_alternativo(self):
        client = APIClient()
        resp = client.post('/api/workers/', {
            'name': 'Rotativo OK',
            'custom_data': self._cd(turno_alternativo=str(self.tarde.id)),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_api_acepta_fijo_sin_alternativo(self):
        client = APIClient()
        resp = client.post('/api/workers/', {
            'name': 'Fijo OK', 'custom_data': self._cd(rotacion='fijo'),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
