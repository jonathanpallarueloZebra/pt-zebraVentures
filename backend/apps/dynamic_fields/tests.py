from django.test import TestCase
from rest_framework.test import APIClient
from .models import EntityField
from .mixins import invalidate_fields_cache


class EntityFieldModelTest(TestCase):
    def test_create(self):
        ef = EntityField.objects.create(
            entity_type='role', key='color', label='Color', field_type='color',
        )
        self.assertIn('role', str(ef))
        self.assertIn('Color', str(ef))

    def test_unique_together(self):
        EntityField.objects.create(entity_type='role', key='campo1', label='C1', field_type='text')
        with self.assertRaises(Exception):
            EntityField.objects.create(entity_type='role', key='campo1', label='C2', field_type='text')


class DynamicFieldsMixinTest(TestCase):
    """Test the mixin via the Worker API which uses DynamicFieldsMixin."""

    def setUp(self):
        self.client = APIClient()
        invalidate_fields_cache()
        EntityField.objects.create(
            entity_type='worker', key='department', label='Departamento',
            field_type='text', default_value='General', active=True,
        )

    def test_field_schema_included(self):
        from apps.workers.models import Worker
        w = Worker.objects.create(name='Test')
        resp = self.client.get(f'/api/workers/{w.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('field_schema', resp.data)
        schema_keys = [f['key'] for f in resp.data['field_schema']]
        self.assertIn('department', schema_keys)

    def test_defaults_applied_on_create(self):
        resp = self.client.post('/api/workers/', {'name': 'Nuevo'}, format='json')
        self.assertEqual(resp.status_code, 201)
        from apps.workers.models import Worker
        w = Worker.objects.get(name='Nuevo')
        self.assertEqual(w.custom_data.get('department'), 'General')

    def test_custom_data_returned(self):
        from apps.workers.models import Worker
        Worker.objects.create(name='Custom', custom_data={'department': 'Farmacia'})
        resp = self.client.get('/api/workers/')
        self.assertEqual(resp.status_code, 200)
        worker_data = [r for r in resp.data if r['name'] == 'Custom'][0]
        self.assertEqual(worker_data['custom_data']['department'], 'Farmacia')


class EntityFieldAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/entity-fields/'

    def test_crud(self):
        resp = self.client.post(self.url, {
            'entity_type': 'worker',
            'key': 'phone',
            'label': 'Telefono',
            'field_type': 'text',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        eid = resp.data['id']

        resp = self.client.get(f'{self.url}{eid}/')
        self.assertEqual(resp.status_code, 200)

        resp = self.client.patch(f'{self.url}{eid}/', {'label': 'Movil'}, format='json')
        self.assertEqual(resp.status_code, 200)

        resp = self.client.delete(f'{self.url}{eid}/')
        self.assertEqual(resp.status_code, 204)

    def test_by_entity_endpoint(self):
        EntityField.objects.create(entity_type='worker', key='f1', label='F1', field_type='text')
        EntityField.objects.create(entity_type='area', key='f2', label='F2', field_type='text')
        resp = self.client.get(f'{self.url}by-entity/worker/')
        self.assertEqual(resp.status_code, 200)
        keys = [f['key'] for f in resp.data]
        self.assertIn('f1', keys)
        self.assertNotIn('f2', keys)


class ShiftDropdownRecordsTest(TestCase):
    """`?entity_type=shift` alimenta los desplegables de turno (turno base /
    alternativo / sábado). No debe ofrecer turnos extra ya caducados, pero sí
    los normales y los que aún no han empezado."""

    def setUp(self):
        from datetime import date, time, timedelta

        from apps.shifts.models import Shift

        self.client = APIClient()
        self.url = '/api/entity-records/?entity_type=shift'
        today = date.today()

        self.normal = Shift.objects.create(
            name='Mañana', start_time=time(7, 45), end_time=time(14, 45))
        self.expired = Shift.objects.create(
            name='Refuerzo caducado', start_time=time(9, 0), end_time=time(21, 0),
            valid_from=today - timedelta(days=30), valid_to=today - timedelta(days=1))
        self.ends_today = Shift.objects.create(
            name='Acaba hoy', start_time=time(9, 0), end_time=time(15, 0),
            valid_from=today - timedelta(days=5), valid_to=today)
        self.future = Shift.objects.create(
            name='Futuro', start_time=time(9, 0), end_time=time(15, 0),
            valid_from=today + timedelta(days=10), valid_to=today + timedelta(days=20))

    def _names(self, resp):
        return {r['data']['nombre'] for r in resp.data}

    def test_excludes_expired_shifts(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Refuerzo caducado', self._names(resp))

    def test_keeps_normal_and_upcoming_shifts(self):
        names = self._names(self.client.get(self.url))
        self.assertIn('Mañana', names)     # sin vigencia → siempre
        self.assertIn('Acaba hoy', names)  # último día es inclusivo
        self.assertIn('Futuro', names)     # aún no empieza, pero no ha caducado

    def test_admin_view_still_lists_expired(self):
        """El turno caducado no se borra: sigue en la vista de admin."""
        names = {s['name'] for s in self.client.get('/api/shifts/all/').data}
        self.assertIn('Refuerzo caducado', names)
