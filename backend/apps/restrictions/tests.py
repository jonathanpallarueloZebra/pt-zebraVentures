from datetime import time

from django.test import TestCase
from rest_framework.test import APIClient
from apps.workers.models import Worker, WorkerPreference
from apps.shifts.models import Shift
from apps.dynamic_fields.models import EntityType, EntityRecord
from .models import Restriction
from . import engine


class EngineTestMixin:
    """Helper to set up workers, shifts and a clean engine cache."""

    def setUp(self):
        engine.clear_cache()
        # Create real Shift objects so _get_shift_slots() returns their IDs
        self.shift_morning = Shift.objects.create(
            name='Mañana', start_time=time(7, 0), end_time=time(15, 0))
        self.shift_afternoon = Shift.objects.create(
            name='Tarde', start_time=time(15, 0), end_time=time(23, 0))
        self.shift_night = Shift.objects.create(
            name='Noche', start_time=time(23, 0), end_time=time(7, 0))
        # Shorthand IDs for plan keys
        self.M = str(self.shift_morning.id)
        self.T = str(self.shift_afternoon.id)
        self.N = str(self.shift_night.id)
        # Role entity records
        self.role_et = EntityType.objects.create(slug='role', name='Rol')
        self.role_farm = EntityRecord.objects.create(
            entity_type=self.role_et, data={'name': 'Farmaceutico'})
        self.role_aux = EntityRecord.objects.create(
            entity_type=self.role_et, data={'name': 'Auxiliar'})
        # Area entity records (for area_role match tests)
        self.area_et = EntityType.objects.create(slug='area', name='Area')
        EntityRecord.objects.create(
            entity_type=self.area_et,
            data={'name': 'Farmacia', 'required_role': self.role_farm.id})
        EntityRecord.objects.create(
            entity_type=self.area_et,
            data={'name': 'Laboratorio'})
        # Workers with role EAV references
        self.w1 = Worker.objects.create(
            name='Ana Garcia', custom_data={'role': self.role_farm.id})
        self.w2 = Worker.objects.create(
            name='Carlos Lopez', custom_data={'role': self.role_aux.id})
        self.w3 = Worker.objects.create(
            name='Maria Torres', custom_data={'role': self.role_farm.id})

    def tearDown(self):
        engine.clear_cache()

    def _day(self, date='2026-04-13', rest=None, **shifts):
        """Build a single day plan dict. Keys morning/afternoon/night are
        automatically mapped to the real Shift IDs."""
        name_map = {
            'morning': self.M, 'afternoon': self.T, 'night': self.N,
        }
        d = {'date': date, 'dayName': 'Lunes', 'rest': rest or []}
        for k, v in shifts.items():
            d[name_map.get(k, k)] = v
        return d

    def _assignment(self, worker, areas=None):
        return {'workerId': worker.id, 'workerName': worker.name, 'areas': areas or []}


