"""Prueba de extremo a extremo de la deteccion de plan desactualizado.

Simula lo que hace el usuario: cambiar el turno de un trabajador en su ficha y
comprobar que SU tienda queda marcada como desactualizada y las demas no.

Deja los datos como estaban (revierte el turno y el updated_at al terminar).
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.dynamic_fields.models import EntityField, EntityType
from apps.planning.models import WeeklyPlan
from apps.planning.schedule_generator import _worker_matches_scope
from apps.planning.serializers import WeeklyPlanJSONSerializer, _stale_info
from apps.workers.models import Worker


class Command(BaseCommand):
    help = 'Prueba que editar el turno de una ficha marca solo su tienda.'

    def handle(self, *args, **opts):
        ok = fail = 0

        def check(nombre, cond):
            nonlocal ok, fail
            if cond:
                ok += 1
                self.stdout.write(f'  OK   {nombre}')
            else:
                fail += 1
                self.stdout.write(self.style.ERROR(f'  FALLO {nombre}'))

        # ── Estado de partida ────────────────────────────────────────────────
        planes = list(WeeklyPlan.objects.filter(scope_entity_id__gt=0)
                      .order_by('-start_date')[:8])
        if not planes:
            self.stdout.write('sin planes guardados: nada que probar')
            return

        self.stdout.write('1) Sin tocar nada, ningun plan debe estar desactualizado')
        sucios = [p for p in planes if _stale_info(p)['stale']]
        check(f'ninguno marcado (marcados: {len(sucios)})', not sucios)

        # Tienda objetivo: la del plan mas reciente.
        objetivo = planes[0]
        scope_id = objetivo.scope_entity_id

        # Campo de enlace trabajador -> tienda.
        scope_et = EntityType.objects.filter(is_planning_scope=True).first()
        lf = EntityField.objects.filter(
            entity_type='worker',
            target_entity=scope_et.slug if scope_et else '',
            field_type__in=['entity_select', 'multi_entity_select'],
        ).first()
        if not lf:
            self.stdout.write('sin campo de enlace: no se puede probar')
            return

        victima = None
        for w in Worker.objects.filter(active=True):
            if _worker_matches_scope(w.custom_data or {}, lf.key, scope_id):
                victima = w
                break
        if victima is None:
            self.stdout.write(f'ningun trabajador en scope {scope_id}')
            return

        original_cd = dict(victima.custom_data or {})
        original_upd = victima.updated_at
        base_antes = original_cd.get('turno_base')

        self.stdout.write(
            f'\n2) Cambiando turno_base de "{victima.name}" '
            f'(tienda {scope_id}, turno {base_antes} -> 999)'
        )
        try:
            with transaction.atomic():
                cd = dict(original_cd)
                cd['turno_base'] = 999          # valor cualquiera: solo importa que cambie
                victima.custom_data = cd
                victima.save()                   # auto_now mueve updated_at

                objetivo.refresh_from_db()
                info = _stale_info(objetivo)
                check('su tienda queda marcada', info['stale'])
                check(
                    f'nombra al editado (dice: {info["stale_workers"][:1]})',
                    victima.name in info['stale_workers'],
                )

                otras = [p for p in planes[1:] if p.scope_entity_id != scope_id]
                marcadas = [p.scope_entity_id for p in otras if _stale_info(p)['stale']]
                check(
                    f'las demas tiendas NO se marcan (marcadas: {marcadas})',
                    not marcadas,
                )

                # El serializer debe exponerlo tal cual lo consume el front.
                data = WeeklyPlanJSONSerializer(objetivo).data
                check("el serializer devuelve stale=True", data.get('stale') is True)
                check(
                    'el serializer devuelve stale_workers',
                    bool(data.get('stale_workers')),
                )

                self.stdout.write('\n3) Tras regenerar (plan guardado de nuevo) se limpia')
                objetivo.save()                  # auto_now: plan mas nuevo que la ficha
                objetivo.refresh_from_db()
                check('deja de estar marcado', not _stale_info(objetivo)['stale'])

                raise RuntimeError('rollback')   # nada de esto se queda escrito
        except RuntimeError:
            pass

        # ── Comprobar que no quedo rastro ────────────────────────────────────
        victima.refresh_from_db()
        check(
            f'la ficha vuelve a su turno original ({base_antes})',
            (victima.custom_data or {}).get('turno_base') == base_antes,
        )
        check('el updated_at no quedo movido', victima.updated_at == original_upd)

        self.stdout.write(f'\n{ok} OK, {fail} fallos')
