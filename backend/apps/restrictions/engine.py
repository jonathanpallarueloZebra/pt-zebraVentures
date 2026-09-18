"""
Rule engine for data-driven restriction evaluation.

Three engines interpret structured config from the database:

1. COUNT engine:
   Counts entities within a scope and checks against a threshold.
   config = {
       "subject": "workers" | "shifts" | "areas",
       "groupBy": "shift" | "shift_area" | "day_worker" | "shift_worker",
       "operator": "lte" | "gte",
       "threshold": <int>,
       "filterField": "" | "role" | "area",
       "filterValue": <role_id> | [area_names],
       "skipEmptyShifts": bool  # opt-in: shifts with zero assignments that
                                # day are not evaluated (for "gte" minimums)
   }

2. EXCLUSION engine:
   Prevents entities from coexisting in certain contexts.
   config = {
       "exclusionType": "consecutive_shifts" | "worker_pair" | "rest_conflict",
       // consecutive_shifts: "shiftA": "night", "shiftB": "morning"
       // worker_pair: "workerPairs": [[id1, id2], ...]
       // rest_conflict: (no extra config)
   }

3. MATCH engine:
   Checks that a field on one entity matches a field on another.
   config = {
       "matchType": "worker_preference" | "area_role",

       // area_role optional overrides (all have defaults, zero-config safe):
       "areaEntityType":  "area",          // slug of the EntityType used for areas
       "roleEntityType":  "role",          // slug of the EntityType used for roles
       "workerRoleField": "role",          // key inside worker.custom_data
       "areaRoleField":   "required_role"  // key inside area EntityRecord.data
   }

   With no data or no EntityRecords the loaders return empty dicts and
   produce zero violations — no crash, no false positives.
"""

import logging
from collections import defaultdict

from apps.dynamic_fields.models import EntityRecord
from apps.shifts.models import Shift
from apps.shift_days.models import ShiftDay
from apps.shifts.utils import shift_codes as _shift_codes_shared

logger = logging.getLogger(__name__)


def _get_shift_slots():
    """Load shift codes (str ids) from Shift model. Cacheado.

    Sin caché esto era una consulta a `shifts_shift` por cada restricción y cada
    plan evaluado: al validar las 15 tiendas de una semana salían 196 consultas
    (~11 s). El resto de cargadores del motor ya usan `_cache`; este se quedó
    fuera.
    """
    if 'shift_slot_codes' not in _cache:
        _cache['shift_slot_codes'] = _shift_codes_shared()
    return _cache['shift_slot_codes']


def _shift_name(slot_code):
    """Resolve a shift slot code (Shift ID) to its display name."""
    if 'shift_names' not in _cache:
        names = {}
        for s in Shift.objects.all():
            names[str(s.id)] = s.name
        _cache['shift_names'] = names
    return _cache.get('shift_names', {}).get(str(slot_code), str(slot_code))


def _get_shift_days_field():
    """Return shift active days from the ShiftDay table.

    Cached in _cache. Returns {shift_id_str: set(weekday_int)} or None for all days.
    This replaces the old EAV/catalog-based detection.
    """
    if 'shift_days_field' not in _cache:
        result = {}
        for s in Shift.objects.order_by('id'):
            weekdays = set(
                ShiftDay.objects.filter(shift=s).values_list('weekday', flat=True)
            )
            result[str(s.id)] = weekdays if weekdays else None
        _cache['shift_days_field'] = result
    return _cache['shift_days_field']


def _get_shift_active_days():
    """Build {shift_code: set(weekday_int)} from the ShiftDay table.

    None means active every day. Cached.
    """
    if 'shift_active_days' not in _cache:
        _cache['shift_active_days'] = _get_shift_days_field()
    return _cache['shift_active_days']


def _shift_active_on_date(slot_code, date_str):
    """Check if a shift slot is active on a given date (YYYY-MM-DD)."""
    active_days = _get_shift_active_days().get(str(slot_code))
    if active_days is None:
        return True  # No days configured = active every day
    try:
        import datetime as dt
        weekday = dt.date.fromisoformat(date_str).weekday()
        return weekday in active_days
    except Exception:
        return True


def evaluate(restriction, plan_data, scope_record_id=None):
    """Main entry point: evaluate a restriction against plan data."""
    engine = restriction.engine
    config = restriction.config or {}
    severity = restriction.severity or 'error'

    if engine == 'count':
        return _eval_count(restriction, config, severity, plan_data)
    elif engine == 'exclusion':
        return _eval_exclusion(restriction, config, severity, plan_data)
    elif engine == 'match':
        return _eval_match(restriction, config, severity, plan_data)
    elif engine == 'condition':
        return _eval_condition(restriction, config, severity, plan_data, scope_record_id=scope_record_id)
    elif engine == 'closed_day':
        return _eval_closed_day(restriction, severity, plan_data, scope_record_id=scope_record_id)
    else:
        logger.warning('Unknown engine "%s" for restriction %s', engine, restriction.id)
        return []


def _violation(restriction, severity, day, shift, message, placeholders=None):
    shift_label = _shift_name(shift) if shift else shift
    custom = getattr(restriction, 'message', '') or ''
    # Ensure placeholders always have the resolved shift name
    if placeholders and 'shift' in placeholders:
        placeholders['shift'] = _shift_name(placeholders['shift'])
    if custom and placeholders:
        try:
            message = custom.format_map(defaultdict(str, placeholders))
        except Exception:
            pass  # fall back to auto-generated message
    elif custom and not placeholders:
        message = custom
    return {
        'restrictionId': restriction.id,
        'restrictionName': restriction.name,
        'message': message,
        'severity': severity,
        'dayDate': day.get('date') if day else None,
        'shift': shift_label,
    }


