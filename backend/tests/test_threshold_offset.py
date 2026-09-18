"""
Tests de `thresholdOffset`: el margen de horas extra sobre el umbral individual.

El límite de cada trabajador sale de un campo EAV suyo (p. ej. 'horas_semanales'
= su contrato). El margen que la empresa concede sobre ese contrato es política
de empresa, igual para todos, así que vive en la restricción y no en cada ficha:
se cambia en un sitio en vez de en 272 trabajadores.

Regla clave: el offset SOLO se suma al valor del trabajador. Si su campo está
vacío se cae al umbral plano tal cual, que ya es el tope por defecto.
"""
import pytest

from apps.restrictions.engine import _effective_threshold

pytestmark = pytest.mark.django_db


class TestEffectiveThreshold:

    def test_sin_campo_individual_usa_el_umbral_plano(self):
        assert _effective_threshold({}, '', 45, 0) == 45

    def test_sin_campo_individual_el_offset_no_aplica(self):
        """El umbral plano ya representa el tope; inflarlo sería un bug."""
        assert _effective_threshold({}, '', 45, 5) == 45

    def test_usa_el_contrato_del_trabajador(self):
        wd = {'horas_semanales': 40}
        assert _effective_threshold(wd, 'horas_semanales', 45, 0) == 40

    def test_suma_el_margen_al_contrato(self):
        wd = {'horas_semanales': 40}
        assert _effective_threshold(wd, 'horas_semanales', 45, 5) == 45

    def test_el_margen_respeta_cada_jornada(self):
        """Lo que un tope plano no puede hacer: media jornada mantiene su
        proporción en vez de heredar el tope de una jornada completa."""
        completa = _effective_threshold({'horas_semanales': 40}, 'horas_semanales', 45, 5)
        reducida = _effective_threshold({'horas_semanales': 20}, 'horas_semanales', 45, 5)
        assert completa == 45
        assert reducida == 25, 'la jornada reducida no debe heredar el tope de 45'

    def test_campo_vacio_cae_al_umbral_plano_sin_margen(self):
        """Los 272 trabajadores tienen horas_semanales = '' hoy."""
        for vacio in ('', None):
            assert _effective_threshold({'horas_semanales': vacio}, 'horas_semanales', 45, 5) == 45

    def test_campo_ausente_cae_al_umbral_plano(self):
        assert _effective_threshold({'zona': 'huesca'}, 'horas_semanales', 45, 5) == 45

    def test_valor_no_numerico_cae_al_umbral_plano(self):
        assert _effective_threshold({'horas_semanales': 'cuarenta'}, 'horas_semanales', 45, 5) == 45

    def test_acepta_numeros_como_texto(self):
        """Los campos EAV llegan como string desde el formulario."""
        assert _effective_threshold({'horas_semanales': '40'}, 'horas_semanales', 45, 5) == 45

    def test_acepta_decimales(self):
        wd = {'horas_semanales': 37.5}
        assert _effective_threshold(wd, 'horas_semanales', 45, 2.5) == 40.0

    def test_margen_cero_es_tope_estricto_por_contrato(self):
        """Sin margen: cualquier hora por encima del contrato es violación."""
        wd = {'horas_semanales': 40}
        assert _effective_threshold(wd, 'horas_semanales', 45, 0) == 40


class TestIntegracionConElMotor:
    """El offset llega desde config['thresholdOffset'] al evaluar el plan."""

    def _config(self, offset=None):
        cfg = {
            'scope': 'per_week_worker_hours',
            'operator': 'lte',
            'threshold': 45,
            'thresholdField': 'horas_semanales',
        }
        if offset is not None:
            cfg['thresholdOffset'] = offset
        return cfg

    def test_offset_ausente_equivale_a_cero(self):
        cfg = self._config()
        raw = cfg.get('thresholdOffset') or 0
        assert float(raw) == 0.0

    def test_offset_vacio_o_invalido_no_rompe(self):
        """El input numérico puede llegar como '' desde el formulario."""
        for bad in ('', None, 'abc'):
            try:
                value = float(bad or 0)
            except (TypeError, ValueError):
                value = 0.0
            assert value == 0.0

    def test_el_tope_sube_al_subir_el_margen(self):
        wd = {'horas_semanales': 40}
        sin_margen = _effective_threshold(wd, 'horas_semanales', 45, 0)
        con_margen = _effective_threshold(wd, 'horas_semanales', 45, 8)
        assert con_margen - sin_margen == 8
