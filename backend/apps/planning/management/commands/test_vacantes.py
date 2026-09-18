"""¿Las "vacantes a poder cubrir" son cubribles DE VERDAD?

Para cada celda vacia de un plan guardado, busca candidatos igual que el front
(tienda + seccion + turno + no ausente + no ocupado ese dia) y luego aplica lo
que el front NO comprueba: tope de horas semanales y tope por area.

Asi se ve si el aviso dice la verdad o si el motor tenia razon al dejarlo vacio.
Solo lectura.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand

from apps.dynamic_fields.models import EntityField, EntityRecord, EntityType
from apps.planning.models import WeeklyPlan
from apps.planning.schedule_generator import _get_shift_slots, _worker_matches_scope
from apps.restrictions.engine import _assignment_hours


def _libra_ese_dia(w, fecha):
    """¿La fecha es uno de sus dias_libres fijos? (regla 'Dias libres personales')

    29 de las 32 personas de pescaderia libran el lunes: sin esto se proponian
    como candidatas para cubrir un lunes.
    """
    import datetime
    from apps.planning.schedule_generator import _field_values, _norm_weekday

    raw = (w.custom_data or {}).get('dias_libres')
    if not raw:
        return False
    idx = datetime.date.fromisoformat(fecha).weekday()
    libres = {_norm_weekday(v) for v in _field_values(raw)}
    libres.discard(None)
    return idx in libres


def _norm_area(s):
    """Copia de la normalizacion de nombres de area del generador."""
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', str(s or '').lower().strip())
                   if unicodedata.category(c) != 'Mn')
from apps.restrictions.engine import (
    _load_scope_record_data, normalize_scope_match_rules, worker_passes_scope_match,
)
from apps.restrictions.models import Restriction
from apps.workers.models import Worker


def _build_area_caps(restrictions):
    """Replica de la logica de topes por area de _fallback_round_robin."""
    por_nombre = {}
    default = None
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
                k = _norm_area(n)
                por_nombre[k] = min(por_nombre.get(k, th), th)
        else:
            default = th if default is None else min(default, th)
    return por_nombre, default


class Command(BaseCommand):
    help = 'Comprueba si las vacantes de un plan son realmente cubribles.'

    def add_arguments(self, parser):
        parser.add_argument('--scope', type=int, default=0)
        parser.add_argument('--start', type=str, default='')

    def handle(self, *args, **opts):
        ref = WeeklyPlan.objects.filter(scope_entity_id__gt=0).order_by('-start_date').first()
        scope_id = opts['scope'] or (ref.scope_entity_id if ref else 0)
        start = opts['start'] or (ref.start_date.strftime('%Y-%m-%d') if ref else '')
        plan_obj = WeeklyPlan.objects.filter(
            scope_entity_id=scope_id, start_date=start).first()
        if not plan_obj or not plan_obj.plan_json:
            self.stdout.write('no hay plan guardado para esa tienda/semana')
            return

        plan = plan_obj.plan_json
        slots = _get_shift_slots()
        codes = [s['code'] for s in slots]
        labels = {s['code']: s['label'] for s in slots}
        areas = {r.id: str((r.data or {}).get('nombre') or '')
                 for r in EntityRecord.objects.all()}

        # Elegibles de esta tienda, con la MISMA logica que el motor.
        restrictions = list(Restriction.objects.filter(active=True).values(
            'id', 'name', 'engine', 'severity', 'config'))
        rule_sets = []
        for r in restrictions:
            sm = (r.get('config') or {}).get('scopeMatch')
            if r.get('engine') == 'condition' and sm:
                rules = normalize_scope_match_rules(sm)
                if rules:
                    rule_sets.append(rules)
        scope_data = _load_scope_record_data(scope_id)
        caps_por_nombre, cap_default = _build_area_caps(restrictions)

        scope_et = EntityType.objects.filter(is_planning_scope=True).first()
        lf = EntityField.objects.filter(
            entity_type='worker',
            target_entity=scope_et.slug if scope_et else '',
            field_type__in=['entity_select', 'multi_entity_select'],
        ).first()

        elegibles = []
        for w in Worker.objects.filter(active=True):
            cd = w.custom_data or {}
            if rule_sets:
                if not all(worker_passes_scope_match(cd, scope_id, scope_data, rs)
                           for rs in rule_sets):
                    continue
            elif lf and not _worker_matches_scope(cd, lf.key, scope_id):
                continue
            elegibles.append(w)

        # Horas ya asignadas esta semana por trabajador (segun el plan guardado).
        horas = defaultdict(float)
        ocupados = defaultdict(set)          # fecha -> ids
        # Ocupados en OTRAS tiendas la misma semana: nadie esta en dos a la vez.
        for otro in WeeklyPlan.objects.filter(start_date=start).exclude(
                scope_entity_id=scope_id):
            for day in (otro.plan_json or []):
                f = day.get('date')
                for code in codes:
                    for e in (day.get(code) or []):
                        wid = int((e or {}).get('workerId', 0) or 0)
                        if wid > 0:
                            ocupados[f].add(wid)
        por_area_turno = defaultdict(int)    # (fecha, code, area) -> n
        for day in plan:
            fecha = day.get('date')
            for code in codes:
                for e in (day.get(code) or []):
                    wid = int((e or {}).get('workerId', 0) or 0)
                    if wid <= 0:
                        continue
                    ocupados[fecha].add(wid)
                    for a in ((e or {}).get('areas') or []):
                        por_area_turno[(fecha, code, str(a))] += 1
                    try:
                        horas[wid] += _assignment_hours(e) or 0
                    except Exception:
                        pass

        def secciones_de(w):
            out = []
            for s in ((w.custom_data or {}).get('secciones') or []):
                sid = int(s['value']) if isinstance(s, dict) else int(s)
                if sid in areas:
                    out.append(areas[sid])
            return out

        def turnos_de(w):
            cd = w.custom_data or {}
            return [str(cd.get(k)) for k in ('turno_base', 'turno_sabado', 'turno_alternativo')
                    if cd.get(k)]

        self.stdout.write(f'tienda={scope_id} semana={start}')
        self.stdout.write(f'elegibles={len(elegibles)}\n')

        # Secciones que aparecen en el plan.
        secciones = set()
        for day in plan:
            for code in codes:
                for e in (day.get(code) or []):
                    for a in ((e or {}).get('areas') or []):
                        secciones.add(str(a))

        # Turnos que APLICAN a cada dia. Sin esto se contaban como vacantes
        # "Sabado Manana" en lunes o "Refuerzo Navidad" en agosto: celdas que no
        # existen en la parrilla. Se deduce del propio plan: un turno aplica a un
        # dia si alguna tienda tiene gente ahi esa semana.
        aplica = defaultdict(set)          # fecha -> {codes}
        for p in WeeklyPlan.objects.filter(start_date=start):
            for day in (p.plan_json or []):
                f = day.get('date')
                for code in codes:
                    if any(int((e or {}).get('workerId', 0) or 0) > 0
                           for e in (day.get(code) or [])):
                        aplica[f].add(code)

        total_vac = con_cand = sin_cand = bloq_cap = bloq_horas = 0
        for day in plan:
            fecha = day.get('date')
            for code in codes:
                if code not in aplica.get(fecha, set()):
                    continue          # ese turno no se usa ese dia: no es vacante
                entries = day.get(code) or []
                asignados_sec = {str(a) for e in entries
                                 for a in ((e or {}).get('areas') or [])
                                 if int((e or {}).get('workerId', 0) or 0) > 0}
                for sec in sorted(secciones):
                    if sec in asignados_sec:
                        continue
                    total_vac += 1
                    # Candidatos "estilo front"
                    cands = [
                        w for w in elegibles
                        if sec in secciones_de(w)
                        and (not turnos_de(w) or str(code) in turnos_de(w))
                        and w.id not in ocupados[fecha]
                        and not _libra_ese_dia(w, fecha)
                    ]
                    if not cands:
                        sin_cand += 1
                        continue
                    con_cand += 1
                    # ¿El tope por area lo permite?
                    cap = caps_por_nombre.get(_norm_area(sec), cap_default)
                    usado = por_area_turno[(fecha, code, sec)]
                    if cap is not None and usado >= cap:
                        bloq_cap += 1
                        self.stdout.write(
                            f'  {fecha} {labels.get(code, code):<14} {sec:<14} '
                            f'{len(cands):>2} cand -> BLOQUEADO tope area ({usado}/{cap})'
                        )
                        continue
                    self.stdout.write(
                        f'  {fecha} {labels.get(code, code):<14} {sec:<14} '
                        f'{len(cands):>2} cand -> cubrible: '
                        f'{", ".join(w.name.split(",")[0] for w in cands[:3])}'
                    )

        self.stdout.write(
            f'\nvacantes={total_vac}  con candidatos={con_cand}  '
            f'sin nadie={sin_cand}  bloqueadas por tope={bloq_cap}'
        )
        self.stdout.write(
            f'=> realmente cubribles (pasan tope de area): {con_cand - bloq_cap}'
        )