# ---------------------------------------------------------------------------
# COUNT ENGINE
# ---------------------------------------------------------------------------
def _eval_count(restriction, config, severity, plan_data):
    subject = config.get('subject', 'workers')
    group_by = config.get('groupBy', 'shift')
    operator = config.get('operator', 'lte')
    threshold = int(config.get('threshold', 1))

    # Generic filter: any worker field (entity_select → ID, catalog_select → code)
    filter_field = config.get('filterField', '')
    filter_entity_type = config.get('filterEntityType', filter_field)
    filter_record_id = config.get('filterRecordId')  # can be int or string
    filter_value = config.get('filterValue')  # string code for catalog_select
    filter_area_names = config.get('filterAreaNames')  # list of area names
    # Opt-in: a un turno sin NINGUNA asignación ese día (la tienda no lo usa)
    # no se le exigen mínimos. Sin esto, un 'gte' dispara "0 (mín N)" en cada
    # turno operativo que el ámbito no utiliza.
    skip_empty_shifts = bool(config.get('skipEmptyShifts'))

    violations = []
    shift_slots = _get_shift_slots()

    # Determine the actual filter value to compare
    has_filter = False
    filter_match_value = None
    if filter_field and filter_record_id is not None:
        has_filter = True
        filter_match_value = filter_record_id
    elif filter_field and filter_value:
        has_filter = True
        filter_match_value = filter_value

    worker_field_map = {}
    if has_filter:
        worker_field_map = _load_worker_field_values(filter_field)

    def _worker_passes_filter(wid):
        """Return False if this worker should be excluded by the filter."""
        if not has_filter:
            return True
        worker_val = worker_field_map.get(wid)
        if worker_val is None:
            return False
        return str(worker_val) == str(filter_match_value)

    for day in plan_data:
        day_date = day.get('date', '')
        if group_by == 'shift_area':
            # Count per (shift, area)
            for shift_type in shift_slots:
                if not _shift_active_on_date(shift_type, day_date):
                    continue  # el turno no opera este día (ShiftDay)
                if skip_empty_shifts and not any(
                        a.get('workerId', 0) > 0 for a in day.get(shift_type, [])):
                    continue  # turno sin uso ese día: no se exigen mínimos
                area_counts = {}
                for assignment in day.get(shift_type, []):
                    wid = assignment.get('workerId', 0)
                    if wid <= 0:
                        continue
                    if not _worker_passes_filter(wid):
                        continue
                    for area in assignment.get('areas', []):
                        area_counts[area] = area_counts.get(area, 0) + 1
                # If filtering by specific area names, only check those
                if filter_area_names:
                    target_areas = filter_area_names if isinstance(filter_area_names, list) else [filter_area_names]
                    items = [(a, area_counts.get(a, 0)) for a in target_areas]
                else:
                    items = list(area_counts.items())
                for area, count in items:
                    if not _check_op(count, operator, threshold):
                        limit_label = 'max' if operator == 'lte' else 'min'
                        violations.append(_violation(
                            restriction, severity, day, shift_type,
                            f'{area}: {count} ({limit_label} {threshold})',
                            {'area': area, 'count': count, 'limit': threshold, 'shift': shift_type},
                        ))

        elif group_by == 'shift':
            # Count per shift
            for shift_type in shift_slots:
                if not _shift_active_on_date(shift_type, day_date):
                    continue  # el turno no opera este día (ShiftDay)
                if skip_empty_shifts and not any(
                        a.get('workerId', 0) > 0 for a in day.get(shift_type, [])):
                    continue  # turno sin uso ese día: no se exigen mínimos
                count = 0
                for assignment in day.get(shift_type, []):
                    wid = assignment.get('workerId', 0)
                    if wid <= 0:
                        continue
                    if not _worker_passes_filter(wid):
                        continue
                    count += 1
                if not _check_op(count, operator, threshold):
                    limit_label = 'max' if operator == 'lte' else 'min'
                    msg = f'{count} ({limit_label} {threshold})'
                    ph = {'count': count, 'limit': threshold, 'shift': shift_type}
                    if has_filter:
                        if filter_record_id is not None:
                            entity_label = _entity_record_label(filter_record_id, filter_entity_type)
                        else:
                            entity_label = str(filter_value)
                        msg = f'{entity_label}: {msg}'
                        ph['entity'] = entity_label
                    violations.append(_violation(restriction, severity, day, shift_type, msg, ph))

        elif group_by == 'day_worker':
            # Count per (day, worker) → e.g. max shifts per day
            worker_counts = {}
            for shift_type in shift_slots:
                for assignment in day.get(shift_type, []):
                    wid = assignment.get('workerId', 0)
                    if wid > 0:
                        if subject == 'shifts':
                            worker_counts[wid] = worker_counts.get(wid, 0) + 1
                        elif subject == 'areas':
                            worker_counts[wid] = worker_counts.get(wid, 0) + len(assignment.get('areas', []))
            for wid, count in worker_counts.items():
                if not _check_op(count, operator, threshold):
                    name = _worker_name(wid)
                    limit_label = 'max' if operator == 'lte' else 'min'
                    violations.append(_violation(
                        restriction, severity, day, 'multiple',
                        f'{name}: {count} ({limit_label} {threshold})',
                        {'worker': name, 'count': count, 'limit': threshold},
                    ))

        elif group_by == 'shift_worker':
            # Count per (shift, worker) → e.g. max areas per worker per shift
            for shift_type in shift_slots:
                if not _shift_active_on_date(shift_type, day_date):
                    continue  # el turno no opera este día (ShiftDay)
                for assignment in day.get(shift_type, []):
                    wid = assignment.get('workerId', 0)
                    if wid <= 0:
                        continue
                    if subject == 'areas':
                        count = len(assignment.get('areas', []))
                    else:
                        count = 1
                    if not _check_op(count, operator, threshold):
                        name = _worker_name(wid)
                        limit_label = 'max' if operator == 'lte' else 'min'
                        violations.append(_violation(
                            restriction, severity, day, shift_type,
                            f'{name}: {count} ({limit_label} {threshold})',
                            {'worker': name, 'count': count, 'limit': threshold, 'shift': shift_type},
                        ))

    return violations


