from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Restriction
from .serializers import RestrictionSerializer
from .validators import validate_plan
from apps.dynamic_fields.models import EntityField, EntityType, EntityRecord
import json, logging, os

logger = logging.getLogger(__name__)


class RestrictionViewSet(viewsets.ModelViewSet):
    queryset = Restriction.objects.all()
    serializer_class = RestrictionSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate a customizable restriction as an independent copy.

        The copy keeps engine/config but is fully autonomous: editing the
        original afterwards does not propagate. `duplicated_from` is only a trace.
        Optional body: {name, scope_records} to name the copy and scope it to
        specific planning records (tiendas) in a single step.
        """
        original = self.get_object()
        if not original.customizable:
            return Response(
                {'error': 'Solo se pueden duplicar restricciones personalizables'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = (request.data.get('name') or '').strip() or self._copy_name(original.name)
        scope_records = request.data.get('scope_records')
        if scope_records is None:
            scope_records = list(original.scope_records or [])

        copy = Restriction.objects.create(
            name=name[:100],
            description=original.description,
            engine=original.engine,
            config=dict(original.config or {}),
            severity=original.severity,
            message=original.message,
            active=original.active,
            customizable=True,
            scope_records=scope_records,
            duplicated_from=original,
        )
        return Response(self.get_serializer(copy).data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _copy_name(base):
        """Return "<base> (copia)", or "(copia N)" if that name is taken."""
        candidate = f'{base} (copia)'
        if not Restriction.objects.filter(name=candidate).exists():
            return candidate
        n = 2
        while Restriction.objects.filter(name=f'{base} (copia {n})').exists():
            n += 1
        return f'{base} (copia {n})'

    @action(detail=False, methods=['get'])
    def engine_schema(self, request):
        """Return the configuration schema for each engine type."""
        schema = {
            'count': {
                'label': 'Conteo',
                'description': 'Cuenta entidades agrupadas y compara contra un umbral',
                'fields': [
                    {'key': 'subject', 'label': 'Que contar', 'field_type': 'select',
                     'options': [
                         {'value': 'workers', 'label': 'Trabajadores'},
                         {'value': 'shifts', 'label': 'Turnos por trabajador'},
                         {'value': 'areas', 'label': 'Areas por trabajador'},
                     ]},
                    {'key': 'groupBy', 'label': 'Agrupar por', 'field_type': 'select',
                     'options': [
                         {'value': 'shift', 'label': 'Por turno'},
                         {'value': 'shift_area', 'label': 'Por turno y area'},
                         {'value': 'day_worker', 'label': 'Por dia y trabajador'},
                         {'value': 'shift_worker', 'label': 'Por turno y trabajador'},
                     ]},
                    {'key': 'operator', 'label': 'Operador', 'field_type': 'select',
                     'options': [
                         {'value': 'lte', 'label': 'Maximo (<=)'},
                         {'value': 'gte', 'label': 'Minimo (>=)'},
                     ]},
                    {'key': 'threshold', 'label': 'Umbral', 'field_type': 'number', 'min': 0, 'max': 50},
                    {'key': 'filterField', 'label': 'Filtrar por', 'field_type': 'select',
                     'options': [
                         {'value': '', 'label': 'Sin filtro'},
                         {'value': 'role', 'label': 'Rol'},
                         {'value': 'area', 'label': 'Areas especificas'},
                     ]},
                    {'key': 'filterValue', 'label': 'Valor del filtro', 'field_type': 'dynamic'},
                ],
            },
            'exclusion': {
                'label': 'Exclusion',
                'description': 'Impide que ciertas situaciones coexistan',
                'fields': [
                    {'key': 'exclusionType', 'label': 'Tipo de exclusion', 'field_type': 'select',
                     'options': [
                         {'value': 'consecutive_shifts', 'label': 'Turnos consecutivos'},
                         {'value': 'worker_pair', 'label': 'Trabajadores incompatibles'},
                         {'value': 'rest_conflict', 'label': 'Descanso en turno'},
                     ]},
                    {'key': 'shiftA', 'label': 'Turno A', 'field_type': 'shift_select',
                     'showWhen': {'exclusionType': 'consecutive_shifts'}},
                    {'key': 'shiftB', 'label': 'Turno B', 'field_type': 'shift_select',
                     'showWhen': {'exclusionType': 'consecutive_shifts'}},
                    {'key': 'workerPairs', 'label': 'Parejas incompatibles', 'field_type': 'worker_pairs',
                     'showWhen': {'exclusionType': 'worker_pair'}},
                ],
            },
            'match': {
                'label': 'Coincidencia',
                'description': 'Verifica que un campo coincida con otro',
                'fields': [
                    {'key': 'matchType', 'label': 'Tipo de coincidencia', 'field_type': 'select',
                     'options': [
                         {'value': 'worker_preference', 'label': 'Preferencia de turno del trabajador'},
                         {'value': 'area_role', 'label': 'Rol requerido por area'},
                         {'value': 'area_membership', 'label': 'La entidad asignada pertenece al trabajador'},
                     ]},
                ],
            },
            'closed_day': {
                'label': 'Cierre',
                'description': (
                    'Bloquea asignaciones en fechas marcadas como día de cierre '
                    '(festivo local, cierre puntual). Los días de cierre se gestionan '
                    'en Planificación > Días de cierre; esta restricción no tiene configuración propia.'
                ),
                'fields': [],
            },
            'condition': {
                'label': 'Condición avanzada',
                'description': 'Motor general con árbol AND/OR/NOT sobre campos EAV. Soporta cualquier campo del trabajador (entity_select, multi_entity_select, catalog_select, boolean, number).',
                'fields': [
                    {'key': 'scope', 'label': 'Ámbito', 'field_type': 'select',
                     'options': [
                         {'value': 'per_shift',             'label': 'Por turno'},
                         {'value': 'per_day',               'label': 'Por día'},
                         {'value': 'per_day_worker',        'label': 'Por trabajador y día'},
                         {'value': 'per_week_worker',       'label': 'Por trabajador y semana completa'},
                         {'value': 'per_week_worker_hours', 'label': 'Horas por trabajador y semana (suma duraciones)'},
                         {'value': 'per_week_worker_shift', 'label': 'Por trabajador, semana y tipo de turno'},
                         {'value': 'per_shift_worker',      'label': 'Por trabajador y turno'},
                         {'value': 'per_shift_area',        'label': 'Por turno y área'},
                     ]},
                    {'key': 'operator', 'label': 'Operador', 'field_type': 'select',
                     'options': [
                         {'value': 'lte', 'label': 'Máximo (≤)'},
                         {'value': 'gte', 'label': 'Mínimo (≥)'},
                         {'value': 'eq',  'label': 'Exactamente (=)'},
                     ]},
                    {'key': 'threshold', 'label': 'Umbral', 'field_type': 'number', 'min': 0, 'max': 100},
                    {'key': 'thresholdField', 'label': 'Campo de umbral dinámico', 'field_type': 'text',
                     'description': (
                         'Clave EAV del trabajador cuyo valor se usa como umbral individual '
                         '(p.ej. "horas_semanales"). Si se especifica, sobreescribe "Umbral" por trabajador. '
                         'Para scope per_week_worker (turnos) y per_week_worker_hours (horas).'
                     ),
                     'showWhen': {'scope': 'per_week_worker'}},
                    {'key': 'dayOfWeek', 'label': 'Solo día de semana', 'field_type': 'select',
                     'options': [
                         {'value': None,  'label': 'Todos los días'},
                         {'value': 0, 'label': 'Lunes'},
                         {'value': 1, 'label': 'Martes'},
                         {'value': 2, 'label': 'Miércoles'},
                         {'value': 3, 'label': 'Jueves'},
                         {'value': 4, 'label': 'Viernes'},
                         {'value': 5, 'label': 'Sábado'},
                         {'value': 6, 'label': 'Domingo'},
                     ]},
                    {'key': 'targetShift', 'label': 'Turno objetivo', 'field_type': 'shift_select',
                     'description': 'Solo para scope per_week_worker_shift: ID del turno a contar.',
                     'showWhen': {'scope': 'per_week_worker_shift'}},
                    {'key': 'filter', 'label': 'Condición (JSON)', 'field_type': 'json',
                     'description': (
                         'Árbol de condiciones sobre campos EAV del trabajador. '
                         'Nodos: {"and":[...]}, {"or":[...]}, {"not":{...}}, '
                         '{"field":"clave","op":"eq|neq|in|nin|gt|gte|lt|lte","value":<val>}. '
                         'Dejar vacío para que cuente todos los trabajadores.'
                     )},
                    {'key': 'scopeMatch', 'label': 'Coincidencia con ámbito (JSON)', 'field_type': 'json',
                     'description': (
                         'Compara campos del trabajador con el ámbito (tienda). '
                         'Formato: {"rules":[regla,...]}. Reglas (OR): '
                         '{"workerField":"campo","matchType":"id"} compara con ID del ámbito; '
                         '{"workerField":"campo","scopeField":"campo_ambito"} compara valores; '
                         'añade "requireField"/"requireValue" para condición extra. '
                         'Si se usa scopeMatch, scope/filter/operator/threshold se ignoran.'
                     )},
                ],
            },
        }
        return Response(schema)


class ValidationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        plan_data = request.data.get('plan', [])
        scope_record_id = request.data.get('scope_record_id')
        if scope_record_id is not None:
            scope_record_id = int(scope_record_id)
        if not plan_data:
            return Response({'error': 'plan data required'}, status=status.HTTP_400_BAD_REQUEST)
        violations = validate_plan(plan_data, scope_record_id=scope_record_id)
        return Response({'isValid': len(violations) == 0, 'violations': violations})


class ConstraintsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        constraints = {}
        restrictions = Restriction.objects.filter(active=True)
        for r in restrictions:
            constraints[r.engine] = {
                'name': r.name,
                'config': r.config,
                'severity': r.severity,
                'active': True,
            }
        return Response(constraints)


class WorkerFieldsView(APIView):
    """Return filterable worker fields for restriction configuration."""
    permission_classes = [AllowAny]

    def get(self, request):
        # number/boolean included: usable in condition filters (gt/gte/lt/lte, eq)
        # and as thresholdField for per-worker dynamic caps (turnos u horas).
        filterable_types = (
            'entity_select', 'catalog_select', 'multi_entity_select', 'multi_catalog_select',
            # 'float' junto a 'number': el tope de horas semanales por contrato
            # se declara como thresholdField y necesita decimales (37,5 h).
            'number', 'float', 'boolean',
        )
        fields = EntityField.objects.filter(
            entity_type='worker',
            field_type__in=filterable_types,
        ).values('key', 'label', 'field_type', 'target_entity', 'kind_code')
        return Response(list(fields))


class RestrictionChatView(APIView):
    """Chat endpoint for creating restrictions with natural language."""
    permission_classes = [AllowAny]

    def post(self, request):
        message = request.data.get('message', '').strip()
        history = request.data.get('history', [])
        if not message:
            return Response({'error': 'message required'}, status=status.HTTP_400_BAD_REQUEST)

        api_key = os.getenv('OPENAI_API_KEY')
        model = os.getenv('AGENT_MODEL', 'gpt-4o-mini')
        if not api_key:
            return Response({'error': 'OpenAI API key not configured'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        system_prompt = self._build_system_prompt()

        messages = [{'role': 'system', 'content': system_prompt}]
        for h in history:
            messages.append({'role': h.get('role', 'user'), 'content': h.get('content', '')})
        messages.append({'role': 'user', 'content': message})

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
            )
            reply = response.choices[0].message.content
            return Response({'response': reply})
        except Exception as e:
            logger.error('Restriction chat error: %s', e)
            return Response({'error': 'Error al procesar la solicitud'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _build_system_prompt(self):
        """Build a system prompt with full context about the restriction system."""
        from apps.shifts.models import Shift
        from apps.catalog.models import KindValue

        # Gather context
        shifts = list(Shift.objects.values('id', 'name'))
        entity_types = list(EntityType.objects.values('slug', 'name'))
        worker_fields = list(EntityField.objects.filter(
            entity_type='worker', active=True
        ).values('key', 'label', 'field_type', 'target_entity', 'kind_code').order_by('order'))

        entity_records = {}
        for et in EntityType.objects.exclude(slug__in=['worker', 'shift']):
            recs = list(EntityRecord.objects.filter(entity_type=et).values('id', 'data'))
            if recs:
                entity_records[et.slug] = recs

        catalog_values = {}
        kind_codes = set(f['kind_code'] for f in worker_fields if f['kind_code'])
        for code in kind_codes:
            vals = list(KindValue.objects.filter(kind__code=code).values('code', 'label'))
            if vals:
                catalog_values[code] = vals

        existing = list(Restriction.objects.values('name', 'engine', 'config', 'severity', 'message', 'scope_records'))

        return f"""Eres un asistente experto en configurar restricciones para un sistema de planificación de turnos de trabajadores.
