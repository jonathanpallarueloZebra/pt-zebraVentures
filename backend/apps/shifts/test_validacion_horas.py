"""La hora de fin de un turno debe ser posterior a la de inicio.

Sin esta validacion se pudo guardar un turno 15:36-13:40 (-1,93 h). No es
cosmetico: las horas de cada asignacion se calculan como fin - inicio, asi que un
turno invertido RESTA horas al contador semanal y el tope por contrato deja de
cuadrar.
"""
from datetime import time

from django.test import TestCase

from apps.shifts.serializers import ShiftSerializer
from apps.shifts.models import Shift


class TestHoraFinPosteriorAInicio(TestCase):

    def _valida(self, inicio, fin, nombre='Turno'):
        s = ShiftSerializer(data={
            'name': nombre, 'start_time': inicio, 'end_time': fin})
        return s.is_valid(), s.errors

    def test_rechaza_turno_invertido(self):
        """El caso real que se colo: 15:36-13:40."""
        valido, errores = self._valida('15:36', '13:40')
        self.assertFalse(valido)
        self.assertIn('end_time', errores)

    def test_rechaza_turno_de_cero_horas(self):
        valido, _ = self._valida('10:00', '10:00')
        self.assertFalse(valido)

    def test_acepta_turno_normal(self):
        valido, errores = self._valida('07:45', '14:45')
        self.assertTrue(valido, errores)

    def test_acepta_turno_de_tarde(self):
        valido, errores = self._valida('14:15', '21:15')
        self.assertTrue(valido, errores)

    def test_el_mensaje_dice_las_horas_recibidas(self):
        """El error nombra el horario, para que se vea el problema."""
        _, errores = self._valida('15:36', '13:40')
        msg = str(errores.get('end_time', ''))
        self.assertIn('15:36', msg)
        self.assertIn('13:40', msg)

    def test_en_PATCH_parcial_se_valida_contra_lo_guardado(self):
        """Cambiar solo la hora de fin tambien se comprueba."""
        turno = Shift.objects.create(
            name='Manana', start_time=time(7, 45), end_time=time(14, 45))
        s = ShiftSerializer(turno, data={'end_time': '06:00'}, partial=True)
        self.assertFalse(s.is_valid())
        self.assertIn('end_time', s.errors)

    def test_en_PATCH_parcial_un_cambio_valido_pasa(self):
        turno = Shift.objects.create(
            name='Manana', start_time=time(7, 45), end_time=time(14, 45))
        s = ShiftSerializer(turno, data={'end_time': '15:30'}, partial=True)
        self.assertTrue(s.is_valid(), s.errors)

    def test_la_vigencia_invertida_sigue_rechazandose(self):
        """La validacion que ya existia no se ha roto."""
        s = ShiftSerializer(data={
            'name': 'Campana', 'start_time': '09:00', 'end_time': '21:00',
            'valid_from': '2026-12-20', 'valid_to': '2026-12-01'})
        self.assertFalse(s.is_valid())
        self.assertIn('valid_to', s.errors)
