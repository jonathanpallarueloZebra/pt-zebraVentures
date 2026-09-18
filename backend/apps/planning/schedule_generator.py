import json
import logging
import os
import threading
from datetime import timedelta

from apps.workers.models import Worker
from apps.shifts.models import Shift
from apps.dynamic_fields.models import EntityRecord, EntityType
from apps.restrictions.models import Restriction
from apps.absences.models import AbsenceRequest
from apps.rest_days.models import RestDay
from apps.shift_days.models import ShiftDay, WEEKDAY_CHOICES
from apps.shifts.utils import load_shift_slots as _load_shift_slots, day_names as _shared_day_names
# Cálculo de horas compartido con el motor de restricciones: si el generador
# reimplementase la duración de un turno o el umbral efectivo, ambos se
# desincronizarían y un plan "válido" al generar saldría en rojo al validar.
from apps.restrictions.engine import _assignment_hours, _effective_threshold

logger = logging.getLogger(__name__)

# Thread-local cache cleared at the start of each generate_schedule call
_thread_local = threading.local()


def _get_gen_cache():
    if not hasattr(_thread_local, 'gen_cache'):
        _thread_local.gen_cache = {}
    return _thread_local.gen_cache


def _get_day_names():
    """Return day-of-week labels from the constant WEEKDAY_CHOICES."""
    return _shared_day_names()


def _get_shift_slots():
    """Load root shift slot definitions from Shift model (excludes variants). Cached per generation."""
    cache = _get_gen_cache()
    if 'shift_slots' in cache:
        return cache['shift_slots']
    result = _load_shift_slots()
    cache['shift_slots'] = result
    return result


def _get_shift_defaults():
    """Build {code: {start, end}} from catalog shift_slot attributes. Cached per generation."""
    cache = _get_gen_cache()
    if 'shift_defaults' in cache:
        return cache['shift_defaults']
    slots = _get_shift_slots()
    defaults = {}
    for s in slots:
        attrs = s.get('attributes', {})
        defaults[s['code']] = {
            'start': attrs.get('start_time', '00:00'),
            'end': attrs.get('end_time', '00:00'),
        }
    cache['shift_defaults'] = defaults
    return defaults


def _get_shift_active_days():
    """Build {shift_code: set(weekday_int)} from the ShiftDay table. Cached per generation.

    If a root shift has no ShiftDay rows, it's considered active every day (None).
    """
    cache = _get_gen_cache()
    if 'shift_active_days' in cache:
        return cache['shift_active_days']
    result = {}
    for s in Shift.objects.order_by('id'):
        weekdays = set(
            ShiftDay.objects.filter(shift=s).values_list('weekday', flat=True)
        )
        result[str(s.id)] = weekdays if weekdays else None  # None = all days
    cache['shift_active_days'] = result
    return result


def _get_shift_validity():
    """Build {shift_code: (valid_from, valid_to)} from Shift. Cached per generation.

    Un turno sin rango de vigencia (turno "normal") tiene (None, None) y está
    operativo cualquier fecha. Los turnos "extra" solo operan dentro de su
    rango (extremos inclusivos) — ver Shift.is_active_on.
    """
    cache = _get_gen_cache()
    if 'shift_validity' in cache:
        return cache['shift_validity']
    result = {
        str(s.id): (s.valid_from, s.valid_to)
        for s in Shift.objects.order_by('id')
    }
    cache['shift_validity'] = result
    return result


def _shift_operates_on(shift_code, day, active_days_map, validity_map):
    """¿El turno opera en la fecha `day` (weekday activo Y dentro de vigencia)?

    Combina las dos condiciones que hacen operativo un turno un día concreto:
    - día de la semana activo (ShiftDay); None = todos los días.
    - fecha dentro del rango de vigencia (valid_from/valid_to); (None, None) =
      siempre vigente. Así conviven turnos normales y extra sin pisarse (AC-4).
    """
    active_days = active_days_map.get(shift_code)
    if active_days is not None and day.weekday() not in active_days:
        return False
    valid_from, valid_to = validity_map.get(shift_code, (None, None))
    if valid_from is not None and day < valid_from:
        return False
    if valid_to is not None and day > valid_to:
        return False
    return True


def empty_week(start_date):
    day_names = _get_day_names()
    shift_codes = [s['code'] for s in _get_shift_slots()]
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


def normalize_week(week, start_date):
    if not isinstance(week, list):
        week = []
    base = empty_week(start_date)
    shift_codes = [s['code'] for s in _get_shift_slots()]
    shift_defaults = _get_shift_defaults()
    day_names = _get_day_names()

    if len(week) < 7:
        week.extend(base[len(week):])
    elif len(week) > 7:
        week = week[:7]

    normalized = []
    for idx, day in enumerate(week):
        nd = {
            'date': day.get('date', base[idx]['date']),
            'dayName': day.get('dayName', day_names[idx] if idx < len(day_names) else f'Dia {idx+1}'),
        }
        raw_rest = day.get('rest', [])
        rest_ids = []
        for r in (raw_rest if isinstance(raw_rest, list) else []):
            if isinstance(r, int):
                rest_ids.append(r)
            elif isinstance(r, dict) and r.get('workerId'):
                try:
                    rest_ids.append(int(r['workerId']))
                except (ValueError, TypeError):
                    pass
        nd['rest'] = rest_ids

        for shift_code in shift_codes:
            entries = day.get(shift_code, []) or []
            new_entries = []
            defaults = shift_defaults.get(shift_code, {'start': '00:00', 'end': '00:00'})
            for e in entries:
                wid = int(e.get('workerId') or e.get('worker_id') or e.get('id') or 0)
                new_entries.append({
                    'workerId': wid,
                    'workerName': e.get('workerName') or e.get('worker_name') or '',
                    'start': e.get('start') or defaults['start'],
                    'end': e.get('end') or defaults['end'],
                    'areas': [str(a) for a in (e.get('areas') or []) if a is not None],
                })
            nd[shift_code] = new_entries
        normalized.append(nd)
    return normalized


def _load_closed_dates(scope_entity_id, start_date, end_date):
    """ISO dates within [start_date, end_date] closed for this scope (or globally)."""
    try:
        from apps.planning.models import ClosedDay
        closed = set()
        for d, sid in ClosedDay.objects.filter(
            date__gte=start_date, date__lte=end_date,
        ).values_list('date', 'scope_entity_id'):
            if sid == 0 or (scope_entity_id and sid == int(scope_entity_id)):
                closed.add(d.isoformat())
        return closed
    except Exception as e:
        logger.warning('Could not load closed days: %s', e)
        return set()


def _apply_closed_days(week, closed_dates, skip_indices=None):
    """Clear assignments on closed dates (workers move to rest). Frozen days untouched."""
    if not closed_dates:
        return week
    skip_indices = skip_indices or set()
    shift_codes = [s['code'] for s in _get_shift_slots()]
    for idx, day in enumerate(week):
        if idx in skip_indices or day.get('date') not in closed_dates:
            continue
        for code in shift_codes:
            for entry in day.get(code, []):
                wid = entry.get('workerId', 0)
                if wid > 0 and wid not in day['rest']:
                    day['rest'].append(wid)
            day[code] = []
    return week


def _worker_matches_scope(custom_data, field_key, scope_entity_id):
    """Return True if the worker's EAV field matches the given scope entity record ID.
    Handles entity_select (int) and multi_entity_select (list/list-of-dicts with priority).
    """
    val = custom_data.get(field_key)
    if val is None:
        return False
    sid = str(scope_entity_id)
    if isinstance(val, list):
        for item in val:
            if isinstance(item, dict):
                # Handle all EAV dict formats: {value:N}, {entity_id:N}, {id:N}
                for k in ('value', 'entity_id', 'id'):
                    if k in item and str(item[k]) == sid:
                        return True
            elif str(item) == sid:
                return True
        return False
    return str(val) == sid


def _eligibility_rule_sets(scope_record_id, restrictions):
    """Collect scopeMatch rule-sets from active 'condition' restrictions that apply to this scope."""
    from apps.restrictions.engine import normalize_scope_match_rules
    rule_sets = []
    for r in restrictions:
        if r.get('engine') != 'condition':
            continue
        scoped = r.get('scope_records') or []
        if scope_record_id and scoped and scope_record_id not in scoped:
            continue
        sm = (r.get('config') or {}).get('scopeMatch')
        if not sm:
            continue
        rules = normalize_scope_match_rules(sm)
        if rules:
            rule_sets.append(rules)
    return rule_sets


def _filter_workers_by_eligibility(workers, scope_record_id, restrictions, linking_field_key):
    """Config-driven scope eligibility (replaces any hardcoded domain filter).

    A worker is eligible if they satisfy EVERY active scopeMatch 'condition' restriction
    that applies to this scope (each restriction's rules are OR'd internally; restrictions
    are AND'd together). If no scopeMatch restriction applies, fall back to the generic
    linking-field filter (the worker field that targets the scope entity == this record).
    This keeps the generator domain-agnostic: zona/contract/etc. policy lives entirely in
    configured restrictions, not in code.
    """
    from apps.restrictions.engine import worker_passes_scope_match, _load_scope_record_data
    rule_sets = _eligibility_rule_sets(scope_record_id, restrictions)
    if not rule_sets:
        if not linking_field_key:
            return workers
        return [w for w in workers if _worker_matches_scope(w['customData'], linking_field_key, scope_record_id)]
    scope_data = _load_scope_record_data(scope_record_id)
    return [
        w for w in workers
        if all(worker_passes_scope_match(w['customData'], scope_record_id, scope_data, rules) for rules in rule_sets)
    ]


