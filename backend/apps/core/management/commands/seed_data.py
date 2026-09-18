from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Load initial seed data for all domain entities.'

    def handle(self, *args, **options):
        self._seed_catalog()
        self._seed_entity_types()
        self._seed_workers()
        self._seed_restrictions()
        self._seed_absence_types()
        self.stdout.write(self.style.SUCCESS('Seed data loaded successfully.'))

    def _seed_catalog(self):
        from apps.catalog.models import Kind, KindAttribute, KindValue, KindValueAttribute
        self.stdout.write('\n-- Catalog --')

        kinds = [
            {
                'code': 'shift_slot',
                'name': 'Franjas horarias',
                'description': 'Franjas de turno disponibles en la planificacion',
                'icon': 'schedule',
                'editable': True,
                'attributes': [
                    {'key': 'start_time', 'label': 'Hora inicio', 'field_type': 'time', 'required': True, 'placeholder': '07:00', 'order': 1},
                    {'key': 'end_time', 'label': 'Hora fin', 'field_type': 'time', 'required': True, 'placeholder': '15:00', 'order': 2},
                ],
                'values': [
                    {'code': 'morning', 'label': 'Manana', 'icon': 'wb_sunny', 'color': '#3B82F6', 'order': 1,
                     'attrs': {'start_time': '07:00', 'end_time': '15:00'}},
                    {'code': 'afternoon', 'label': 'Tarde', 'icon': 'wb_twilight', 'color': '#F59E0B', 'order': 2,
                     'attrs': {'start_time': '15:00', 'end_time': '23:00'}},
                    {'code': 'night', 'label': 'Noche', 'icon': 'nightlight', 'color': '#8B5CF6', 'order': 3,
                     'attrs': {'start_time': '23:00', 'end_time': '07:00'}},
                ],
            },
            {
                'code': 'restriction_type',
                'name': 'Tipos de restriccion',
                'description': 'Tipos de reglas que se aplican a la planificacion',
                'icon': 'rule',
                'editable': True,
                'attributes': [],
                'values': [
                    {'code': 'max_workers_per_area', 'label': 'Maximo trabajadores por area', 'order': 1, 'attrs': {}},
                    {'code': 'min_workers_per_area', 'label': 'Minimo trabajadores por area', 'order': 2, 'attrs': {}},
                    {'code': 'no_empty_areas', 'label': 'Sin areas vacias', 'order': 3, 'attrs': {}},
                    {'code': 'night_morning_conflict', 'label': 'Conflicto entre turnos consecutivos', 'order': 4, 'attrs': {}},
                    {'code': 'max_shifts_per_day', 'label': 'Maximo turnos por dia', 'order': 5, 'attrs': {}},
                    {'code': 'preferred_shifts_warning', 'label': 'Aviso turnos preferidos', 'order': 6, 'attrs': {}},
                    {'code': 'role_required', 'label': 'Rol requerido por area', 'order': 7, 'attrs': {}},
                    {'code': 'incompatible_workers', 'label': 'Trabajadores incompatibles', 'order': 8, 'attrs': {}},
                    {'code': 'max_areas_per_worker', 'label': 'Maximo areas por trabajador', 'order': 9, 'attrs': {}},
                    {'code': 'no_rest_workers_in_shifts', 'label': 'Sin trabajadores en descanso en turnos', 'order': 10, 'attrs': {}},
                    {'code': 'area_required_role', 'label': 'Validacion rol requerido por area', 'order': 11, 'attrs': {}},
                ],
            },
            {
                'code': 'absence_status',
                'name': 'Estados de solicitud',
                'description': 'Estados posibles para solicitudes de ausencia',
                'icon': 'assignment',
                'editable': False,
                'attributes': [],
                'values': [
                    {'code': 'pending', 'label': 'Pendiente', 'icon': 'hourglass_empty', 'color': '#F59E0B', 'order': 1, 'attrs': {}},
                    {'code': 'approved', 'label': 'Aprobada', 'icon': 'check_circle', 'color': '#22C55E', 'order': 2, 'attrs': {}},
                    {'code': 'rejected', 'label': 'Rechazada', 'icon': 'cancel', 'color': '#EF4444', 'order': 3, 'attrs': {}},
                ],
            },
            {
                'code': 'severity',
                'name': 'Niveles de severidad',
                'description': 'Niveles de severidad para violaciones de restricciones',
                'icon': 'warning',
                'editable': False,
                'attributes': [],
                'values': [
                    {'code': 'warning', 'label': 'Advertencia', 'icon': 'warning', 'color': '#F59E0B', 'order': 1, 'attrs': {}},
                    {'code': 'error', 'label': 'Error', 'icon': 'error', 'color': '#EF4444', 'order': 2, 'attrs': {}},
                ],
            },
        ]

        for kind_data in kinds:
            attributes_data = kind_data.pop('attributes')
            values_data = kind_data.pop('values')
            kind, created = Kind.objects.get_or_create(
                code=kind_data['code'],
                defaults=kind_data,
            )
            status = 'created' if created else 'exists'
            self.stdout.write(f'  Kind "{kind.code}" - {status}')

            # Seed KindAttribute schema
            attr_map = {}
            for attr_data in attributes_data:
                attr, _ = KindAttribute.objects.get_or_create(
                    kind=kind, key=attr_data['key'], defaults=attr_data,
                )
                attr_map[attr.key] = attr

            # Seed KindValues and their attribute values
            for val_data in values_data:
                val_attrs = val_data.pop('attrs', {})
                val, val_created = KindValue.objects.get_or_create(
                    kind=kind, code=val_data['code'], defaults=val_data,
                )
                vs = 'created' if val_created else 'exists'
                self.stdout.write(f'    Value "{val.code}" - {vs}')
                for key, value in val_attrs.items():
                    attr_obj = attr_map.get(key)
                    if attr_obj:
                        KindValueAttribute.objects.get_or_create(
                            kind_value=val, attribute=attr_obj, defaults={'value': value},
                        )

    def _seed_workers(self):
        from apps.workers.models import Worker, WorkerPreference
        self.stdout.write('\n-- Workers --')

    def _seed_entity_types(self):
        from apps.dynamic_fields.models import EntityType
        from apps.workers.models import Worker, WorkerPreference
        self.stdout.write('\n-- Entity Types --')
        system_types = [
            {'slug': 'worker', 'name': 'Empleados', 'icon': 'people', 'order': 0, 'show_in_sidebar': False, 'is_system': True, 'display_field': 'name'},
        ]
        for et_data in system_types:
            et, created = EntityType.objects.get_or_create(slug=et_data['slug'], defaults=et_data)
            self.stdout.write(f'  EntityType "{et.slug}" - {"created" if created else "exists"}')
        workers_data = [
            {'name': 'Ana Garcia', 'prefs': ['morning', 'afternoon']},
            {'name': 'Nilla Esteban', 'prefs': ['morning']},
            {'name': 'Carlos Lopez', 'prefs': ['night']},
            {'name': 'Cintia Perez', 'prefs': ['morning', 'afternoon']},
            {'name': 'David Ruiz', 'prefs': ['morning']},
            {'name': 'Elena Martinez', 'prefs': ['afternoon']},
        ]
        for item in workers_data:
            worker, created = Worker.objects.get_or_create(name=item['name'])
            if created:
                for pref in item['prefs']:
                    WorkerPreference.objects.get_or_create(worker=worker, shift_type=pref)
            status = 'created' if created else 'exists'
            self.stdout.write(f'  Worker "{worker.name}" - {status}')

    def _seed_restrictions(self):
        from apps.restrictions.models import Restriction
        self.stdout.write('\n-- Restrictions --')
        data = [
            {
                'name': 'Maximo 3 trabajadores por area',
                'description': 'Limita trabajadores por area por turno',
                'engine': 'count',
                'config': {'subject': 'workers', 'groupBy': 'shift_area', 'operator': 'lte', 'threshold': 3},
                'severity': 'error',
            },
            {
                'name': 'Sin areas vacias',
                'description': 'Todas las areas deben tener al menos 1 trabajador',
                'engine': 'count',
                'config': {'subject': 'workers', 'groupBy': 'shift_area', 'operator': 'gte', 'threshold': 1, 'filterField': 'area', 'filterValue': ['Area 1', 'Area 2', 'Area 3']},
                'severity': 'error',
            },
            {
                'name': 'Conflicto noche-manana',
                'description': 'Evita que un trabajador haga noche y al dia siguiente manana',
                'engine': 'exclusion',
                'config': {'exclusionType': 'consecutive_shifts', 'shiftA': 'night', 'shiftB': 'morning'},
                'severity': 'warning',
            },
            {
                'name': 'Maximo 1 turno por dia',
                'description': 'Un trabajador no puede tener mas de 1 turno al dia',
                'engine': 'count',
                'config': {'subject': 'shifts', 'groupBy': 'day_worker', 'operator': 'lte', 'threshold': 1},
                'severity': 'error',
            },
            {
                'name': 'Maximo 2 areas por trabajador',
                'description': 'Un trabajador no puede cubrir mas de 2 areas por turno',
                'engine': 'count',
                'config': {'subject': 'areas', 'groupBy': 'shift_worker', 'operator': 'lte', 'threshold': 2},
                'severity': 'warning',
            },
            {
                'name': 'Sin trabajadores en descanso en turnos',
                'description': 'Impide asignar a un turno a trabajadores que descansan ese dia',
                'engine': 'exclusion',
                'config': {'exclusionType': 'rest_conflict'},
                'severity': 'error',
            },
            {
                'name': 'Aviso turnos preferidos',
                'description': 'Avisa si se asigna un turno no preferido por el trabajador',
                'engine': 'match',
                'config': {'matchType': 'worker_preference'},
                'severity': 'warning',
            },
            {
                'name': 'Validacion rol requerido por area',
                'description': 'Verifica que el trabajador tenga el rol requerido del area',
                'engine': 'match',
                'config': {'matchType': 'area_role'},
                'severity': 'error',
            },
        ]
        for item in data:
            obj, created = Restriction.objects.get_or_create(name=item['name'], defaults=item)
            status = 'created' if created else 'exists'
            self.stdout.write(f'  Restriction "{obj.name}" - {status}')

    def _seed_absence_types(self):
        from apps.absences.models import AbsenceType
        self.stdout.write('\n-- Absence types --')
        data = [
            {'name': 'Vacaciones', 'requires_approval': True},
            {'name': 'Baja médica', 'requires_approval': False},
            {'name': 'Asuntos propios', 'requires_approval': True},
            {'name': 'Permiso retribuido', 'requires_approval': True},
        ]
        for item in data:
            obj, created = AbsenceType.objects.get_or_create(name=item['name'], defaults=item)
            status = 'created' if created else 'exists'
            self.stdout.write(f'  AbsenceType "{obj.name}" - {status}')
