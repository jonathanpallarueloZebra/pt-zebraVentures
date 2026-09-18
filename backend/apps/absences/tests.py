from datetime import date, timedelta

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.workers.models import Worker
from apps.rest_days.models import RestDay
from .models import AbsenceType, AbsenceRequest

User = get_user_model()


class AbsenceTypeTest(TestCase):
    def test_create(self):
        at = AbsenceType.objects.create(name='Vacaciones')
        self.assertEqual(str(at), 'Vacaciones')
        self.assertTrue(at.requires_approval)
        self.assertTrue(at.active)

    def test_unique_name(self):
        AbsenceType.objects.create(name='Unico')
        with self.assertRaises(Exception):
            AbsenceType.objects.create(name='Unico')


class AbsenceRequestTest(TestCase):
    def setUp(self):
        self.worker = Worker.objects.create(name='Ana')
        self.type = AbsenceType.objects.create(name='Vacaciones')
        self.client = APIClient()
        self.url = '/api/absences/requests/'

    def test_create_request(self):
        resp = self.client.post(self.url, {
            'worker': self.worker.id,
            'type': self.type.id,
            'start_date': '2026-04-20',
            'end_date': '2026-04-22',
            'reason': 'Viaje',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(AbsenceRequest.objects.count(), 1)
        self.assertEqual(AbsenceRequest.objects.first().status, 'pending')

    def test_approve_creates_rest_days(self):
        ar = AbsenceRequest.objects.create(
            worker=self.worker, type=self.type,
            start_date=date(2026, 4, 20), end_date=date(2026, 4, 22),
        )
        resp = self.client.patch(f'{self.url}{ar.id}/approve/')
        self.assertEqual(resp.status_code, 200)
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'approved')
        # Should create 3 rest days (20, 21, 22)
        self.assertEqual(RestDay.objects.filter(worker=self.worker).count(), 3)

    def test_approve_idempotent_rest_days(self):
        """If a RestDay already exists, approve should not crash."""
        RestDay.objects.create(worker=self.worker, date=date(2026, 4, 20))
        ar = AbsenceRequest.objects.create(
            worker=self.worker, type=self.type,
            start_date=date(2026, 4, 20), end_date=date(2026, 4, 21),
        )
        resp = self.client.patch(f'{self.url}{ar.id}/approve/')
        self.assertEqual(resp.status_code, 200)
        # 2 distinct rest days (20 was pre-existing, 21 is new)
        self.assertEqual(RestDay.objects.filter(worker=self.worker).count(), 2)

    def test_reject_request(self):
        ar = AbsenceRequest.objects.create(
            worker=self.worker, type=self.type,
            start_date=date(2026, 4, 20), end_date=date(2026, 4, 20),
        )
        resp = self.client.patch(f'{self.url}{ar.id}/reject/')
        self.assertEqual(resp.status_code, 200)
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'rejected')
        # No rest days created
        self.assertEqual(RestDay.objects.filter(worker=self.worker).count(), 0)

    def test_cannot_approve_non_pending(self):
        ar = AbsenceRequest.objects.create(
            worker=self.worker, type=self.type,
            start_date=date(2026, 4, 20), end_date=date(2026, 4, 20),
            status='approved',
        )
        resp = self.client.patch(f'{self.url}{ar.id}/approve/')
        self.assertEqual(resp.status_code, 400)

    def test_cannot_reject_non_pending(self):
        ar = AbsenceRequest.objects.create(
            worker=self.worker, type=self.type,
            start_date=date(2026, 4, 20), end_date=date(2026, 4, 20),
            status='rejected',
        )
        resp = self.client.patch(f'{self.url}{ar.id}/reject/')
        self.assertEqual(resp.status_code, 400)

    def test_filter_by_status(self):
        AbsenceRequest.objects.create(
            worker=self.worker, type=self.type,
            start_date=date(2026, 4, 20), end_date=date(2026, 4, 20),
            status='pending',
        )
        AbsenceRequest.objects.create(
            worker=self.worker, type=self.type,
            start_date=date(2026, 4, 21), end_date=date(2026, 4, 21),
            status='approved',
        )
        resp = self.client.get(f'{self.url}?status=pending')
        self.assertEqual(len(resp.data), 1)

    def test_filter_by_worker(self):
        w2 = Worker.objects.create(name='Carlos')
        AbsenceRequest.objects.create(
            worker=self.worker, type=self.type,
            start_date=date(2026, 4, 20), end_date=date(2026, 4, 20),
        )
        AbsenceRequest.objects.create(
            worker=w2, type=self.type,
            start_date=date(2026, 4, 20), end_date=date(2026, 4, 20),
        )
        resp = self.client.get(f'{self.url}?worker={self.worker.id}')
        self.assertEqual(len(resp.data), 1)


