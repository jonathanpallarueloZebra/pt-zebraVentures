"""Deja Ausencias configurable desde AdminZebra, como el resto de entidades.

Crea:
  - EntityType 'absence'          -> aparece en AdminZebra > Entidades
  - Kind 'absence_type'           -> aparece en AdminZebra > Catalogo (AC-3)
  - los KindValue de los tipos que YA existen en AbsenceType (AC-5: no se
    pierde ninguno) mas "Excedencia" y "Otro" (AC-4)
  - los EntityField del formulario/tabla de ausencias (AC-1/AC-2)

Es idempotente: se puede ejecutar varias veces sin duplicar nada. Por defecto
solo SIMULA; hay que pasar --aplicar para escribir.

    manage.py configurar_ausencias            # simula y muestra que haria
    manage.py configurar_ausencias --aplicar  # escribe
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.absences.models import AbsenceType
from apps.catalog.models import Kind, KindValue
from apps.dynamic_fields.mixins import invalidate_fields_cache
from apps.dynamic_fields.models import EntityField, EntityType

KIND_CODE = 'absence_type'

# Tipos que se anaden como parte de la tarea (AC-4). Los que ya existan en
# AbsenceType se migran solos, no hace falta listarlos aqui.
TIPOS_NUEVOS = ['Excedencia', 'Otro']

# Campos del formulario de ausencias. Los que el planificador necesita
# (start_date, end_date, indefinite) NO van aqui: son columnas fijas del modelo
# y no pueden desactivarse desde la configuracion sin romper la generacion.
CAMPOS = [
    {
        'key': 'tipo', 'label': 'Tipo de ausencia',
        'field_type': 'catalog_select', 'kind_code': KIND_CODE,
        'required': True, 'show_in_list': True, 'show_as_filter': True,
        'order': 1,
        'help_text': 'Los valores se gestionan en Catalogo > Tipos de ausencia.',
    },
    {
        'key': 'observaciones', 'label': 'Observaciones',
        'field_type': 'textarea', 'required': False,
        'show_in_list': False, 'show_as_filter': False, 'order': 2,
        'placeholder': 'Detalle opcional de la ausencia',
    },
    {
        'key': 'justificante', 'label': 'Justificante entregado',
        'field_type': 'boolean', 'required': False,
        'show_in_list': True, 'show_as_filter': True, 'order': 3,
    },
]


class Command(BaseCommand):
    help = 'Configura Ausencias como entidad dinamica y su catalogo de tipos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--aplicar', action='store_true',
            help='Escribe los cambios. Sin este flag solo simula.')

    def handle(self, *args, **opts):
        aplicar = opts['aplicar']
        self.stdout.write('' if aplicar else '-- SIMULACION (usa --aplicar para escribir) --')
        self.stdout.write('')

        with transaction.atomic():
            self._entity_type(aplicar)
            kind = self._kind(aplicar)
            self._valores(kind, aplicar)
            self._campos(aplicar)

            if not aplicar:
                transaction.set_rollback(True)

        if aplicar:
            invalidate_fields_cache('absence')
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Aplicado.'))
        else:
            self.stdout.write('')
            self.stdout.write('Nada escrito.')

    # ── EntityType ───────────────────────────────────────────────

    def _entity_type(self, aplicar):
        et = EntityType.objects.filter(slug='absence').first()
        if et:
            self.stdout.write(f'EntityType "absence": ya existe (id={et.id})')
            return et
        self.stdout.write('EntityType "absence": CREAR')
        if not aplicar:
            return None
        return EntityType.objects.create(
            slug='absence', name='Ausencias', icon='event_busy',
            # No va al sidebar: la seccion Ausencias ya tiene su propia pantalla;
            # esto es solo para que sus campos salgan en AdminZebra.
            show_in_sidebar=False,
            is_system=True,   # la gestiona la app, no se puede borrar
            display_field='tipo',
            order=50,
        )

    # ── Kind del catalogo de tipos (AC-3) ────────────────────────

    def _kind(self, aplicar):
        kind = Kind.objects.filter(code=KIND_CODE).first()
        if kind:
            self.stdout.write(f'Kind "{KIND_CODE}": ya existe (id={kind.id})')
            return kind
        self.stdout.write(f'Kind "{KIND_CODE}": CREAR')
        if not aplicar:
            return None
        return Kind.objects.create(
            code=KIND_CODE, name='Tipos de ausencia',
            description='Valores del desplegable "Tipo de ausencia". '
                        'Se pueden anadir, editar y desactivar desde aqui.',
            icon='event_busy',
            editable=True,   # AC-3: el cliente los gestiona
        )

    # ── Valores: los existentes (AC-5) + los nuevos (AC-4) ───────

    def _valores(self, kind, aplicar):
        existentes = list(AbsenceType.objects.all().order_by('name'))
        nombres_existentes = [t.name for t in existentes]

        self.stdout.write('')
        self.stdout.write('Valores del catalogo:')
        orden = 0
        for t in existentes:
            orden += 1
            self._valor(kind, t.name, orden, t.active, aplicar, origen='existente')

        for nombre in TIPOS_NUEVOS:
            if nombre in nombres_existentes:
                self.stdout.write(f'   {nombre:24} ya existia como tipo, no se duplica')
                continue
            orden += 1
            self._valor(kind, nombre, orden, True, aplicar, origen='NUEVO (AC-4)')

    def _valor(self, kind, nombre, orden, activo, aplicar, origen):
        code = slugify(nombre).replace('-', '_')[:50]
        ya = kind and KindValue.objects.filter(kind=kind, code=code).exists()
        estado = 'ya existe' if ya else 'CREAR'
        self.stdout.write(f'   {nombre:24} code={code:22} {estado:10} [{origen}]')
        if not aplicar or ya or not kind:
            return
        KindValue.objects.create(
            kind=kind, code=code, label=nombre, order=orden, active=activo)

    # ── Campos del formulario / columnas (AC-1/AC-2) ─────────────

    def _campos(self, aplicar):
        self.stdout.write('')
        self.stdout.write('Campos de la entidad:')
        for cfg in CAMPOS:
            ya = EntityField.objects.filter(
                entity_type='absence', key=cfg['key']).first()
            if ya:
                self.stdout.write(f'   {cfg["key"]:16} ya existe (id={ya.id})')
                continue
            self.stdout.write(f'   {cfg["key"]:16} CREAR ({cfg["field_type"]})')
            if aplicar:
                EntityField.objects.create(entity_type='absence', **cfg)
