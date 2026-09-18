"""Tests de la generacion masiva por lista de ambitos (zona / todas).

La opcion "Generar esta zona" no anade endpoint: manda al de generacion masiva
un SUBCONJUNTO de tiendas. Estos tests fijan ese contrato, que es lo que permite
que zona y todas compartan algoritmo.
"""
from datetime import date, time

from django.test import TestCase
from rest_framework.test import APIClient

from apps.authentication.models import CustomUser
from apps.dynamic_fields.models import EntityRecord, EntityType
from apps.planning.models import WeeklyPlan
from apps.shifts.models import Shift


class TestGeneracionMasivaPorLista(TestCase):
    """El endpoint acepta cualquier lista de ambitos, no solo 'todas'."""

    def setUp(self):
        from django.conf import settings
        if 'testserver' not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']
        self.client = APIClient()
        user = CustomUser.objects.create_user(
            username='zonatest', email='zona@test.com', password='x',
            is_staff=True)
        self.client.force_authenticate(user=user)

        Shift.objects.create(name='Mañana', start_time=time(7, 45),
                             end_time=time(14, 45))
        et = EntityType.objects.create(
            slug='tienda', name='Tienda', is_planning_scope=True,
            display_field='codigo')
        # 2 tiendas en huesca, 1 en jaca
        self.t1 = EntityRecord.objects.create(
            entity_type=et, data={'codigo': 'T01', 'zona': 'huesca'})
        self.t2 = EntityRecord.objects.create(
            entity_type=et, data={'codigo': 'T02', 'zona': 'huesca'})
        self.t3 = EntityRecord.objects.create(
            entity_type=et, data={'codigo': 'T15', 'zona': 'jaca'})

    def _generar(self, scopes, start='2026-08-03'):
        return self.client.post('/api/planning/schedule/generate-bulk/',
                                {'startDate': start, 'scopes': scopes},
                                format='json')

    def test_acepta_una_lista_parcial_de_ambitos(self):
        """Es lo que hace 'Generar esta zona': mandar solo sus tiendas."""
        r = self._generar([self.t1.id, self.t2.id])
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))

    def test_devuelve_un_resultado_por_ambito_pedido(self):
        r = self._generar([self.t1.id, self.t2.id])
        results = (getattr(r, 'data', {}) or {}).get('results', [])
        self.assertEqual(len(results), 2)
        self.assertEqual({x['scope'] for x in results},
                         {self.t1.id, self.t2.id})

    def test_no_devuelve_ambitos_que_no_se_pidieron(self):
        """Generar la zona de huesca no debe tocar la tienda de jaca."""
        r = self._generar([self.t1.id, self.t2.id])
        results = (getattr(r, 'data', {}) or {}).get('results', [])
        self.assertNotIn(self.t3.id, {x['scope'] for x in results})

    def test_una_sola_tienda_tambien_vale(self):
        """Una zona de 1 tienda (caso Monzon) no es un caso especial."""
        r = self._generar([self.t3.id])
        self.assertEqual(r.status_code, 200)
        results = (getattr(r, 'data', {}) or {}).get('results', [])
        self.assertEqual(len(results), 1)

    def test_lista_vacia_da_error(self):
        r = self._generar([])
        self.assertEqual(r.status_code, 400)

    def test_scopes_debe_ser_lista(self):
        r = self.client.post('/api/planning/schedule/generate-bulk/',
                             {'startDate': '2026-08-03', 'scopes': self.t1.id},
                             format='json')
        self.assertEqual(r.status_code, 400)

    def test_no_guarda_los_planes(self):
        """La generacion masiva devuelve BORRADORES: guardar es del usuario."""
        self._generar([self.t1.id, self.t2.id])
        self.assertEqual(
            WeeklyPlan.objects.filter(start_date=date(2026, 8, 3)).count(), 0)


class TestZonaDeLasTiendas(TestCase):
    """El dato de zona vive en el registro de la tienda, no en otra tabla."""

    def setUp(self):
        et = EntityType.objects.create(
            slug='tienda', name='Tienda', is_planning_scope=True,
            display_field='codigo')
        for cod, zona in [('T01', 'huesca'), ('T02', 'huesca'),
                          ('T13', 'barbastro'), ('T19', 'monzon')]:
            EntityRecord.objects.create(
                entity_type=et, data={'codigo': cod, 'zona': zona})
        self.et = et

    def _zona_de(self, codigo):
        r = EntityRecord.objects.get(entity_type=self.et, data__codigo=codigo)
        return (r.data or {}).get('zona')

    def _tiendas_de_zona(self, zona):
        return [r for r in EntityRecord.objects.filter(entity_type=self.et)
                if (r.data or {}).get('zona') == zona]

    def test_la_zona_viene_en_el_registro(self):
        """El contador del desplegable no necesita ninguna llamada extra."""
        self.assertEqual(self._zona_de('T01'), 'huesca')

    def test_agrupa_las_tiendas_de_la_misma_zona(self):
        self.assertEqual(len(self._tiendas_de_zona('huesca')), 2)

    def test_una_zona_puede_tener_una_sola_tienda(self):
        self.assertEqual(len(self._tiendas_de_zona('monzon')), 1)

    def test_la_tienda_seleccionada_va_en_su_propia_zona(self):
        """AC-4: la zona incluye a la tienda desde la que se lanza."""
        t01 = EntityRecord.objects.get(entity_type=self.et, data__codigo='T01')
        ids = [r.id for r in self._tiendas_de_zona(self._zona_de('T01'))]
        self.assertIn(t01.id, ids)

    def test_no_mezcla_zonas(self):
        ids = {r.id for r in self._tiendas_de_zona('huesca')}
        t13 = EntityRecord.objects.get(entity_type=self.et, data__codigo='T13')
        self.assertNotIn(t13.id, ids)
