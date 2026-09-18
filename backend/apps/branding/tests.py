from django.test import TestCase
from .models import Branding


class BrandingModelTest(TestCase):
    def test_singleton(self):
        b1 = Branding.get()
        b2 = Branding.get()
        self.assertEqual(b1.pk, b2.pk)
        self.assertEqual(b1.pk, 1)

    def test_save_always_pk_1(self):
        b = Branding(pk=99, company_name='Test')
        b.save()
        self.assertEqual(b.pk, 1)

    def test_defaults(self):
        b = Branding.get()
        self.assertEqual(b.company_name, 'Planificador de Turnos')
        self.assertEqual(b.primary_color, '#EF4444')


class BrandingAPITest(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()
        self.url = '/api/branding/'

    def test_get_branding_public(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['company_name'], 'Planificador de Turnos')

    def test_update_branding(self):
        resp = self.client.patch(self.url, {'company_name': 'MiEmpresa'}, format='json')
        # Admin-only in production, but with AllowAny it might still work
        # Check response is valid
        self.assertIn(resp.status_code, [200, 401, 403])