Tu trabajo es ayudar al usuario a crear restricciones usando lenguaje natural. Cuando tengas suficiente información, genera el JSON de la restricción.

REGLAS IMPORTANTES:
1. Si la petición del usuario no es clara, hazle preguntas concretas para aclarar exactamente qué quiere.
2. Cuando tengas suficiente información, responde con el JSON de la restricción dentro de un bloque ```json ... ```.
3. El JSON debe tener estos campos: name, description, engine, config, severity, message, scope_records, active.
4. Explica brevemente qué hace la restricción antes del JSON.
5. Solo genera UNA restricción por mensaje.
6. Responde siempre en español.

MOTORES DISPONIBLES:

1. **count** — Cuenta entidades y compara contra un umbral.
   config: {{ subject: "workers"|"shifts"|"areas", groupBy: "shift"|"shift_area"|"day_worker"|"shift_worker", operator: "lte"|"gte", threshold: int, filterField: ""|"role"|"area", filterEntityType: string, filterRecordId: int, filterValue: string, filterAreaNames: [string], skipEmptyShifts: bool (opcional: los turnos sin ninguna asignación ese día no se evalúan — recomendado en mínimos "gte" cuando el ámbito no usa todos los turnos) }}

2. **exclusion** — Impide situaciones incompatibles.
   config para turnos consecutivos: {{ exclusionType: "consecutive_shifts", shiftA: "ID_turno", shiftB: "ID_turno" }}
   config para trabajadores incompatibles: {{ exclusionType: "worker_pair", workerPairs: [[id1, id2]] }}
   config para conflicto descanso: {{ exclusionType: "rest_conflict" }}

