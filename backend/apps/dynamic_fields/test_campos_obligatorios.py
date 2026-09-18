"""Los campos marcados como obligatorios en la configuracion se exigen AL CREAR.

La lista de obligatorios no esta escrita en ningun sitio del codigo: sale de
`EntityField.required`, la misma configuracion que el front recibe en
`field_schema`. Marcar o desmarcar un campo en Admin Zebra cambia a la vez lo
que pide el formulario y lo que valida el backend.

Al EDITAR no se exige a proposito: en QA hay 103 empleados reales cargados sin
'regimen', y validarlos en el update impediria editarles cualquier otro dato.
"""
from django.test import TestCase

from apps.dynamic_fields.mixins import invalidate_fields_cache
from apps.dynamic_fields.models import EntityField
from apps.workers.models import Worker
from apps.workers.serializers import WorkerSerializer


class TestCamposObligatoriosAlCrear(TestCase):

    def setUp(self):
        EntityField.objects.create(
            entity_type='worker', key='codigo_test', label='Codigo empleado',
            field_type='text', required=True, order=1,
        )
        EntityField.objects.create(
            entity_type='worker', key='regimen_test', label='Regimen',
            field_type='select', required=True, options=['Fijo', 'Temporal'], order=2,
        )
        EntityField.objects.create(
            entity_type='worker', key='observaciones_test', label='Observaciones',
            field_type='textarea', required=False, order=3,
        )
        invalidate_fields_cache('worker')

    def tearDown(self):
        EntityField.objects.filter(entity_type='worker', key__endswith='_test').delete()
        invalidate_fields_cache('worker')

    def _crear(self, custom_data, nombre='Nuevo'):
        s = WorkerSerializer(data={'name': nombre, 'custom_data': custom_data})
        return s.is_valid(), s.errors

    # ── AC-4: el backend rechaza la creacion incompleta ──────────

    def test_rechaza_si_faltan_todos_los_obligatorios(self):
        valido, errores = self._crear({})
        self.assertFalse(valido)
        self.assertIn('codigo_test', errores['custom_data'])
        self.assertIn('regimen_test', errores['custom_data'])

    def test_rechaza_si_falta_uno_solo(self):
        valido, errores = self._crear({'codigo_test': '011570'})
        self.assertFalse(valido)
        self.assertIn('regimen_test', errores['custom_data'])
        self.assertNotIn('codigo_test', errores['custom_data'])

    def test_el_error_nombra_el_campo(self):
        """Un "datos invalidos" a secas no dice que arreglar (AC-4)."""
        _, errores = self._crear({})
        self.assertIn('Codigo empleado', str(errores['custom_data']['codigo_test']))
        self.assertIn('obligatorio', str(errores['custom_data']['codigo_test']))

    def test_cadena_vacia_cuenta_como_vacio(self):
        valido, errores = self._crear({'codigo_test': '', 'regimen_test': 'Fijo'})
        self.assertFalse(valido)
        self.assertIn('codigo_test', errores['custom_data'])

    def test_acepta_si_estan_todos(self):
        valido, errores = self._crear(
            {'codigo_test': '011570', 'regimen_test': 'Fijo'})
        self.assertTrue(valido, errores)

    def test_los_no_obligatorios_no_se_exigen(self):
        valido, errores = self._crear(
            {'codigo_test': '011570', 'regimen_test': 'Fijo'})
        self.assertTrue(valido, errores)
        self.assertNotIn('observaciones_test', str(errores))

    # ── El 0 y el False son valores validos, no huecos ────────────

    def test_el_cero_no_cuenta_como_vacio(self):
        """"Turnos max./semana = 0" esta relleno; None no."""
        EntityField.objects.create(
            entity_type='worker', key='turnos_test', label='Turnos max.',
            field_type='number', required=True, order=4,
        )
        invalidate_fields_cache('worker')
        valido, errores = self._crear(
            {'codigo_test': 'X', 'regimen_test': 'Fijo', 'turnos_test': 0})
        self.assertTrue(valido, errores)

    def test_el_false_no_cuenta_como_vacio(self):
        EntityField.objects.create(
            entity_type='worker', key='reducida_test', label='Jornada reducida',
            field_type='boolean', required=True, order=5,
        )
        invalidate_fields_cache('worker')
        valido, errores = self._crear(
            {'codigo_test': 'X', 'regimen_test': 'Fijo', 'reducida_test': False})
        self.assertTrue(valido, errores)

    def test_lista_vacia_si_cuenta_como_vacio(self):
        """Los multi_*_select guardan listas: [] es "sin elegir nada"."""
        EntityField.objects.create(
            entity_type='worker', key='secciones_test', label='Secciones',
            field_type='multi_entity_select', required=True, order=6,
        )
        invalidate_fields_cache('worker')
        valido, errores = self._crear(
            {'codigo_test': 'X', 'regimen_test': 'Fijo', 'secciones_test': []})
        self.assertFalse(valido)
        self.assertIn('secciones_test', errores['custom_data'])

    def test_un_default_en_la_config_rellena_el_campo(self):
        """Si la configuracion da un valor por defecto, el campo no falta."""
        EntityField.objects.create(
            entity_type='worker', key='nivel_test', label='Nivel',
            field_type='text', required=True, default_value='Base', order=7,
        )
        invalidate_fields_cache('worker')
        valido, errores = self._crear(
            {'codigo_test': 'X', 'regimen_test': 'Fijo'})
        self.assertTrue(valido, errores)

    # ── AC-5 / no romper lo existente: la EDICION no se bloquea ───

    def test_editar_una_ficha_con_obligatorios_vacios_sigue_funcionando(self):
        """El caso de los 103 empleados sin 'regimen' cargados de antes."""
        w = Worker.objects.create(name='Heredada', custom_data={'codigo_test': 'X'})
        s = WorkerSerializer(
            instance=w, data={'custom_data': {'observaciones_test': 'nota'}},
            partial=True)
        self.assertTrue(s.is_valid(), s.errors)

    def test_desmarcar_el_obligatorio_en_la_config_lo_deja_de_exigir(self):
        """No hay lista duplicada: manda la configuracion (AC-5)."""
        EntityField.objects.filter(
            entity_type='worker', key='regimen_test').update(required=False)
        invalidate_fields_cache('worker')
        valido, errores = self._crear({'codigo_test': '011570'})
        self.assertTrue(valido, errores)