def _build_pills_map():
    """Build worker_id → list of pill names from the show_in_schedule entity.

    Looks up the entity type with show_in_schedule=True, finds the worker field
    that references it, then resolves each worker's record IDs to display names.
    """
    from apps.dynamic_fields.models import EntityField as EF

    pills_et = EntityType.objects.filter(show_in_schedule=True).first()
    if not pills_et:
        return {}, None

    pills_display = pills_et.display_field or 'nombre'
    # Build id → name map for pill records
    record_name_map = {}
    for r in EntityRecord.objects.filter(entity_type=pills_et):
        name = r.data.get(pills_display) or r.data.get('nombre') or r.data.get('name') or ''
        if name:
            record_name_map[r.id] = name

    # Find the worker field that targets this entity
    linking_field = EF.objects.filter(
        entity_type='worker',
        target_entity=pills_et.slug,
        field_type__in=['entity_select', 'multi_entity_select'],
    ).first()

    pills_field_key = linking_field.key if linking_field else None
    return record_name_map, pills_field_key


def _resolve_worker_pills(custom_data, pills_field_key, record_name_map):
    """Resolve a worker's pill record IDs to display names, sorted by priority.

    Handles both EAV priority formats:
    - Simple list: [4, 1]  → index = priority (0 is highest)
    - Priority objects: [{value: 4, priority: 1}, {value: 1, priority: 2}]
    Returns names sorted by ascending priority (highest priority first).
    """
    if not pills_field_key or not record_name_map:
        return []
    val = custom_data.get(pills_field_key)
    if val is None:
        return []
    if not isinstance(val, list):
        val = [val]
    # Build (priority, record_id) tuples
    entries = []
    for idx, item in enumerate(val):
        if isinstance(item, dict):
            rid = item.get('value') or item.get('id')
            prio = item.get('priority', idx + 1)
        else:
            rid = item
            prio = idx + 1
        try:
            rid = int(rid)
        except (ValueError, TypeError):
            continue
        if rid in record_name_map:
            entries.append((prio, rid))
    # Sort by priority (ascending – 1 is highest)
    entries.sort(key=lambda x: x[0])
    return [record_name_map[rid] for _, rid in entries]


def _get_primary_shift_key():
    """Auto-discover the primary worker→shift field key (first entity_select targeting shift).

    This is the ONLY auto-discovery: the base shift field always exists and is universal.
    """
    cache = _get_gen_cache()
    if 'primary_shift_key' in cache:
        return cache['primary_shift_key']

    from apps.dynamic_fields.models import EntityField as EF
    f = EF.objects.filter(
        entity_type='worker', active=True,
        field_type__in=['entity_select', 'multi_entity_select'],
        target_entity='shift',
    ).order_by('order').first()

    key = f.key if f else None
    cache['primary_shift_key'] = key
    return key


def _get_assignment_rules(scope_record_id=None):
    """Load active assignment rules, optionally filtered by scope. Cached per generation."""
    cache = _get_gen_cache()
    cache_key = f'assignment_rules_{scope_record_id}'
    if cache_key in cache:
        return cache[cache_key]

    from apps.assignments.models import AssignmentRule
    rules = list(AssignmentRule.objects.filter(active=True).order_by('priority'))
    if scope_record_id:
        rules = [r for r in rules if not r.scope_records or scope_record_id in r.scope_records]
    cache[cache_key] = rules
    return rules


def _apply_assignment_rules(cd, primary_shift, rules, week_num, day_of_year=0, weekday=None):
    """Apply assignment rules sequentially to determine the effective shift.

    Universal engine: each rule has a condition + override + temporal pattern.
    Config keys:
        conditionField: str - worker field to check
        conditionValue: str - value to match (empty = any truthy)
        overrideField: str - worker field containing the alternative shift ID
        pattern: 'always' | 'alternate_weekly' | 'alternate_daily' | 'weekday'
        frequencyField: str - worker field with frequency number
        frequencyValue: int - fixed frequency (used if frequencyField is empty)
        weekday: int (0=Mon..6=Sun) - day the override applies (pattern 'weekday')
    """
    effective = primary_shift
    for rule in rules:
        config = rule.config or {}
        effective = _apply_single_rule(cd, effective, config, week_num, day_of_year, weekday)
    return effective


