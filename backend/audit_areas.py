"""Mide cuánta gente pierde turno por el TOPE DE ÁREA y cuántos se podrían
recolocar en otra de sus áreas con hueco.

Replica el bucle de asignación de _fallback_round_robin sin modificarlo, y en
el punto donde el generador manda a descanso por área llena, comprueba si el
trabajador tenía OTRA área elegible con plaza libre.
"""
import os
import sys
from collections import Counter
from datetime import date, timedelta

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402
django.setup()

from apps.planning import schedule_generator as G  # noqa: E402
from apps.dynamic_fields.models import EntityType, EntityRecord  # noqa: E402


def medir(start_date, scope_id):
    """Cuenta, día a día y turno a turno, los descartes por área llena."""
    from apps.restrictions.models import Restriction
    from apps.workers.models import Worker

    restrictions = list(Restriction.objects.filter(active=True).values(
        'id', 'name', 'engine', 'config', 'severity', 'scope_records'))

    # Topes por área (misma lógica que el generador)
    def norm(s):
        import unicodedata
        return ''.join(c for c in unicodedata.normalize('NFD', str(s or '').lower().strip())
                       if unicodedata.category(c) != 'Mn')
    cap_default, cap_by_name = None, {}
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
                cap_by_name[norm(n)] = min(cap_by_name.get(norm(n), th), th)
        else:
            cap_default = th if cap_default is None else min(cap_default, th)

    def cap_of(area):
        s = cap_by_name.get(norm(area))
        return s if s is not None else cap_default

    # Generar el plan real
    result = G.generate_schedule(start_date, scope_id)
    plan = result.get('plan', [])
    slots = G._get_shift_slots()
    labels = {s['code']: s['label'] for s in slots}
    codes = [s['code'] for s in slots]

    # Población elegible con sus áreas
    pills_map, pills_key = G._build_pills_map()
    linking = None
    scope_et = EntityType.objects.filter(is_planning_scope=True).first()
    if scope_et:
        from apps.dynamic_fields.models import EntityField
        lf = EntityField.objects.filter(
            entity_type='worker', target_entity=scope_et.slug,
            field_type__in=['entity_select', 'multi_entity_select']).first()
        linking = lf.key if lf else None

    workers = []
    for w in Worker.objects.filter(active=True):
        workers.append({'id': w.id, 'name': w.name, 'customData': w.custom_data or {},
                        'pills': G._resolve_worker_pills(w.custom_data or {}, pills_key, pills_map)})
    if scope_id:
        workers = G._filter_workers_by_eligibility(workers, scope_id, restrictions, linking)
    by_id = {w['id']: w for w in workers}

    print(f'\n{"="*76}')
    print(f'IMPACTO DEL TOPE POR ÁREA — semana {start_date} · ámbito {scope_id}')
    print(f'{"="*76}')
    print(f'Elegibles: {len(workers)} · tope por defecto: {cap_default} · '
          f'específicos: { {k: v for k, v in cap_by_name.items()} }')

    total_libres = 0
    total_recolocables = 0
    detalle_areas = Counter()

    for d in plan:
        fecha = d.get('date')
        asignados_hoy = set()
        ocupacion = {}   # (shift, area_norm) -> n
        for sc in codes:
            for e in d.get(sc, []):
                if e.get('workerId', 0) > 0:
                    asignados_hoy.add(e['workerId'])
                    for a in (e.get('areas') or []):
                        ocupacion[(sc, norm(a))] = ocupacion.get((sc, norm(a)), 0) + 1

        # ¿Hay turnos operativos hoy?
        turnos_hoy = [sc for sc in codes if d.get(sc)]
        if not turnos_hoy:
            continue

        # Gente que no trabaja hoy y NO está de baja/ausencia
        rest = set(d.get('rest', []))
        libres = [wid for wid in by_id if wid not in asignados_hoy]
        # De esos, quién tendría hueco en alguna de SUS áreas
        recolocables = []
        for wid in libres:
            w = by_id[wid]
            for sc in turnos_hoy:
                hueco = False
                for area in (w['pills'] or []):
                    c = cap_of(area)
                    if c is None or ocupacion.get((sc, norm(area)), 0) < c:
                        hueco = True
                        detalle_areas[area] += 1
                        break
                if hueco:
                    recolocables.append(wid)
                    break

        total_libres += len(libres)
        total_recolocables += len(recolocables)
        print(f'\n  {d.get("dayName",""):<10} {fecha}  '
              f'asignados={len(asignados_hoy):<3} libres={len(libres):<3} '
              f'de ellos con hueco en su área={len(recolocables)}')
        if recolocables:
            nombres = [by_id[i]['name'][:26] for i in recolocables[:6]]
            print(f'             podrían entrar: ' + ', '.join(nombres)
                  + (f' … +{len(recolocables)-6}' if len(recolocables) > 6 else ''))
        # Ocupación por área de cada turno
        for sc in turnos_hoy:
            occ = [(a, n) for (s, a), n in ocupacion.items() if s == sc]
            if occ:
                txt = ', '.join(f'{a}={n}/{cap_of(a) or "∞"}' for a, n in sorted(occ))
                print(f'             {labels.get(sc, sc)}: {txt}')

    print(f'\n{"-"*76}')
    print(f'TOTAL SEMANA: {total_libres} huecos persona-día sin asignar; '
          f'{total_recolocables} tenían plaza libre en alguna de sus áreas.')
    if total_libres:
        pct = 100 * total_recolocables / total_libres
        print(f'  -> el {pct:.0f}% de los no asignados PODRÍA haber entrado.')
        print(f'  -> el resto ({total_libres - total_recolocables}) está bloqueado por '
              f'tope de área lleno en todas sus secciones, cupo semanal o ausencia.')
    print(f'{"="*76}')


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--scope', type=int, required=True)
    ap.add_argument('--start', type=str, required=True)
    a = ap.parse_args()
    d = date.fromisoformat(a.start)
    medir(d - timedelta(days=d.weekday()), a.scope)