# ---------------------------------------------------------------------------
# EXCLUSION ENGINE
# ---------------------------------------------------------------------------
def _eval_exclusion(restriction, config, severity, plan_data):
    exclusion_type = config.get('exclusionType', '')

    if exclusion_type == 'consecutive_shifts':
        return _excl_consecutive(restriction, config, severity, plan_data)
    elif exclusion_type == 'worker_pair':
        return _excl_worker_pair(restriction, config, severity, plan_data)
    elif exclusion_type == 'rest_conflict':
        return _excl_rest(restriction, severity, plan_data)
    else:
        logger.warning('Unknown exclusionType "%s" for restriction %s', exclusion_type, restriction.id)
        return []


def _excl_consecutive(restriction, config, severity, plan_data):
    """Same worker in shiftA one day and shiftB the next."""
    violations = []
    shift_a = config.get('shiftA', '')
    shift_b = config.get('shiftB', '')
    for i, day in enumerate(plan_data):
        if i >= len(plan_data) - 1:
            continue
        next_day = plan_data[i + 1]
        workers_a = set()
        for assignment in day.get(shift_a, []):
            wid = assignment.get('workerId', 0)
            if wid > 0:
                workers_a.add(wid)
        for assignment in next_day.get(shift_b, []):
            wid = assignment.get('workerId', 0)
            if wid in workers_a:
                name = _worker_name(wid)
                violations.append(_violation(
                    restriction, severity, next_day, shift_b,
                    f'{name} tiene turnos consecutivos conflictivos',
                    {'worker': name, 'shift': shift_b},
                ))
    return violations


def _excl_worker_pair(restriction, config, severity, plan_data):
    """Two specific workers should not be in the same shift."""
    violations = []
    pairs = config.get('workerPairs', [])
    if not pairs:
        return violations
    shift_slots = _get_shift_slots()
    for day in plan_data:
        for shift_type in shift_slots:
            worker_ids = set()
            for assignment in day.get(shift_type, []):
                wid = assignment.get('workerId', 0)
                if wid > 0:
                    worker_ids.add(wid)
            for pair in pairs:
                if len(pair) == 2:
                    w1, w2 = int(pair[0]), int(pair[1])
                    if w1 in worker_ids and w2 in worker_ids:
                        n1 = _worker_name(w1)
                        n2 = _worker_name(w2)
                        violations.append(_violation(
                            restriction, severity, day, shift_type,
                            f'{n1} y {n2} son incompatibles en el mismo turno',
                            {'worker1': n1, 'worker2': n2, 'shift': shift_type},
                        ))
    return violations


def _excl_rest(restriction, severity, plan_data):
    """Worker in rest should not appear in any shift."""
    violations = []
    shift_slots = _get_shift_slots()
    for day in plan_data:
        rest_ids = set()
        for r in day.get('rest', []):
            if isinstance(r, int):
                rest_ids.add(r)
            elif isinstance(r, dict) and r.get('workerId'):
                rest_ids.add(int(r['workerId']))
        for shift_type in shift_slots:
            for assignment in day.get(shift_type, []):
                wid = assignment.get('workerId', 0)
                if wid in rest_ids:
                    name = _worker_name(wid)
                    violations.append(_violation(
                        restriction, severity, day, shift_type,
                        f'{name} esta en descanso pero asignado a turno',
                        {'worker': name, 'shift': shift_type},
                    ))
    return violations


# ---------------------------------------------------------------------------
# CLOSED DAY ENGINE
# ---------------------------------------------------------------------------
def _load_closed_dates(scope_record_id=None):
    """Return set of ISO dates closed for this scope (global closures included)."""
    cache_key = f'closed_dates__{scope_record_id}'
    if cache_key not in _cache:
        try:
            from apps.planning.models import ClosedDay
            qs = ClosedDay.objects.all()
            dates = set()
            for cd in qs.values_list('date', 'scope_entity_id'):
                d, sid = cd
                if sid == 0 or (scope_record_id and sid == int(scope_record_id)):
                    dates.add(d.isoformat())
            _cache[cache_key] = dates
        except Exception:
            _cache[cache_key] = set()
    return _cache[cache_key]


def _eval_closed_day(restriction, severity, plan_data, scope_record_id=None):
    """Any assignment on a ClosedDay date (for this scope or global) is a violation."""
    violations = []
    closed = _load_closed_dates(scope_record_id)
    if not closed:
        return violations
    shift_slots = _get_shift_slots()
    for day in plan_data:
        if day.get('date') not in closed:
            continue
        for shift_type in shift_slots:
            for assignment in day.get(shift_type, []):
                wid = assignment.get('workerId', 0)
                if wid > 0:
                    name = _worker_name(wid)
                    violations.append(_violation(
                        restriction, severity, day, shift_type,
                        f'{name} asignado en día de cierre ({day.get("date")})',
                        {'worker': name, 'shift': shift_type},
                    ))
    return violations


# ---------------------------------------------------------------------------
# MATCH ENGINE
# ---------------------------------------------------------------------------
def _eval_match(restriction, config, severity, plan_data):
    match_type = config.get('matchType', '')

    if match_type == 'worker_preference':
        return _match_preference(restriction, severity, plan_data)
    elif match_type == 'area_role':
        return _match_area_role(restriction, config, severity, plan_data)
    elif match_type == 'area_membership':
        return _match_area_membership(restriction, config, severity, plan_data)
    else:
        logger.warning('Unknown matchType "%s" for restriction %s', match_type, restriction.id)
        return []