def _apply_single_rule(cd, current_shift, config, week_num, day_of_year, weekday=None):
    """Universal assignment rule: condition → override with temporal pattern."""
    condition_field = config.get('conditionField', '')
    override_field = config.get('overrideField', '')
    pattern = config.get('pattern', 'always')

    if not override_field:
        return current_shift

    # Check condition (if configured). Se delega en _rule_condition_matches
    # para tener UNA sola implementación: antes había una copia aquí que no
    # entendía los campos multi-valor.
    if condition_field and not _rule_condition_matches(cd, config):
        return current_shift

    # Get the override shift
    override_shift = str(cd.get(override_field, '') or '')
    if not override_shift:
        return current_shift

    # Get frequency
    freq = 1
    freq_field = config.get('frequencyField', '')
    freq_value = config.get('frequencyValue', 0)
    if freq_field:
        try:
            freq = max(1, int(cd.get(freq_field) or 1))
        except (ValueError, TypeError):
            freq = 1
    elif freq_value:
        try:
            freq = max(1, int(freq_value))
        except (ValueError, TypeError):
            freq = 1

    # Apply temporal pattern
    if pattern == 'always':
        return override_shift
    elif pattern == 'alternate_weekly':
        return override_shift if (week_num // freq) % 2 == 1 else current_shift
    elif pattern == 'alternate_daily':
        return override_shift if (day_of_year // freq) % 2 == 1 else current_shift
    elif pattern == 'weekday':
        try:
            target_wd = int(config.get('weekday'))
        except (TypeError, ValueError):
            return current_shift
        return override_shift if weekday == target_wd else current_shift
    else:
        return current_shift


def _normalize_hhmm(value):
    """'8:5' / '08:05:00' / datetime.time → '08:05'. None si no es una hora válida."""
    if value is None or value == '':
        return None
    if hasattr(value, 'hour') and hasattr(value, 'minute'):
        return f'{value.hour:02d}:{value.minute:02d}'
    parts = str(value).strip().split(':')
    if len(parts) < 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
    except (TypeError, ValueError):
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return f'{h:02d}:{m:02d}'


def _resolve_worker_times(cd, defaults, rules, weekday, shift_id=None):
    """Horario efectivo de un trabajador para un día concreto.

    Las reglas con `overrideType: 'times'` no cambian de turno: sustituyen las
    HORAS del turno por las del trabajador (startField/endField apuntan a campos
    de su ficha, p.ej. hora_entrada/hora_salida) o por unas fijas
    (startValue/endValue, p.ej. el horario de encargadas). `weekdays` limita a
    qué días de la semana aplica (0=lunes … 6=domingo).

    Se recorren en orden de prioridad y gana la última que aplique, igual que
    `_apply_assignment_rules` con los cambios de turno. El horario de la ficha
    manda aunque se salga del turno: en los datos reales hay mucha gente con
    08:00-15:00 sobre un turno 07:45-14:45, y son horarios reales, no erratas.

    `applyShift` limita la regla al turno ya resuelto (`shift_id`). Es lo que
    distingue las dos reglas de encargadas: misma condición y mismos weekdays,
    pero una es para la semana de mañana (turno 153) y otra para la de tarde
    (154). Sin comprobarlo, las dos aplicarían siempre y ganaría la de tarde.

    Devuelve (start, end, rule_name) o (defaults, None) si ninguna regla aplica.
    """
    start = defaults.get('start')
    end = defaults.get('end')
    applied = None
    for rule in rules:
        config = rule.config or {}
        if config.get('overrideType') != 'times':
            continue
        weekdays = config.get('weekdays')
        if weekdays and weekday is not None and weekday not in weekdays:
            continue
        apply_shift = config.get('applyShift')
        if apply_shift and shift_id is not None and str(apply_shift) != str(shift_id):
            continue
        if not _rule_condition_matches(cd, config):
            continue
        # startField/endField leen la ficha; startValue/endValue son fijos.
        s = _normalize_hhmm(
            cd.get(config['startField']) if config.get('startField') else config.get('startValue')
        )
        e = _normalize_hhmm(
            cd.get(config['endField']) if config.get('endField') else config.get('endValue')
        )
        # Sin ninguna de las dos horas la regla no aporta nada: se ignora en
        # vez de dejar el turno a medias.
        if s is None and e is None:
            continue
        cand_start = s if s is not None else start
        cand_end = e if e is not None else end
        # Red de seguridad: el horario personal es UNO SOLO para L-V, así que a
        # quien rota mañana/tarde le sirve para una semana y no para la otra. Si
        # el horario propuesto no solapa al menos la mitad del turno, se descarta
        # y se dejan las horas del turno: es mejor un horario genérico correcto
        # que uno "personal" imposible (turno de Tarde con horas de mañana).
        if not _times_fit_shift(cand_start, cand_end, defaults):
            continue
        start, end = cand_start, cand_end
        applied = rule.name
    return start, end, applied


def _hhmm_to_min(value):
    """'08:30' → 510. None si no se puede interpretar."""
    hhmm = _normalize_hhmm(value)
    if hhmm is None:
        return None
    h, m = hhmm.split(':')
    return int(h) * 60 + int(m)


def _times_fit_shift(start, end, defaults, min_overlap_ratio=0.5):
    """¿El horario [start, end] encaja con el turno de `defaults`?

    Encaja si solapa al menos `min_overlap_ratio` de la duración del turno. No se
    exige que quepa dentro: hay mucha gente con 08:00-15:00 sobre un turno
    07:45-14:45, y son horarios reales que deben respetarse. Lo que se descarta es
    el caso sin sentido: horas de mañana sobre un turno de tarde.

    Si algún dato no es interpretable devuelve True (no se descarta por dudas).
    """
    s, e = _hhmm_to_min(start), _hhmm_to_min(end)
    ts, te = _hhmm_to_min(defaults.get('start')), _hhmm_to_min(defaults.get('end'))
    if None in (s, e, ts, te):
        return True
    duration = te - ts
    if duration <= 0:          # turno nocturno o mal definido: no se juzga
        return True
    overlap = min(e, te) - max(s, ts)
    return overlap >= duration * min_overlap_ratio


def _field_values(field_val):
    """Valores comparables de un campo EAV, como lista de strings.

    Los campos multi-valor (multi_entity_select, p.ej. `secciones`) se guardan
    como [{'value': 76, 'priority': 1}, ...]; los simples, como un escalar. Sin
    desenvolver el 'value' la comparación se hacía contra el repr de la lista
    entera y no casaba nunca.
    """
    if isinstance(field_val, (list, tuple)):
        out = []
        for item in field_val:
            if isinstance(item, dict):
                v = item.get('value', item.get('id'))
                if v is not None:
                    out.append(str(v).lower())
            elif item is not None:
                out.append(str(item).lower())
        return out
    if isinstance(field_val, dict):
        v = field_val.get('value', field_val.get('id'))
        return [str(v).lower()] if v is not None else []
    return [str(field_val).lower()]


_WEEKDAY_CODES = {
    'lunes': 0, 'martes': 1, 'miercoles': 2, 'jueves': 3,
    'viernes': 4, 'sabado': 5, 'domingo': 6,
}


def _norm_weekday(value):
    """'Lunes'/'lunes'/'0'/0 → 0 (lunes) … 6 (domingo). None si no se reconoce.

    Los valores del catálogo llegan como códigos sin acentos ('miercoles'), pero
    se acepta también el índice numérico por si otra configuración lo usa.
    """
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in _WEEKDAY_CODES:
        return _WEEKDAY_CODES[s]
    # Sin acentos, por si el valor llega como 'miércoles'/'sábado'.
    import unicodedata
    s = ''.join(c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn')
    if s in _WEEKDAY_CODES:
        return _WEEKDAY_CODES[s]
    try:
        n = int(s)
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= 6 else None


def _rule_condition_matches(cd, config):
    """¿El trabajador cumple la condición de esta regla de asignación?

    Misma lógica que _apply_single_rule() para no divergir: valor exacto si hay
    conditionValue, y comprobación de "truthy" si solo hay conditionField.
    En campos multi-valor basta con que ALGUNO coincida (p.ej. la sección 76
    dentro de la lista de secciones del trabajador).
    """
    condition_field = config.get('conditionField', '')
    if not condition_field:
        return True
    field_val = cd.get(condition_field, '')
    condition_value = config.get('conditionValue', '')
    if condition_value:
        return str(condition_value).lower() in _field_values(field_val)
    return field_val is True or (
        str(field_val).lower() in ('true', '1') if field_val else False
    )


def _find_unrotated_workers(workers, rules):
    """Trabajadores marcados para rotar que no pueden rotar.

    Devuelve {nombre_de_regla: [nombres]} para las reglas con patrón de
    alternancia (alternate_weekly / alternate_daily) cuya condición cumple el
    trabajador pero que no tienen valor en el campo de override. Sin ese valor,
    _apply_single_rule() devuelve el turno actual y la rotación no ocurre nunca.

    Solo se miran los patrones de alternancia: en 'weekday' (p.ej. el turno de
    sábado) o 'always' que falte el override es normal, no una incoherencia.
    """
    out = {}
    for rule in rules:
        config = rule.config or {}
        if config.get('pattern') not in ('alternate_weekly', 'alternate_daily'):
            continue
        override_field = config.get('overrideField', '')
        if not override_field:
            continue
        for w in workers:
            cd = w.get('customData', {}) or {}
            if not _rule_condition_matches(cd, config):
                continue
            if str(cd.get(override_field, '') or ''):
                continue
            out.setdefault(rule.name, []).append(w.get('name', f"#{w.get('id')}"))
    return out


def _resolve_worker_shift_code(cd, shift_key, rules, week_num, day_of_year=0, weekday=None):
    """Return the effective shift ID (str) for a worker given assignment rules."""
    primary = str(cd.get(shift_key, '') or '') if shift_key else ''
    if not primary:
        return None
    return _apply_assignment_rules(cd, primary, rules, week_num, day_of_year, weekday)


def generate_schedule(start_date, scope_entity_id=0, target_dates=None, base_plan=None,
                      busy_map=None, extra_hours=None):
    """Generate (or partially regenerate) the weekly plan for a scope.

    target_dates: optional list of ISO dates within the week to REgenerate.
    When given, base_plan (the existing week) is required and every other day
    is frozen: it passes through untouched and its assignments count towards
    weekly caps and consecutive-shift checks. Partial regeneration is always
    deterministic (no OpenAI) so the frozen context is respected.

    busy_map: {'YYYY-MM-DD': {worker_id, ...}} de trabajadores ya asignados ESE
    día en OTRO ámbito. Nadie puede estar en dos tiendas a la vez, así que se
    tratan como no disponibles (igual que una ausencia). Lo usa la generación
    en bloque, que planifica varias tiendas de la misma semana: sin esto, un
    trabajador elegible en varias tiendas (p.ej. personal común que cubre toda
    su zona) acaba asignado simultáneamente en todas ellas.
    """
    _get_gen_cache().clear()

    restrictions = list(
        Restriction.objects.filter(active=True).values('id', 'name', 'engine', 'config', 'severity', 'scope_records')
    )

    # ── Partial regeneration: freeze the days NOT being regenerated ──────
    frozen_days = None
    if target_dates:
        targets = {str(d) for d in target_dates}
        base = normalize_week(list(base_plan or []), start_date)
        frozen_days = {
            idx: day for idx, day in enumerate(base)
            if day.get('date') not in targets
        }

    # ── Resolve scope via EAV ──────────────────────────────────────────────
    scope_et = None
    scope_slug = None
    linking_field_key = None
    area_display = 'nombre'
    try:
        from apps.dynamic_fields.models import EntityField as EF
        scope_et = EntityType.objects.filter(is_planning_scope=True).first()
        if scope_et:
            scope_slug = scope_et.slug
            area_display = scope_et.display_field or 'nombre'
            # Find the worker EntityField that targets the scope entity slug
            lf = EF.objects.filter(
                entity_type='worker',
                target_entity=scope_slug,
                field_type__in=['entity_select', 'multi_entity_select'],
            ).first()
            if lf:
                linking_field_key = lf.key
            logger.info('Planning scope: %s (slug=%s, linking_field=%s)', scope_et.name, scope_slug, linking_field_key)
    except Exception as e:
        logger.warning('Could not resolve planning scope: %s', e)

    # ── Resolve pills (show_in_schedule entity, e.g. roles) ───────────────
    pills_record_map, pills_field_key = _build_pills_map()

    # ── Build worker pool (all active) ──────────────────────────────────
    workers_qs = Worker.objects.filter(active=True)
    # Preferencias en UNA consulta. Con `prefetch_related('preferences')` +
    # `w.preferences.values_list(...)` dentro del bucle NO se usaba el prefetch:
    # values_list lanza su propia consulta, así que salían 272 (una por
    # trabajador) y solo eso eran ~9 s de cada generación.
    from apps.workers.models import WorkerPreference
    prefs_map = {}
    for wid, shift in WorkerPreference.objects.filter(
            worker__active=True).values_list('worker_id', 'shift_type'):
        if shift:
            prefs_map.setdefault(wid, []).append(shift)

    workers = []
    for w in workers_qs:
        cd = w.custom_data or {}
        preferred = prefs_map.get(w.id, [])
        workers.append({
            'id': w.id,
            'name': w.name,
            'active': w.active,
            'preferredShifts': preferred,
            'customData': cd,
            'pills': _resolve_worker_pills(cd, pills_field_key, pills_record_map),
        })

    # ── Scope eligibility (config-driven: scopeMatch restrictions; else linking field) ──
    if scope_entity_id > 0:
        before = len(workers)
        workers = _filter_workers_by_eligibility(workers, scope_entity_id, restrictions, linking_field_key)
        logger.info('Scope eligibility: %d → %d workers', before, len(workers))

    # ── Resolve areas for this scope ────────────────────────────────────
    areas_qs = EntityRecord.objects.none()
    try:
        if scope_et:
            if scope_entity_id > 0:
                areas_qs = EntityRecord.objects.filter(entity_type=scope_et, id=scope_entity_id)
            else:
                areas_qs = EntityRecord.objects.filter(entity_type=scope_et)
    except Exception:
        pass
    areas = [
        {
            'id': a.id,
            'name': a.data.get(area_display) or a.data.get('nombre') or a.data.get('name') or f'area-{a.id}',
            'required_role': a.data.get('required_role'),
            'active': a.data.get('active', True),
        }
        for a in areas_qs
        if a.data.get('active', True)
    ]

    shift_slots = _get_shift_slots()
    shift_key = _get_primary_shift_key()
    assignment_rules = _get_assignment_rules(scope_entity_id if scope_entity_id > 0 else None)

    logger.info('generate_schedule: %d workers, %d areas, %d shifts, %d assignment rules',
                len(workers), len(areas), len(shift_slots), len(assignment_rules))

    # Load absences and rest days for this week
    end_date = start_date + timedelta(days=6)
    absent_map = _build_absent_map(start_date, end_date)

    # Quien ya trabaja ese día en OTRA tienda no está disponible aquí: se suma
    # al mapa de ausencias (misma semántica, "hoy no puede cubrir turno").
    if busy_map:
        merged = {d: set(ids) for d, ids in absent_map.items()}
        for day, ids in busy_map.items():
            merged.setdefault(day, set()).update(ids)
        absent_map = merged

    # Horas que cada trabajador YA lleva esta semana en OTRAS tiendas. El tope de
    # horas es del CONTRATO (de la persona), no de la tienda: sin esto, alguien
    # con 35h podía hacer 5 días en una tienda y el sábado en otra (42,5h) sin
    # que ninguna de las dos superase el tope por separado. Se arranca el
    # contador con esas horas para que el tope se aplique al total real.
    prior_hours = _prior_week_hours(start_date, scope_entity_id)
    if extra_hours:
        # Generación en bloque: los ámbitos ya generados en esta tanda todavía no
        # están en BD, así que sus horas llegan por parámetro.
        for wid, hrs in extra_hours.items():
            prior_hours[int(wid)] = prior_hours.get(int(wid), 0.0) + float(hrs)

    # Closed days (festivos locales / cierres) for this scope
    closed_dates = _load_closed_dates(scope_entity_id, start_date, end_date)

    warnings = []
    if closed_dates:
        warnings.append('Días de cierre en esta semana: ' + ', '.join(sorted(closed_dates)))

    # ── Detect data issues upfront ──────────────────────────────────────
    shift_code_set = {s['code'] for s in shift_slots}
    shift_labels = {s['code']: s['label'] for s in shift_slots}
    week_num_up = start_date.isocalendar()[1]

    # Collect every shift code any worker in this scope could ever use
    # (primary field + all override/secondary fields declared in assignment rules)
    shifts_in_scope: set = set()
    for w in workers:
        cd = w.get('customData', {})
        if shift_key:
            v = str(cd.get(shift_key, '') or '')
            if v:
                shifts_in_scope.add(v)
        for rule in assignment_rules:
            override_field = (rule.config or {}).get('overrideField', '')
            if override_field:
                v = str(cd.get(override_field, '') or '')
                if v:
                    shifts_in_scope.add(v)

    # Build workers_per_shift using RESOLVED effective shifts for this week
    # (applies assignment / rotation rules so rotative workers count in their actual slot)
    workers_per_shift: dict = {sc: [] for sc in shift_code_set}
    for w in workers:
        eff = _resolve_worker_shift_code(
            w.get('customData', {}), shift_key, assignment_rules, week_num_up,
        )
        if eff and eff in workers_per_shift:
            workers_per_shift[eff].append(w['name'])

    # Only warn about SECONDARY/OVERRIDE shifts in scope that have 0 workers resolved to them.
    # Primary shifts having 0 workers is the expected rotation effect — workers moved to secondary.
    secondary_shifts_in_scope: set = set()
    for w in workers:
        cd = w.get('customData', {})
        for rule in assignment_rules:
            override_field = (rule.config or {}).get('overrideField', '')
            if override_field:
                v = str(cd.get(override_field, '') or '')
                if v:
                    secondary_shifts_in_scope.add(v)
    primary_shifts_in_scope: set = shifts_in_scope - secondary_shifts_in_scope

    # Turnos que solo aplican UN dia de la semana (regla pattern='weekday', p.ej.
    # 'Sabado Manana'). No se pueden contar con `workers_per_shift`, que resuelve
    # el turno EFECTIVO de la semana: quien tiene turno_sabado resuelve a su
    # turno base ('Manana'), asi que el de sabado salia siempre con 0 y avisaba
    # "0 trabajadores asignados" aunque la ficha de 10 personas lo tuviera.
    weekday_shift_codes: set = set()
    for rule in assignment_rules:
        cfg = rule.config or {}
        if cfg.get('pattern') != 'weekday':
            continue
        override_field = cfg.get('overrideField', '')
        if not override_field:
            continue
        for w in workers:
            v = str((w.get('customData') or {}).get(override_field, '') or '')
            if v:
                weekday_shift_codes.add(v)

    for sc, names in workers_per_shift.items():
        if (not names
                and sc in secondary_shifts_in_scope
                and sc not in primary_shifts_in_scope
                and sc not in weekday_shift_codes):
            warnings.append(f'Turno "{shift_labels.get(sc, sc)}" tiene 0 trabajadores asignados en este \u00e1mbito.')

    # Rotación que no rota: el trabajador cumple la condición de una regla de
    # override (p.ej. rotacion == 'semanal') pero no tiene valor en el campo de
    # turno alternativo. _apply_single_rule() lo deja en su turno base y devuelve
    # sin hacer nada, asi que en la practica es un turno FIJO aunque la ficha diga
    # que rota. Antes fallaba en silencio: ni error, ni aviso, ni log.
    unrotated = _find_unrotated_workers(workers, assignment_rules)
    for rule_name, names in sorted(unrotated.items()):
        shown = ', '.join(sorted(names)[:5])
        extra = f' y {len(names) - 5} mas' if len(names) > 5 else ''
        warnings.append(
            f'{len(names)} trabajador(es) cumplen "{rule_name}" pero no tienen '
            f'turno alternativo, asi que NO rotan y se quedan en su turno base: '
            f'{shown}{extra}.'
        )

    if not workers:
        warnings.append('No hay trabajadores activos para este ámbito.')

    # Try OpenAI (never for partial regeneration: frozen context must be exact)
    openai_api_key = os.getenv('OPENAI_API_KEY')
    used_ai = False
    violations = []
    if openai_api_key and frozen_days is None:
        result = _try_openai(openai_api_key, start_date, restrictions, workers, areas, shift_slots)
        if result is not None:
            normalized = _apply_closed_days(normalize_week(result, start_date), closed_dates)
            violations = _collect_violations(normalized, scope_record_id=scope_entity_id)
            error_count = sum(1 for v in violations if v.get('severity') == 'error')
            if error_count == 0:
                logger.info('OpenAI generation succeeded (0 errors)')
                used_ai = True
                plan = normalized
            else:
                logger.warning('OpenAI result has %d error violations, falling back to deterministic', error_count)
                violations = []  # will re-validate after fallback

    cap_report: dict = {}
    if not used_ai:
        plan = _fallback_round_robin(
            start_date, workers, restrictions, areas, absent_map,
            cap_report=cap_report, prior_hours=prior_hours,
            frozen_days=frozen_days, closed_dates=closed_dates,
        )
        # Reuse engine cache from prior validation (data hasn't changed)
        violations = _collect_violations(plan, scope_record_id=scope_entity_id, clear_cache=False)

    # ── Personal libre que no se pudo colocar por falta de PLAZA ────────────
    # Explica el caso que antes quedaba mudo: el plan sale con vacantes y a la vez
    # con gente descansando. No es que falte personal: es que sus secciones ya
    # están al tope y no se les asigna otra que no sea suya (hacerlo violaría la
    # polivalencia). El aviso dice la sección, el tope y qué se puede tocar.
    if cap_report:
        for (area_name, cap), names in sorted(cap_report.items(), key=lambda kv: -len(kv[1])):
            shown = ', '.join(sorted(names)[:5])
            extra = f' y {len(names) - 5} mas' if len(names) > 5 else ''
            cap_txt = f'tope {cap}' if cap is not None else 'sin tope'
            warnings.append(
                f'{len(names)} persona(s) sin turno porque "{area_name}" ya esta al '
                f'maximo ({cap_txt}) en los turnos donde podian entrar: {shown}{extra}. '
                f'No se les asigna otra seccion porque no esta en su polivalencia. '
                f'Para cubrirlo: sube el tope de "{area_name}" en Restricciones, o '
                f'anade mas secciones a su ficha.'
            )

    error_violations = [v for v in violations if v['severity'] == 'error']
    warning_violations = [v for v in violations if v['severity'] != 'error']

    if not error_violations and not warning_violations:
        if not warnings:  # no upfront data warnings either
            warnings.append('Planificación generada sin problemas.')
    else:
        if error_violations:
            warnings.append(_summarize_violations(error_violations, 'error'))
        if warning_violations:
            warnings.append(_summarize_violations(warning_violations, 'warning'))

    _log_plan_trace(plan, workers, scope_entity_id, start_date, absent_map, closed_dates)

    return {'plan': plan, 'warnings': warnings}


def _log_plan_trace(plan, workers, scope_entity_id, start_date, absent_map, closed_dates):
    """Vuelca en el log cómo ha quedado el reparto de la semana.

    Sirve para auditar una generación real desde la app (el script
    audit_generador.py solo ve generaciones lanzadas a mano). Se desactiva
    poniendo SCHEDULE_TRACE=0 en el entorno.
    """
    import os
    if os.environ.get('SCHEDULE_TRACE', '1') == '0':
        return
    try:
        from collections import Counter
        shift_slots = _get_shift_slots()
        codes = [s['code'] for s in shift_slots]
        labels = {s['code']: s['label'] for s in shift_slots}
        by_id = {w['id']: w for w in workers}

        out = []
        out.append('=' * 74)
        out.append(f'PLAN GENERADO — ámbito {scope_entity_id} · semana {start_date}')
        out.append('=' * 74)
        out.append(f'Candidatos elegibles: {len(workers)}')

        trabajados = Counter()
        for day in plan:
            if not isinstance(day, dict):
                continue
            date_str = day.get('date', '')
            if date_str in closed_dates:
                out.append(f'\n── {day.get("dayName","")} {date_str} — CERRADO (festivo/domingo)')
                continue
            # Día sin ningún turno operativo (domingo, o turnos fuera de su
            # vigencia): no es que falte gente, es que no se trabaja.
            if not any((day.get(c) or []) for c in codes):
                out.append(f'\n── {day.get("dayName","")} {date_str} — sin turnos operativos')
                continue
            total_dia = 0
            lineas = []
            for code in codes:
                entries = [e for e in (day.get(code) or []) if e.get('workerId', 0) > 0]
                if not entries:
                    continue
                total_dia += len(entries)
                lineas.append(f'   {labels.get(code, code)} ({len(entries)}):')
                for e in entries:
                    wid = e.get('workerId')
                    trabajados[wid] += 1
                    areas = ', '.join(e.get('areas') or []) or 'sin área'
                    lineas.append(
                        f'      · {str(e.get("workerName",""))[:32]:<34} '
                        f'{e.get("start","")}-{e.get("end","")}  [{areas}]'
                    )
            out.append(f'\n── {day.get("dayName","")} {date_str} — {total_dia} asignados')
            out.extend(lineas)
            ausentes = absent_map.get(date_str, set())
            libres = [by_id[i]['name'] for i in by_id
                      if i not in {e.get('workerId') for c in codes for e in (day.get(c) or [])}
                      and i not in ausentes]
            if libres:
                out.append(f'   SIN ASIGNAR ({len(libres)}): ' + ', '.join(n[:24] for n in libres[:10])
                           + (f' … +{len(libres)-10}' if len(libres) > 10 else ''))
            if ausentes:
                out.append(f'   No disponibles (ausencia u otra tienda): {len(ausentes)}')

        sin_turno = [w['name'] for w in workers if trabajados.get(w['id'], 0) == 0]
        out.append('')
        out.append(f'RESUMEN: {sum(trabajados.values())} asignaciones · '
                   f'{len(trabajados)} personas con turno · {len(sin_turno)} sin ningún turno')
        if sin_turno:
            out.append('   Sin turno: ' + ', '.join(n[:24] for n in sin_turno[:10])
                       + (f' … +{len(sin_turno)-10}' if len(sin_turno) > 10 else ''))
        out.append('=' * 74)

        # print() y no logger.info(): la config de LOGGING del proyecto está
        # comentada en settings.py, así que los INFO no llegan a la consola.
        # flush=True para que aparezca al instante en el runserver.
        print('\n'.join(out), flush=True)
    except Exception:
        # La traza NUNCA debe romper una generación válida.
        logger.exception('No se pudo volcar la traza del plan')


def _count_errors(plan_data, scope_record_id=None):
    """Run all active restrictions against a plan and count error-severity violations."""
    violations = _collect_violations(plan_data, scope_record_id=scope_record_id)
    return sum(1 for v in violations if v.get('severity') == 'error')


def _collect_violations(plan_data, scope_record_id=None, clear_cache=True):
    """Run all active restrictions and return the list of all violations."""
    try:
        from apps.restrictions.models import Restriction
        from apps.restrictions.engine import evaluate, _cache
        if clear_cache:
            _cache.clear()
        all_violations = []
        for r in Restriction.objects.filter(active=True):
            # Respect scope_records: skip restrictions scoped to other records
            scoped = r.scope_records or []
            if scope_record_id and scoped and scope_record_id not in scoped:
                continue
            all_violations.extend(evaluate(r, plan_data, scope_record_id=scope_record_id))
        return all_violations
    except Exception as e:
        logger.warning('Post-validation failed: %s', e)
        return []


def _count_violations(plan_data, scope_record_id=None):
    """Run all active restrictions and return (error_count, warning_count)."""
    violations = _collect_violations(plan_data, scope_record_id=scope_record_id)
    errors = sum(1 for v in violations if v.get('severity') == 'error')
    warnings = sum(1 for v in violations if v.get('severity') != 'error')
    return errors, warnings


def _summarize_violations(violations, level):
    """Build a human-readable grouped summary from a list of violations."""
    from collections import Counter

    count = len(violations)
    if level == 'error':
        header = f'{count} {"error" if count == 1 else "errores"} en el plan:'
    else:
        header = f'{count} {"aviso" if count == 1 else "avisos"} en el plan:'

    # Group by restriction name and collect unique messages
    by_restriction = {}
    for v in violations:
        name = v.get('restrictionName', 'Restricción desconocida')
        msg = v.get('message', '')
        by_restriction.setdefault(name, []).append(msg)

    # Build detail lines
    details = []
    for name, messages in by_restriction.items():
        if len(messages) == 1:
            details.append(f'  – {name}: {messages[0]}')
        else:
            # If all messages are similar (same restriction repeated), show count + first example
            unique = list(dict.fromkeys(messages))  # deduplicate preserving order
            if len(unique) <= 3:
                for m in unique:
                    details.append(f'  – {name}: {m}')
            else:
                details.append(f'  – {name} ({len(messages)} veces). Ej: {unique[0]}')

    return header + '\n' + '\n'.join(details)


def _build_absent_map(start_date, end_date):
    """Build {date_str: set(worker_ids)} for workers who cannot work on each day.

    Cubre dos tipos de ausencia aprobada que solapan la ventana [start, end]:
    - con fecha de fin: bloquea el rango [start_date, end_date].
    - indefinida (end_date NULL): bloquea desde su start_date en adelante, sin
      fin, por lo que dentro de la ventana bloquea hasta `end_date` (AC-4).
    """
    from django.db.models import Q
    absent = {}
    # Approved absences que solapan la ventana: fin >= inicio de ventana, o
    # indefinidas (end_date NULL) que empezaron antes del fin de la ventana.
    for ar in AbsenceRequest.objects.filter(
        Q(end_date__gte=start_date) | Q(end_date__isnull=True),
        status='approved',
        start_date__lte=end_date,
    ).values_list('worker_id', 'start_date', 'end_date'):
        wid, sd, ed = ar
        # Sin fecha de fin (indefinida) → se bloquea hasta el fin de la ventana.
        window_end = end_date if ed is None else min(ed, end_date)
        d = max(sd, start_date)
        while d <= window_end:
            ds = d.strftime('%Y-%m-%d')
            absent.setdefault(ds, set()).add(wid)
            d += timedelta(days=1)
    # Rest days
    for rd in RestDay.objects.filter(
        date__gte=start_date,
        date__lte=end_date,
    ).values_list('worker_id', 'date'):
        wid, dt = rd
        ds = dt.strftime('%Y-%m-%d')
        absent.setdefault(ds, set()).add(wid)
    return absent


def _try_openai(api_key, start_date, restrictions, workers, areas, shift_slots):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, timeout=45)
        model = os.getenv('AGENT_MODEL')
        if not model:
            logger.warning('AGENT_MODEL not set in env, skipping OpenAI generation')
            return None

        day_names = _get_day_names()
        shift_codes = [s['code'] for s in shift_slots]
        shift_desc = ', '.join(f'"{s["code"]}" ({s["label"]})' for s in shift_slots)

        # Collect pill names (roles) assigned to workers
        all_pills = sorted({p for w in workers for p in w.get('pills', [])})

        example_day = {
            'date': start_date.strftime('%Y-%m-%d'),
            'dayName': day_names[0] if day_names else 'Lunes',
            'rest': [],
        }
        for sc in shift_codes:
            example_day[sc] = [{'workerId': 0, 'workerName': '', 'start': '00:00', 'end': '00:00', 'areas': []}]

        system_prompt = (
            'You are an assistant that generates employee weekly schedules. '
            'Return ONLY a valid JSON array with exactly 7 elements (one per day). '
            'Each day object MUST have: "date" (YYYY-MM-DD), "dayName" (string), "rest" (array of worker IDs), '
            f'and one array for each shift code: {shift_desc}. '
            'Each shift array contains objects with: "workerId" (int), "workerName" (string), '
            '"start" (HH:MM), "end" (HH:MM), "areas" (array with exactly ONE role name: the worker\'s highest-priority role from their "pills" list). '
            'IMPORTANT: For each worker, use ONLY the FIRST element of their "pills" array as the single entry in "areas". '
            f'Available roles: {json.dumps(all_pills)}. '
            'Respect the restrictions provided. Respect workers\' preferredShifts when possible.'
        )

        # Include only essential fields in worker data sent to OpenAI
        workers_for_prompt = [
            {'id': w['id'], 'name': w['name'], 'preferredShifts': w['preferredShifts'], 'pills': w.get('pills', [])[:1]}
            for w in workers
        ]

        # Only include restriction fields the model needs
        restrictions_for_prompt = [
            {'name': r['name'], 'engine': r['engine'], 'config': r['config'], 'severity': r['severity']}
            for r in restrictions
        ]

        prompt = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'restrictions': restrictions_for_prompt,
            'workers': workers_for_prompt,
            'shift_slots': [{'code': s['code'], 'label': s['label'],
                             'start_time': s.get('attributes', {}).get('start_time', '00:00'),
                             'end_time': s.get('attributes', {}).get('end_time', '00:00')}
                            for s in shift_slots],
        }

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': json.dumps(prompt, default=str)},
        ]

        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=4000,
            response_format={'type': 'json_object'},
        )
        text = resp.choices[0].message.content
        text = text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1] if '\n' in text else text[3:]
            if text.endswith('```'):
                text = text[:-3]
        parsed = json.loads(text)
        if isinstance(parsed, dict) and parsed.get('week'):
            return parsed['week']
        if isinstance(parsed, list):
            return parsed
    except Exception as e:
        logger.warning('OpenAI schedule generation failed: %s', e)
    return None


