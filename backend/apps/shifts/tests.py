from datetime import date, time, timedelta

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Shift


class TestShiftValidityModel(TestCase):
    """Vigencia por rango de fechas en el modelo Shift (AC-1, AC-2, AC-5)."""

    def _shift(self, **kwargs):
        base = dict(name='T', start_time=time(9, 0), end_time=time(15, 0))
        base.update(kwargs)
        return Shift.objects.create(**base)

    def test_normal_shift_has_no_validity(self):
        s = self._shift()
        self.assertFalse(s.has_validity)
        self.assertTrue(s.is_active_on(date(2020, 1, 1)))
        self.assertTrue(s.is_active_on(date(2099, 12, 31)))

    def test_range_active_only_within(self):  # AC-2
        s = self._shift(valid_from=date(2026, 12, 20), valid_to=date(2027, 1, 6))
        self.assertTrue(s.has_validity)
        self.assertFalse(s.is_active_on(date(2026, 12, 19)))  # antes
        self.assertTrue(s.is_active_on(date(2026, 12, 20)))   # inicio inclusive
        self.assertTrue(s.is_active_on(date(2026, 12, 31)))   # dentro
        self.assertTrue(s.is_active_on(date(2027, 1, 6)))     # fin inclusive
        self.assertFalse(s.is_active_on(date(2027, 1, 7)))    # después

    def test_open_ended_from(self):
        s = self._shift(valid_from=date(2026, 8, 1), valid_to=None)
        self.assertFalse(s.is_active_on(date(2026, 7, 31)))
        self.assertTrue(s.is_active_on(date(2030, 1, 1)))

    def test_open_ended_to(self):
        s = self._shift(valid_from=None, valid_to=date(2026, 8, 10))
        self.assertTrue(s.is_active_on(date(2000, 1, 1)))
        self.assertFalse(s.is_active_on(date(2026, 8, 11)))

    def test_is_expired(self):  # AC-5
        past = self._shift(valid_to=date(2026, 1, 1))
        self.assertTrue(past.is_expired(date(2026, 7, 20)))
        future = self._shift(valid_to=date(2099, 1, 1))
        self.assertFalse(future.is_expired(date(2026, 7, 20)))
        normal = self._shift()
        self.assertFalse(normal.is_expired(date(2026, 7, 20)))


class TestShiftValiditySerializer(TestCase):
    """El serializer valida el rango y expone los campos (AC-1)."""

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/shifts/'

    def test_create_with_validity(self):
        resp = self.client.post(self.url, {
            'name': 'Refuerzo Navidad',
            'start_time': '09:00', 'end_time': '21:00',
            'valid_from': '2026-12-20', 'valid_to': '2027-01-06',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['valid_from'], '2026-12-20')
        self.assertEqual(resp.data['valid_to'], '2027-01-06')

    def test_rejects_from_after_to(self):
        resp = self.client.post(self.url, {
            'name': 'Malo', 'start_time': '09:00', 'end_time': '15:00',
            'valid_from': '2027-01-10', 'valid_to': '2027-01-01',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('valid_to', resp.data)

    def test_normal_shift_serializes_nulls(self):
        resp = self.client.post(self.url, {
            'name': 'Mañana', 'start_time': '09:00', 'end_time': '15:00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.data['valid_from'])
        self.assertIsNone(resp.data['valid_to'])


class TestShiftValidityEndpointFilter(TestCase):
    """El listado filtra por vigencia según ?date / ?active (AC-2, AC-5)."""

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/shifts/'
        self.normal = Shift.objects.create(name='Normal', start_time=time(9, 0), end_time=time(15, 0))
        self.xmas = Shift.objects.create(
            name='Navidad', start_time=time(9, 0), end_time=time(21, 0),
            valid_from=date(2026, 12, 20), valid_to=date(2027, 1, 6),
        )
        self.expired = Shift.objects.create(
            name='Caducado', start_time=time(9, 0), end_time=time(15, 0),
            valid_from=date(2025, 1, 1), valid_to=date(2025, 1, 10),
        )

    def _names(self, resp):
        return {s['name'] for s in resp.data}

    def test_date_inside_range_includes_extra(self):  # AC-2
        resp = self.client.get(f'{self.url}?date=2026-12-25')
        names = self._names(resp)
        self.assertIn('Normal', names)   # normal siempre
        self.assertIn('Navidad', names)  # vigente ese día
        self.assertNotIn('Caducado', names)

    def test_date_outside_range_excludes_extra(self):  # AC-2
        resp = self.client.get(f'{self.url}?date=2026-07-20')
        names = self._names(resp)
        self.assertIn('Normal', names)
        self.assertNotIn('Navidad', names)   # aún no vigente
        self.assertNotIn('Caducado', names)

    def test_active_excludes_expired(self):  # AC-5
        resp = self.client.get(f'{self.url}?active=true')
        names = self._names(resp)
        self.assertIn('Normal', names)
        self.assertIn('Navidad', names)      # vigencia futura, sigue disponible
        self.assertNotIn('Caducado', names)  # ya caducado

    def test_all_endpoint_includes_history(self):  # AC-5 (histórico visible en admin)
        resp = self.client.get(f'{self.url}all/')
        names = self._names(resp)
        self.assertIn('Caducado', names)