def _match_preference(restriction, severity, plan_data):
    """Warn when a worker is assigned to a non-preferred shift."""
    violations = []
    worker_prefs = _load_worker_prefs()
    if not worker_prefs:
        return violations
    shift_slots = _get_shift_slots()
    for day in plan_data:
        for shift_type in shift_slots:
            for assignment in day.get(shift_type, []):
                wid = assignment.get('workerId', 0)
                if wid > 0 and wid in worker_prefs:
                    if shift_type not in worker_prefs[wid]:
                        name = _worker_name(wid)
                        violations.append(_violation(
                            restriction, severity, day, shift_type,
                            f'{name} asignado a turno no preferido ({shift_type})',
                            {'worker': name, 'shift': shift_type},
                        ))
    return violations


def _match_area_role(restriction, config, severity, plan_data):
    """Worker's role must match the area's required role.

    Multi-value aware: the required role passes if it is among ANY of the
    worker's field values (e.g. polivalencia Cat1..4), not just the primary.
    """
    area_entity_type  = config.get('areaEntityType',  'area')
    role_entity_type  = config.get('roleEntityType',  'role')
    worker_role_field = config.get('workerRoleField', 'role')
    area_role_field   = config.get('areaRoleField',   'required_role')

    violations = []
    area_role_map = _load_area_roles(area_entity_type, area_role_field)
    if not area_role_map:
        return violations
    worker_values_map = _load_worker_field_values_all(worker_role_field)
    shift_slots = _get_shift_slots()
    for day in plan_data:
        for shift_type in shift_slots:
            for assignment in day.get(shift_type, []):
                wid = assignment.get('workerId', 0)
                if wid <= 0:
                    continue
                for area_name in assignment.get('areas', []):
                    required = area_role_map.get(area_name)
                    if required is None:
                        continue
                    actual = worker_values_map.get(wid, [])
                    if str(required) not in [str(v) for v in actual]:
                        wname = _worker_name(wid)
                        rname = _role_name(required, role_entity_type)
                        violations.append(_violation(
                            restriction, severity, day, shift_type,
                            f'{wname} no tiene rol {rname} requerido en {area_name}',
                            {'worker': wname, 'role': rname, 'area': area_name, 'shift': shift_type},
                        ))
    return violations


def _match_area_membership(restriction, config, severity, plan_data):
    """The assigned pill/area must be among the worker's own field values.

    Generic polyvalence guard: validates that every pill assigned in the plan
    belongs to the worker's multi-select field (e.g. secciones/roles Cat1..N).
    config = {
        "workerField": "<worker custom_data key>",   # required
        "areaEntityType": "<slug>",  # optional; defaults to the show_in_schedule entity
    }
    """
    worker_field = config.get('workerField', '')
    if not worker_field:
        return []
    area_slug = config.get('areaEntityType', '')
    name_to_id = _load_area_name_ids(area_slug)
    if not name_to_id:
        return []
    worker_values_map = _load_worker_field_values_all(worker_field)
    violations = []
    shift_slots = _get_shift_slots()
    for day in plan_data:
        for shift_type in shift_slots:
            for assignment in day.get(shift_type, []):
                wid = assignment.get('workerId', 0)
                if wid <= 0:
                    continue
                values = [str(v) for v in worker_values_map.get(wid, [])]
                for area_name in assignment.get('areas', []):
                    rid = name_to_id.get(area_name)
                    if rid is None:
                        continue  # pill desconocida: no juzgamos
                    if str(rid) not in values:
                        wname = _worker_name(wid)
                        violations.append(_violation(
                            restriction, severity, day, shift_type,
                            f'{wname} no tiene "{area_name}" entre sus valores de {worker_field}',
                            {'worker': wname, 'area': area_name, 'shift': shift_type},
                        ))
    return violations


# ---------------------------------------------------------------------------
# Helper data loaders (cached per function call scope)
# ---------------------------------------------------------------------------
_cache = {}


def _load_worker_field_values(field_key='role'):
    """
    Return {worker_id: primary_value} for the given custom_data key.
    Handles entity_select (int), multi_entity_select (list / list-of-priority-dicts),
    catalog_select (str) and multi_catalog_select (list of str).
    For multi-value fields the FIRST (highest-priority) value is used.
    """
    cache_key = f'worker_field__{field_key}'
    if cache_key not in _cache:
        try:
            from apps.workers.models import Worker
            result = {}
            for w in Worker.objects.filter(active=True):
                raw = w.custom_data.get(field_key)
                if raw is None:
                    continue
                values = _extract_field_values(w.custom_data, field_key)
                if values:
                    result[w.id] = values[0]  # primary value
            _cache[cache_key] = result
        except Exception:
            _cache[cache_key] = {}
    return _cache[cache_key]


# Keep old name as alias for match engine callers
_load_worker_roles = _load_worker_field_values


def _load_worker_field_values_all(field_key):
    """Return {worker_id: [all values]} for the given custom_data key.

    Multi-value counterpart of _load_worker_field_values: keeps EVERY value
    (e.g. all polyvalence sections), not just the primary one.
    """
    cache_key = f'worker_field_all__{field_key}'
    if cache_key not in _cache:
        try:
            from apps.workers.models import Worker
            result = {}
            for w in Worker.objects.filter(active=True):
                values = _extract_field_values(w.custom_data or {}, field_key)
                if values:
                    result[w.id] = values
            _cache[cache_key] = result
        except Exception:
            _cache[cache_key] = {}
    return _cache[cache_key]


