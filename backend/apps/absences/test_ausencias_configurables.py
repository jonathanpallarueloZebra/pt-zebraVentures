"""Ausencias como entidad configurable desde AdminZebra.

El tipo de ausencia pasa a salir del catalogo (Kind 'absence_type'), que es lo
que el cliente gestiona, pero la FK a AbsenceType se MANTIENE y se sincroniza
por nombre: las ausencias ya registradas siguen apuntando a su fila de siempre
y no hay que migrar datos.
"""
from datetime import date, timedelta

from django.test import TestCase

from apps.absences.models import AbsenceRequest, AbsenceType
from apps.absences.serializers import AbsenceRequestSerializer, resolver_absence_type
from apps.catalog.models import Kind, KindValue
from apps.dynamic_fields.mixins import invalidate_fields_cache
from apps.dynamic_fields.models import EntityField
from apps.workers.models import Worker


class TestAusenciasConfigurables(TestCase):

    def setUp(self):
        self.worker = Worker.objects.create(name='Empleado de prueba')
        self.tipo_viejo = AbsenceType.objects.create(name='Vacaciones')

        self.kind = Kind.objects.create(code='absence_type', name='Tipos de ausencia')
        for i, nombre in enumerate(['Vacaciones', 'Excedencia', 'Otro'], start=1):
            KindValue.objects.create(
                kind=self.kind, code=nombre.lower(), label=nombre, order=i)

        EntityField.objects.create(
            entity_type='absence', key='tipo', label='Tipo de ausencia',
            field_type='catalog_select', kind_code='absence_type',
            required=True, show_in_list=True, order=1,
        )
        EntityField.objects.create(
            entity_type='absence', key='justificante', label='Justificante',
            field_type='boolean', show_in_list=True, order=2,
        )
        invalidate_fields_cache('absence')

    def tearDown(self):
        EntityField.objects.filter(entity_type='absence').delete()
        invalidate_fields_cache('absence')

    def _crear(self, custom_data, **extra):
        datos = {
            'worker': self.worker.id,
            'start_date': date.today().isoformat(),
            'end_date': (date.today() + timedelta(days=3)).isoformat(),
            'custom_data': custom_data,
        }
        datos.update(extra)
        s = AbsenceRequestSerializer(data=datos)
        return s.is_valid(), s

    # ── AC-4: los tipos nuevos funcionan ─────────────────────────

    def test_se_puede_crear_con_un_tipo_nuevo_del_catalogo(self):
        """"Excedencia" no tenia fila en AbsenceType: se crea al resolverlo."""
        self.assertFalse(AbsenceType.objects.filter(name='Excedencia').exists())
        valido, s = self._crear({'tipo': 'Excedencia'})
        self.assertTrue(valido, s.errors)
        s.save()
        self.assertTrue(AbsenceType.objects.filter(name='Excedencia').exists())

    def test_el_tipo_otro_tambien(self):
        valido, s = self._crear({'tipo': 'Otro'})
        self.assertTrue(valido, s.errors)

    # ── AC-5: no se pierde ni se duplica lo que ya existia ───────

    def test_reutiliza_el_absencetype_existente_sin_duplicar(self):
        antes = AbsenceType.objects.filter(name='Vacaciones').count()
        valido, s = self._crear({'tipo': 'Vacaciones'})
        self.assertTrue(valido, s.errors)
        s.save()
        self.assertEqual(AbsenceType.objects.filter(name='Vacaciones').count(), antes)

    def test_resolver_ignora_los_acentos(self):
        """Al importar por Excel se escribe "Baja medica" sin tilde: no debe
        crearse un tipo aparte del que ya existe con tilde."""
        con_tilde = AbsenceType.objects.create(name='Formacion especial')
        antes = AbsenceType.objects.count()
        self.assertEqual(resolver_absence_type('FORMACION ESPECIAL').id, con_tilde.id)
        self.assertEqual(AbsenceType.objects.count(), antes)

    def test_resolver_ignora_mayusculas_y_espacios(self):
        """Que el catalogo diga "vacaciones " no debe crear un tipo duplicado."""
        tipo = resolver_absence_type('  vacaciones ')
        self.assertEqual(tipo.id, self.tipo_viejo.id)

    def test_una_ausencia_antigua_sigue_editandose(self):
        """Las 29 ausencias ya registradas tienen custom_data vacio: su tipo
        vive solo en la FK. Al leerlas se rellena, asi que el desplegable sale
        con valor y el guardado no falla por "obligatorio"."""
        vieja = AbsenceRequest.objects.create(
            worker=self.worker, type=self.tipo_viejo,
            start_date=date.today(), end_date=date.today() + timedelta(days=1),
            custom_data={},
        )
        d = AbsenceRequestSerializer(vieja).data
        self.assertEqual(d['custom_data']['tipo'], 'Vacaciones')

        s = AbsenceRequestSerializer(
            instance=vieja,
            data={'reason': 'editado', 'custom_data': d['custom_data']},
            partial=True)
        self.assertTrue(s.is_valid(), s.errors)

    # ── AC-1 / AC-2: campos y columnas configurables ─────────────

    def test_el_field_schema_llega_a_la_pantalla(self):
        a = AbsenceRequest.objects.create(
            worker=self.worker, type=self.tipo_viejo,
            start_date=date.today(), end_date=date.today() + timedelta(days=1))
        d = AbsenceRequestSerializer(a).data
        claves = [f['key'] for f in d['field_schema']]
        self.assertIn('tipo', claves)
        self.assertIn('justificante', claves)

    def test_las_columnas_las_marca_la_configuracion(self):
        """AC-2: show_in_list decide que columnas pinta la tabla."""
        EntityField.objects.filter(
            entity_type='absence', key='justificante').update(show_in_list=False)
        invalidate_fields_cache('absence')
        a = AbsenceRequest.objects.create(
            worker=self.worker, type=self.tipo_viejo,
            start_date=date.today(), end_date=date.today() + timedelta(days=1))
        d = AbsenceRequestSerializer(a).data
        en_tabla = [f['key'] for f in d['field_schema'] if f['show_in_list']]
        self.assertIn('tipo', en_tabla)
        self.assertNotIn('justificante', en_tabla)

    def test_el_tipo_es_obligatorio_por_configuracion(self):
        """AC-1: la obligatoriedad sale del campo, no del codigo."""
        valido, s = self._crear({})
        self.assertFalse(valido)
        self.assertIn('tipo', str(s.errors))

    def test_si_se_desmarca_obligatorio_deja_de_exigirse(self):
        EntityField.objects.filter(
            entity_type='absence', key='tipo').update(required=False)
        invalidate_fields_cache('absence')
        # sin tipo en custom_data, pero con la FK directa
        valido, s = self._crear({}, type=self.tipo_viejo.id)
        self.assertTrue(valido, s.errors)

    # ── Los campos que necesita el planificador siguen fijos ─────

    def test_la_fecha_de_fin_sigue_siendo_obligatoria(self):
        """No es configurable a proposito: el planificador la necesita."""
        s = AbsenceRequestSerializer(data={
            'worker': self.worker.id,
            'start_date': date.today().isoformat(),
            'custom_data': {'tipo': 'Vacaciones'},
        })
        self.assertFalse(s.is_valid())
        self.assertIn('end_date', s.errors)

    def test_la_indefinida_sigue_sin_pedir_fecha_de_fin(self):
        s = AbsenceRequestSerializer(data={
            'worker': self.worker.id,
            'start_date': date.today().isoformat(),
            'indefinite': True,
            'custom_data': {'tipo': 'Vacaciones'},
        })
        self.assertTrue(s.is_valid(), s.errors)