# ---------------------------------------------------------------------------
# COUNT ENGINE TESTS
# ---------------------------------------------------------------------------
class CountEngineTest(EngineTestMixin, TestCase):

    def test_max_workers_per_shift_pass(self):
        r = Restriction.objects.create(
            name='Max 3 workers/shift', engine='count', severity='error',
            config={'subject': 'workers', 'groupBy': 'shift', 'operator': 'lte', 'threshold': 3},
        )
        plan = [self._day(morning=[
            self._assignment(self.w1),
            self._assignment(self.w2),
        ])]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 0)

    def test_max_workers_per_shift_fail(self):
        r = Restriction.objects.create(
            name='Max 1 worker/shift', engine='count', severity='error',
            config={'subject': 'workers', 'groupBy': 'shift', 'operator': 'lte', 'threshold': 1},
        )
        plan = [self._day(morning=[
            self._assignment(self.w1),
            self._assignment(self.w2),
        ])]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 1)
        self.assertIn('2', violations[0]['message'])

    def test_min_workers_per_shift(self):
        r = Restriction.objects.create(
            name='Min 2 workers/shift', engine='count', severity='error',
            config={'subject': 'workers', 'groupBy': 'shift', 'operator': 'gte', 'threshold': 2},
        )
        plan = [self._day(morning=[self._assignment(self.w1)])]
        violations = engine.evaluate(r, plan)
        self.assertGreater(len(violations), 0)

    def test_max_shifts_per_day_worker(self):
        r = Restriction.objects.create(
            name='Max 1 shift/day', engine='count', severity='error',
            config={'subject': 'shifts', 'groupBy': 'day_worker', 'operator': 'lte', 'threshold': 1},
        )
        plan = [self._day(
            morning=[self._assignment(self.w1)],
            night=[self._assignment(self.w1)],
        )]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 1)
        self.assertIn('Ana Garcia', violations[0]['message'])

    def test_max_shifts_per_day_pass(self):
        r = Restriction.objects.create(
            name='Max 1 shift/day', engine='count', severity='error',
            config={'subject': 'shifts', 'groupBy': 'day_worker', 'operator': 'lte', 'threshold': 1},
        )
        plan = [self._day(morning=[self._assignment(self.w1)])]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 0)

    def test_count_per_shift_area(self):
        r = Restriction.objects.create(
            name='Max 2 workers/area', engine='count', severity='error',
            config={'subject': 'workers', 'groupBy': 'shift_area', 'operator': 'lte', 'threshold': 2},
        )
        plan = [self._day(morning=[
            self._assignment(self.w1, areas=['Farmacia']),
            self._assignment(self.w2, areas=['Farmacia']),
            self._assignment(self.w3, areas=['Farmacia']),
        ])]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 1)
        self.assertIn('Farmacia', violations[0]['message'])

    def test_min_workers_per_area_no_one(self):
        r = Restriction.objects.create(
            name='Min 1 worker/area', engine='count', severity='error',
            config={'subject': 'workers', 'groupBy': 'shift_area', 'operator': 'gte', 'threshold': 1},
        )
        # Only assignments in 'Farmacia', none in 'Laboratorio'
        plan = [self._day(morning=[
            self._assignment(self.w1, areas=['Farmacia']),
        ])]
        violations = engine.evaluate(r, plan)
        # No violation for 'Laboratorio' since it's not present in the plan
        # groupBy shift_area counts per (shift, area) — only areas that appear
        self.assertEqual(len(violations), 0)

    def test_count_with_role_filter(self):
        r = Restriction.objects.create(
            name='Min 1 farmaceutico/shift', engine='count', severity='error',
            config={
                'subject': 'workers', 'groupBy': 'shift', 'operator': 'gte', 'threshold': 1,
                'filterField': 'role', 'filterValue': self.role_farm.id,
            },
        )
        # Only auxiliar → fail
        plan = [self._day(morning=[self._assignment(self.w2)])]
        violations = engine.evaluate(r, plan)
        self.assertGreater(len(violations), 0)

    def test_count_with_role_filter_pass(self):
        engine.clear_cache()
        r = Restriction.objects.create(
            name='Min 1 farmaceutico/shift', engine='count', severity='error',
            config={
                'subject': 'workers', 'groupBy': 'shift', 'operator': 'gte', 'threshold': 1,
                'filterField': 'role', 'filterValue': self.role_farm.id,
            },
        )
        # Farmaceutico in ALL shifts → no violations
        plan = [self._day(
            morning=[self._assignment(self.w1)],
            afternoon=[self._assignment(self.w3)],  # w3 is also Farmaceutico
            night=[self._assignment(self.w1)],
        )]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 0)

    def test_count_per_shift_worker_areas(self):
        r = Restriction.objects.create(
            name='Max 2 areas/worker/shift', engine='count', severity='error',
            config={'subject': 'areas', 'groupBy': 'shift_worker', 'operator': 'lte', 'threshold': 2},
        )
        plan = [self._day(morning=[
            self._assignment(self.w1, areas=['Farmacia', 'Laboratorio', 'Almacen']),
        ])]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 1)

    def test_ignores_zero_worker_id(self):
        r = Restriction.objects.create(
            name='Max 5/shift', engine='count', severity='error',
            config={'subject': 'workers', 'groupBy': 'shift', 'operator': 'lte', 'threshold': 5},
        )
        plan = [self._day(morning=[{'workerId': 0, 'areas': []}])]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 0)