def _load_area_name_ids(area_slug=''):
    """Return {display_name: record_id} for an area/pills entity type.

    If area_slug is empty, uses the EntityType flagged show_in_schedule=True
    (the same source the schedule generator uses for pills).
    """
    cache_key = f'area_name_ids__{area_slug}'
    if cache_key not in _cache:
        try:
            from apps.dynamic_fields.models import EntityType
            et = None
            if area_slug:
                et = EntityType.objects.filter(slug=area_slug).first()
            if et is None:
                et = EntityType.objects.filter(show_in_schedule=True).first()
            result = {}
            if et is not None:
                display = et.display_field or 'nombre'
                for r in EntityRecord.objects.filter(entity_type=et):
                    name = r.data.get(display) or r.data.get('nombre') or r.data.get('name')
                    if name:
                        result[str(name)] = r.id
            _cache[cache_key] = result
        except Exception:
            _cache[cache_key] = {}
    return _cache[cache_key]


def _load_worker_prefs():
    if 'worker_prefs' not in _cache:
        try:
            from apps.workers.models import WorkerPreference
            # Una sola consulta a la tabla de preferencias, agrupando en Python.
            #
            # Antes se iteraba sobre Worker con prefetch_related y dentro se
            # hacía `w.preferences.values_list(...)`: values_list NO usa el
            # prefetch, así que lanzaba una consulta POR TRABAJADOR (272) y este
            # cargador solo se llevaba 6,5 s de los 17 s de una generación.
            prefs = {}
            for wid, shift in WorkerPreference.objects.filter(
                    worker__active=True).values_list('worker_id', 'shift_type'):
                if shift:
                    prefs.setdefault(wid, set()).add(shift)
            _cache['worker_prefs'] = prefs
        except Exception:
            _cache['worker_prefs'] = {}
    return _cache['worker_prefs']


def _load_area_roles(area_entity_type='area', area_role_field='required_role'):
    cache_key = f'area_roles__{area_entity_type}__{area_role_field}'
    if cache_key not in _cache:
        try:
            result = {}
            for a in EntityRecord.objects.filter(entity_type=area_entity_type):
                name = a.data.get('nombre') or a.data.get('name', '')
                req_role = a.data.get(area_role_field)
                if name and req_role:
                    result[name] = req_role
                    short = a.data.get('short_name', '')
                    if short:
                        result[short] = req_role
            _cache[cache_key] = result
        except Exception:
            _cache[cache_key] = {}
    return _cache[cache_key]


def _load_worker_names():
    if 'worker_names' not in _cache:
        try:
            from apps.workers.models import Worker
            _cache['worker_names'] = {w.id: w.name for w in Worker.objects.all()}
        except Exception:
            _cache['worker_names'] = {}
    return _cache['worker_names']


def _load_role_names(role_entity_type='role'):
    cache_key = f'role_names__{role_entity_type}'
    if cache_key not in _cache:
        try:
            _cache[cache_key] = {
                r.id: r.data.get('nombre') or r.data.get('name', str(r.id))
                for r in EntityRecord.objects.filter(entity_type=role_entity_type)
            }
        except Exception:
            _cache[cache_key] = {}
    return _cache[cache_key]


def _entity_record_label(record_id, entity_type='role'):
    """Return the display label of an EntityRecord by ID."""
    if record_id is None:
        return '?'
    names = _load_role_names(entity_type)
    return names.get(int(record_id), str(record_id))


def _worker_name(wid):
    names = _load_worker_names()
    return names.get(wid, str(wid))


def _role_name(role_id, role_entity_type='role'):
    if role_id is None:
        return '?'
    names = _load_role_names(role_entity_type)
    return names.get(int(role_id), str(role_id))


def _to_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _check_op(value, operator, threshold):
    if operator == 'lte':
        return value <= threshold
    elif operator == 'gte':
        return value >= threshold
    elif operator == 'eq':
        return value == threshold
    elif operator == 'neq':
        return value != threshold
    return True


def clear_cache():
    """Deprecated: usar invalidate_cache().

    Antes se llamaba al inicio de CADA validación, lo que forzaba a recargar
    toda la BD (trabajadores, áreas, campos, preferencias, catálogos) en cada
    movimiento del planificador → validación lenta. Ahora la caché persiste
    entre validaciones y se invalida por señales cuando cambian los datos base
    (ver signals.py). Se mantiene como alias para no romper llamadas externas.
    """
    invalidate_cache()


def invalidate_cache():
    """Vaciar la caché en memoria del engine.

    La disparan las señales post_save/post_delete de los modelos de los que
    depende la validación (Worker, WorkerPreference, EntityRecord/EntityType,
    Shift/ShiftDay, ClosedDay, Restriction). Así la siguiente validación
    recarga datos frescos sin servir información obsoleta, pero mientras nada
    cambia la caché se reutiliza y la validación es rápida.
    """
    _cache.clear()


# ---------------------------------------------------------------------------
# CONDITION ENGINE — general-purpose rule engine
# ---------------------------------------------------------------------------
# config = {
#   "scope": "per_shift" | "per_day" | "per_day_worker" | "per_week_worker"
#           | "per_shift_worker" | "per_shift_area",
#   "dayOfWeek": null | 0-6,   # Monday=0, Sunday=6. Only check that weekday.
#   "filter": <condition_node> | null,   # filter which workers count
#   "operator": "lte" | "gte" | "eq",
#   "threshold": <int>,
#   "scopeEntityType": "<slug>",  # required for per_shift_area
# }
#
# condition_node =
#   { "and": [<node>, ...] }
#   { "or":  [<node>, ...] }
#   { "not": <node> }
#   { "field": "<worker_custom_data_key>",
#     "op": "eq" | "neq" | "in" | "nin" | "gt" | "gte" | "lt" | "lte",
#     "value": <any>  }
#
# Field values are extracted correctly for:
#   entity_select         → int ID
#   multi_entity_select   → list of IDs or list of {entity_id: N, priority: N}
#   catalog_select        → string code
#   multi_catalog_select  → list of string codes
#   boolean / number / text → raw value
# ---------------------------------------------------------------------------

