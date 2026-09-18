"""Flag "Sin asignar" en los filtros manuales (EntityField.allow_unassigned_filter).

El flag vive en cada campo, no en un ajuste global: activarlo en la tienda de
empleados no lo activa en los demas filtros. El backend solo lo EXPONE en el
field_schema; el filtrado en si es del front (la tabla se filtra en memoria
sobre los registros ya cargados), asi que aqui se comprueba que el flag llega
correctamente y por campo.
"""
from django.test import TestCase

from apps.dynamic_fields.mixins import invalidate_fields_cache
from apps.dynamic_fields.models import EntityField
from apps.dynamic_fields.serializers import EntityFieldSerializer
from apps.workers.models import Worker
from apps.workers.serializers import WorkerSerializer


class TestFlagSinAsignar(TestCase):

    def setUp(self):
        self.con_flag = EntityField.objects.create(
            entity_type='worker', key='tienda_test', label='Tienda',
            field_type='entity_select', show_as_filter=True,
            allow_unassigned_filter=True, order=1,
        )
        self.sin_flag = EntityField.objects.create(
            entity_type='worker', key='zona_test', label='Zona',
            field_type='catalog_select', show_as_filter=True,
            allow_unassigned_filter=False, order=2,
        )
        invalidate_fields_cache('worker')

    def tearDown(self):
        EntityField.objects.filter(entity_type='worker', key__endswith='_test').delete()
        invalidate_fields_cache('worker')

    def _schema(self):
        w = Worker.objects.create(name='Para el schema', custom_data={})
        return {f['key']: f for f in WorkerSerializer(w).data['field_schema']}

    # ── AC-1 / AC-4: el flag es por campo, no global ──────────────

    def test_por_defecto_esta_desactivado(self):
        """No cambia el comportamiento de los filtros que ya existian."""
        f = EntityField.objects.create(
            entity_type='worker', key='nuevo_test', label='Nuevo',
            field_type='text', order=9)
        self.assertFalse(f.allow_unassigned_filter)

    def test_es_independiente_para_cada_filtro(self):
        """AC-4: activarlo en un campo no lo activa en otro."""
        schema = self._schema()
        self.assertTrue(schema['tienda_test']['allow_unassigned_filter'])
        self.assertFalse(schema['zona_test']['allow_unassigned_filter'])

    def test_activarlo_en_uno_no_toca_al_otro(self):
        self.sin_flag.allow_unassigned_filter = True
        self.sin_flag.save()
        invalidate_fields_cache('worker')
        schema = self._schema()
        self.assertTrue(schema['zona_test']['allow_unassigned_filter'])
        # el primero sigue como estaba
        self.assertTrue(schema['tienda_test']['allow_unassigned_filter'])

    # ── AC-2: el flag llega al front por las dos vias ─────────────

    def test_llega_en_el_field_schema(self):
        """La via del cliente: /api/workers/ trae field_schema."""
        self.assertIn('allow_unassigned_filter', self._schema()['tienda_test'])

    def test_llega_en_el_serializer_de_campos(self):
        """La via de AdminZebra: /api/entity-fields/ para editar el campo."""
        data = EntityFieldSerializer(self.con_flag).data
        self.assertTrue(data['allow_unassigned_filter'])

    def test_el_schema_tambien_expone_show_as_filter(self):
        """Sin este, el front no sabe que campos son filtrables."""
        self.assertTrue(self._schema()['tienda_test']['show_as_filter'])

    # ── Se puede activar y desactivar (AC-1) ─────────────────────

    def test_se_puede_desactivar(self):
        self.con_flag.allow_unassigned_filter = False
        self.con_flag.save()
        invalidate_fields_cache('worker')
        self.assertFalse(self._schema()['tienda_test']['allow_unassigned_filter'])

    def test_se_puede_editar_por_la_api(self):
        s = EntityFieldSerializer(
            instance=self.sin_flag,
            data={'allow_unassigned_filter': True}, partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        self.sin_flag.refresh_from_db()
        self.assertTrue(self.sin_flag.allow_unassigned_filter)