# ---------------------------------------------------------------------------
# EXCLUSION ENGINE TESTS
# ---------------------------------------------------------------------------
class ExclusionConsecutiveTest(EngineTestMixin, TestCase):

    def test_consecutive_night_morning_violation(self):
        r = Restriction.objects.create(
            name='No noche-manana', engine='exclusion', severity='error',
            config={'exclusionType': 'consecutive_shifts', 'shiftA': self.N, 'shiftB': self.M},
        )
        plan = [
            self._day(date='2026-04-13', night=[self._assignment(self.w1)]),
            self._day(date='2026-04-14', morning=[self._assignment(self.w1)]),
        ]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 1)
        self.assertIn('Ana Garcia', violations[0]['message'])
        self.assertEqual(violations[0]['dayDate'], '2026-04-14')

    def test_consecutive_no_violation(self):
        r = Restriction.objects.create(
            name='No noche-manana', engine='exclusion', severity='error',
            config={'exclusionType': 'consecutive_shifts', 'shiftA': self.N, 'shiftB': self.M},
        )
        plan = [
            self._day(date='2026-04-13', night=[self._assignment(self.w1)]),
            self._day(date='2026-04-14', morning=[self._assignment(self.w2)]),  # different worker
        ]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 0)

    def test_consecutive_last_day_no_crash(self):
        """Last day has no next day, should not crash."""
        r = Restriction.objects.create(
            name='No noche-manana', engine='exclusion', severity='error',
            config={'exclusionType': 'consecutive_shifts', 'shiftA': self.N, 'shiftB': self.M},
        )
        plan = [self._day(date='2026-04-19', night=[self._assignment(self.w1)])]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 0)


class ExclusionWorkerPairTest(EngineTestMixin, TestCase):

    def test_incompatible_pair_violation(self):
        r = Restriction.objects.create(
            name='Incompatibles', engine='exclusion', severity='error',
            config={'exclusionType': 'worker_pair', 'workerPairs': [[self.w1.id, self.w2.id]]},
        )
        plan = [self._day(morning=[
            self._assignment(self.w1),
            self._assignment(self.w2),
        ])]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 1)
        self.assertIn('incompatibles', violations[0]['message'])

    def test_incompatible_pair_ok_different_shifts(self):
        r = Restriction.objects.create(
            name='Incompatibles', engine='exclusion', severity='error',
            config={'exclusionType': 'worker_pair', 'workerPairs': [[self.w1.id, self.w2.id]]},
        )
        plan = [self._day(
            morning=[self._assignment(self.w1)],
            night=[self._assignment(self.w2)],
        )]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 0)

    def test_empty_pairs_no_crash(self):
        r = Restriction.objects.create(
            name='Incomp', engine='exclusion', severity='error',
            config={'exclusionType': 'worker_pair', 'workerPairs': []},
        )
        plan = [self._day(morning=[self._assignment(self.w1)])]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 0)


class ExclusionRestConflictTest(EngineTestMixin, TestCase):

    def test_rest_conflict_with_int_list(self):
        r = Restriction.objects.create(
            name='Descanso', engine='exclusion', severity='error',
            config={'exclusionType': 'rest_conflict'},
        )
        plan = [self._day(
            rest=[self.w1.id],
            morning=[self._assignment(self.w1)],
        )]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 1)
        self.assertIn('descanso', violations[0]['message'].lower())

    def test_rest_conflict_with_dict_list(self):
        r = Restriction.objects.create(
            name='Descanso', engine='exclusion', severity='error',
            config={'exclusionType': 'rest_conflict'},
        )
        plan = [self._day(
            rest=[{'workerId': self.w2.id}],
            morning=[self._assignment(self.w2)],
        )]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 1)

    def test_rest_no_conflict(self):
        r = Restriction.objects.create(
            name='Descanso', engine='exclusion', severity='error',
            config={'exclusionType': 'rest_conflict'},
        )
        plan = [self._day(
            rest=[self.w3.id],
            morning=[self._assignment(self.w1)],
        )]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 0)