def _prior_week_hours(start_date, scope_entity_id):
    """{worker_id: horas} ya asignadas esa semana en OTROS ámbitos guardados.

    El tope de horas semanales es del contrato de la PERSONA, así que hay que
    contar lo que ya hace en el resto de tiendas. Se excluye el ámbito que se
    está generando (sus horas se recalculan desde cero) y se ignoran los errores
    de datos: ante la duda, 0 horas previas (nunca inventa carga).
    """
    hours: dict = {}
    try:
        from apps.planning.models import WeeklyPlan
        shift_codes = [s['code'] for s in _get_shift_slots()]
        qs = WeeklyPlan.objects.filter(start_date=start_date)
        if scope_entity_id:
            qs = qs.exclude(scope_entity_id=scope_entity_id)
        for plan in qs:
            for day in (plan.plan_json or []):
                if not isinstance(day, dict):
                    continue
                for code in shift_codes:
                    for entry in (day.get(code) or []):
                        wid = entry.get('workerId', 0)
                        if wid:
                            hours[int(wid)] = hours.get(int(wid), 0.0) + _assignment_hours(entry)
    except Exception as exc:
        logger.warning('Could not read prior week hours: %s', exc)
        return {}
    return hours


def _fallback_round_robin(start_date, workers, restrictions=None, areas=None, absent_map=None,
                          cap_report=None, prior_hours=None,
                          frozen_days=None, closed_dates=None):
    """Constraint-aware schedule generation.

    Strategy:
    1. Assign each worker to their shift resolved via auto-discovered EAV fields
    2. Respect hard constraints: max 1 shift/day, absences, rest days, consecutive
       exclusion, incompatible worker pairs, closed days
    3. Distribute workers evenly across the week (per-worker weekly caps, dynamic
       via thresholdField when configured)
    4. frozen_days ({day_idx: day_dict}) pass through untouched (partial regen);
       their assignments still count towards weekly caps and consecutive checks.
    """
    if restrictions is None:
        restrictions = []
    if areas is None:
        areas = []
    if absent_map is None:
        absent_map = {}
    if frozen_days is None:
        frozen_days = {}
    if closed_dates is None:
        closed_dates = set()

    if not workers:
        return normalize_week(empty_week(start_date), start_date)

    week = empty_week(start_date)
    shift_defaults = _get_shift_defaults()
    shift_codes = list(shift_defaults.keys())
    shift_active_days = _get_shift_active_days()
    shift_validity = _get_shift_validity()

    # ── Parse exclusion restrictions for consecutive shift check ────────
    no_consecutive_pairs = []
    for r in restrictions:
        cfg = r.get('config') or {}
        if r.get('engine') == 'exclusion' and cfg.get('exclusionType') == 'consecutive_shifts':
            no_consecutive_pairs.append((str(cfg.get('shiftA', '')), str(cfg.get('shiftB', ''))))
    no_consecutive = no_consecutive_pairs[0] if no_consecutive_pairs else None  # backward compat

    # ── Parse incompatible worker pairs (exclusion worker_pair) ─────────
    incompatible = {}  # wid → set(partner ids) que no pueden compartir turno
    for r in restrictions:
        cfg = r.get('config') or {}
        if r.get('engine') == 'exclusion' and cfg.get('exclusionType') == 'worker_pair':
            for pair in cfg.get('workerPairs', []):
                if len(pair) == 2:
                    try:
                        w1, w2 = int(pair[0]), int(pair[1])
                    except (TypeError, ValueError):
                        continue
                    incompatible.setdefault(w1, set()).add(w2)
                    incompatible.setdefault(w2, set()).add(w1)

    # ── Pre-build ERROR restriction blocks per weekday ───────────────────
    # For every active ERROR condition restriction of type "per_shift / lte 0 / dayOfWeek N",
    # compute which workers match the filter and must be excluded on that weekday.
    try:
        from apps.restrictions.engine import _eval_condition_node
        error_blocks: dict = {}  # weekday_int -> set(worker_ids)
        for r in restrictions:
            if r.get('severity') != 'error' or r.get('engine') != 'condition':
                continue
            cfg = r.get('config') or {}
            if cfg.get('scope') != 'per_shift' or cfg.get('operator') != 'lte':
                continue
            if int(cfg.get('threshold', 1)) != 0:
                continue
            dow = cfg.get('dayOfWeek')
            filter_node = cfg.get('filter')
            if dow is None or filter_node is None:
                continue
            weekday = int(dow)
            day_ctx = {'weekday': weekday}
            for w in workers:
                if _eval_condition_node(filter_node, w.get('customData', {}), day_ctx):
                    error_blocks.setdefault(weekday, set()).add(w['id'])
    except Exception as _e:
        logger.warning('Could not build error blocks from ERROR restrictions: %s', _e)
        error_blocks = {}

    # ── Pre-build ERROR restriction blocks per (worker, shift) ───────────
    # Para cada restricción de ERROR tipo "condition / per_week_worker_shift /
    # lte 0 / targetShift=S" (p.ej. "Régimen antiguo no trabaja sábado tarde"):
    # los trabajadores que casan el filtro NO pueden asignarse a ese turno S.
    # El validador cuenta ≥1 en ese turno como error; aquí lo impedimos en
    # origen (antes el round-robin ignoraba estas reglas y generaba el error).
    shift_blocks: dict = {}  # shift_code (str) -> set(worker_ids)
    try:
        from apps.restrictions.engine import _eval_condition_node
        for r in restrictions:
            if r.get('severity') != 'error' or r.get('engine') != 'condition':
                continue
            cfg = r.get('config') or {}
            if cfg.get('scope') != 'per_week_worker_shift' or cfg.get('operator') != 'lte':
                continue
            if int(cfg.get('threshold', 1)) != 0:
                continue
            target_shift = cfg.get('targetShift')
            filter_node = cfg.get('filter')
            if not target_shift or filter_node is None:
                continue
            ts = str(target_shift)
            for w in workers:
                if _eval_condition_node(filter_node, w.get('customData', {}), None):
                    shift_blocks.setdefault(ts, set()).add(w['id'])
    except Exception as _e:
        logger.warning('Could not build shift blocks from ERROR restrictions: %s', _e)
        shift_blocks = {}

    # ── Parse "máximo N trabajadores por área" (count / shift_area / lte) ─
    # Devuelve: tope por defecto (regla sin filtro de áreas) y topes por área
    # concreta (reglas con filterAreaNames). El generador respetará estos topes
    # al asignar y reubicará a los que sobren en otra área elegible (AC).
    def _norm_area(s):
        import unicodedata
        return ''.join(c for c in unicodedata.normalize('NFD', str(s or '').lower().strip())
                       if unicodedata.category(c) != 'Mn')
    area_cap_default = None       # tope para cualquier área sin filtro
    area_cap_by_name = {}         # nombre_normalizado → tope
    for r in restrictions:
        cfg = r.get('config') or {}
        if r.get('engine') != 'count' or cfg.get('groupBy') != 'shift_area':
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
                # el más restrictivo gana si hay varias reglas para el área
                key = _norm_area(n)
                area_cap_by_name[key] = min(area_cap_by_name.get(key, th), th)
        else:
            area_cap_default = th if area_cap_default is None else min(area_cap_default, th)

    # ¿Hay que respetar el turno preferido? (match / worker_preference). Solo
    # ordena candidatos; si la restricción no está activa el orden no cambia.
    prefer_shifts = any(
        r.get('engine') == 'match'
        and (r.get('config') or {}).get('matchType') == 'worker_preference'
        for r in restrictions
    )

    # ── Topes por CAMPO de la ficha (count / groupBy 'shift' / lte) ──────
    # P.ej. "máximo 2 trabajadores ETT por turno": no limita un área sino a
    # quienes tienen tipo_contrato == 'ett'. Antes solo se validaba DESPUÉS de
    # generar: el motor podía meter a 3 ETT y luego marcarlo como violación.
    # Aquí se lee para respetarlo ya al asignar.
    field_caps = []   # [{'field','value','cap'}]
    for r in restrictions:
        cfg = r.get('config') or {}
        if r.get('engine') != 'count' or cfg.get('groupBy') != 'shift':
            continue
        if cfg.get('subject') != 'workers' or cfg.get('operator') != 'lte':
            continue
        if not cfg.get('filterField'):
            continue
        try:
            th = int(cfg.get('threshold'))
        except (TypeError, ValueError):
            continue
        field_caps.append({
            'field': cfg['filterField'],
            'value': str(cfg.get('filterValue', '') or '').strip().lower(),
            'cap': th,
        })

    def _field_cap_blocks(cd, used):
        """¿Algún tope por campo impide asignar a este trabajador en el turno?

        Devuelve la lista de índices de reglas que SÍ le aplican (para poder
        sumarlas si finalmente se asigna), o None si alguna está llena.
        """
        aplican = []
        for i, fc in enumerate(field_caps):
            val = str(cd.get(fc['field'], '') or '').strip().lower()
            if val != fc['value']:
                continue
            if used.get(i, 0) >= fc['cap']:
                return None          # esta regla ya está al tope
            aplican.append(i)
        return aplican

    def _area_cap(area_name):
        """Tope de plazas de un área (por nombre); None = sin límite."""
        specific = area_cap_by_name.get(_norm_area(area_name))
        if specific is not None:
            return specific
        return area_cap_default

    # Quién se queda sin turno por falta de PLAZA en sus secciones, y dónde.
    # {(nombre_seccion, tope): set(nombres)} — alimenta el aviso "tienes gente
    # libre pero sus secciones están llenas", que antes no se decía en ninguna
    # parte: el plan salía con vacantes y con gente en casa sin explicación.
    # Se escribe en `cap_report` (dict que pasa quien llama) para poder construir
    # el aviso sin cambiar lo que devuelve esta función.
    blocked_by_cap: dict = cap_report if cap_report is not None else {}

    # ── Resolve shift via assignment rules ───────────────────────────
    shift_key = _get_primary_shift_key()
    assignment_rules = _get_assignment_rules()
    week_num = start_date.isocalendar()[1]

    # ── Build worker→shift map (respects assignment rules) ──────────────
    shift_workers = {sc: [] for sc in shift_codes}  # shift_code → [worker dicts]
    unassigned = []
    for w in workers:
        sc = _resolve_worker_shift_code(
            w.get('customData', {}), shift_key, assignment_rules, week_num,
        )
        if sc and sc in shift_workers:
            shift_workers[sc].append(w)
        else:
            unassigned.append(w)
    # Distribute unassigned workers evenly across shifts
    for idx, w in enumerate(unassigned):
        sc = shift_codes[idx % len(shift_codes)]
        shift_workers[sc].append(w)

    # ── Read max shifts per week from restrictions (no default) ─────────
    # Supports per-worker dynamic caps via thresholdField (e.g. jornada reducida).
    # Si hay VARIAS restricciones de este ámbito se aplica la más restrictiva:
    # quedarse con la primera dejaba silenciosamente sin efecto a las demás.
    max_shifts_week = None  # None = no limit unless a restriction says so
    week_threshold_field = ''
    for r in restrictions:
        cfg = r.get('config') or {}
        if cfg.get('scope') == 'per_week_worker' and cfg.get('operator') == 'lte':
            try:
                candidate = int(cfg.get('threshold', 7))
            except (TypeError, ValueError):
                continue
            if max_shifts_week is None or candidate < max_shifts_week:
                max_shifts_week = candidate
                week_threshold_field = cfg.get('thresholdField', '') or ''

    worker_cd_map = {w['id']: w.get('customData', {}) for w in workers}

    def _week_cap(wid):
        """Tope semanal efectivo del trabajador (dinámico si hay thresholdField)."""
        if max_shifts_week is None:
            return None
        if week_threshold_field:
            try:
                return int(float(worker_cd_map.get(wid, {}).get(week_threshold_field, max_shifts_week)))
            except (TypeError, ValueError):
                return max_shifts_week
        return max_shifts_week

    # ── Tope de HORAS semanales (per_week_worker_hours) ──────────────────
    # El generador razonaba solo en nº de turnos: podía producir planes que se
    # pasaban de horas y el exceso solo se veía después, como aviso. Aquí se
    # lee el tope de horas para respetarlo YA al asignar.
    #
    # El umbral efectivo de cada trabajador sale de su campo EAV de contrato
    # (thresholdField, p.ej. 'horas_semanales') + thresholdOffset (margen de
    # empresa: contrato + N horas extra permitidas). Si el trabajador no tiene
    # el campo relleno se usa el umbral plano de la restricción — mismo criterio
    # que _effective_threshold() del motor, que es la fuente de verdad.
    max_hours_week = None
    hours_threshold_field = ''
    hours_threshold_offset = 0.0
    for r in restrictions:
        cfg = r.get('config') or {}
        if cfg.get('scope') == 'per_week_worker_hours' and cfg.get('operator') == 'lte':
            try:
                candidate = float(cfg.get('threshold', 0))
            except (TypeError, ValueError):
                continue
            if max_hours_week is None or candidate < max_hours_week:
                max_hours_week = candidate
                hours_threshold_field = cfg.get('thresholdField', '') or ''
                try:
                    hours_threshold_offset = float(cfg.get('thresholdOffset', 0) or 0)
                except (TypeError, ValueError):
                    hours_threshold_offset = 0.0

    def _hours_cap(wid):
        """Tope de horas semanales del trabajador (contrato + margen)."""
        if max_hours_week is None:
            return None
        return _effective_threshold(
            worker_cd_map.get(wid, {}),
            hours_threshold_field,
            max_hours_week,
            hours_threshold_offset,
        )

    # ── Pre-plan rest days so workers don't exhaust quota before weekend ─
    # If a shift operates more days than a worker is allowed, stagger days
    # off across the pool so every operating day still has coverage.
    frozen_idx = set(frozen_days.keys())
    worker_planned_rest = {}  # wid → set of day_idx (0-6 within the week)
    if max_shifts_week is not None:
        for shift_code in shift_codes:
            # Operating day indices for this shift, excluding frozen and closed days
            operating_indices = []
            for di in range(7):
                if di in frozen_idx:
                    continue
                d = start_date + timedelta(days=di)
                if d.isoformat() in closed_dates:
                    continue
                # Debe operar ese weekday Y estar dentro de su vigencia (AC-2).
                if _shift_operates_on(shift_code, d, shift_active_days, shift_validity):
                    operating_indices.append(di)
            n_operating = len(operating_indices)
            if not n_operating:
                continue
            pool = shift_workers.get(shift_code, [])
            if not pool:
                continue
            for w_idx, w in enumerate(pool):
                wid = w['id']
                cap = _week_cap(wid)
                if cap is None or n_operating <= cap:
                    continue
                rest_needed = n_operating - cap  # per worker
                for r in range(rest_needed):
                    # Stagger: each worker rests on different operating days
                    rest_pos = (w_idx + r * len(pool)) % n_operating
                    rest_day = operating_indices[rest_pos]
                    worker_planned_rest.setdefault(wid, set()).add(rest_day)

    # ── Días libres FIJOS por contrato (overrideType 'day_off') ─────────
    # Reglas de asignación con `overrideType: 'day_off'` y `daysField`: el campo
    # del trabajador (p.ej. `dias_libres`, multi_catalog_select con valores
    # 'lunes'..'domingo') lista los días que NO trabaja nunca. Es el caso de
    # pescadería, que libra los lunes porque no hay lonja en domingo.
    # Antes se ignoraba en silencio: la regla estaba activa en BD pero el motor
    # no entendía 'day_off', así que se asignaba a gente en su día libre.
    for rule in assignment_rules:
        cfg = rule.config or {}
        if cfg.get('overrideType') != 'day_off':
            continue
        days_field = cfg.get('daysField')
        if not days_field:
            continue
        for w in workers:
            cd = w.get('customData', {}) or {}
            if not _rule_condition_matches(cd, cfg):
                continue
            libres = {_norm_weekday(v) for v in _field_values(cd.get(days_field))}
            libres.discard(None)
            if not libres:
                continue
            for di in range(7):
                if (start_date + timedelta(days=di)).weekday() in libres:
                    worker_planned_rest.setdefault(w['id'], set()).add(di)

    # ── Assign workers per day ──────────────────────────────────────────
    prev_day_assignments = {}  # shift_code → set of worker ids
    # Nº de días ya trabajados por trabajador en la semana. Se usa para REPARTIR
    # el trabajo (y por tanto los descansos): cada día se atiende primero a los
    # que MENOS han trabajado, así no descansan siempre los mismos y los
    # descansos se distribuyen entre los 7 días.
    worked_count = {}
    # Horas ya acumuladas por trabajador en la semana. Alimenta el tope de horas
    # (_hours_cap) para no asignar un turno que haría pasarse del contrato.
    # Arranca con las horas que ya hace en OTRAS tiendas esa misma semana: el
    # contrato es de la persona, no de la tienda.
    worked_hours = dict(prior_hours or {})

    for day_idx, day in enumerate(week):
        # Frozen day (partial regeneration): splice it in untouched and use its
        # assignments as context for consecutive-shift checks and weekly caps.
        if day_idx in frozen_idx:
            frozen = frozen_days[day_idx]
            week[day_idx] = frozen
            today_shift_workers = {}
            for shift_code in shift_codes:
                today_shift_workers[shift_code] = {
                    e.get('workerId', 0) for e in frozen.get(shift_code, [])
                    if e.get('workerId', 0) > 0
                }
                # Las horas de un día congelado cuentan para el tope semanal:
                # no se pueden retocar, pero sí consumen contrato.
                for e in frozen.get(shift_code, []):
                    if e.get('workerId', 0) > 0:
                        wid_f = e['workerId']
                        worked_hours[wid_f] = worked_hours.get(wid_f, 0.0) + _assignment_hours(e)
            prev_day_assignments = today_shift_workers
            continue

        day_assigned = set()
        today_shift_workers = {}
        day_date = day['date']
        day_absent = absent_map.get(day_date, set())

        # Closed day (festivo/cierre): nobody works, everyone rests.
        if day_date in closed_dates:
            day['rest'] = sorted({w['id'] for w in workers} | set(day_absent))
            for shift_code in shift_codes:
                day[shift_code] = []
            prev_day_assignments = {sc: set() for sc in shift_codes}
            continue

        # Determine weekday index for shift active-days check
        from datetime import date as _date
        weekday_idx = _date.fromisoformat(day_date).weekday()

        # Add absent workers to rest
        day['rest'] = list(day_absent)

        # Re-resolve pools for THIS weekday so assignment rules with a 'weekday'
        # pattern (e.g. Saturday shift override) reroute the worker to their effective
        # shift. On days where no rule changes the shift, the pools are identical to the
        # weekly shift_workers (same buckets, same order), preserving the existing rotation.
        effective_sw = {sc: [] for sc in shift_codes}
        for sc_base in shift_codes:
            for w in shift_workers[sc_base]:
                eff_sc = _resolve_worker_shift_code(
                    w.get('customData', {}), shift_key, assignment_rules,
                    week_num, weekday=weekday_idx,
                )
                target = eff_sc if (eff_sc and eff_sc in effective_sw) else sc_base
                effective_sw[target].append(w)

        _day_obj = _date.fromisoformat(day_date)
        for shift_code in shift_codes:
            # Skip shift if it doesn't operate this day: weekday inactive OR
            # fuera de su rango de vigencia (turno extra caducado/futuro). Así
            # un turno normal y uno extra conviven el mismo día sin pisarse (AC-4).
            if not _shift_operates_on(shift_code, _day_obj, shift_active_days, shift_validity):
                day[shift_code] = []
                # Workers of this shift get rest on inactive days
                for w in effective_sw.get(shift_code, []):
                    if w['id'] not in day_absent and w['id'] not in day['rest']:
                        day['rest'].append(w['id'])
                today_shift_workers[shift_code] = set()
                continue

            defaults = shift_defaults[shift_code]
            pool = effective_sw[shift_code]

            # Reparto equitativo: atender primero a los que MENOS han trabajado
            # esta semana (así, cuando hay más gente que plazas, los descansos
            # rotan entre días y no descansan siempre los mismos). Se conserva
            # el orden original como desempate estable para no cambiar de golpe
            # toda la rotación.
            # A igualdad de carga, primero quien PREFIERE este turno (match /
            # worker_preference). Es una preferencia, no una prohibición: no se
            # descarta a nadie, solo se atiende antes a quien lo tiene entre sus
            # turnos preferidos. Así, cuando hay más gente que plazas, el que se
            # queda fuera es alguien a quien el turno no le encaja.
            rotated = sorted(
                pool,
                key=lambda w: (
                    worked_count.get(w['id'], 0),
                    0 if (not prefer_shifts
                          or shift_code in (w.get('preferredShifts') or [])) else 1,
                ),
            )

            shift_entries = []
            assigned_ids = set()
            # Plazas ocupadas por área en ESTE turno/día (para respetar el tope
            # "máximo N por área"). area_norm → nº asignados.
            area_used = {}
            # Idem para los topes por CAMPO de la ficha (count/shift con
            # filterField, p.ej. "máximo 2 ETT por turno"): índice de la regla →
            # nº de asignados que la cumplen en este turno.
            field_used = {}

            for w in rotated:
                wid = w['id']
                # Skip absent
                if wid in day_absent:
                    continue
                # Skip if blocked by an ERROR restriction on this weekday
                if wid in error_blocks.get(weekday_idx, set()):
                    if wid not in day['rest']:
                        day['rest'].append(wid)
                    continue
                # Skip if an ERROR restriction PROHÍBE este turno concreto a este
                # trabajador (p.ej. "régimen antiguo no trabaja sábado tarde").
                # NO va a descanso: podría cubrir otro turno del día; solo se le
                # excluye de ESTE turno para no incumplir la restricción.
                if wid in shift_blocks.get(str(shift_code), set()):
                    continue
                # Skip already assigned today (max 1 shift/day)
                if wid in day_assigned:
                    continue
                # Skip if this is a pre-planned rest day for this worker
                if day_idx in worker_planned_rest.get(wid, set()):
                    if wid not in day['rest']:
                        day['rest'].append(wid)
                    continue
                # Skip consecutive shift violation (check all configured pairs)
                skip_worker = False
                for pair_a, pair_b in no_consecutive_pairs:
                    if shift_code == pair_b:
                        if wid in prev_day_assignments.get(pair_a, set()):
                            skip_worker = True
                            break
                if skip_worker:
                    continue
                # Skip incompatible worker pairs (exclusion worker_pair):
                # never place both partners in the same shift.
                partners = incompatible.get(wid)
                if partners and partners & assigned_ids:
                    continue

                # ── Topes por campo de la ficha (p.ej. máx. 2 ETT/turno) ────
                # Va antes del tope de horas y de ocupar plaza de área: si no
                # cabe por esta vía, no debe consumir nada.
                cd_w = w.get('customData', {}) or {}
                field_hits = _field_cap_blocks(cd_w, field_used)
                if field_hits is None:
                    continue

                # ── Tope de horas semanales ─────────────────────────────────
                # Si este turno le haría superar su contrato (+ margen), no se
                # le asigna. Se comprueba ANTES de ocupar plaza de área para no
                # consumir un hueco que puede aprovechar otro compañero.
                hours_cap = _hours_cap(wid)
                if hours_cap is not None:
                    # Con el horario REAL del trabajador, no el del turno: si no,
                    # se decide con 7h y luego se suman 5h (o al revés), y el tope
                    # cuadra mal justo para los ~75 con horario propio.
                    cap_start, cap_end, _ = _resolve_worker_times(
                        w.get('customData', {}) or {}, defaults, assignment_rules,
                        weekday_idx, shift_id=shift_code,
                    )
                    entry_hours = _assignment_hours({'start': cap_start, 'end': cap_end})
                    if worked_hours.get(wid, 0.0) + entry_hours > hours_cap:
                        # Ya no le caben más horas esta semana → descansa.
                        if wid not in day['rest']:
                            day['rest'].append(wid)
                        continue

                # ── Elegir área respetando el tope "máximo N por área" ──────
                # Se prueban las áreas del trabajador por orden de prioridad
                # (pills). Se coge la PRIMERA con plaza libre. Si ninguna de sus
                # áreas tiene hueco → no se asigna este turno (queda en descanso;
                # el faltante se refleja como vacante/aviso, no como error).
                worker_areas = w.get('pills', []) or []
                chosen_areas = []
                if worker_areas:
                    for area_name in worker_areas:
                        an = _norm_area(area_name)
                        cap = _area_cap(area_name)
                        if cap is None or area_used.get(an, 0) < cap:
                            chosen_areas = [area_name]
                            area_used[an] = area_used.get(an, 0) + 1
                            break
                    if not chosen_areas:
                        # Ninguna de sus áreas tiene hueco → descansa este día.
                        # NO se le asigna una sección que no sea suya: hacerlo
                        # generaría un aviso de polivalencia y pondría a alguien
                        # donde no puede trabajar. Se anota para avisar de que
                        # hay personal libre con sus secciones llenas.
                        for area_name in worker_areas:
                            key = (str(area_name), _area_cap(area_name))
                            blocked_by_cap.setdefault(key, set()).add(w['name'])
                        if wid not in day['rest']:
                            day['rest'].append(wid)
                        continue
                # (Sin pills definidas: se asigna sin área, como antes.)

                # Horario efectivo: el de su ficha si alguna regla 'times' aplica
                # (hora_entrada/salida, horario de encargadas…), o el del turno.
                w_start, w_end, _ = _resolve_worker_times(
                    w.get('customData', {}) or {}, defaults, assignment_rules, weekday_idx,
                    shift_id=shift_code,
                )
                shift_entries.append({
                    'workerId': wid,
                    'workerName': w['name'],
                    'start': w_start,
                    'end': w_end,
                    'areas': chosen_areas,
                })
                assigned_ids.add(wid)
                day_assigned.add(wid)
                # Se suman los topes por campo SOLO al confirmar la asignación:
                # si se hiciera al comprobar, un descarte posterior (horas, área)
                # dejaría la cuota consumida por alguien que no entró.
                for i in field_hits:
                    field_used[i] = field_used.get(i, 0) + 1
                worked_count[wid] = worked_count.get(wid, 0) + 1  # reparto semanal
                # Las horas semanales se cuentan sobre el horario REAL, no el del
                # turno: si no, los topes por horas cuadraban mal para los ~75
                # trabajadores con horario propio.
                worked_hours[wid] = worked_hours.get(wid, 0.0) + _assignment_hours(
                    {'start': w_start, 'end': w_end}
                )

            day[shift_code] = shift_entries
            today_shift_workers[shift_code] = assigned_ids

        prev_day_assignments = today_shift_workers

    # ── Enforce max shifts per week: trim excess (safety net) ───────────
    # Two passes: frozen days count first (never trimmed), then the rest is
    # trimmed in order against each worker's effective cap (dynamic if set).
    if max_shifts_week is not None:
        weekly_counts = {}  # wid → count

        for day_idx, day in enumerate(week):
            if day_idx not in frozen_idx:
                continue
            for shift_code in shift_codes:
                for entry in day.get(shift_code, []):
                    wid = entry.get('workerId', 0)
                    if wid > 0:
                        weekly_counts[wid] = weekly_counts.get(wid, 0) + 1

        for day_idx, day in enumerate(week):
            if day_idx in frozen_idx:
                continue
            for shift_code in shift_codes:
                kept = []
                for entry in day.get(shift_code, []):
                    wid = entry['workerId']
                    if wid <= 0:
                        kept.append(entry)
                        continue
                    current = weekly_counts.get(wid, 0)
                    cap = _week_cap(wid)
                    if cap is None or current < cap:
                        weekly_counts[wid] = current + 1
                        kept.append(entry)
                    else:
                        # Move to rest for this day
                        if wid not in day.get('rest', []):
                            day.setdefault('rest', []).append(wid)
                day[shift_code] = kept

    # ── Enforce max hours per week: trim excess (safety net) ────────────
    # Mismo patrón que el tope de turnos: los días congelados cuentan primero
    # (no se tocan) y el resto se recorta contra el tope efectivo de cada uno.
    # El bucle de asignación ya lo respeta; esto cubre los caminos que no pasan
    # por él (p.ej. días congelados que por sí solos exceden el contrato).
    if max_hours_week is not None:
        weekly_hours = {}  # wid → horas

        for day_idx, day in enumerate(week):
            if day_idx not in frozen_idx:
                continue
            for shift_code in shift_codes:
                for entry in day.get(shift_code, []):
                    wid = entry.get('workerId', 0)
                    if wid > 0:
                        weekly_hours[wid] = weekly_hours.get(wid, 0.0) + _assignment_hours(entry)

        for day_idx, day in enumerate(week):
            if day_idx in frozen_idx:
                continue
            for shift_code in shift_codes:
                kept = []
                for entry in day.get(shift_code, []):
                    wid = entry.get('workerId', 0)
                    if wid <= 0:
                        kept.append(entry)
                        continue
                    cap = _hours_cap(wid)
                    entry_hours = _assignment_hours(entry)
                    current = weekly_hours.get(wid, 0.0)
                    if cap is None or current + entry_hours <= cap:
                        weekly_hours[wid] = current + entry_hours
                        kept.append(entry)
                    else:
                        # Move to rest for this day
                        if wid not in day.get('rest', []):
                            day.setdefault('rest', []).append(wid)
                day[shift_code] = kept

    return normalize_week(week, start_date)
