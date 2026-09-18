"""
Tests del CRUD de días de cierre (/planning/closed-days/).

Cubren el flujo real del panel de cliente (/closed-days), donde un "día de
cierre" con N tiendas son N filas que comparten fecha:
  - alta múltiple: marcar varias tiendas crea un cierre por cada una
  - edición: sincroniza el conjunto (mantiene, crea los nuevos, borra los
    desmarcados) — el bug era que solo se guardaba el primer ámbito
  - unique_together (date, scope_entity_id)
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.planning.models import ClosedDay

pytestmark = pytest.mark.django_db

URL = '/api/planning/closed-days/'


@pytest.fixture
def client():
    user = get_user_model().objects.create_user(
        username='tester', email='tester@example.com', password='x',
    )
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def scopes_for(date):
    """Ámbitos guardados para una fecha, como set (lo que ve el front al recargar)."""
    return set(
        ClosedDay.objects.filter(date=date).values_list('scope_entity_id', flat=True)
    )


class TestAlta:

    def test_crea_un_cierre_por_tienda(self, client):
        """Marcar T01..T08 crea 8 filas, una por tienda."""
        for scope in range(54, 62):
            r = client.post(URL, {
                'date': '2026-08-10', 'scope_entity_id': scope, 'reason': 'San Lorenzo',
            }, format='json')
            assert r.status_code == 201, r.data

        assert scopes_for('2026-08-10') == set(range(54, 62))

    def test_global_es_scope_cero(self, client):
        r = client.post(URL, {
            'date': '2026-12-25', 'scope_entity_id': 0, 'reason': 'Navidad',
        }, format='json')
        assert r.status_code == 201
        assert scopes_for('2026-12-25') == {0}

    def test_no_permite_duplicar_fecha_y_ambito(self, client):
        client.post(URL, {'date': '2026-08-10', 'scope_entity_id': 55}, format='json')
        r = client.post(URL, {'date': '2026-08-10', 'scope_entity_id': 55}, format='json')
        assert r.status_code == 400
        assert ClosedDay.objects.filter(date='2026-08-10').count() == 1

    def test_misma_tienda_en_fechas_distintas_si(self, client):
        client.post(URL, {'date': '2026-08-10', 'scope_entity_id': 55}, format='json')
        r = client.post(URL, {'date': '2026-08-11', 'scope_entity_id': 55}, format='json')
        assert r.status_code == 201


class TestEdicion:
    """El componente sincroniza el grupo: update de los que siguen,
    create de los nuevos y delete de los desmarcados."""

    def _crear(self, client, date, scopes, reason=''):
        ids = {}
        for s in scopes:
            r = client.post(URL, {'date': date, 'scope_entity_id': s, 'reason': reason}, format='json')
            assert r.status_code == 201, r.data
            ids[s] = r.data['id']
        return ids

    def test_anadir_tiendas_conserva_las_existentes(self, client):
        """Bug original: editar T02 y marcar T01..T08 guardaba solo una."""
        ids = self._crear(client, '2026-08-10', [55], 'San Lorenzo')

        before = {55: ids[55]}
        wanted = {54, 55, 56, 57, 58, 59, 60, 61}

        # keep (siguen marcados) → PATCH
        for scope, cd_id in before.items():
            if scope in wanted:
                r = client.patch(f'{URL}{cd_id}/', {
                    'date': '2026-08-10', 'scope_entity_id': scope, 'reason': 'San Lorenzo',
                }, format='json')
                assert r.status_code == 200, r.data
        # nuevos → POST
        for scope in wanted - set(before):
            r = client.post(URL, {
                'date': '2026-08-10', 'scope_entity_id': scope, 'reason': 'San Lorenzo',
            }, format='json')
            assert r.status_code == 201, r.data

        assert scopes_for('2026-08-10') == wanted
        assert ClosedDay.objects.filter(date='2026-08-10').count() == 8

    def test_desmarcar_borra_esos_ambitos(self, client):
        ids = self._crear(client, '2026-08-10', [54, 55, 56, 57])

        wanted = {54, 55}
        for scope, cd_id in ids.items():
            if scope not in wanted:
                r = client.delete(f'{URL}{cd_id}/')
                assert r.status_code == 204

        assert scopes_for('2026-08-10') == wanted

    def test_cambiar_motivo_afecta_a_todas_las_tiendas(self, client):
        ids = self._crear(client, '2026-08-10', [54, 55, 56], 'San Lorenzo')

        for cd_id in ids.values():
            r = client.patch(f'{URL}{cd_id}/', {'reason': 'Fiesta local'}, format='json')
            assert r.status_code == 200

        reasons = set(
            ClosedDay.objects.filter(date='2026-08-10').values_list('reason', flat=True)
        )
        assert reasons == {'Fiesta local'}

    def test_cambiar_fecha_mueve_todo_el_grupo(self, client):
        ids = self._crear(client, '2026-08-10', [54, 55, 56], 'San Lorenzo')

        for scope, cd_id in ids.items():
            r = client.patch(f'{URL}{cd_id}/', {
                'date': '2026-08-11', 'scope_entity_id': scope, 'reason': 'San Lorenzo',
            }, format='json')
            assert r.status_code == 200, r.data

        assert scopes_for('2026-08-10') == set()
        assert scopes_for('2026-08-11') == {54, 55, 56}

    def test_pasar_de_tiendas_a_global(self, client):
        ids = self._crear(client, '2026-08-10', [54, 55])

        # Marcar "Global" → queda scope 0 y se borran las tiendas.
        first_scope, first_id = sorted(ids.items())[0]
        r = client.patch(f'{URL}{first_id}/', {
            'date': '2026-08-10', 'scope_entity_id': 0,
        }, format='json')
        assert r.status_code == 200, r.data
        for scope, cd_id in ids.items():
            if scope != first_scope:
                assert client.delete(f'{URL}{cd_id}/').status_code == 204

        assert scopes_for('2026-08-10') == {0}

    def test_borrar_el_dia_entero(self, client):
        ids = self._crear(client, '2026-08-10', [54, 55, 56])
        for cd_id in ids.values():
            assert client.delete(f'{URL}{cd_id}/').status_code == 204
        assert scopes_for('2026-08-10') == set()


class TestListadoYPermisos:

    def test_get_devuelve_todas_las_filas_del_dia(self, client):
        for s in [54, 55, 56]:
            client.post(URL, {'date': '2026-08-10', 'scope_entity_id': s}, format='json')
        client.post(URL, {'date': '2026-12-25', 'scope_entity_id': 0}, format='json')

        r = client.get(URL)
        assert r.status_code == 200
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        del_dia = [x for x in rows if x['date'] == '2026-08-10']
        assert len(del_dia) == 3

    def test_filtro_por_scope_incluye_globales(self, client):
        client.post(URL, {'date': '2026-08-10', 'scope_entity_id': 55}, format='json')
        client.post(URL, {'date': '2026-08-10', 'scope_entity_id': 56}, format='json')
        client.post(URL, {'date': '2026-12-25', 'scope_entity_id': 0}, format='json')

        r = client.get(f'{URL}?scope=55')
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        assert {x['scope_entity_id'] for x in rows} == {55, 0}

    def test_requiere_autenticacion(self):
        r = APIClient().get(URL)
        assert r.status_code in (401, 403)
