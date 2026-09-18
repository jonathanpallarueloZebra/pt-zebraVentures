from datetime import datetime, timedelta, date as date_type

from rest_framework import serializers
from apps.catalog.helpers import get_values
from apps.shifts.models import Shift
from apps.shifts.utils import shift_codes as _shared_shift_codes, day_names as _shared_day_names
from .models import ClosedDay, WeeklyPlan


class ClosedDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClosedDay
        fields = ['id', 'date', 'scope_entity_id', 'reason', 'created_at']
        read_only_fields = ['id', 'created_at']


def _day_names():
    vals = get_values('dias')
    if vals:
        return [v['label'] for v in vals]
    return _shared_day_names()


def _shift_codes():
    return _shared_shift_codes()


def empty_week(start_date):
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    elif not isinstance(start_date, date_type):
        start_date = datetime.utcnow().date()
    day_names = _day_names()
    shift_codes = _shift_codes()
    result = []
    for i in range(7):
        day = {
            'date': (start_date + timedelta(days=i)).strftime('%Y-%m-%d'),
            'dayName': day_names[i] if i < len(day_names) else f'Dia {i+1}',
            'rest': [],
        }
        for code in shift_codes:
            day[code] = []
        result.append(day)
    return result


def _worker_ids_en_plan(plan_json):
    """ids de los trabajadores que aparecen en el plan guardado."""
    ids = set()

    def _rec(nodo):
        if isinstance(nodo, list):
            for x in nodo:
                _rec(x)
        elif isinstance(nodo, dict):
            wid = nodo.get('workerId')
            if isinstance(wid, int):
                ids.add(wid)
            for x in nodo.values():
                if isinstance(x, (list, dict)):
                    _rec(x)

    _rec(plan_json or [])
    return ids


def _stale_info(plan):
    """¿Hay fichas de ESTA tienda tocadas después de guardar el plan?

    Devuelve {'stale': bool, 'stale_since': datetime|None, 'stale_workers': [str]}.

    Solo mira los trabajadores del ámbito del plan: si se edita una ficha de T05
    no tiene por qué avisar en T01. Cuando el plan no tiene ámbito (scope 0,
    legado) se mira toda la plantilla, que es lo que planifica.
    """
    from apps.workers.models import Worker
    from apps.dynamic_fields.models import EntityType, EntityField
    from .schedule_generator import _worker_matches_scope

    tocados = list(
        Worker.objects
        .filter(updated_at__gt=plan.updated_at)
        .order_by('-updated_at')
        .values('id', 'name', 'custom_data', 'updated_at')
    )
    if not tocados:
        return {'stale': False, 'stale_since': None, 'stale_workers': []}

    # Campo de la ficha que enlaza trabajador → tienda (el mismo que usa el
    # generador para decidir quién es elegible en un ámbito).
    # Se resuelve igual que en generate_schedule(): el campo de trabajador que
    # apunta a la entidad de ámbito. Si falla, no se filtra (mejor avisar de más
    # que romper la carga del plan).
    linking_field_key = None
    if plan.scope_entity_id:
        try:
            scope_et = EntityType.objects.filter(is_planning_scope=True).first()
            if scope_et:
                lf = EntityField.objects.filter(
                    entity_type='worker',
                    target_entity=scope_et.slug,
                    field_type__in=['entity_select', 'multi_entity_select'],
                ).first()
                if lf:
                    linking_field_key = lf.key
        except Exception:
            linking_field_key = None

    if plan.scope_entity_id and linking_field_key:
        # Quien ya figura EN el plan cuenta siempre, aunque su ficha no case con
        # el ambito: los volantes (COMUN/ETT) no tienen tienda propia y aun asi
        # se planifican aqui. Sin esto, cambiar la ficha de un volante no
        # disparaba ningun aviso — y son la mayoria del plan (31 de 43 en T01).
        planificados = _worker_ids_en_plan(plan.plan_json)
        tocados = [
            w for w in tocados
            if w['id'] in planificados
            or _worker_matches_scope(w['custom_data'] or {},
                                     linking_field_key,
                                     plan.scope_entity_id)
        ]
        if not tocados:
            return {'stale': False, 'stale_since': None, 'stale_workers': []}

    return {
        'stale': True,
        'stale_since': tocados[0]['updated_at'],
        # Nombres para poder decir "has cambiado a Campo Gomez" en vez de
        # "algo cambió". Se cortan en 5: el aviso es una pista, no un listado.
        #
        # El filtro va ANTES del corte: cortando primero, si los 5 trabajadores
        # mas recientes no tenian nombre la lista salia vacia y el front caia en
        # el generico "algun empleado" aunque hubiera fichas con nombre detras.
        'stale_workers': [w['name'] for w in tocados if w['name']][:5],
    }


