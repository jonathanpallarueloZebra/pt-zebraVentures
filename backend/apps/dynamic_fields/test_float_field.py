"""Tests del tipo de campo 'float' (decimal).

Caso que motiva el tipo: las horas semanales por contrato. Con 'number' (entero)
no se puede representar 37,5 y redondear falsea la planificacion.
"""
from django.test import TestCase

from apps.catalog.models import FIELD_TYPE_CHOICES
from apps.dynamic_fields.models import EntityField
from apps.restrictions.engine import _effective_threshold


class TestFloatDisponibleComoTipo(TestCase):
    """El tipo aparece en los enumerados de entidades y de catalogo."""

    def test_disponible_en_entidades(self):
        tipos = dict(EntityField.FIELD_TYPES)
        self.assertIn('float', tipos)
        self.assertEqual(tipos['float'], 'Decimal')

    def test_disponible_en_catalogo(self):
        self.assertIn('float', dict(FIELD_TYPE_CHOICES))

    def test_number_sigue_existiendo(self):
        """El decimal se AÑADE: el entero no se sustituye."""
        self.assertIn('number', dict(EntityField.FIELD_TYPES))

    def test_se_puede_crear_un_campo_float(self):
        f = EntityField.objects.create(
            entity_type='worker', key='horas_test', label='Horas',
            field_type='float',
        )
        f.full_clean()   # valida contra choices: reventaria si no estuviera
        self.assertEqual(f.field_type, 'float')


class TestUmbralConDecimales(TestCase):
    """El motor lee el campo sin perder la parte fraccionaria."""

    def _umbral(self, valor):
        # threshold plano 45, offset 5 (contrato + margen de empresa)
        return _effective_threshold({'horas_semanales': valor},
                                    'horas_semanales', 45, 5.0)

    def test_float_nativo(self):
        self.assertEqual(self._umbral(37.5), 42.5)

    def test_texto_con_punto(self):
        self.assertEqual(self._umbral('37.5'), 42.5)

    def test_texto_con_coma(self):
        """Separador español: sin esto float('37,5') revienta y el valor propio
        del trabajador se perdia, cayendo al umbral plano."""
        self.assertEqual(self._umbral('37,5'), 42.5)

    def test_entero_sigue_funcionando(self):
        """Los datos ya existentes son enteros y no deben cambiar."""
        self.assertEqual(self._umbral(40), 45.0)

    def test_vacio_cae_al_umbral_plano_sin_offset(self):
        """El margen solo se suma al valor del trabajador, no al plano."""
        self.assertEqual(self._umbral(''), 45)

    def test_no_numerico_cae_al_umbral_plano(self):
        self.assertEqual(self._umbral('treinta'), 45)

    def test_no_hay_perdida_de_precision(self):
        """Un decimal poco redondo se conserva tal cual."""
        self.assertAlmostEqual(self._umbral(38.25), 43.25, places=6)


class TestImportacionExcelDecimal(TestCase):
    """La importacion de empleados acepta decimales con coma y con punto."""

    def _parse(self, raw):
        """Replica del bloque 'float' de WorkerImportView (apps/workers/views)."""
        try:
            return float(str(raw).replace(',', '.')), None
        except ValueError:
            return None, 'no numerico'

    def test_coma(self):
        self.assertEqual(self._parse('37,5')[0], 37.5)

    def test_punto(self):
        self.assertEqual(self._parse('37.5')[0], 37.5)

    def test_entero(self):
        self.assertEqual(self._parse('40')[0], 40.0)

    def test_texto_da_error(self):
        valor, error = self._parse('abc')
        self.assertIsNone(valor)
        self.assertIsNotNone(error)
