"""Inspecciona los campos de ficha que usa el front para buscar candidatos.

Solo lectura. Sirve para comprobar que el regex /polivalen|seccion|area/ del
front casa con los nombres REALES de los campos, y cuanta gente tiene seccion
secundaria (los candidatos que antes se ignoraban).
"""
from collections import Counter

from django.core.management.base import BaseCommand

from apps.workers.models import Worker


class Command(BaseCommand):
    help = 'Muestra las claves de custom_data relacionadas con seccion/turno.'

    def handle(self, *args, **opts):
        import re
        pat_sec = re.compile(r'polivalen|seccion|secciones|area', re.I)
        pat_turno = re.compile(r'turno', re.I)

        claves = Counter()
        sec_keys = Counter()
        turno_keys = Counter()
        con_multi = 0

        workers = list(Worker.objects.filter(active=True))
        for w in workers:
            cd = w.custom_data or {}
            for k, v in cd.items():
                claves[k] += 1
                if pat_sec.search(k):
                    sec_keys[k] += 1
                    if isinstance(v, list) and len(v) > 1:
                        con_multi += 1
                if pat_turno.search(k):
                    turno_keys[k] += 1

        self.stdout.write(f'trabajadores activos: {len(workers)}')
        self.stdout.write('\n-- claves que casan seccion/polivalencia --')
        for k, n in sec_keys.most_common():
            self.stdout.write(f'  {k}: {n}')
        self.stdout.write('\n-- claves que casan turno --')
        for k, n in turno_keys.most_common():
            self.stdout.write(f'  {k}: {n}')
        self.stdout.write(f'\nfichas con seccion multiple (>1 valor): {con_multi}')

        self.stdout.write('\n-- ejemplo de valores --')
        for w in workers[:3]:
            cd = w.custom_data or {}
            muestra = {k: v for k, v in cd.items()
                       if pat_sec.search(k) or pat_turno.search(k)}
            self.stdout.write(f'  {w.name}: {muestra}')
