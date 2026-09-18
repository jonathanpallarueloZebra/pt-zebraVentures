from datetime import date, timedelta

from django.test import TestCase
from rest_framework.test import APIClient
from apps.workers.models import Worker
from .models import RestDay


class RestDayModelTest(TestCase):
    def setUp(self):
        self.worker = Worker.objects.create(name='Ana')

    def test_create(self):
        rd = RestDay.objects.create(worker=self.worker, date='2026-04-13', reason='Vacaciones')
        self.assertEqual(str(rd), 'Ana - 2026-04-13')

    def test_unique_together(self):
        RestDay.objects.create(worker=self.worker, date='2026-04-13')
        with self.assertRaises(Exception):
            RestDay.objects.create(worker=self.worker, date='2026-04-13')


class RestDayAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/rest-days/'
        self.worker = Worker.objects.create(name='Ana')

    def test_create_rest_day(self):
        resp = self.client.post(self.url, {
            'workerId': self.worker.id,
            'date': '2026-04-13',
            'reason': 'Descanso semanal',
        }, format='json')
        self.assertEqual(resp.status_code, 201)

    def test_weekly_endpoint(self):
        RestDay.objects.create(worker=self.worker, date='2026-04-13')
        RestDay.objects.create(worker=self.worker, date='2026-04-15')
        RestDay.objects.create(worker=self.worker, date='2026-04-25')  # outside range
        resp = self.client.get(f'{self.url}weekly/?start=2026-04-13')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)

    def test_weekly_requires_start(self):
        resp = self.client.get(f'{self.url}weekly/')
        self.assertEqual(resp.status_code, 400)