def _extract_field_values(custom_data, field_key):
    """Return a flat list of all scalar values for field_key from custom_data."""
    val = custom_data.get(field_key)
    if val is None:
        return []
    if isinstance(val, list):
        result = []
        for item in val:
            if isinstance(item, dict):
                # Priority-dict formats:
                # {'entity_id': N, 'priority': N}  OR  {'id': N}  OR  {'value': N, 'priority': N}
                for k in ('entity_id', 'id', 'value'):
                    if k in item:
                        result.append(item[k])
                        break
                else:
                    # Unknown dict shape — skip priority-like keys to avoid false matches
                    for v in item.values():
                        if not isinstance(v, (bool, type(None))):
                            result.append(v)
                            break
            else:
                result.append(item)
        return result
    return [val]


def _assignment_hours(assignment):
    """Duration in hours of a plan assignment from its 'start'/'end' HH:MM strings.

    Overnight shifts (end < start) wrap past midnight. Returns 0.0 when the
    times are missing or unparseable (never guesses).
    """
    try:
        start = str(assignment.get('start', '') or '')
        end = str(assignment.get('end', '') or '')
        sh, sm = (int(x) for x in start.split(':')[:2])
        eh, em = (int(x) for x in end.split(':')[:2])
        minutes = (eh * 60 + em) - (sh * 60 + sm)
        if minutes < 0:
            minutes += 24 * 60
        return minutes / 60.0
    except (ValueError, TypeError, AttributeError):
        return 0.0


# Map weekday index to Spanish day names used in select fields
_WEEKDAY_NAMES = {
    0: 'lunes', 1: 'martes', 2: 'miércoles', 3: 'jueves',
    4: 'viernes', 5: 'sábado', 6: 'domingo',
}


def _eval_condition_node(node, custom_data, day_context=None):
    """Recursively evaluate a condition node against a worker's custom_data.

    day_context: optional dict with 'weekday' (0-6) and 'date' (ISO str).
    """
    if not isinstance(node, dict):
        return True

    if 'and' in node:
        return all(_eval_condition_node(c, custom_data, day_context) for c in node['and'])
    if 'or' in node:
        return any(_eval_condition_node(c, custom_data, day_context) for c in node['or'])
    if 'not' in node:
        return not _eval_condition_node(node['not'], custom_data, day_context)

    field = node.get('field')
    op = node.get('op', 'eq')
    target = node.get('value')

    if not field:
        return True

    values = _extract_field_values(custom_data, field)
    if not values:
        # Field absent: only 'neq' and 'nin' pass when nothing is present
        return op in ('neq', 'nin')

    str_values = [str(v) for v in values]

    # day_match: checks if the field's value matches the current day's weekday name
    if op == 'day_match':
        if not day_context or 'weekday' not in day_context:
            return False
        current_day_name = _WEEKDAY_NAMES.get(day_context['weekday'], '')
        return any(v.lower().strip() == current_day_name for v in str_values)

    if op == 'eq':
        t = str(target).lower()
        return t in [v.lower() for v in str_values]
    if op == 'neq':
        t = str(target).lower()
        return t not in [v.lower() for v in str_values]
    if op == 'in':
        targets = [str(t) for t in (target if isinstance(target, list) else [target])]
        return any(v in targets for v in str_values)
    if op == 'nin':
        targets = [str(t) for t in (target if isinstance(target, list) else [target])]
        return not any(v in targets for v in str_values)
    if op in ('gt', 'gte', 'lt', 'lte'):
        try:
            num_vals = [float(v) for v in str_values]
            num_target = float(target)
            if op == 'gt':  return any(v > num_target for v in num_vals)
            if op == 'gte': return any(v >= num_target for v in num_vals)
            if op == 'lt':  return any(v < num_target for v in num_vals)
            if op == 'lte': return any(v <= num_target for v in num_vals)
        except (TypeError, ValueError):
            return False
    return False


def _load_all_worker_data():
    """Return {worker_id: custom_data} for all active workers."""
    if 'all_worker_data' not in _cache:
        try:
            from apps.workers.models import Worker
            _cache['all_worker_data'] = {
                w.id: (w.custom_data or {})
                for w in Worker.objects.filter(active=True)
            }
        except Exception:
            _cache['all_worker_data'] = {}
    return _cache['all_worker_data']


def _load_scope_record_data(scope_record_id):
    """Load the data dict for a scope (planning entity) record from EAV."""
    cache_key = f'scope_record_{scope_record_id}'
    if cache_key not in _cache:
        _cache[cache_key] = {}
        if scope_record_id:
            try:
                from apps.dynamic_fields.models import EntityRecord
                rec = EntityRecord.objects.get(pk=scope_record_id)
                _cache[cache_key] = rec.data or {}
            except Exception:
                pass
    return _cache[cache_key]


def normalize_scope_match_rules(scope_match):
    """Normalize a scopeMatch config to a list of rule dicts.

    Supports legacy {workerField, scopeField} and the current {rules: [...]} shape.
    """
    rules = scope_match.get('rules')
    if rules is None:
        wf = scope_match.get('workerField', '')
        sf = scope_match.get('scopeField', '')
        rules = [{'workerField': wf, 'scopeField': sf}] if wf and sf else []
    return rules


def _effective_threshold(worker_data, threshold_field, threshold, offset=0.0):
    """Límite de este trabajador: su campo EAV + offset, o el umbral plano.

    threshold_field (p. ej. 'horas_semanales') da el límite propio de cada uno y
    offset es el margen que la empresa concede sobre él (contrato + 5h extra).
    El margen SOLO se suma al valor del trabajador: si el campo está vacío o no
    es un número se cae al umbral plano tal cual, que ya representa el tope por
    defecto y no debe inflarse.
    """
    if threshold_field:
        raw = worker_data.get(threshold_field)
        if raw not in (None, ''):
            try:
                # Se acepta la coma decimal: un campo 'float' editado a mano
                # puede llegar como "37,5" y con float() directo reventaría,
                # cayendo silenciosamente al umbral plano.
                if isinstance(raw, str):
                    raw = raw.replace(',', '.')
                return float(raw) + offset
            except (ValueError, TypeError):
                pass
    return threshold