# ---------------------------------------------------------------------------
# MATCH ENGINE TESTS
# ---------------------------------------------------------------------------
class MatchPreferenceTest(EngineTestMixin, TestCase):

    def test_preference_warning(self):
        WorkerPreference.objects.create(worker=self.w1, shift_type=self.M)
        r = Restriction.objects.create(
            name='Preferencia', engine='match', severity='warning',
            config={'matchType': 'worker_preference'},
        )
        # w1 prefers morning but assigned to night
        plan = [self._day(night=[self._assignment(self.w1)])]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]['severity'], 'warning')
        self.assertIn('no preferido', violations[0]['message'])

    def test_preference_match_ok(self):
        WorkerPreference.objects.create(worker=self.w1, shift_type=self.M)
        r = Restriction.objects.create(
            name='Preferencia', engine='match', severity='warning',
            config={'matchType': 'worker_preference'},
        )
        plan = [self._day(morning=[self._assignment(self.w1)])]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 0)

    def test_worker_without_prefs_not_flagged(self):
        """Workers with no preferences should not trigger violations."""
        r = Restriction.objects.create(
            name='Preferencia', engine='match', severity='warning',
            config={'matchType': 'worker_preference'},
        )
        plan = [self._day(morning=[self._assignment(self.w2)])]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 0)


class MatchAreaRoleTest(EngineTestMixin, TestCase):

    def test_area_role_violation(self):
        r = Restriction.objects.create(
            name='Rol area', engine='match', severity='error',
            config={'matchType': 'area_role'},
        )
        # w2 is Auxiliar but assigned to Farmacia (requires Farmaceutico)
        plan = [self._day(morning=[
            self._assignment(self.w2, areas=['Farmacia']),
        ])]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 1)
        self.assertIn('Farmaceutico', violations[0]['message'])

    def test_area_role_correct(self):
        r = Restriction.objects.create(
            name='Rol area', engine='match', severity='error',
            config={'matchType': 'area_role'},
        )
        # w1 is Farmaceutico, assigned to Farmacia — OK
        plan = [self._day(morning=[
            self._assignment(self.w1, areas=['Farmacia']),
        ])]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 0)

    def test_area_no_required_role(self):
        r = Restriction.objects.create(
            name='Rol area', engine='match', severity='error',
            config={'matchType': 'area_role'},
        )
        # Laboratorio has no required_role, anyone can go
        plan = [self._day(morning=[
            self._assignment(self.w2, areas=['Laboratorio']),
        ])]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 0)


# ---------------------------------------------------------------------------
# ENGINE DISPATCH & EDGE CASES
# ---------------------------------------------------------------------------
class EngineEdgeCaseTest(EngineTestMixin, TestCase):

    def test_unknown_engine_returns_empty(self):
        r = Restriction.objects.create(
            name='Unknown', engine='fuzzy', config={},
        )
        violations = engine.evaluate(r, [])
        self.assertEqual(violations, [])

    def test_unknown_exclusion_type(self):
        r = Restriction.objects.create(
            name='Unknown excl', engine='exclusion', config={'exclusionType': 'unicorn'},
        )
        violations = engine.evaluate(r, [])
        self.assertEqual(violations, [])

    def test_unknown_match_type(self):
        r = Restriction.objects.create(
            name='Unknown match', engine='match', config={'matchType': 'magic'},
        )
        violations = engine.evaluate(r, [])
        self.assertEqual(violations, [])

    def test_empty_plan(self):
        r = Restriction.objects.create(
            name='Count', engine='count', severity='error',
            config={'subject': 'workers', 'groupBy': 'shift', 'operator': 'lte', 'threshold': 5},
        )
        violations = engine.evaluate(r, [])
        self.assertEqual(violations, [])

    def test_empty_config(self):
        r = Restriction.objects.create(name='No config', engine='count', config={})
        violations = engine.evaluate(r, [self._day(morning=[self._assignment(self.w1)])])
        # Should not crash — uses defaults
        self.assertIsInstance(violations, list)

    def test_violation_structure(self):
        r = Restriction.objects.create(
            name='Test Name', engine='count', severity='warning',
            config={'subject': 'shifts', 'groupBy': 'day_worker', 'operator': 'lte', 'threshold': 1},
        )
        plan = [self._day(
            morning=[self._assignment(self.w1)],
            night=[self._assignment(self.w1)],
        )]
        violations = engine.evaluate(r, plan)
        self.assertEqual(len(violations), 1)
        v = violations[0]
        self.assertEqual(v['restrictionId'], r.id)
        self.assertEqual(v['restrictionName'], 'Test Name')
        self.assertEqual(v['severity'], 'warning')
        self.assertEqual(v['dayDate'], '2026-04-13')
        self.assertIn('shift', v)
        self.assertIn('message', v)


