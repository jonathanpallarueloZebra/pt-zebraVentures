"""La elegibilidad por tienda/zona AMPLIA el pool, no lo reduce.

Hallazgo del analisis (`manage.py analizar_restricciones`): al desactivar la
restriccion de elegibilidad, T01 pasaba de 293 asignaciones a 87. Suena al
reves, pero es correcto:

  - CON la restriccion `scopeMatch` -> entran los de la tienda MAS los volantes
    de la misma zona (la regla tiene dos condiciones en OR).
  - SIN ella -> `_filter_workers_by_eligibility` cae al filtro simple por el
    campo de enlace (`tienda`), y solo quedan los que lo tienen relleno.

Con 46 trabajadores sin tienda asignada, la diferencia es enorme. Estos tests
fijan ese comportamiento para que no se "corrija" por parecer un error.
"""
from django.test import TestCase

from apps.dynamic_fields.models import EntityRecord, EntityType
from apps.planning.schedule_generator import _filter_workers_by_eligibility


class TestElegibilidadFallback(TestCase):

    def setUp(self):
        # La regla de zona compara contra el dato del ÁMBITO, así que la tienda
        # tiene que existir con su zona: sin este registro la regla no casa con
        # nadie y el test mediría otra cosa.
        from apps.restrictions.engine import _cache
        _cache.clear()
        et, _ = EntityType.objects.get_or_create(
            slug='tienda', defaults={'name': 'Tienda', 'is_planning_scope': True})
        self.tienda = EntityRecord.objects.create(
            entity_type=et, data={'codigo': 'T01', 'zona': 'huesca'})
        self.scope_id = self.tienda.id
        # 1 de la tienda, 2 volantes sin tienda pero de la misma zona, y 1 de
        # otra zona (que no debe entrar ni con la regla puesta).
        self.workers = [
            {'id': 1, 'name': 'PROPIO', 'customData': {
                'tienda': self.scope_id, 'zona': 'huesca'}},
            {'id': 2, 'name': 'VOLANTE A', 'customData': {
                'zona': 'huesca', 'tipo_contrato': 'comun'}},
            {'id': 3, 'name': 'VOLANTE B', 'customData': {
                'zona': 'huesca', 'tipo_contrato': 'ett'}},
            {'id': 4, 'name': 'OTRA ZONA', 'customData': {
                'zona': 'jaca', 'tipo_contrato': 'comun'}},
        ]

    def _nombres(self, res):
        return sorted(w['name'] for w in res)

    def test_sin_restricciones_solo_los_de_la_tienda(self):
        """Sin scopeMatch se usa el campo de enlace: solo quien tiene tienda."""
        res = _filter_workers_by_eligibility(
            self.workers, self.scope_id, restrictions=[], linking_field_key='tienda')
        self.assertEqual(self._nombres(res), ['PROPIO'])

    def test_sin_restricciones_y_sin_campo_de_enlace_no_filtra(self):
        """Sin nada que filtrar se devuelve el pool entero (no se inventa)."""
        res = _filter_workers_by_eligibility(
            self.workers, self.scope_id, restrictions=[], linking_field_key=None)
        self.assertEqual(len(res), 4)

    def test_desactivar_la_restriccion_reduce_el_pool(self):
        """El hallazgo, explicito: quitarla deja MENOS gente, no mas."""
        con = _filter_workers_by_eligibility(
            self.workers, self.scope_id,
            restrictions=[{
                'id': 1, 'name': 'Elegibilidad', 'engine': 'condition',
                'severity': 'error',
                'config': {'scopeMatch': {'rules': [
                    {'matchType': 'id', 'workerField': 'tienda'},
                    {'matchType': 'field', 'workerField': 'zona',
                     'scopeField': 'zona'},
                ]}},
            }],
            linking_field_key='tienda')
        sin = _filter_workers_by_eligibility(
            self.workers, self.scope_id, restrictions=[], linking_field_key='tienda')
        self.assertGreater(
            len(con), len(sin),
            'la restriccion de elegibilidad debe AMPLIAR el pool con los '
            'volantes de zona; si reduce, algo cambio en el fallback')
