import logging
import os

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import AssignmentRule
from .serializers import AssignmentRuleSerializer

logger = logging.getLogger(__name__)


class AssignmentRuleViewSet(viewsets.ModelViewSet):
    queryset = AssignmentRule.objects.all()
    serializer_class = AssignmentRuleSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def patterns(self, request):
        """Return available temporal patterns for assignment rules."""
        return Response([
            {'value': 'always', 'label': 'Siempre', 'description': 'Aplica el override directo (sin alternancia)'},
            {'value': 'alternate_weekly', 'label': 'Alternar por semanas', 'description': 'Alterna entre turno principal y alternativo cada N semanas'},
            {'value': 'alternate_daily', 'label': 'Alternar por dias', 'description': 'Alterna entre turno principal y alternativo cada N dias'},
            {'value': 'weekday', 'label': 'Solo un dia concreto', 'description': 'Aplica el override unicamente en el dia de la semana indicado en config.weekday (0=lunes..6=domingo)'},
        ])

    @action(detail=False, methods=['get'])
    def worker_fields(self, request):
        """Return worker fields grouped by type for the config form."""
        from apps.dynamic_fields.models import EntityField
        fields = EntityField.objects.filter(entity_type='worker', active=True).order_by('order')
        return Response([
            {
                'key': f.key,
                'label': f.label or f.key,
                'field_type': f.field_type,
                'target_entity': f.target_entity or '',
            }
            for f in fields
        ])


class AssignmentChatView(APIView):
    """Chat endpoint for creating assignment rules with natural language."""
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
            logger.error('Assignment chat error: %s', e)
            return Response({'error': 'Error al procesar la solicitud'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _build_system_prompt(self):
        from apps.dynamic_fields.models import EntityField, EntityType, EntityRecord
        from apps.shifts.models import Shift

        shifts = list(Shift.objects.values('id', 'name'))
        worker_fields = list(EntityField.objects.filter(
            entity_type='worker', active=True
        ).values('key', 'label', 'field_type', 'target_entity').order_by('order'))
        existing = list(AssignmentRule.objects.values('name', 'config', 'active', 'priority'))

        return f"""Eres un asistente experto en configurar reglas de asignación para un planificador de turnos.
Tu trabajo es ayudar al usuario a crear reglas que determinan el turno efectivo de un trabajador.

REGLAS:
1. Si la petición no es clara, haz preguntas concretas.
2. Cuando tengas suficiente información, responde con el JSON dentro de ```json ... ```.
3. El JSON debe tener: name, description, config, active, priority, scope_records.
4. Explica brevemente qué hace la regla antes del JSON.
5. Solo genera UNA regla por mensaje.
6. Responde siempre en español.

ESTRUCTURA DE CONFIG:
{{
  "conditionField": "clave_campo_worker",   // Campo del trabajador a evaluar (booleano, select, etc). Vacío = aplica a todos.
  "conditionValue": "valor",                 // Valor que debe tener. Vacío = cualquier valor truthy.
  "overrideField": "clave_campo_worker",     // Campo que contiene el turno alternativo (entity_select → shift)
  "pattern": "always|alternate_weekly|alternate_daily|weekday",
  "frequencyField": "clave_campo_worker",    // (opcional) Campo numérico del worker con la frecuencia
  "frequencyValue": 1,                       // (opcional) Frecuencia fija si no viene de un campo
  "weekday": 5                               // (solo pattern 'weekday') dia 0=Lun..6=Dom en que aplica el override
}}

PATRONES:
- "always": El override se aplica siempre que se cumpla la condición.
- "alternate_weekly": Alterna entre turno principal y override cada N semanas.
- "alternate_daily": Alterna cada N días.
- "weekday": Aplica el override solo en el día de la semana indicado en "weekday" (0=Lun..6=Dom). Útil para el turno de sábado.

DATOS DEL SISTEMA:
- Turnos: {shifts}
- Campos del trabajador: {worker_fields}
- Reglas existentes: {existing}

EJEMPLOS:
1. "Quiero que los que tienen turno rotativo alteren cada semana":
   config = {{ "conditionField": "turno_rotativo", "conditionValue": "true", "overrideField": "turno_secundario", "pattern": "alternate_weekly", "frequencyField": "frecuencia_rotacion" }}

2. "Los que tengan jornada partida siempre usar su turno especial":
   config = {{ "conditionField": "jornada_partida", "conditionValue": "true", "overrideField": "turno_especial", "pattern": "always" }}
"""