# ---------------------------------------------------------------------------
# VALIDATORS (validate_plan integration)
# ---------------------------------------------------------------------------
class ValidatePlanTest(EngineTestMixin, TestCase):

    def test_validate_plan_aggregates_all_restrictions(self):
        from .validators import validate_plan
        Restriction.objects.create(
            name='Max 1 shift/day', engine='count', severity='error', active=True,
            config={'subject': 'shifts', 'groupBy': 'day_worker', 'operator': 'lte', 'threshold': 1},
        )
        Restriction.objects.create(
            name='Descanso', engine='exclusion', severity='error', active=True,
            config={'exclusionType': 'rest_conflict'},
        )
        plan = [self._day(
            rest=[self.w1.id],
            morning=[self._assignment(self.w1)],
            night=[self._assignment(self.w1)],
        )]
        violations = validate_plan(plan)
        # Should have at least 2: max shifts + rest conflict
        self.assertGreaterEqual(len(violations), 2)
        names = {v['restrictionName'] for v in violations}
        self.assertIn('Max 1 shift/day', names)
        self.assertIn('Descanso', names)

    def test_validate_plan_inactive_restrictions_ignored(self):
        from .validators import validate_plan
        Restriction.objects.create(
            name='Inactive', engine='count', severity='error', active=False,
            config={'subject': 'shifts', 'groupBy': 'day_worker', 'operator': 'lte', 'threshold': 1},
        )
        plan = [self._day(
            morning=[self._assignment(self.w1)],
            night=[self._assignment(self.w1)],
        )]
        violations = validate_plan(plan)
        self.assertEqual(len(violations), 0)