def _busy_elsewhere(plan):
    """{fecha: [workerId, ...]} de quien trabaja en OTRA tienda esa semana.

    El generador ya lo tiene en cuenta (busy_map), pero el front no lo sabía: al
    diagnosticar un hueco daba por libres a los volantes que otra tienda ya tenía
    asignados, y sugería cubrir con gente imposible.
    """
    from apps.shifts.utils import shift_codes as _codes

    if not plan.scope_entity_id:
        return {}
    codes = _codes()
    ocupados = {}
    otros = WeeklyPlan.objects.filter(start_date=plan.start_date).exclude(
        scope_entity_id=plan.scope_entity_id)
    for p in otros:
        for day in (p.plan_json or []):
            fecha = day.get('date')
            if not fecha:
                continue
            for code in codes:
                for e in (day.get(code) or []):
                    if not isinstance(e, dict):
                        continue
                    try:
                        wid = int(e.get('workerId', 0) or 0)
                    except (TypeError, ValueError):
                        continue
                    if wid > 0:
                        ocupados.setdefault(fecha, set()).add(wid)
    return {f: sorted(ids) for f, ids in ocupados.items()}


class WeeklyPlanJSONSerializer(serializers.ModelSerializer):
    start = serializers.DateField(source='start_date')
    plan = serializers.JSONField(source='plan_json')
    scope_entity_id = serializers.IntegerField()

    class Meta:
        model = WeeklyPlan
        fields = ['start', 'scope_entity_id', 'plan']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not instance.plan_json:
            data['plan'] = empty_week(instance.start_date)

        # ¿Se ha tocado alguna ficha DESPUÉS de guardar este plan?
        #
        # El plan es un resultado ya calculado: si el usuario cambia el turno de
        # un trabajador para cubrir una vacante, el plan guardado sigue igual y
        # los avisos siguen saliendo. Sin esta señal el usuario no sabe si su
        # cambio sirvió (ni que hace falta regenerar).
        #
        # No regeneramos solos a propósito: regenerar reasigna la semana entera
        # y borraría los ajustes manuales. Aquí solo avisamos; regenerar lo
        # decide el usuario.
        data['stale'] = False
        data['stale_since'] = None
        if instance.plan_json and instance.updated_at:
            data.update(_stale_info(instance))

        # Quién trabaja ya en OTRA tienda cada día de esta semana. Nadie puede
        # estar en dos tiendas a la vez, así que el front lo necesita para no
        # ofrecer como "libre" a alguien que otra tienda ya tiene cogido (los
        # volantes sin tienda propia se los queda la primera que genera).
        data['busy_elsewhere'] = _busy_elsewhere(instance)
        return data


class WeeklyPlanJSONCreateSerializer(serializers.Serializer):
    start = serializers.DateField()
    plan = serializers.ListField()
    scope = serializers.IntegerField(default=0)

    def validate_plan(self, plan):
        """Rechaza asignaciones a turnos fuera de su vigencia (AC-2/AC-5).

        Para cada día del plan y cada turno con trabajador asignado, comprueba
        que el turno esté vigente en la fecha de ese día. Un turno normal (sin
        rango) pasa siempre; un turno extra caducado o aún no vigente no admite
        asignaciones nuevas, aunque siga existiendo como registro histórico.

        Solo valida los turnos que aparecen en el plan, así que un plan que no
        toca turnos caducados no se ve afectado (no rompe históricos ya guardados).
        """
        validity = {
            str(s.id): s for s in Shift.objects.all()
        }
        errors = []
        for day in plan:
            if not isinstance(day, dict):
                continue
            day_str = day.get('date')
            day_date = None
            if isinstance(day_str, str):
                try:
                    day_date = datetime.strptime(day_str, '%Y-%m-%d').date()
                except ValueError:
                    day_date = None
            if day_date is None:
                continue
            for shift_code, entries in day.items():
                if not isinstance(entries, list):
                    continue
                shift = validity.get(str(shift_code))
                if shift is None or not shift.has_validity:
                    continue  # turno normal o clave no-turno (date/dayName/rest)
                has_assignment = any(
                    isinstance(e, dict) and int(e.get('workerId', 0) or 0) > 0
                    for e in entries
                )
                if has_assignment and not shift.is_active_on(day_date):
                    errors.append(
                        f'El turno "{shift.name}" no está vigente el {day_str} '
                        f'(vigencia: {shift.valid_from or "—"} a {shift.valid_to or "—"}).'
                    )
        if errors:
            raise serializers.ValidationError(errors)
        return plan

    def create_or_update(self):
        start_date = self.validated_data['start']
        plan_data = self.validated_data['plan']
        scope_entity_id = self.validated_data.get('scope', 0)
        weekly_plan, _ = WeeklyPlan.objects.update_or_create(
            start_date=start_date,
            scope_entity_id=scope_entity_id,
            defaults={'plan_json': plan_data},
        )
        return weekly_plan