class TestAbsenceIndefinite(TestCase):
    """Ausencia indefinida (sin fecha de fin) — checkbox + exclusión de planificación."""

    def setUp(self):
        self.worker = Worker.objects.create(name='Bea')
        self.type = AbsenceType.objects.create(name='Baja médica')
        self.client = APIClient()
        self.url = '/api/absences/requests/'

    # ── AC-1/AC-2: crear indefinida sin fecha de fin ────────────────────────
    def test_create_indefinite_without_end_date(self):
        resp = self.client.post(self.url, {
            'worker': self.worker.id, 'type': self.type.id,
            'start_date': '2026-07-20', 'indefinite': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ar = AbsenceRequest.objects.get(id=resp.data['id'])
        self.assertTrue(ar.indefinite)
        self.assertIsNone(ar.end_date)
        self.assertTrue(ar.is_open_ended)

    # ── AC-2: indefinida ignora la fecha de fin aunque venga ────────────────
    def test_indefinite_clears_end_date(self):
        resp = self.client.post(self.url, {
            'worker': self.worker.id, 'type': self.type.id,
            'start_date': '2026-07-20', 'end_date': '2026-08-01', 'indefinite': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(AbsenceRequest.objects.get(id=resp.data['id']).end_date)

    # ── AC-3: no indefinida exige fecha de fin ──────────────────────────────
    def test_non_indefinite_requires_end_date(self):
        resp = self.client.post(self.url, {
            'worker': self.worker.id, 'type': self.type.id,
            'start_date': '2026-07-20', 'indefinite': False,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('end_date', resp.data)

    def test_end_before_start_rejected(self):
        resp = self.client.post(self.url, {
            'worker': self.worker.id, 'type': self.type.id,
            'start_date': '2026-07-20', 'end_date': '2026-07-10',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    # ── AC-4: indefinida aprobada excluye de la planificación desde start ───
    def test_indefinite_blocks_planning_open_ended(self):
        from apps.planning.schedule_generator import _build_absent_map
        ar = AbsenceRequest.objects.create(
            worker=self.worker, type=self.type,
            start_date=date(2026, 7, 6), end_date=None, indefinite=True,
            status='approved',
        )
        # Semana MUY posterior al inicio: sigue bloqueado (sin fin).
        start = date(2026, 9, 7)  # lunes
        absent = _build_absent_map(start, start + timedelta(days=6))
        blocked_days = [d for d, wids in absent.items() if self.worker.id in wids]
        self.assertEqual(len(blocked_days), 7, 'La indefinida debe bloquear los 7 días de la semana')

    def test_indefinite_does_not_block_before_start(self):
        from apps.planning.schedule_generator import _build_absent_map
        AbsenceRequest.objects.create(
            worker=self.worker, type=self.type,
            start_date=date(2026, 8, 1), end_date=None, indefinite=True,
            status='approved',
        )
        # Semana ANTERIOR al inicio de la ausencia: no bloquea.
        start = date(2026, 7, 6)
        absent = _build_absent_map(start, start + timedelta(days=6))
        blocked = [d for d, wids in absent.items() if self.worker.id in wids]
        self.assertEqual(blocked, [])

    def test_indefinite_pending_does_not_block(self):
        from apps.planning.schedule_generator import _build_absent_map
        AbsenceRequest.objects.create(
            worker=self.worker, type=self.type,
            start_date=date(2026, 7, 6), end_date=None, indefinite=True,
            status='pending',  # aún no aprobada → no bloquea
        )
        start = date(2026, 7, 6)
        absent = _build_absent_map(start, start + timedelta(days=6))
        blocked = [d for d, wids in absent.items() if self.worker.id in wids]
        self.assertEqual(blocked, [])

    # ── AC-5: cerrar indefinida con fecha fin reactiva la disponibilidad ────
    def test_close_indefinite_with_end_date(self):
        ar = AbsenceRequest.objects.create(
            worker=self.worker, type=self.type,
            start_date=date(2026, 7, 6), end_date=None, indefinite=True,
            status='approved',
        )
        resp = self.client.patch(f'{self.url}{ar.id}/', {
            'indefinite': False, 'end_date': '2026-07-08',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ar.refresh_from_db()
        self.assertFalse(ar.indefinite)
        self.assertEqual(ar.end_date, date(2026, 7, 8))
        # Tras cerrarla, a partir del 9 el trabajador vuelve a estar disponible.
        from apps.planning.schedule_generator import _build_absent_map
        start = date(2026, 7, 6)
        absent = _build_absent_map(start, start + timedelta(days=6))
        blocked = sorted(d for d, wids in absent.items() if self.worker.id in wids)
        self.assertEqual(blocked, ['2026-07-06', '2026-07-07', '2026-07-08'])

    def test_approve_indefinite_no_crash(self):
        """Aprobar una indefinida (sin end_date) no debe crashear ni crear RestDay con fin."""
        ar = AbsenceRequest.objects.create(
            worker=self.worker, type=self.type,
            start_date=date(2026, 7, 6), end_date=None, indefinite=True,
        )
        resp = self.client.patch(f'{self.url}{ar.id}/approve/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'approved')
        # No se crean RestDay concretos para una indefinida.
        self.assertEqual(RestDay.objects.filter(worker=self.worker).count(), 0)