def worker_passes_scope_match(worker_data, scope_record_id, scope_data, rules):
    """True if the worker satisfies the scopeMatch rule-set (passes if ANY rule matches).

    Each rule: {workerField, matchType: 'field'|'id'|'attr', scopeField?, requireField?, requireValue?}
      - 'id'   : the scope record id is among the worker field values.
      - 'field': scope_data[scopeField] is among the worker field values.
      - 'attr' : worker merely carries the field (no scope gate); combine with requireField.
    requireField/requireValue add an extra worker-field condition.
    This is the single source of truth for scope eligibility, shared by the
    restriction validator (_eval_condition) and the schedule generator's pre-filter.
    """
    for rule in rules:
        wf = rule.get('workerField', '')
        if not wf:
            continue
        w_values = _extract_field_values(worker_data, wf)
        if not w_values:
            continue
        match_type = rule.get('matchType', 'field')
        if match_type == 'id':
            ok = str(scope_record_id) in [str(v) for v in w_values]
        elif match_type == 'attr':
            ok = True
        else:
            sf = rule.get('scopeField', '')
            sv = scope_data.get(sf)
            ok = sv is not None and str(sv) in [str(v) for v in w_values]
        if not ok:
            continue
        req_field = rule.get('requireField')
        if req_field:
            req_val = rule.get('requireValue')
            actual = _extract_field_values(worker_data, req_field)
            if not actual or str(req_val).lower() not in [str(v).lower() for v in actual]:
                continue
        return True
    return False