3. **match** — Verifica coincidencias de campos.
   config preferencia turno: {{ matchType: "worker_preference" }}
   config rol por area: {{ matchType: "area_role", areaEntityType: "area", roleEntityType: "role", workerRoleField: "rol", areaRoleField: "required_role" }}

4. **condition** — Motor avanzado con filtros sobre campos EAV del trabajador.
   config: {{ scope: "per_shift"|"per_day"|"per_day_worker"|"per_week_worker"|"per_week_worker_shift"|"per_shift_worker"|"per_shift_area", operator: "lte"|"gte"|"eq", threshold: int, dayOfWeek: null|0-6, targetShift: "ID" (solo per_week_worker_shift), filter: null|condición_json }}
   
   Condiciones JSON (sobre campos del trabajador):
   - Hoja: {{ "field": "clave_campo", "op": "eq|neq|in|nin|gt|gte|lt|lte", "value": valor }}
   - AND: {{ "and": [condición, ...] }}
   - OR: {{ "or": [condición, ...] }}
   - NOT: {{ "not": condición }}
   
   Para campos multi_entity_select (como "rol"), usa op "in" con [id_entidad] como value.
   Para campos entity_select, usa op "eq" con id_entidad como value.
   Para campos catalog_select, usa op "eq" con código string como value.
   Para campos boolean, usa op "eq" con true/false.
   
   **scopeMatch** (solo en condition): compara campos del trabajador contra el ámbito (tienda) de la planificación.
   Se usa en lugar de filter/operator/threshold cuando la restricción es "el trabajador pertenece a este ámbito".
   config: {{ scopeMatch: {{ rules: [ regla, ... ] }} }}
   Cada regla (se cumple si ALGUNA coincide):
   - Coincidencia por ID: {{ "workerField": "campo_entity_select", "matchType": "id" }} → compara el valor del campo con el ID del ámbito.
   - Coincidencia por campo: {{ "workerField": "campo_worker", "scopeField": "campo_ambito" }} → compara ambos valores.
   - Condición extra: añade "requireField": "campo_bool", "requireValue": true/false para exigir un campo adicional del trabajador.

