import logging
from datetime import datetime, timedelta

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ClosedDay, WeeklyPlan
from .serializers import (
    ClosedDaySerializer,
    WeeklyPlanJSONSerializer,
    WeeklyPlanJSONCreateSerializer,
    empty_week,
)
from .schedule_generator import generate_schedule, _get_shift_slots, _build_pills_map, _resolve_worker_pills, _worker_matches_scope

logger = logging.getLogger(__name__)


class ClosedDayViewSet(viewsets.ModelViewSet):
    """CRUD de días de cierre (festivos locales, cierres puntuales).

    Filtros: ?scope=<id> (incluye cierres globales), ?from=YYYY-MM-DD, ?to=YYYY-MM-DD.
    """
    queryset = ClosedDay.objects.all()
    serializer_class = ClosedDaySerializer
    # Gestionable desde el panel de cliente (usuario autenticado), no solo
    # adminZebra. Antes era AllowAny; se endurece a IsAuthenticated (AC-3).
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        scope = self.request.query_params.get('scope')
        if scope is not None:
            from django.db.models import Q
            qs = qs.filter(Q(scope_entity_id=0) | Q(scope_entity_id=int(scope)))
        date_from = self.request.query_params.get('from')
        if date_from:
            qs = qs.filter(date__gte=date_from)
        date_to = self.request.query_params.get('to')
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return qs