def _eval_condition(restriction, config, severity, plan_data, scope_record_id=None):
    import datetime as dt

    scope = config.get('scope', 'per_shift')
    day_of_week = config.get('dayOfWeek')          # int 0-6 or None
    filter_node = config.get('filter')             # condition node or None
    operator    = config.get('operator', 'lte')
    threshold   = int(config.get('threshold', 1))
    threshold_field = config.get('thresholdField', '')  # worker EAV field used as per-worker threshold
    # Margen sobre el umbral por trabajador: el límite real es
    # thresholdField + thresholdOffset (p. ej. contrato + 5h extra). Vive en la
    # restricción, no en la ficha: es política de empresa, igual para todos, y
    # así se cambia en un sitio en vez de en cada trabajador. Sin
    # thresholdField no aplica (el umbral plano ya es el límite).
    try:
        threshold_offset = float(config.get('thresholdOffset') or 0)
    except (TypeError, ValueError):
        threshold_offset = 0.0
    scope_match = config.get('scopeMatch')         # {workerField, scopeField}

    worker_data_map = _load_all_worker_data()
    shift_slots = _get_shift_slots()
    violations  = []

    # ── scopeMatch: compare worker fields against scope record ─────────
    if scope_match and scope_record_id:
        rules = normalize_scope_match_rules(scope_match)
        if rules:
            scope_data = _load_scope_record_data(scope_record_id)
            for day in plan_data:
                for slot in shift_slots:
                    for a in day.get(slot, []):
                        wid = a.get('workerId', 0)
                        if wid <= 0:
                            continue
                        w_data = worker_data_map.get(wid, {})
                        if not worker_passes_scope_match(w_data, scope_record_id, scope_data, rules):
                            name = _worker_name(wid)
                            violations.append(_violation(
                                restriction, severity, day, slot,
                                f'{name} no cumple las condiciones de ámbito',
                                {'worker': name, 'shift': slot},
                            ))
            return violations

    _day_context = {}  # mutable, updated per-day in loop

    def passes(wid):
        if not filter_node:
            return True
        return _eval_condition_node(filter_node, worker_data_map.get(wid, {}), _day_context)

    # ── Weekly scope: accumulate across all days ───────────────────────────
    if scope == 'per_week_worker':
        worker_counts = {}
        for day in plan_data:
            try:
                _day_context['weekday'] = dt.date.fromisoformat(day['date']).weekday()
                _day_context['date'] = day['date']
            except Exception:
                pass
            for slot in shift_slots:
                for a in day.get(slot, []):
                    wid = a.get('workerId', 0)
                    if wid > 0 and passes(wid):
                        worker_counts[wid] = worker_counts.get(wid, 0) + 1
        for wid, count in worker_counts.items():
            # Support per-worker dynamic threshold from an EAV field (e.g. horas_semanales)
            effective_threshold = int(_effective_threshold(
                worker_data_map.get(wid, {}), threshold_field, threshold, threshold_offset))
            if not _check_op(count, operator, effective_threshold):
                name = _worker_name(wid)
                limit_label = 'máx' if operator == 'lte' else 'mín'
                violations.append(_violation(
                    restriction, severity, None, None,
                    f'{name}: {count} turnos en la semana ({limit_label} {effective_threshold})',
                    {'worker': name, 'count': count, 'limit': effective_threshold},
                ))
        return violations

    # ── Weekly HOURS per worker: sums assignment durations (contracts in hours) ─
    if scope == 'per_week_worker_hours':
        worker_hours: dict = {}
        for day in plan_data:
            try:
                _day_context['weekday'] = dt.date.fromisoformat(day['date']).weekday()
                _day_context['date'] = day['date']
            except Exception:
                pass
            for slot in shift_slots:
                for a in day.get(slot, []):
                    wid = a.get('workerId', 0)
                    if wid > 0 and passes(wid):
                        worker_hours[wid] = worker_hours.get(wid, 0.0) + _assignment_hours(a)
        for wid, hours in worker_hours.items():
            effective_threshold = _effective_threshold(
                worker_data_map.get(wid, {}), threshold_field, threshold, threshold_offset)
            if not _check_op(hours, operator, effective_threshold):
                name = _worker_name(wid)
                limit_label = 'máx' if operator == 'lte' else 'mín'
                hours_str = f'{hours:g}'
                limit_str = f'{effective_threshold:g}'
                violations.append(_violation(
                    restriction, severity, None, None,
                    f'{name}: {hours_str}h en la semana ({limit_label} {limit_str}h)',
                    {'worker': name, 'count': hours_str, 'limit': limit_str},
                ))
        return violations

    # ── Weekly per (worker, shift_type): e.g. max 3 night shifts per week ─
    if scope == 'per_week_worker_shift':
        # {wid: {slot: count}}
        worker_slot_counts: dict = {}
        target_slot = config.get('targetShift')  # None = all slots separately
        for day in plan_data:
            slots_to_check = [target_slot] if target_slot else shift_slots
            for slot in slots_to_check:
                for a in day.get(slot, []):
                    wid = a.get('workerId', 0)
                    if wid > 0 and passes(wid):
                        if wid not in worker_slot_counts:
                            worker_slot_counts[wid] = {}
                        worker_slot_counts[wid][slot] = worker_slot_counts[wid].get(slot, 0) + 1
        for wid, slot_map in worker_slot_counts.items():
            for slot, count in slot_map.items():
                if not _check_op(count, operator, threshold):
                    name = _worker_name(wid)
                    limit_label = 'máx' if operator == 'lte' else 'mín'
                    violations.append(_violation(
                        restriction, severity, None, slot,
                        f'{name}: {count} veces turno {slot} en la semana ({limit_label} {threshold})',
                        {'worker': name, 'count': count, 'limit': threshold, 'shift': slot},
                    ))
        return violations

    # ── Day-by-day scopes ─────────────────────────────────────────────────
    for day in plan_data:
        # Update day context for day_match operator
        try:
            _day_context['weekday'] = dt.date.fromisoformat(day['date']).weekday()
            _day_context['date'] = day['date']
        except Exception:
            _day_context.clear()

        # Optional day-of-week filter
        if day_of_week is not None:
            try:
                actual_dow = dt.date.fromisoformat(day['date']).weekday()
                if actual_dow != int(day_of_week):
                    continue
            except Exception:
                pass

        if scope == 'per_shift':
            day_date = day.get('date', '')
            for slot in shift_slots:
                if not _shift_active_on_date(slot, day_date):
                    continue
                count = sum(
                    1 for a in day.get(slot, [])
                    if a.get('workerId', 0) > 0 and passes(a['workerId'])
                )
                if not _check_op(count, operator, threshold):
                    limit_label = 'máx' if operator == 'lte' else 'mín'
                    violations.append(_violation(
                        restriction, severity, day, slot,
                        f'{count} ({limit_label} {threshold})',
                        {'count': count, 'limit': threshold, 'shift': slot},
                    ))

        elif scope == 'per_day':
            seen = set()
            for slot in shift_slots:
                for a in day.get(slot, []):
                    wid = a.get('workerId', 0)
                    if wid > 0 and passes(wid):
                        seen.add(wid)
            count = len(seen)
            if not _check_op(count, operator, threshold):
                limit_label = 'máx' if operator == 'lte' else 'mín'
                violations.append(_violation(
                    restriction, severity, day, None,
                    f'{count} trabajadores en el día ({limit_label} {threshold})',
                    {'count': count, 'limit': threshold},
                ))

        elif scope == 'per_day_worker':
            worker_counts = {}
            for slot in shift_slots:
                for a in day.get(slot, []):
                    wid = a.get('workerId', 0)
                    if wid > 0 and passes(wid):
                        worker_counts[wid] = worker_counts.get(wid, 0) + 1
            for wid, count in worker_counts.items():
                if not _check_op(count, operator, threshold):
                    name = _worker_name(wid)
                    limit_label = 'máx' if operator == 'lte' else 'mín'
                    violations.append(_violation(
                        restriction, severity, day, None,
                        f'{name}: {count} turnos hoy ({limit_label} {threshold})',
                        {'worker': name, 'count': count, 'limit': threshold},
                    ))

        elif scope == 'per_shift_worker':
            day_date = day.get('date', '')
            for slot in shift_slots:
                if not _shift_active_on_date(slot, day_date):
                    continue
                for a in day.get(slot, []):
                    wid = a.get('workerId', 0)
                    if wid <= 0 or not passes(wid):
                        continue
                    # Count areas or just presence (1)
                    count = len(a.get('areas', [])) if a.get('areas') else 1
                    if not _check_op(count, operator, threshold):
                        name = _worker_name(wid)
                        limit_label = 'máx' if operator == 'lte' else 'mín'
                        violations.append(_violation(
                            restriction, severity, day, slot,
                            f'{name}: {count} ({limit_label} {threshold})',
                            {'worker': name, 'count': count, 'limit': threshold, 'shift': slot},
                        ))

        elif scope == 'per_shift_area':
            day_date = day.get('date', '')
            for slot in shift_slots:
                if not _shift_active_on_date(slot, day_date):
                    continue
                area_counts = {}
                for a in day.get(slot, []):
                    wid = a.get('workerId', 0)
                    if wid <= 0 or not passes(wid):
                        continue
                    for area in a.get('areas', []):
                        area_counts[area] = area_counts.get(area, 0) + 1
                for area, count in area_counts.items():
                    if not _check_op(count, operator, threshold):
                        limit_label = 'máx' if operator == 'lte' else 'mín'
                        violations.append(_violation(
                            restriction, severity, day, slot,
                            f'{area}: {count} ({limit_label} {threshold})',
                            {'area': area, 'count': count, 'limit': threshold, 'shift': slot},
                        ))

    return violations