PLACEHOLDERS para el campo "message": {{worker}}, {{count}}, {{limit}}, {{area}}, {{shift}}, {{role}}, {{worker1}}, {{worker2}}

scope_records: lista de IDs de tiendas a las que aplica. Vacío [] = aplica a todas.

DATOS DEL SISTEMA:

Turnos: {json.dumps(shifts, ensure_ascii=False)}

Entidades: {json.dumps(entity_types, ensure_ascii=False)}

Campos del trabajador: {json.dumps(worker_fields, ensure_ascii=False)}

Registros de entidades:
{json.dumps(entity_records, ensure_ascii=False, indent=2)}

Valores de catálogo:
{json.dumps(catalog_values, ensure_ascii=False, indent=2)}

Restricciones existentes (para referencia y evitar duplicados):
{json.dumps(existing, ensure_ascii=False, indent=2)}

EJEMPLOS DE RESTRICCIONES REALES:

Ejemplo 1 — "Mínimo 1 Cajero por turno":
```json
{{"name": "Min 1 Cajero por turno", "engine": "condition", "config": {{"scope": "per_shift", "filter": {{"op": "in", "field": "rol", "value": [1]}}, "operator": "gte", "threshold": 1}}, "severity": "error", "message": "Turno {{shift}}: {{count}} cajeros (min {{limit}})", "description": "Cada turno debe tener al menos 1 cajero", "scope_records": [], "active": true}}
```