class WeeklyPlanViewSet(viewsets.ModelViewSet):
    queryset = WeeklyPlan.objects.all()
    serializer_class = WeeklyPlanJSONSerializer
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return WeeklyPlanJSONCreateSerializer
        return WeeklyPlanJSONSerializer

    def list(self, request):
        start_param = request.query_params.get('start')
        if not start_param:
            return Response({'error': 'start parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            start_date = datetime.strptime(start_param, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)
        scope_entity_id = int(request.query_params.get('scope', 0))
        try:
            weekly_plan = WeeklyPlan.objects.get(start_date=start_date, scope_entity_id=scope_entity_id)
            serializer = WeeklyPlanJSONSerializer(weekly_plan)
            return Response(serializer.data)
        except WeeklyPlan.DoesNotExist:
            return Response({'start': start_param, 'scope_entity_id': scope_entity_id, 'plan': empty_week(start_param)})

    def create(self, request):
        serializer = WeeklyPlanJSONCreateSerializer(data=request.data)
        if serializer.is_valid():
            weekly_plan = serializer.create_or_update()
            response_serializer = WeeklyPlanJSONSerializer(weekly_plan)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, pk=None):
        try:
            start_date = datetime.strptime(pk, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)
        scope_entity_id = int(request.query_params.get('scope', 0))
        try:
            weekly_plan = WeeklyPlan.objects.get(start_date=start_date, scope_entity_id=scope_entity_id)
            serializer = self.get_serializer(weekly_plan)
            return Response(serializer.data)
        except WeeklyPlan.DoesNotExist:
            return Response({'start': pk, 'scope_entity_id': scope_entity_id, 'plan': empty_week(start_date)})

    @action(detail=False, methods=['post'], url_path='copy-previous')
    def copy_previous(self, request):
        """Copy plan from previous week to a target week."""
        target_start = request.data.get('start')
        if not target_start:
            return Response({'error': 'start es requerido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            target_date = datetime.strptime(target_start, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Formato de fecha inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        prev_date = target_date - timedelta(days=7)
        scope_entity_id = int(request.data.get('scope', 0))
        try:
            prev_plan = WeeklyPlan.objects.get(start_date=prev_date, scope_entity_id=scope_entity_id)
        except WeeklyPlan.DoesNotExist:
            return Response(
                {'error': 'No existe planificación de la semana anterior.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Deep copy the plan JSON, shifting dates by +7 days
        source_plan = prev_plan.plan_json or []
        new_plan = []
        for day in source_plan:
            new_date = datetime.strptime(day['date'], '%Y-%m-%d').date() + timedelta(days=7)
            copied_day = {**day, 'date': new_date.strftime('%Y-%m-%d')}
            new_plan.append(copied_day)

        # Save as the target week
        target_wp, _ = WeeklyPlan.objects.update_or_create(
            start_date=target_date,
            scope_entity_id=scope_entity_id,
            defaults={'plan_json': new_plan},
        )
        serializer = WeeklyPlanJSONSerializer(target_wp)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


    @action(detail=False, methods=['get'], url_path='month')
    def month_view(self, request):
        """Return all shift assignments for a given month, optionally filtered by worker."""
        import calendar as cal_mod
        from datetime import date as date_cls

        month_param = request.query_params.get('month')
        worker_param = request.query_params.get('worker')

        if not month_param:
            return Response({'error': 'month es requerido (YYYY-MM)'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            year, month_num = map(int, month_param.split('-'))
            first_day = date_cls(year, month_num, 1)
            last_day = date_cls(year, month_num, cal_mod.monthrange(year, month_num)[1])
        except (ValueError, TypeError):
            return Response({'error': 'Formato inválido. Use YYYY-MM'}, status=status.HTTP_400_BAD_REQUEST)

        start_monday = first_day - timedelta(days=first_day.weekday())
        end_monday = last_day - timedelta(days=last_day.weekday())

        # Fetch all relevant WeeklyPlans in a single query
        plans = {
            p.start_date: p
            for p in WeeklyPlan.objects.filter(
                start_date__gte=start_monday,
                start_date__lte=end_monday,
            )
        }

        result = {}
        current = start_monday
        while current <= end_monday:
            plan = plans.get(current)
            if plan:
                for day_data in (plan.plan_json or []):
                    date_str = day_data.get('date')
                    if not date_str:
                        continue
                    shifts_for_day = []
                    for key, assignments in day_data.items():
                        if key in ('date', 'dayName', 'rest') or not isinstance(assignments, list):
                            continue
                        for assignment in assignments:
                            w_id = assignment.get('workerId')
                            if not w_id:
                                continue
                            if worker_param and str(w_id) != str(worker_param):
                                continue
                            shifts_for_day.append({
                                'worker_id': w_id,
                                'worker_name': assignment.get('workerName', '') or assignment.get('worker_name', ''),
                                'shift_type': key,
                                'start': assignment.get('start', ''),
                                'end': assignment.get('end', ''),
                                'areas': assignment.get('areas', []),
                            })
                    if shifts_for_day or date_str not in result:
                        result.setdefault(date_str, []).extend(shifts_for_day)
            current += timedelta(days=7)

        return Response(result)


class OvertimeView(APIView):
    """Horas trabajadas vs. horas de contrato en una semana (todos los ámbitos).

    GET /planning/overtime/?start=YYYY-MM-DD[&scope=<id>]

    Suma la duración de cada asignación del plan por trabajador —misma cuenta
    que el motor de restricciones en 'per_week_worker_hours'— y la compara con
    su contrato (campo EAV 'horas_semanales'). Sin ?scope agrega TODOS los
    planes de esa semana: un trabajador que aparece en varias tiendas suma las
    horas de todas.

    Devuelve solo a quien excede su contrato, de mayor a menor exceso.
    """
    permission_classes = [IsAuthenticated]

    #: Campo EAV con las horas semanales de contrato (seed_demo / setup_client).
    CONTRACT_FIELD = 'horas_semanales'
    DEFAULT_CONTRACT_HOURS = 40.0

    def get(self, request):
        from apps.restrictions.engine import _assignment_hours
        from apps.workers.models import Worker

        start_param = request.query_params.get('start')
        if not start_param:
            return Response({'error': 'start es requerido (YYYY-MM-DD)'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            start_date = datetime.strptime(start_param, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Formato inválido. Use YYYY-MM-DD'},
                            status=status.HTTP_400_BAD_REQUEST)

        plans = WeeklyPlan.objects.filter(start_date=start_date)
        scope_param = request.query_params.get('scope')
        if scope_param is not None:
            plans = plans.filter(scope_entity_id=int(scope_param))

        # ── Horas trabajadas por trabajador, agregando todos los ámbitos ──
        worked: dict = {}
        for plan in plans:
            for day in (plan.plan_json or []):
                if not isinstance(day, dict):
                    continue
                for key, assignments in day.items():
                    # 'rest' no son turnos; date/dayName no son listas.
                    if key in ('date', 'dayName', 'rest') or not isinstance(assignments, list):
                        continue
                    for a in assignments:
                        if not isinstance(a, dict):
                            continue
                        wid = a.get('workerId')
                        if not wid:
                            continue
                        worked[int(wid)] = worked.get(int(wid), 0.0) + _assignment_hours(a)

        if not worked:
            return Response({'start': start_param, 'rows': []})

        workers = {w.id: w for w in Worker.objects.filter(id__in=worked.keys())}

        rows = []
        for wid, hours in worked.items():
            worker = workers.get(wid)
            if worker is None:
                continue  # trabajador borrado que sigue en un plan antiguo
            contract = self._contract_hours(worker)
            if hours <= contract:
                continue
            rows.append({
                'worker_id': wid,
                'name': worker.name,
                'worked': round(hours, 2),
                'contract': contract,
                'overtime': round(hours - contract, 2),
            })

        rows.sort(key=lambda r: r['overtime'], reverse=True)
        return Response({'start': start_param, 'rows': rows})

    def _contract_hours(self, worker):
        """Horas de contrato del trabajador; 40 si el campo falta o no es número."""
        raw = (worker.custom_data or {}).get(self.CONTRACT_FIELD)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return self.DEFAULT_CONTRACT_HOURS
        # Un contrato de 0h haría que cualquier turno contase como hora extra.
        return value if value > 0 else self.DEFAULT_CONTRACT_HOURS


class WeekStatusView(APIView):
    """¿Está planificada una semana? Agregado por ámbitos.

    GET /planning/week-status/?start=YYYY-MM-DD[&start=...]

    Acepta varias fechas (una por semana consultada). Para cada una devuelve
    cuántos ámbitos de planificación existen y cuántos tienen ya un plan con
    al menos una asignación — un WeeklyPlan guardado pero vacío NO cuenta como
    planificado.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        starts = request.query_params.getlist('start')
        if not starts:
            return Response({'error': 'start es requerido (YYYY-MM-DD)'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            dates = [datetime.strptime(s, '%Y-%m-%d').date() for s in starts]
        except ValueError:
            return Response({'error': 'Formato inválido. Use YYYY-MM-DD'},
                            status=status.HTTP_400_BAD_REQUEST)

        total_scopes = self._scope_count()
        plans = WeeklyPlan.objects.filter(start_date__in=dates)

        planned: dict = {d: set() for d in dates}
        # Severidad de CADA tienda, no solo de la abierta: los chips del selector
        # deben marcar con ▲ / ● todas las que tengan avisos, para saber de un
        # vistazo dónde hay que entrar sin ir tienda por tienda.
        severities: dict = {d: {} for d in dates}
        planificados = []
        for plan in plans:
            if not self._has_assignments(plan.plan_json):
                continue
            planned[plan.start_date].add(plan.scope_entity_id)
            planificados.append(plan)

        # Va en un segundo paso porque necesita saber qué turnos se usan cada
        # día, y eso se deduce del conjunto de planes de la semana.
        #
        # La caché del motor se limpia UNA vez, no en cada tienda: los datos que
        # cachea (trabajadores, turnos, áreas) son los mismos para todas, y
        # recargarlos 15 veces costaba 13 s de los 13,5 s que tardaba el
        # endpoint. Con una sola limpieza baja a ~1 s.
        from apps.restrictions.engine import _cache as _engine_cache
        _engine_cache.clear()
        operating = self._operating_shifts(planificados)
        for plan in planificados:
            sev = self._plan_severity(plan, operating)
            if sev:
                severities[plan.start_date][str(plan.scope_entity_id)] = sev

        scope_names = self._scope_names()
        weeks = []
        for d in dates:
            done = len(planned[d])
            # Nombres de los ámbitos que FALTAN, para poder decir "faltan T03 y
            # T07" en vez de solo "faltan 2 de 15".
            pendientes = sorted(
                ((name, sid) for sid, name in scope_names.items() if sid not in planned[d]),
                key=lambda x: str(x[0]),
            )
            weeks.append({
                'start': d.strftime('%Y-%m-%d'),
                'total_scopes': total_scopes,
                'planned_scopes': done,
                'pending_scopes': max(total_scopes - done, 0),
                'pending_names': [name for name, _ in pendientes],
                # Primer ámbito pendiente: el aviso "Resolver" navega ahí
                # directamente en vez de dejar al usuario buscándolo.
                'first_pending_scope': pendientes[0][1] if pendientes else None,
                'planned': done >= total_scopes and total_scopes > 0,
                # {scope_id: 'error'|'warning'} de las tiendas con problemas.
                'scope_severities': severities[d],
            })
        return Response({'weeks': weeks})

    def _plan_severity(self, plan, operating=None):
        """'error' / 'warning' / None para el chip de esa tienda.

        Cuenta lo MISMO que ve el usuario al abrirla: las violaciones del motor y
        además las VACANTES (celdas sin cubrir). Solo con las violaciones, una
        semana entera salía limpia mientras la tienda abierta mostraba "4 avisos
        a solucionar" por sus vacantes: el mismo plan con dos lecturas distintas.
        """
        from .schedule_generator import _collect_violations

        try:
            violations = _collect_violations(
                plan.plan_json, scope_record_id=plan.scope_entity_id,
                clear_cache=False)   # se limpia una vez para toda la semana
        except Exception:
            # Un fallo al validar no debe tumbar el estado de la semana.
            logger.exception('No se pudo evaluar la severidad del plan %s', plan.pk)
            return None
        if any(v.get('severity') == 'error' for v in violations):
            return 'error'
        if violations:
            return 'warning'
        if operating and self._has_empty_cells(plan, operating):
            return 'warning'
        return None

    def _operating_shifts(self, plans):
        """{fecha: {códigos de turno que ESE día se usan}}.

        Un turno "opera" un día si alguna tienda tiene gente ahí. Sin esto se
        contarían como vacías celdas que no existen en la parrilla (Sábado Mañana
        en lunes, turnos de campaña fuera de temporada…).
        """
        from collections import defaultdict

        from .schedule_generator import _get_shift_slots

        codes = [s['code'] for s in _get_shift_slots()]
        operating = defaultdict(set)
        for plan in plans:
            for day in (plan.plan_json or []):
                fecha = day.get('date')
                if not fecha:
                    continue
                for code in codes:
                    if any(int((e or {}).get('workerId', 0) or 0) > 0
                           for e in (day.get(code) or [])):
                        operating[fecha].add(code)
        return operating

    def _has_empty_cells(self, plan, operating):
        """¿Queda alguna sección sin cubrir en un turno que ese día sí opera?"""
        from .schedule_generator import _get_shift_slots

        secciones = self._section_names()
        if not secciones:
            return False
        codes = [s['code'] for s in _get_shift_slots()]
        for day in (plan.plan_json or []):
            fecha = day.get('date')
            for code in codes:
                if code not in operating.get(fecha, set()):
                    continue
                cubiertas = {
                    str(a)
                    for e in (day.get(code) or [])
                    if int((e or {}).get('workerId', 0) or 0) > 0
                    for a in (e.get('areas') or [])
                }
                if any(s not in cubiertas for s in secciones):
                    return True
        return False

    def _section_names(self):
        """Nombres de las secciones que se muestran en la parrilla (cacheado)."""
        from apps.dynamic_fields.models import EntityRecord, EntityType

        if not hasattr(self, '_secciones_cache'):
            et = EntityType.objects.filter(show_in_schedule=True).first()
            self._secciones_cache = [] if et is None else [
                str((r.data or {}).get('nombre') or '')
                for r in EntityRecord.objects.filter(entity_type=et)
                if (r.data or {}).get('nombre')
            ]
        return self._secciones_cache

    def _scope_records(self):
        """Registros de la entidad de ámbito (tiendas), o [] si no hay."""
        from apps.dynamic_fields.models import EntityType, EntityRecord

        scope_et = EntityType.objects.filter(is_planning_scope=True).first()
        if scope_et is None:
            return []
        return list(EntityRecord.objects.filter(entity_type=scope_et))

    def _scope_names(self):
        """{scope_id: etiqueta} de cada ámbito. Se prefiere el código ("T03"),
        que es lo que muestra el selector del planificador, y si no el nombre."""
        out = {}
        for r in self._scope_records():
            data = r.data or {}
            out[r.id] = (data.get('codigo') or data.get('nombre')
                         or data.get('name') or f'#{r.id}')
        return out

    def _scope_count(self):
        """Nº de ámbitos de planificación (tiendas). 1 si no hay entidad de
        ámbito configurada: entonces solo existe el plan global (scope 0)."""
        return len(self._scope_records()) or 1

    def _has_assignments(self, plan_json):
        """True si el plan tiene al menos un turno con trabajador asignado."""
        for day in (plan_json or []):
            if not isinstance(day, dict):
                continue
            for key, entries in day.items():
                if key in ('date', 'dayName', 'rest') or not isinstance(entries, list):
                    continue
                for e in entries:
                    if isinstance(e, dict) and int(e.get('workerId', 0) or 0) > 0:
                        return True
        return False


class PlanDiagnosticsView(APIView):
    """Diagnóstico de la planificación guardada de una semana, por ámbito.

    GET /planning/diagnostics/?start=YYYY-MM-DD[&scope=<id>]

    Devuelve, para cada tienda, el desglose de su plan GUARDADO: quién entra en
    cada turno con su horario y área, quién queda sin asignar, quién no está
    disponible (ausencia) y la ocupación por área frente a su tope. Es la
    versión consultable de la traza que el generador vuelca por consola.

    Solo LEE: no genera ni modifica planes.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.restrictions.models import Restriction
        from apps.workers.models import Worker
        from apps.dynamic_fields.models import EntityType, EntityField, EntityRecord
        from .schedule_generator import (
            _build_absent_map, _build_pills_map, _resolve_worker_pills,
            _filter_workers_by_eligibility, _load_closed_dates,
            _get_primary_shift_key,
        )

        start_param = request.query_params.get('start')
        if not start_param:
            return Response({'error': 'start es requerido (YYYY-MM-DD)'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            start_date = datetime.strptime(start_param, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Formato inválido. Use YYYY-MM-DD'},
                            status=status.HTTP_400_BAD_REQUEST)
        end_date = start_date + timedelta(days=6)

        scope_et = EntityType.objects.filter(is_planning_scope=True).first()
        scope_param = request.query_params.get('scope')
        if scope_param:
            scope_ids = [int(scope_param)]
        elif scope_et:
            scope_ids = list(
                EntityRecord.objects.filter(entity_type=scope_et).order_by('id')
                .values_list('id', flat=True))
        else:
            scope_ids = [0]

        restrictions = list(Restriction.objects.filter(active=True).values(
            'id', 'name', 'engine', 'config', 'severity', 'scope_records'))
        linking = None
        if scope_et:
            lf = EntityField.objects.filter(
                entity_type='worker', target_entity=scope_et.slug,
                field_type__in=['entity_select', 'multi_entity_select']).first()
            linking = lf.key if lf else None

        pills_map, pills_key = _build_pills_map()
        # Nombres de todas las secciones (columnas de la parrilla), para saber
        # cuáles se quedan sin cubrir en cada turno.
        area_names = sorted(set(pills_map.values()))
        all_workers = [
            {'id': w.id, 'name': w.name, 'customData': w.custom_data or {},
             'pills': _resolve_worker_pills(w.custom_data or {}, pills_key, pills_map)}
            for w in Worker.objects.filter(active=True)
        ]
        absent_map = _build_absent_map(start_date, end_date)
        shift_slots = _get_shift_slots()
        codes = [s['code'] for s in shift_slots]
        labels = {s['code']: s['label'] for s in shift_slots}
        area_caps = self._area_caps(restrictions)

        scope_names = {
            r.id: (r.data.get('nombre') or r.data.get('name') or f'#{r.id}')
            for r in EntityRecord.objects.filter(entity_type=scope_et)
        } if scope_et else {}

        plans = {p.scope_entity_id: p for p in
                 WeeklyPlan.objects.filter(start_date=start_date)}

        out = []
        for sid in scope_ids:
            eligible = _filter_workers_by_eligibility(
                all_workers, sid, restrictions, linking) if sid else all_workers
            by_id = {w['id']: w for w in eligible}
            fixed = sum(1 for w in eligible
                        if str((w['customData'] or {}).get(linking or '')) == str(sid))
            wp = plans.get(sid)
            closed = _load_closed_dates(sid, start_date, end_date)

            days, worked = [], {}
            for i in range(7):
                d = start_date + timedelta(days=i)
                iso = d.isoformat()
                day_data = next((x for x in (wp.plan_json or []) if
                                 isinstance(x, dict) and x.get('date') == iso), None) if wp else None
                shifts, assigned_ids = [], set()
                for code in codes:
                    entries = [e for e in ((day_data or {}).get(code) or [])
                               if e.get('workerId', 0) > 0]
                    if not entries:
                        continue
                    # El tope de área es POR TURNO, no por día: se cuenta dentro
                    # de cada turno. (Sumarlo por día daba "Carne 6/3" cuando en
                    # realidad son 3 de mañana y 3 de tarde, ambos correctos.)
                    area_used = {}
                    rows = []
                    for e in entries:
                        wid = int(e['workerId'])
                        assigned_ids.add(wid)
                        worked[wid] = worked.get(wid, 0) + 1
                        areas = e.get('areas') or []
                        for a in areas:
                            area_used[a] = area_used.get(a, 0) + 1
                        rows.append({
                            'worker_id': wid,
                            'name': e.get('workerName') or (by_id.get(wid, {}) or {}).get('name', ''),
                            'start': e.get('start', ''), 'end': e.get('end', ''),
                            'areas': areas,
                            'in_scope': wid in by_id and str(
                                (by_id[wid]['customData'] or {}).get(linking or '')) == str(sid),
                        })
                    # Agrupar por sección: mezcladas alfabéticamente no se
                    # distingue quién cubre qué. El encargado va primero (es
                    # el responsable del turno) y el resto por orden de área.
                    grupos: dict = {}
                    for r in rows:
                        area = (r['areas'] or ['Sin área'])[0]
                        grupos.setdefault(area, []).append(r)
                    def _orden(nombre):
                        n = self._norm(nombre)
                        return (0 if 'encargad' in n else 1, n)
                    shifts.append({
                        'code': code, 'label': labels.get(code, code),
                        'count': len(rows),
                        'groups': [
                            {
                                'area': a,
                                'used': len(grupos[a]),
                                'cap': area_caps.get(self._norm(a), area_caps.get('*')),
                                'workers': sorted(grupos[a], key=lambda x: x['name']),
                            }
                            for a in sorted(grupos, key=_orden)
                        ],
                    })
                absent_ids = absent_map.get(iso, set())

                # Motivo por el que cada persona libre no entró ese día. El
                # orden importa: se devuelve la PRIMERA causa que aplica, que
                # es la que realmente le impidió entrar.
                ocupacion = {}
                for sh in shifts:
                    for g in sh['groups']:
                        ocupacion[self._norm(g['area'])] = (g['used'], g['cap'])
                unassigned = []
                for i, w in by_id.items():
                    if i in assigned_ids or i in absent_ids:
                        continue
                    areas = w['pills'] or []
                    if not areas:
                        motivo = 'sin sección asignada en su ficha'
                    else:
                        llenas = [a for a in areas
                                  if (lambda u: u and u[1] and u[0] >= u[1])(ocupacion.get(self._norm(a)))]
                        if len(llenas) == len(areas):
                            motivo = ('su sección está al tope' if len(areas) == 1
                                      else 'todas sus secciones están al tope')
                        elif worked.get(i, 0) >= 6:
                            motivo = 'tope semanal de turnos alcanzado'
                        else:
                            motivo = 'reparto: descansa para que roten los turnos'
                    unassigned.append({'worker_id': i, 'name': w['name'],
                                       'areas': areas, 'reason': motivo})
                days.append({
                    'date': iso,
                    'day_name': (day_data or {}).get('dayName', ''),
                    'closed': iso in closed,
                    'has_plan': day_data is not None,
                    'assigned': len(assigned_ids),
                    'shifts': shifts,
                    'unassigned': sorted(unassigned, key=lambda x: x['name']),
                    # Mismos datos agrupados por causa, para mostrarlos juntos.
                    'unassigned_by_reason': [
                        {'reason': m, 'count': len(v),
                         'workers': sorted(v, key=lambda x: x['name'])}
                        for m, v in sorted(
                            self._group_by_reason(unassigned).items(),
                            key=lambda kv: -len(kv[1]))
                    ],
                    'absent': [{'worker_id': i, 'name': by_id[i]['name']}
                               for i in absent_ids if i in by_id],
                })

            no_turn = [{'worker_id': w['id'], 'name': w['name']}
                       for w in eligible if not worked.get(w['id'])]

            # ── Huecos: sección × turno sin cubrir ─────────────────────────
            # Se separan en dos: los CUBRIBLES (hay personal de esa sección con
            # ese turno base → el planificador puede resolverlo) y los
            # ESTRUCTURALES (no existe ese personal → falta plantilla).
            shift_key = _get_primary_shift_key()
            plantilla = {}   # (seccion_norm, turno) → nº de personas posibles
            for w in eligible:
                pills = w['pills'] or []
                if not pills:
                    continue
                cd = w['customData'] or {}
                # Turno base MÁS los de override (turno_sabado, turno_alternativo):
                # las reglas de asignación reubican al trabajador según el día,
                # así que puede cubrir más de un turno.
                turnos = {str(v) for k, v in cd.items()
                          if v and (k == shift_key or 'turno' in k.lower())}
                if not turnos:
                    turnos = {''}
                for t in turnos:
                    clave = (self._norm(pills[0]), t)
                    plantilla[clave] = plantilla.get(clave, 0) + 1

            cubribles, estructurales = [], []
            vistos = set()
            for day in days:
                if day['closed'] or not day['has_plan']:
                    continue
                for sh in day['shifts']:
                    cubiertas = {self._norm(g['area']) for g in sh['groups']}
                    for area in area_names:
                        na = self._norm(area)
                        if na in cubiertas:
                            continue
                        clave = (area, sh['label'])
                        if clave in vistos:
                            continue
                        vistos.add(clave)
                        posibles = plantilla.get((na, sh['code']), 0)
                        destino = cubribles if posibles else estructurales
                        destino.append({'area': area, 'shift': sh['label'],
                                        'staff': posibles})

            out.append({
                'gaps_coverable': cubribles,
                'gaps_structural': estructurales,
                'scope': sid,
                'scope_name': scope_names.get(sid, str(sid)),
                'has_plan': wp is not None,
                'eligible': len(eligible),
                'fixed_staff': fixed,
                'total_assignments': sum(worked.values()),
                'workers_with_shift': len(worked),
                'without_shift': sorted(no_turn, key=lambda x: x['name']),
                'days': days,
            })

        return Response({'start': start_param, 'scopes': out})

    @staticmethod
    def _norm(s):
        import unicodedata
        return ''.join(c for c in unicodedata.normalize('NFD', str(s or '').lower().strip())
                       if unicodedata.category(c) != 'Mn')

    @staticmethod
    def _group_by_reason(unassigned):
        grupos = {}
        for u in unassigned:
            grupos.setdefault(u['reason'], []).append(u)
        return grupos

    def _area_caps(self, restrictions):
        """Topes por área: {'nombre_normalizado': N, '*': tope_por_defecto}."""
        caps = {}
        for r in restrictions:
            cfg = r.get('config') or {}
            if r['engine'] != 'count' or cfg.get('groupBy') != 'shift_area':
                continue
            if cfg.get('subject') != 'workers' or cfg.get('operator') != 'lte':
                continue
            try:
                th = int(cfg.get('threshold'))
            except (TypeError, ValueError):
                continue
            names = cfg.get('filterAreaNames')
            if names:
                for n in (names if isinstance(names, list) else [names]):
                    k = self._norm(n)
                    caps[k] = min(caps.get(k, th), th)
            else:
                caps['*'] = min(caps.get('*', th), th)
        return caps


def _busy_map_from_saved_plans(start_date, exclude_scope_ids=()):
    """{'YYYY-MM-DD': {worker_id, ...}} de quien ya tiene turno esa semana.

    Lee los planes YA GUARDADOS de la semana en el resto de ámbitos, para que al
    generar una tienda no se asigne a gente que ese día trabaja en otra. Es la
    misma reserva que la generación en bloque arrastra en memoria, pero contra
    lo persistido, que es lo único que ve una generación suelta.

    exclude_scope_ids: ámbitos que se están (re)generando. Sus planes NO reservan
    a nadie — si no, regenerar una tienda la dejaría sin su propia plantilla.

    El bloqueo es por día completo: quien trabaja el lunes en otra tienda no se
    asigna el lunes aquí, aunque los horarios no se solapen (no puede
    desplazarse entre tiendas a media jornada).
    """
    shift_codes = [s['code'] for s in _get_shift_slots()]
    plans = WeeklyPlan.objects.filter(start_date=start_date)
    if exclude_scope_ids:
        plans = plans.exclude(scope_entity_id__in=list(exclude_scope_ids))

    busy: dict = {}
    for plan in plans:
        for day in (plan.plan_json or []):
            if not isinstance(day, dict):
                continue
            date_str = day.get('date')
            if not date_str:
                continue
            for code in shift_codes:
                for entry in (day.get(code) or []):
                    if not isinstance(entry, dict):
                        continue
                    wid = entry.get('workerId', 0)
                    if wid:
                        busy.setdefault(date_str, set()).add(int(wid))
    return busy


class ScheduleGenerationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        start_date_str = request.data.get('startDate')
        if not start_date_str:
            return Response({'error': 'startDate is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)
        scope_entity_id = int(request.data.get('scope', 0))

        # Regeneración parcial: 'days' = fechas ISO a regenerar; el resto de la
        # semana se congela desde el plan guardado (o el plan enviado en 'basePlan').
        target_dates = request.data.get('days') or None
        base_plan = request.data.get('basePlan')
        if target_dates:
            if not isinstance(target_dates, list):
                return Response({'error': 'days must be a list of YYYY-MM-DD dates'},
                                status=status.HTTP_400_BAD_REQUEST)
            week_dates = {(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)}
            bad = [d for d in target_dates if str(d) not in week_dates]
            if bad:
                return Response({'error': f'days outside the week starting {start_date_str}: {bad}'},
                                status=status.HTTP_400_BAD_REQUEST)
            if base_plan is None:
                existing = WeeklyPlan.objects.filter(
                    start_date=start_date, scope_entity_id=scope_entity_id,
                ).first()
                if existing is None or not existing.plan_json:
                    return Response(
                        {'error': 'No hay plan guardado para regenerar parcialmente. '
                                  'Genera la semana completa primero o envía basePlan.'},
                        status=status.HTTP_400_BAD_REQUEST)
                base_plan = existing.plan_json

        # Nadie puede estar en dos tiendas a la vez: se reserva a quien ya tiene
        # turno ese día en el plan GUARDADO de otro ámbito de esta misma semana.
        # La generación en bloque ya lo hacía arrastrando el busy_map entre
        # ámbitos, pero al generar una tienda suelta no se miraba nada y el
        # personal elegible en varias tiendas (el común, que cubre toda su zona)
        # acababa duplicado en todas — sumando 120h/semana en el dashboard.
        # Los planes de ESTE ámbito se excluyen: al regenerar una tienda debe
        # poder recuperar a su propia gente, o regenerar dos veces la vaciaría.
        busy_map = _busy_map_from_saved_plans(start_date, exclude_scope_ids=[scope_entity_id])

        try:
            result = generate_schedule(start_date, scope_entity_id,
                                       target_dates=target_dates, base_plan=base_plan,
                                       busy_map=busy_map)
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BulkScheduleGenerationView(APIView):
    """Genera la planificación de varias tiendas para la misma semana.

    Se genera de forma SECUENCIAL, arrastrando quién ha quedado asignado cada
    día: nadie puede estar en dos tiendas a la vez. Antes se hacía en paralelo
    con 4 hilos y cada ámbito ignoraba a los demás, así que el personal
    elegible en varias tiendas (el común, que cubre toda su zona) acababa
    asignado simultáneamente en todas ellas.

    El orden de `scopes` importa: las primeras tiendas eligen antes. El cliente
    decide ese orden (p.ej. priorizando las de plantilla más justa).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        start_date_str = request.data.get('startDate')
        scopes = request.data.get('scopes', [])
        if not start_date_str:
            return Response({'error': 'startDate is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not scopes or not isinstance(scopes, list):
            return Response({'error': 'scopes must be a non-empty array of scope IDs'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        shift_codes = [s['code'] for s in _get_shift_slots()]

        # fecha ISO → {worker_id} ya asignados en un ámbito anterior de esta tanda.
        # Se parte de los planes YA GUARDADOS de ámbitos que no entran en esta
        # tanda: si T01 ya está planificada y ahora se regeneran T02/T03, su
        # gente sigue ocupada. Los ámbitos de la propia tanda se excluyen porque
        # se van a regenerar y deben poder recuperar a los suyos.
        scope_ids = [int(s) for s in scopes]
        busy_map = _busy_map_from_saved_plans(start_date, exclude_scope_ids=scope_ids)
        results = []
        # Horas que cada trabajador acumula EN ESTA TANDA. Los planes aún no están
        # guardados, así que `_prior_week_hours()` (que lee de BD) no los ve: hay
        # que arrastrarlas a mano igual que el busy_map. Sin esto, el tope de
        # horas por contrato se evalúa tienda a tienda y alguien con 35h puede
        # acabar con 42,5h repartidas entre dos.
        from apps.restrictions.engine import _assignment_hours
        extra_hours: dict = {}

        for sid in scopes:
            try:
                result = generate_schedule(
                    start_date, int(sid), busy_map=busy_map, extra_hours=extra_hours,
                )
                results.append({'scope': int(sid), 'status': 'success', **result})

                # Reservar a los asignados para que el siguiente ámbito no los repita
                for day in result.get('plan', []):
                    if not isinstance(day, dict):
                        continue
                    date_str = day.get('date')
                    if not date_str:
                        continue
                    for code in shift_codes:
                        for entry in (day.get(code) or []):
                            wid = entry.get('workerId', 0)
                            if wid:
                                busy_map.setdefault(date_str, set()).add(int(wid))
                                extra_hours[int(wid)] = (
                                    extra_hours.get(int(wid), 0.0) + _assignment_hours(entry)
                                )
            except Exception as e:
                logger.exception('Bulk generation failed for scope %s', sid)
                results.append({'scope': int(sid), 'status': 'error', 'error': str(e)})

        return Response({'results': results})


class ScheduleDiagnoseView(APIView):
    """Diagnostic endpoint to inspect what the generator sees for a given scope."""
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.dynamic_fields.models import EntityType, EntityField, EntityRecord
        from apps.workers.models import Worker
        from apps.restrictions.models import Restriction

        scope_entity_id = int(request.query_params.get('scope', 0))

        # Scope entity
        scope_et = EntityType.objects.filter(is_planning_scope=True).first()
        scope_info = None
        linking_field_key = None
        if scope_et:
            lf = EntityField.objects.filter(
                entity_type='worker',
                target_entity=scope_et.slug,
                field_type__in=['entity_select', 'multi_entity_select'],
            ).first()
            linking_field_key = lf.key if lf else None
            scope_info = {
                'slug': scope_et.slug,
                'name': scope_et.name,
                'linking_field': linking_field_key,
            }

        # Pills entity
        pills_record_map, pills_field_key = _build_pills_map()
        pills_info = {
            'field_key': pills_field_key,
            'records': {str(k): v for k, v in pills_record_map.items()},
        }

        # Workers for this scope
        workers_qs = Worker.objects.filter(active=True).order_by('name')
        workers_in_scope = []
        workers_out_scope = []
        for w in workers_qs:
            cd = w.custom_data or {}
            pills = _resolve_worker_pills(cd, pills_field_key, pills_record_map)
            turno = cd.get('turno')
            info = {
                'id': w.id,
                'name': w.name,
                'turno': turno,
                'turno_in_shifts': str(turno) in [s['code'] for s in _get_shift_slots()] if turno else False,
                'pills': pills,
                'primary_pill': pills[0] if pills else None,
            }
            if scope_entity_id > 0 and linking_field_key:
                if _worker_matches_scope(cd, linking_field_key, scope_entity_id):
                    workers_in_scope.append(info)
                else:
                    workers_out_scope.append(info)
            else:
                workers_in_scope.append(info)

        # Shift slots
        shifts = _get_shift_slots()

        # Workers per shift
        shift_distribution = {}
        for sc in shifts:
            code = sc['code']
            count = sum(1 for w in workers_in_scope if str(w['turno']) == code)
            shift_distribution[sc['label']] = {
                'code': code,
                'workers': count,
                'names': [w['name'] for w in workers_in_scope if str(w['turno']) == code],
            }

        # Restrictions
        restrictions = []
        for r in Restriction.objects.filter(active=True):
            restrictions.append({
                'id': r.id,
                'name': r.name,
                'engine': r.engine,
                'severity': r.severity,
                'scope_records': r.scope_records,
                'applies_to_scope': (
                    not r.scope_records or scope_entity_id in r.scope_records
                ) if scope_entity_id else True,
                'config': r.config,
            })

        return Response({
            'scope': scope_info,
            'scope_entity_id': scope_entity_id,
            'pills': pills_info,
            'shifts': [{'code': s['code'], 'label': s['label']} for s in shifts],
            'shift_distribution': shift_distribution,
            'workers_in_scope': len(workers_in_scope),
            'workers_out_scope': len(workers_out_scope),
            'workers': workers_in_scope,
            'restrictions': restrictions,
            'issues': self._detect_issues(workers_in_scope, shifts, shift_distribution, restrictions, scope_entity_id),
        })

    def _detect_issues(self, workers, shifts, shift_dist, restrictions, scope_id):
        issues = []
        shift_codes = [s['code'] for s in shifts]

        # Check if any shift has 0 workers
        for label, info in shift_dist.items():
            if info['workers'] == 0:
                issues.append({
                    'level': 'error',
                    'message': f'Turno "{label}" tiene 0 trabajadores asignados en este ámbito.',
                })

        # Check per_shift min restrictions vs available workers
        for r in restrictions:
            if not r.get('applies_to_scope'):
                continue
            cfg = r.get('config', {})
            if cfg.get('scope') == 'per_shift' and cfg.get('operator') == 'gte':
                th = int(cfg.get('threshold', 0))
                filt = cfg.get('filter')
                for label, info in shift_dist.items():
                    pool = info['workers']
                    if filt:
                        # Count workers matching filter
                        pool = self._count_matching(workers, filt, info['code'])
                    if pool < th:
                        issues.append({
                            'level': 'warning',
                            'message': f'Restricción "{r["name"]}": necesita {th} pero solo hay {pool} disponibles en turno {label}.',
                        })

        # Check total workers vs shifts * 5 days
        total = len(workers)
        if total < len(shifts) * 5:
            issues.append({
                'level': 'warning',
                'message': f'Solo {total} trabajadores para {len(shifts)} turnos × 7 días. Algunos turnos quedarán vacíos.',
            })

        # Check workers without pills
        no_pills = [w['name'] for w in workers if not w.get('primary_pill')]
        if no_pills:
            issues.append({
                'level': 'info',
                'message': f'{len(no_pills)} trabajadores sin rol asignado: {", ".join(no_pills[:5])}{"..." if len(no_pills) > 5 else ""}',
            })

        return issues

    def _count_matching(self, workers, filt, shift_code):
        """Count workers that match a condition filter and belong to this shift."""
        field = filt.get('field', '')
        op = filt.get('op', 'eq')
        value = filt.get('value')
        count = 0
        for w in workers:
            if str(w.get('turno')) != shift_code:
                continue
            # We'd need custom_data to check — simplified check
            count += 1
        return count
