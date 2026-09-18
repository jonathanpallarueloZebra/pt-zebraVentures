"""Auditoría del generador de turnos: ¿por qué queda gente sin asignar?

Uso:
    python audit_generador.py [--scope 54] [--start 2026-08-03]

Ejecuta el generador real sobre los datos actuales y desglosa, para cada
trabajador y día, el MOTIVO por el que no se le asignó turno. Los motivos
replican exactamente los `continue` de _fallback_round_robin.
"""
import os
import sys
import argparse
from collections import Counter, defaultdict
from datetime import date, timedelta

# La consola de Windows es cp1252 y revienta con acentos/símbolos.
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.planning import schedule_generator as G  # noqa: E402
from apps.dynamic_fields.models import EntityType, EntityRecord  # noqa: E402


def monday_of(d):
    return d - timedelta(days=d.weekday())


def audit(start_date, scope_id):
    print('=' * 78)
    print(f'AUDITORÍA DEL GENERADOR — semana {start_date} · ámbito {scope_id}')
    print('=' * 78)

    # ── 1. Población de partida ────────────────────────────────────────────
    from apps.workers.models import Worker
    from apps.restrictions.models import Restriction

    all_active = Worker.objects.filter(active=True).count()

    # Reproduce el filtrado de scope que hace generate_schedule
    scope_et = EntityType.objects.filter(is_planning_scope=True).first()
    linking = None
    if scope_et:
        from apps.dynamic_fields.models import EntityField
        lf = EntityField.objects.filter(
            entity_type='worker', target_entity=scope_et.slug,
            field_type__in=['entity_select', 'multi_entity_select'],
        ).first()
        linking = lf.key if lf else None

    in_scope = []
    for w in Worker.objects.filter(active=True):
        cd = w.custom_data or {}
        if scope_id and linking:
            if G._worker_matches_scope(cd, linking, scope_id):
                in_scope.append(w)
        else:
            in_scope.append(w)

    print(f'\n1. POBLACIÓN')
    print(f'   Trabajadores activos (total):        {all_active}')
    print(f'   En este ámbito (campo "{linking}"):  {len(in_scope)}')
    if not in_scope:
        print('\n   >>> Nadie pertenece a este ámbito: el plan saldrá vacío.')
        return

    # ── 1b. Ficha de cada trabajador tal y como la LEE el generador ────────
    pills_map, pills_key = G._build_pills_map()
    shift_key = G._get_primary_shift_key()
    rules = G._get_assignment_rules()
    wk = start_date.isocalendar()[1]
    shift_slots = G._get_shift_slots()
    codes = [s['code'] for s in shift_slots]
    labels = {s['code']: s['label'] for s in shift_slots}

    print(f'\n1b. FICHA DE ENTRADA (campos que usa el generador)')
    print(f'    campo turno   = "{shift_key}"')
    print(f'    campo áreas   = "{pills_key}"')
    print(f'    turnos activos: ' + ', '.join(f'{c}={labels[c]}' for c in codes))
    print()
    print(f'    {"#":<4}{"nombre":<32}{"turno ficha":<14}{"->turno real":<14}{"áreas":<28}')
    print(f'    {"-"*4}{"-"*32}{"-"*14}{"-"*14}{"-"*28}')
    sin_turno, sin_area, turno_malo = [], [], []
    for i, w in enumerate(in_scope, 1):
        cd = w.custom_data or {}
        raw = cd.get(shift_key)
        eff = G._resolve_worker_shift_code(cd, shift_key, rules, wk)
        pills = G._resolve_worker_pills(cd, pills_key, pills_map)
        if not raw:
            sin_turno.append(w)
        elif eff not in codes:
            turno_malo.append((w, eff))
        if not pills:
            sin_area.append(w)
        marca = '' if (eff in codes) else '  <-- turno no valido'
        print(f'    {i:<4}{w.name[:31]:<32}{str(raw or "—")[:13]:<14}'
              f'{(labels.get(eff, eff) or "—")[:13]:<14}{(", ".join(pills) or "—")[:27]:<28}{marca}')

    print(f'\n    Resumen de la ficha:')
    print(f'      sin campo "{shift_key}":  {len(sin_turno)}')
    print(f'      con turno inexistente:    {len(turno_malo)}')
    print(f'      sin áreas asignadas:      {len(sin_area)}')

    # ── 2. Ejecutar el generador real ──────────────────────────────────────
    result = G.generate_schedule(start_date, scope_id)
    plan = result.get('plan', [])
    warnings = result.get('warnings', [])

    shift_codes = [s['code'] for s in G._get_shift_slots()]
    shift_labels = {s['code']: s['label'] for s in G._get_shift_slots()}

    # ── 3. Ocupación día a día ─────────────────────────────────────────────
    print(f'\n2. OCUPACIÓN POR DÍA')
    print(f'   {"día":<12} {"fecha":<11} {"asignados":>9} {"descanso":>9}  detalle por turno')
    total_slots = 0
    for d in plan:
        asignados = 0
        detalle = []
        for sc in shift_codes:
            n = len([e for e in d.get(sc, []) if e.get('workerId', 0) > 0])
            asignados += n
            if n:
                detalle.append(f'{shift_labels.get(sc, sc)}={n}')
        total_slots += asignados
        print(f'   {d.get("dayName", ""):<12} {d.get("date", ""):<11} '
              f'{asignados:>9} {len(d.get("rest", [])):>9}  {", ".join(detalle) or "—"}')

    # ── 3b. Traza día a día: quién entra, quién se queda fuera y por qué ──
    print(f'\n2b. TRAZA DÍA A DÍA (asignados vs. disponibles que quedan fuera)')
    ids_scope = {w.id: w.name for w in in_scope}
    for d in plan:
        fecha = d.get('date', '')
        print(f'\n    ── {d.get("dayName","")} {fecha} ──')
        asignados_hoy = {}
        for sc in codes:
            ents = [e for e in d.get(sc, []) if e.get('workerId', 0) > 0]
            if not ents and not d.get(sc):
                continue
            print(f'      {labels.get(sc, sc)} ({len(ents)} asignados):')
            for e in ents:
                areas = ', '.join(e.get('areas') or []) or 'sin área'
                marca = '' if e['workerId'] in ids_scope else '   [FUERA DEL ÁMBITO]'
                print(f'         · {e.get("workerName","?")[:34]:<36} {e.get("start")}-{e.get("end")}  [{areas}]{marca}')
                asignados_hoy[e['workerId']] = sc
        descansan = [ids_scope[i] for i in d.get('rest', []) if i in ids_scope]
        libres = [n for i, n in ids_scope.items() if i not in asignados_hoy and i not in d.get('rest', [])]
        if descansan:
            print(f'      Descanso ({len(descansan)}): ' + ', '.join(n[:22] for n in descansan[:8])
                  + (f' … +{len(descansan)-8}' if len(descansan) > 8 else ''))
        if libres:
            print(f'      >>> SIN ASIGNAR NI DESCANSO ({len(libres)}): '
                  + ', '.join(n[:22] for n in libres[:8])
                  + (f' … +{len(libres)-8}' if len(libres) > 8 else ''))

    # ── 4. Quién no trabaja NINGÚN día ─────────────────────────────────────
    trabajados = Counter()
    for d in plan:
        for sc in shift_codes:
            for e in d.get(sc, []):
                if e.get('workerId', 0) > 0:
                    trabajados[e['workerId']] += 1

    nunca = [w for w in in_scope if trabajados.get(w.id, 0) == 0]
    print(f'\n3. REPARTO SEMANAL')
    print(f'   Asignaciones totales:                {total_slots}')
    print(f'   Trabajadores con ≥1 turno:           {len(in_scope) - len(nunca)}')
    print(f'   Trabajadores SIN NINGÚN turno:       {len(nunca)}')
    if trabajados:
        dist = Counter(trabajados.values())
        print(f'   Distribución (días/semana): ' +
              ', '.join(f'{k}d={v}p' for k, v in sorted(dist.items())))

    # ── 5. Diagnóstico por trabajador sin turnos ───────────────────────────
    if nunca:
        print(f'\n4. LOS {len(nunca)} SIN TURNO — datos que usa el generador')
        pills_map, pills_key = G._build_pills_map()
        shift_key = G._get_primary_shift_key()
        restrictions = list(Restriction.objects.filter(active=True).values(
            'name', 'engine', 'severity', 'config', 'scope_records'))
        rules = G._get_assignment_rules()
        wk = start_date.isocalendar()[1]

        motivos = Counter()
        print(f'   {"nombre":<34} {"turno":<8} {"áreas (pills)":<32} motivo probable')
        for w in nunca[:40]:
            cd = w.custom_data or {}
            pills = G._resolve_worker_pills(cd, pills_key, pills_map)
            sc = G._resolve_worker_shift_code(cd, shift_key, rules, wk)

            if not sc:
                motivo = f'sin "{shift_key}" -> reparto round-robin'
                motivos['sin turno asignado en su ficha'] += 1
            elif sc not in shift_codes:
                motivo = f'turno "{sc}" no existe en el catálogo'
                motivos['turno inexistente'] += 1
            elif not pills:
                motivo = 'sin áreas/secciones -> se asigna sin área'
                motivos['sin áreas definidas'] += 1
            else:
                motivo = 'descartado por tope de área o cupo semanal'
                motivos['tope de área / cupo semanal'] += 1

            print(f'   {w.name[:33]:<34} {str(sc)[:7]:<8} '
                  f'{(", ".join(pills) or "—")[:31]:<32} {motivo}')
        if len(nunca) > 40:
            print(f'   ... y {len(nunca) - 40} más')

        print(f'\n   RESUMEN DE MOTIVOS:')
        for m, c in motivos.most_common():
            print(f'     {c:>4}  {m}')

    # ── 6. Topes de área configurados ──────────────────────────────────────
    print(f'\n5. TOPES QUE LIMITAN LA ASIGNACIÓN')
    restrictions = list(Restriction.objects.filter(active=True).values(
        'name', 'engine', 'severity', 'config'))
    hay = False
    for r in restrictions:
        cfg = r.get('config') or {}
        if r['engine'] == 'count' and cfg.get('groupBy') == 'shift_area' \
                and cfg.get('operator') == 'lte':
            areas = cfg.get('filterAreaNames') or ['(todas)']
            print(f'   [máx por área] {r["name"]}: <= {cfg.get("threshold")} en {areas}')
            hay = True
        if cfg.get('scope') == 'per_week_worker' and cfg.get('operator') == 'lte':
            tf = cfg.get('thresholdField') or '—'
            print(f'   [máx turnos/semana] {r["name"]}: <= {cfg.get("threshold")} '
                  f'(campo dinámico: {tf})')
            hay = True
    if not hay:
        print('   (ninguna restricción de tope activa)')

    # ── 7. Avisos del propio generador ─────────────────────────────────────
    if warnings:
        print(f'\n6. AVISOS DEL GENERADOR ({len(warnings)})')
        for w in warnings[:15]:
            print(f'   - {w}')
        if len(warnings) > 15:
            print(f'   ... y {len(warnings) - 15} más')

    print('\n' + '=' * 78)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--scope', type=int, default=None)
    ap.add_argument('--start', type=str, default=None)
    a = ap.parse_args()

    start = date.fromisoformat(a.start) if a.start else monday_of(date.today())
    start = monday_of(start)

    if a.scope is not None:
        audit(start, a.scope)
    else:
        et = EntityType.objects.filter(is_planning_scope=True).first()
        scopes = list(EntityRecord.objects.filter(entity_type=et).values_list('id', flat=True)) if et else [0]
        print(f'Sin --scope: auditando los {len(scopes)} ámbitos existentes.\n')
        for s in scopes:
            audit(start, s)