Ejemplo 2 — "Máximo 5 turnos por semana por trabajador":
```json
{{"name": "Max 5 turnos por semana", "engine": "condition", "config": {{"scope": "per_week_worker", "operator": "lte", "threshold": 5}}, "severity": "error", "message": "{{worker}}: {{count}} turnos en la semana (max {{limit}})", "description": "Un trabajador no puede tener más de 5 turnos por semana", "scope_records": [], "active": true}}
```

Ejemplo 3 — "Máximo 3 trabajadores ETT por turno":
```json
{{"name": "Max 3 trabajadores ETT por tienda", "engine": "condition", "config": {{"scope": "per_shift_area", "filter": {{"op": "eq", "field": "tipo_de_contrato", "value": "ett"}}, "operator": "lte", "threshold": 3}}, "severity": "error", "message": "Tienda {{area}}: {{count}} trabajadores ETT en turno {{shift}} (max {{limit}})", "description": "No más de 3 trabajadores con contrato ETT por turno en cada tienda", "scope_records": [], "active": true}}
```

Ejemplo 4 — "Trabajador solo en tiendas de su zona (con disponibilidad de traslado para rotar)":
```json
{{"name": "Trabajador solo en tiendas de su zona", "engine": "condition", "config": {{"scopeMatch": {{"rules": [{{"workerField": "tienda_de_preferencia", "matchType": "id"}}, {{"workerField": "zona", "scopeField": "zona", "requireField": "disponibilidad_de_traslado", "requireValue": true}}]}}}}, "severity": "error", "message": "{{worker}} no puede trabajar en esta tienda (no es su tienda ni tiene disponibilidad de traslado en su zona)", "description": "Un trabajador solo puede estar en su tienda preferida, o en otra tienda de su zona si tiene disponibilidad de traslado", "scope_records": [], "active": true}}
```
"""
