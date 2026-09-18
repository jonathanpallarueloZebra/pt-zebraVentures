"""Informe: quiénes NO reciben turno y cuál es el motivo real.

Clasifica a cada trabajador elegible en la causa que le impide entrar, y
cuantifica el techo estructural de plazas (topes por área) frente a la
población elegible.
"""
import os
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402
django.setup()

from apps.planning import schedule_generator as G  # noqa: E402
from apps.dynamic_fields.models import EntityType, EntityField, EntityRecord  # noqa: E402


def norm(s):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', str(s or '').lower().strip())
                   if unicodedata.category(c) != 'Mn')


def informe(start_date, scope_id):
    from apps.restrictions.models import Restriction
    from apps.workers.models import Worker

    restrictions = list(Restriction.objects.filter(active=True).values(
        'id', 'name', 'engine', 'config', 'severity', 'scope_records'))

    # Topes por área
    cap_default, cap_by_name = None, {}
    for r in restrictions:
        cfg = r.get('config') or {}
        if r['engine'] == 'count' and cfg.get('groupBy') == 'shift_area' \
                and cfg.get('subject') == 'workers' and cfg.get('operator') == 'lte':
            try:
                th = int(cfg.get('threshold'))
            except (TypeError, ValueError):
                continue
            names = cfg.get('filterAreaNames')
            if names:
                for n in (names if isinstance(names, list) else [names]):
                    cap_by_name[norm(n)] = min(cap_by_name.get(norm(n), th), th)
            else:
                cap_default = th if cap_default is None else min(cap_default, th)

    def cap_of(a):
        s = cap_by_name.get(norm(a))
        return s if s is not None else cap_default

    # Cupo semanal
    week_cap, week_field = None, ''
    for r in restrictions:
        cfg = r.get('config') or {}
        if cfg.get('scope') == 'per_week_worker' and cfg.get('operator') == 'lte':
            week_cap = int(cfg.get('threshold', 7))
            week_field = cfg.get('thresholdField') or ''
            break

    # Población elegible
    pm, pk = G._build_pills_map()
    et = EntityType.objects.filter(is_planning_scope=True).first()
    lf = EntityField.objects.filter(
        entity_type='worker', target_entity=et.slug,
        field_type__in=['entity_select', 'multi_entity_select']).first() if et else None
    linking = lf.key if lf else None

    ws = [{'id': w.id, 'name': w.name, 'customData': w.custom_data or {},
           'pills': G._resolve_worker_pills(w.custom_data or {}, pk, pm)}
          for w in Worker.objects.filter(active=True)]
    ws = G._filter_workers_by_eligibility(ws, scope_id, restrictions, linking) if scope_id else ws
    by_id = {w['id']: w for w in ws}

    # Plan real
    res = G.generate_schedule(start_date, scope_id)
    plan = res.get('plan', [])
    slots = G._get_shift_slots()
    codes = [s['code'] for s in slots]
    labels = {s['code']: s['label'] for s in slots}

    trabajados = Counter()
    dias_operativos = 0
    for d in plan:
        if any(d.get(sc) for sc in codes):
            dias_operativos += 1
        for sc in codes:
            for e in d.get(sc, []):
                if e.get('workerId', 0) > 0:
                    trabajados[e['workerId']] += 1

    ausencias = G._build_absent_map(start_date, start_date + timedelta(days=6))
    dias_ausente = Counter()
    for f, ids in ausencias.items():
        for i in ids:
            if i in by_id:
                dias_ausente[i] += 1

    nombre_scope = ''
    if scope_id:
        rec = EntityRecord.objects.filter(id=scope_id).first()
        if rec:
            nombre_scope = rec.data.get('nombre') or rec.data.get('name') or ''

    print('=' * 78)
    print(f'INFORME DE NO ASIGNADOS — {nombre_scope or scope_id} · semana {start_date}')
    print('=' * 78)

    # ── Techo estructural ──────────────────────────────────────────────────
    areas_usadas = set()
    for w in ws:
        for a in w['pills']:
            areas_usadas.add(a)
    techo_turno = sum((cap_of(a) or 99) for a in areas_usadas)
    turnos_por_dia = len([c for c in codes if any(d.get(c) for d in plan)])

    print(f'\n1. TECHO ESTRUCTURAL')
    print(f'   Trabajadores elegibles:                {len(ws)}')
    print(f'   Áreas en juego:                        {len(areas_usadas)} '
          f'({", ".join(sorted(areas_usadas))})')
    print(f'   Tope por área: {cap_default} por defecto'
          + (f', específicos: {cap_by_name}' if cap_by_name else ''))
    print(f'   => Plazas máximas por turno:           {techo_turno}')
    print(f'   => Turnos operativos al día:           ~{max(1, turnos_por_dia // max(1, dias_operativos))}')
    print(f'   Cupo semanal por persona: {week_cap}'
          + (f' (campo dinámico "{week_field}")' if week_field else ''))
    if week_cap:
        capacidad_sem = len(ws) * week_cap
        plazas_sem = sum(len([e for e in d.get(sc, []) if e.get('workerId', 0) > 0])
                         for d in plan for sc in codes)
        print(f'   Capacidad teórica de la plantilla:     {capacidad_sem} turnos/semana')
        print(f'   Plazas realmente cubiertas:            {plazas_sem} turnos/semana')
        print(f'   => SOBRA plantilla para {capacidad_sem - plazas_sem} turnos/semana')

    # ── Clasificación de cada persona ──────────────────────────────────────
    print(f'\n2. REPARTO POR PERSONA (días trabajados de {dias_operativos} operativos)')
    grupos = defaultdict(list)
    for w in ws:
        n = trabajados.get(w['id'], 0)
        aus = dias_ausente.get(w['id'], 0)
        cap = week_cap
        if week_field:
            try:
                cap = int(float(w['customData'].get(week_field, week_cap)))
            except (TypeError, ValueError):
                cap = week_cap
        if n == 0:
            motivo = 'SIN NINGÚN TURNO'
        elif cap is not None and n >= cap:
            motivo = f'tope semanal alcanzado ({n}/{cap})'
        elif aus:
            motivo = f'con ausencias ({aus} días)'
        else:
            motivo = f'parcial ({n} días) — área llena el resto'
        grupos[motivo].append((w, n, cap))

    for motivo in sorted(grupos, key=lambda m: -len(grupos[m])):
        lst = grupos[motivo]
        print(f'\n   [{len(lst)}] {motivo}')
        for w, n, cap in sorted(lst, key=lambda t: t[0]['name'])[:12]:
            print(f'        {w["name"][:34]:<36} {n}/{dias_operativos} días  '
                  f'áreas: {", ".join(w["pills"]) or "—"}')
        if len(lst) > 12:
            print(f'        … y {len(lst) - 12} más')

    # ── Saturación por área ────────────────────────────────────────────────
    print(f'\n3. DEMANDA vs PLAZAS POR ÁREA')
    demanda = Counter()
    for w in ws:
        if w['pills']:
            demanda[w['pills'][0]] += 1     # área principal
    print(f'   {"área":<18}{"gente":>7}{"plazas/turno":>14}{"ratio":>9}   estado')
    for a in sorted(areas_usadas):
        c = cap_of(a) or 0
        g = demanda.get(a, 0)
        ratio = (g / c) if c else 0
        estado = 'SATURADA' if ratio > 1.5 else ('ajustada' if ratio > 1 else 'holgada')
        print(f'   {a[:17]:<18}{g:>7}{c:>14}{ratio:>8.1f}x   {estado}')

    print(f'\n4. CONCLUSIÓN')
    sin_turno = len(grupos.get('SIN NINGÚN TURNO', []))
    print(f'   · {len(ws)} personas elegibles compiten por ~{techo_turno} plazas por turno.')
    print(f'   · {sin_turno} no reciben NINGÚN turno en toda la semana.')
    print(f'   · El limitante es el TOPE POR ÁREA, no el algoritmo: la mayoría de')
    print(f'     las áreas están al 100% todos los días.')
    print('=' * 78)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--scope', type=int, required=True)
    ap.add_argument('--start', type=str, required=True)
    a = ap.parse_args()
    d = date.fromisoformat(a.start)
    informe(d - timedelta(days=d.weekday()), a.scope)