# ---------------------------------------------------------------------------
# API TESTS
# ---------------------------------------------------------------------------
class ValidationAPITest(EngineTestMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        Restriction.objects.create(
            name='Max 1/day', engine='count', severity='error', active=True,
            config={'subject': 'shifts', 'groupBy': 'day_worker', 'operator': 'lte', 'threshold': 1},
        )

    def test_validate_endpoint_success(self):
        plan = [self._day(morning=[self._assignment(self.w1)])]
        resp = self.client.post('/api/restrictions/validate/', {'plan': plan}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['isValid'])
        self.assertEqual(resp.data['violations'], [])

    def test_validate_endpoint_violations(self):
        plan = [self._day(
            morning=[self._assignment(self.w1)],
            night=[self._assignment(self.w1)],
        )]
        resp = self.client.post('/api/restrictions/validate/', {'plan': plan}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['isValid'])
        self.assertGreater(len(resp.data['violations']), 0)

    def test_validate_endpoint_empty_plan(self):
        resp = self.client.post('/api/restrictions/validate/', {'plan': []}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_validate_endpoint_no_plan(self):
        resp = self.client.post('/api/restrictions/validate/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_engine_schema_endpoint(self):
        resp = self.client.get('/api/restrictions/engine_schema/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('count', resp.data)
        self.assertIn('exclusion', resp.data)
        self.assertIn('match', resp.data)

    def test_constraints_endpoint(self):
        resp = self.client.get('/api/restrictions/constraints/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('count', resp.data)

    def test_restriction_crud(self):
        resp = self.client.post('/api/restrictions/', {
            'name': 'Nueva',
            'engine': 'count',
            'config': {'subject': 'workers', 'groupBy': 'shift', 'operator': 'lte', 'threshold': 5},
            'severity': 'warning',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        rid = resp.data['id']

        resp = self.client.get(f'/api/restrictions/{rid}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['name'], 'Nueva')

        resp = self.client.patch(f'/api/restrictions/{rid}/', {'name': 'Editada'}, format='json')
        self.assertEqual(resp.status_code, 200)

        resp = self.client.delete(f'/api/restrictions/{rid}/')
        self.assertEqual(resp.status_code, 204)


class CustomizableRestrictionTest(TestCase):
    """Flag `customizable` + endpoint de duplicado.

    Fija = el cliente solo la activa/desactiva.
    Personalizable = el cliente edita valores, la duplica y le asigna ambito.
    """

    def setUp(self):
        self.client = APIClient()
        self.custom = Restriction.objects.create(
            name='Trabajadores incompatibles', engine='exclusion',
            severity='error', active=True, customizable=True,
            config={'exclusionType': 'worker_pair', 'workerPairs': [[1, 2]]},
            scope_records=[10],
        )
        self.fixed = Restriction.objects.create(
            name='Max 1 turno al dia', engine='count', severity='error', active=True,
            config={'subject': 'shifts', 'groupBy': 'day_worker', 'operator': 'lte', 'threshold': 1},
        )

    def test_customizable_defaults_to_false(self):
        self.assertFalse(self.fixed.customizable)

    def test_customizable_is_exposed_by_api(self):
        resp = self.client.get(f'/api/restrictions/{self.custom.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['customizable'])
        self.assertIsNone(resp.data['duplicated_from'])

    def test_duplicate_creates_independent_copy(self):
        resp = self.client.post(f'/api/restrictions/{self.custom.id}/duplicate/', {}, format='json')
        self.assertEqual(resp.status_code, 201)
        copy = Restriction.objects.get(pk=resp.data['id'])

        self.assertNotEqual(copy.pk, self.custom.pk)
        self.assertEqual(copy.name, 'Trabajadores incompatibles (copia)')
        self.assertEqual(copy.engine, self.custom.engine)
        self.assertEqual(copy.config, self.custom.config)
        self.assertTrue(copy.customizable)
        self.assertEqual(copy.duplicated_from_id, self.custom.pk)

        # La copia es autonoma: editar el original no la toca.
        self.custom.config = {'exclusionType': 'worker_pair', 'workerPairs': []}
        self.custom.save()
        copy.refresh_from_db()
        self.assertEqual(copy.config['workerPairs'], [[1, 2]])

        # Y su config no comparte referencia con la del original.
        self.assertIsNot(copy.config, self.custom.config)

    def test_duplicate_accepts_name_and_scope(self):
        resp = self.client.post(
            f'/api/restrictions/{self.custom.id}/duplicate/',
            {'name': 'Incompatibles Huesca', 'scope_records': [7, 8]},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['name'], 'Incompatibles Huesca')
        self.assertEqual(resp.data['scope_records'], [7, 8])

    def test_duplicate_inherits_scope_when_not_given(self):
        resp = self.client.post(f'/api/restrictions/{self.custom.id}/duplicate/', {}, format='json')
        self.assertEqual(resp.data['scope_records'], [10])

    def test_duplicate_allows_empty_scope(self):
        """scope_records=[] debe respetarse (aplica a todos), no heredar el del original."""
        resp = self.client.post(
            f'/api/restrictions/{self.custom.id}/duplicate/',
            {'scope_records': []}, format='json',
        )
        self.assertEqual(resp.data['scope_records'], [])

    def test_duplicate_avoids_name_collision(self):
        first = self.client.post(f'/api/restrictions/{self.custom.id}/duplicate/', {}, format='json')
        second = self.client.post(f'/api/restrictions/{self.custom.id}/duplicate/', {}, format='json')
        self.assertEqual(first.data['name'], 'Trabajadores incompatibles (copia)')
        self.assertEqual(second.data['name'], 'Trabajadores incompatibles (copia 2)')

    def test_duplicate_rejects_fixed_restriction(self):
        resp = self.client.post(f'/api/restrictions/{self.fixed.id}/duplicate/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Restriction.objects.filter(duplicated_from=self.fixed).count(), 0)

    def test_deleting_original_keeps_copy(self):
        resp = self.client.post(f'/api/restrictions/{self.custom.id}/duplicate/', {}, format='json')
        copy_id = resp.data['id']
        self.custom.delete()
        copy = Restriction.objects.get(pk=copy_id)
        self.assertIsNone(copy.duplicated_from_id)
