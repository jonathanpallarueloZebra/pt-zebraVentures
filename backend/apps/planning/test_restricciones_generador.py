"""Tests de lo cambiado al hacer que el generador respete las restricciones.

Cubre:
  - el tope "máximo N por campo de la ficha" (p.ej. 2 ETT por turno), que antes
    solo se validaba DESPUÉS de generar;
  - que las preferencias de turno se cargan en UNA consulta (había dos N+1 que
    lanzaban 272 consultas cada uno, ~14 s de cada generación).
"""
from datetime import date, time

from django.db import connection, reset_queries
from django.test import TestCase, override_settings

from apps.shifts.models import Shift
from apps.workers.models import Worker, WorkerPreference


def _limpiar_caches():
    from apps.planning.schedule_generator import _thread_local
    from apps.restrictions.engine import _cache
    if hasattr(_thread_local, 'gen_cache'):
        _thread_local.gen_cache = {}
    _cache.clear()


class TestTopePorCampoFicha(TestCase):
    """El tope "máximo N por campo de la ficha" se respeta AL GENERAR.

    Caso real: "máximo 2 trabajadores ETT por turno" (count / groupBy 'shift' /
    filterField). Antes el motor podía meter a 3 en el mismo turno y marcarlo
    como violación después.
    """

    def setUp(self):
        from apps.restrictions.models import Restriction
        _limpiar_caches()
        self.manana = Shift.objects.create(
            name='Mañana', start_time=time(7, 45), end_time=time(14, 45))
        self.restr = Restriction.objects.create(
            name='Máximo 2 ETT por turno', engine='count', severity='warning',
            active=True,
            config={'groupBy': 'shift', 'subject': 'workers', 'operator': 'lte',
                    'threshold': 2, 'filterField': 'tipo_contrato',
                    'filterValue': 'ett'},
        )

    def _restricciones(self):
        from apps.restrictions.models import Restriction
        return list(Restriction.objects.filter(active=True).values(
            'id', 'name', 'engine', 'severity', 'config'))

    def _worker(self, i, contrato='ett'):
        return {
            'id': i, 'name': f'{contrato.upper()} {i}', 'active': True,
            'preferredShifts': [], 'pills': [],
            'customData': {'tipo_contrato': contrato,
                           'turno_base': str(self.manana.id)},
        }

    def _asignados(self, day):
        return [e for e in (day.get(str(self.manana.id)) or [])
                if int(e.get('workerId', 0) or 0) > 0]

    def test_no_asigna_mas_de_los_permitidos(self):
        """Con 4 ETT elegibles, en un turno entran como mucho 2."""
        from apps.planning.schedule_generator import _fallback_round_robin
        workers = [self._worker(i) for i in range(1, 5)]
        plan = _fallback_round_robin(
            date(2026, 8, 3), workers, self._restricciones(), areas=None)
        for day in plan:
            n = len(self._asignados(day))
            self.assertLessEqual(
                n, 2, f"{day['date']}: {n} ETT asignados, el tope es 2")

    def test_los_que_no_cumplen_el_filtro_no_consumen_cuota(self):
        """El tope es solo para ETT: la plantilla no se ve afectada."""
        from apps.planning.schedule_generator import _fallback_round_robin
        workers = [self._worker(1), self._worker(2),
                   self._worker(3, contrato='plantilla')]
        plan = _fallback_round_robin(
            date(2026, 8, 3), workers, self._restricciones(), areas=None)
        nombres = {e['workerName'] for day in plan for e in self._asignados(day)}
        self.assertIn('PLANTILLA 3', nombres,
                      'la plantilla no debe quedar fuera por el tope de ETT')

    def test_sin_restriccion_no_hay_tope(self):
        """Desactivada la restricción, pueden entrar los 4."""
        from apps.planning.schedule_generator import _fallback_round_robin
        self.restr.active = False
        self.restr.save()
        _limpiar_caches()
        workers = [self._worker(i) for i in range(1, 5)]
        plan = _fallback_round_robin(
            date(2026, 8, 3), workers, self._restricciones(), areas=None)
        maximo = max(len(self._asignados(d)) for d in plan)
        self.assertEqual(maximo, 4, 'sin restricción activa no debe haber tope')


class TestPreferenciasSinNMasUno(TestCase):
    """Las preferencias se cargan en UNA consulta, no una por trabajador.

    `prefetch_related('preferences')` + `w.preferences.values_list(...)` NO usa
    el prefetch: values_list lanza su propia consulta. Eran 272 consultas por
    generación en dos sitios distintos. Estos tests fijan el contrato.
    """

    def setUp(self):
        _limpiar_caches()
        self.manana = Shift.objects.create(
            name='Mañana', start_time=time(7, 45), end_time=time(14, 45))
        for i in range(12):
            w = Worker.objects.create(name=f'W{i}', active=True, custom_data={})
            WorkerPreference.objects.create(
                worker=w, shift_type=str(self.manana.id))

    def test_engine_carga_preferencias_en_una_consulta(self):
        from apps.restrictions.engine import _load_worker_prefs
        _limpiar_caches()
        with self.assertNumQueries(1):
            prefs = _load_worker_prefs()
        self.assertEqual(len(prefs), 12)
        for turnos in prefs.values():
            self.assertEqual(turnos, {str(self.manana.id)})

    def test_solo_cuenta_trabajadores_activos(self):
        from apps.restrictions.engine import _load_worker_prefs
        Worker.objects.filter(name='W0').update(active=False)
        _limpiar_caches()
        self.assertEqual(len(_load_worker_prefs()), 11)

    def test_el_generador_no_escala_con_el_numero_de_trabajadores(self):
        """Añadir 30 trabajadores no debe añadir 30 consultas."""
        from apps.planning.schedule_generator import generate_schedule

        def _consultas():
            _limpiar_caches()
            reset_queries()
            generate_schedule(date(2026, 8, 3), scope_entity_id=0)
            return len(connection.queries)

        with override_settings(DEBUG=True):
            antes = _consultas()
            for i in range(30):
                w = Worker.objects.create(
                    name=f'EXTRA{i}', active=True, custom_data={})
                WorkerPreference.objects.create(
                    worker=w, shift_type=str(self.manana.id))
            despues = _consultas()

        self.assertLessEqual(
            despues, antes + 2,
            f'las consultas crecen con la plantilla ({antes} -> {despues} '
            f'con +30 trabajadores): hay un N+1')
