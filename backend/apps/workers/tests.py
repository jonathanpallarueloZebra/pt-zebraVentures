from django.test import TestCase
from rest_framework.test import APIClient
from .models import Worker, WorkerPreference


class WorkerModelTest(TestCase):
    def test_create_worker(self):
        w = Worker.objects.create(name='Ana Garcia')
        self.assertEqual(str(w), 'Ana Garcia')
        self.assertTrue(w.active)

    def test_worker_preference(self):
        w = Worker.objects.create(name='Ana Garcia')
        WorkerPreference.objects.create(worker=w, shift_type='morning')
        WorkerPreference.objects.create(worker=w, shift_type='afternoon')
        self.assertEqual(w.preferences.count(), 2)

    def test_preference_unique_together(self):
        w = Worker.objects.create(name='Ana Garcia')
        WorkerPreference.objects.create(worker=w, shift_type='morning')
        with self.assertRaises(Exception):
            WorkerPreference.objects.create(worker=w, shift_type='morning')


class WorkerAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/workers/'

    def test_list_workers_only_active(self):
        Worker.objects.create(name='Activo')
        Worker.objects.create(name='Inactivo', active=False)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        names = [w['name'] for w in resp.data]
        self.assertIn('Activo', names)
        self.assertNotIn('Inactivo', names)

    def test_all_endpoint_includes_inactive(self):
        Worker.objects.create(name='Activo')
        Worker.objects.create(name='Inactivo', active=False)
        resp = self.client.get(f'{self.url}all/')
        self.assertEqual(resp.status_code, 200)
        names = [w['name'] for w in resp.data]
        self.assertIn('Activo', names)
        self.assertIn('Inactivo', names)

    def test_create_worker_with_preferences(self):
        resp = self.client.post(self.url, {
            'name': 'Carlos',
            'preferredShifts': ['morning', 'night'],
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        w = Worker.objects.get(name='Carlos')
        self.assertEqual(w.preferences.count(), 2)

    def test_update_worker_replaces_preferences(self):
        w = Worker.objects.create(name='Ana')
        WorkerPreference.objects.create(worker=w, shift_type='morning')
        resp = self.client.put(f'{self.url}{w.id}/', {
            'name': 'Ana',
            'preferredShifts': ['night'],
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(w.preferences.values_list('shift_type', flat=True)), ['night'])
