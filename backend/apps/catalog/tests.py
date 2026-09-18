from django.test import TestCase
from .models import Kind, KindAttribute, KindValue, KindValueAttribute
from .helpers import get_values, get_codes, get_choices, get_attribute_value


class CatalogModelTest(TestCase):
    def setUp(self):
        self.kind = Kind.objects.create(code='shift_slot', name='Turno tipo')
        self.attr_start = KindAttribute.objects.create(
            kind=self.kind, key='start_time', label='Hora inicio', field_type='time', order=0,
        )
        self.attr_end = KindAttribute.objects.create(
            kind=self.kind, key='end_time', label='Hora fin', field_type='time', order=1,
        )
        self.val_morning = KindValue.objects.create(
            kind=self.kind, code='morning', label='Manana', color='#FFC107', order=0,
        )
        KindValueAttribute.objects.create(
            kind_value=self.val_morning, attribute=self.attr_start, value='07:00',
        )
        KindValueAttribute.objects.create(
            kind_value=self.val_morning, attribute=self.attr_end, value='15:00',
        )
        self.val_night = KindValue.objects.create(
            kind=self.kind, code='night', label='Noche', color='#3F51B5', order=2,
        )

    def test_kind_str(self):
        self.assertEqual(str(self.kind), 'Turno tipo')

    def test_kind_value_str(self):
        self.assertIn('morning', str(self.val_morning))

    def test_attribute_unique_per_kind(self):
        with self.assertRaises(Exception):
            KindAttribute.objects.create(
                kind=self.kind, key='start_time', label='Duplicado', field_type='text',
            )

    def test_value_unique_per_kind(self):
        with self.assertRaises(Exception):
            KindValue.objects.create(kind=self.kind, code='morning', label='Otro Manana')


class CatalogHelperTest(TestCase):
    def setUp(self):
        self.kind = Kind.objects.create(code='test_kind', name='Test')
        self.attr = KindAttribute.objects.create(
            kind=self.kind, key='color_hex', label='Color', field_type='text',
        )
        self.v1 = KindValue.objects.create(kind=self.kind, code='a', label='Alpha', order=0)
        self.v2 = KindValue.objects.create(kind=self.kind, code='b', label='Beta', order=1)
        self.v3 = KindValue.objects.create(kind=self.kind, code='c', label='Gamma', order=2, active=False)
        KindValueAttribute.objects.create(kind_value=self.v1, attribute=self.attr, value='#FF0000')

    def test_get_values(self):
        vals = get_values('test_kind')
        self.assertEqual(len(vals), 2)  # active only
        self.assertEqual(vals[0]['code'], 'a')
        self.assertEqual(vals[0]['attributes']['color_hex'], '#FF0000')

    def test_get_values_incluye_inactivos(self):
        vals = get_values('test_kind', active_only=False)
        self.assertEqual(len(vals), 3)

    def test_get_codes(self):
        codes = get_codes('test_kind')
        self.assertEqual(codes, ['a', 'b'])

    def test_get_choices(self):
        choices = get_choices('test_kind')
        self.assertEqual(choices, [('a', 'Alpha'), ('b', 'Beta')])

    def test_get_attribute_value(self):
        val = get_attribute_value('test_kind', 'a', 'color_hex')
        self.assertEqual(val, '#FF0000')

    def test_get_attribute_value_missing(self):
        val = get_attribute_value('test_kind', 'b', 'color_hex', default='none')
        self.assertEqual(val, 'none')

    def test_get_values_nonexistent_kind(self):
        vals = get_values('nonexistent')
        self.assertEqual(vals, [])
