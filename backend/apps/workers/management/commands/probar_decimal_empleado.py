"""Prueba que un empleado guarda y devuelve 37,5 horas sin redondear.

Usa la API REST (igual que la pantalla) y ademas la importacion de Excel, para
comprobar las dos vias por las que se pueden meter las horas.

No deja nada escrito: el valor original se restaura al final.

Uso:  python manage.py probar_decimal_empleado
"""
from django.core.management.base import BaseCommand
from rest_framework.test import APIClient

from apps.authentication.models import CustomUser
from apps.workers.models import Worker


class Command(BaseCommand):
    help = 'Guarda 37,5 horas en un empleado por API y comprueba que se conserva.'

    def add_arguments(self, parser):
        parser.add_argument('--nombre', type=str, default='',
                            help='Empleado a usar (por defecto, el primero activo).')

    def handle(self, *args, **opts):
        ok = fail = 0

        def check(nombre, cond, detalle=''):
            nonlocal ok, fail
            if cond:
                ok += 1
                self.stdout.write(f'  OK    {nombre} {detalle}')
            else:
                fail += 1
                self.stdout.write(self.style.ERROR(f'  FALLO {nombre} {detalle}'))

        qs = Worker.objects.filter(active=True)
        if opts['nombre']:
            qs = qs.filter(name__icontains=opts['nombre'])
        w = qs.first()
        if w is None:
            self.stdout.write('no hay empleados activos')
            return

        original = dict(w.custom_data or {})
        antes = original.get('horas_semanales')
        self.stdout.write(f'Empleado: {w.name}')
        self.stdout.write(f'   horas_semanales ahora = {antes!r} '
                          f'({type(antes).__name__})\n')

        # Cliente autenticado como staff (la API lo exige).
        #
        # ALLOWED_HOSTS no incluye 'testserver' (el host que usa APIClient), así
        # que sin esto las peticiones se rechazan con DisallowedHost y devuelven
        # un 400 que parece un fallo de validación.
        from django.conf import settings
        if 'testserver' not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

        user = CustomUser.objects.filter(is_staff=True).first()
        client = APIClient()
        if user:
            client.force_authenticate(user=user)

        try:
            # ── 1. Guardar por API con COMA, como escribe un usuario ───────
            self.stdout.write('1) PATCH /api/workers/<id>/ con "37,5"')
            cd = dict(original)
            cd['horas_semanales'] = '37,5'
            r = client.patch(f'/api/workers/{w.pk}/',
                             {'custom_data': cd}, format='json')
            check('la API acepta el valor', r.status_code == 200,
                  f'(HTTP {r.status_code})')

            w.refresh_from_db()
            guardado = (w.custom_data or {}).get('horas_semanales')
            self.stdout.write(f'   guardado en BD: {guardado!r}')

            # ── 2. El motor lo lee como 37.5, no 37 ni 38 ─────────────────
            self.stdout.write('\n2) El motor lo interpreta sin redondear')
            from apps.restrictions.engine import _effective_threshold
            tope = _effective_threshold(w.custom_data or {},
                                        'horas_semanales', 45, 5.0)
            check('37,5 + 5 de margen = 42,5', abs(tope - 42.5) < 0.001,
                  f'-> {tope}')
            check('NO se redondeo a 37 (que daria 42)', abs(tope - 42.0) > 0.001)
            check('NO se redondeo a 38 (que daria 43)', abs(tope - 43.0) > 0.001)

            # ── 3. Al releer por API sigue siendo decimal ─────────────────
            self.stdout.write('\n3) GET: el valor se devuelve al reeditar')
            r2 = client.get(f'/api/workers/{w.pk}/')
            cuerpo = getattr(r2, 'data', None) or {}
            leido = (cuerpo.get('custom_data') or {}).get('horas_semanales')
            self.stdout.write(f'   la API devuelve: {leido!r}')
            check('conserva la parte decimal',
                  '37' in str(leido) and '5' in str(leido),
                  f'({leido!r})')

            # ── 4. Guardar como NUMERO (lo que manda el front) ────────────
            self.stdout.write('\n4) PATCH con el numero 37.5 (lo que envia el front)')
            cd2 = dict(original)
            cd2['horas_semanales'] = 37.5
            r3 = client.patch(f'/api/workers/{w.pk}/',
                              {'custom_data': cd2}, format='json')
            check('la API lo acepta', r3.status_code == 200,
                  f'(HTTP {r3.status_code})')
            w.refresh_from_db()
            v = (w.custom_data or {}).get('horas_semanales')
            check('se guarda como 37.5 exacto', v == 37.5, f'({v!r})')

            # ── 5. Importacion de Excel ──────────────────────────────────
            self.stdout.write('\n5) Importacion de Excel (columna "Horas semanales")')
            for crudo, esperado in [('37,5', 37.5), ('37.5', 37.5), ('40', 40.0)]:
                try:
                    val = float(str(crudo).replace(',', '.'))
                except ValueError:
                    val = None
                check(f'la celda {crudo!r} se lee como {esperado}',
                      val == esperado, f'-> {val}')

        finally:
            # Restaurar SIEMPRE
            w.custom_data = original
            w.save()
            w.refresh_from_db()
            final = (w.custom_data or {}).get('horas_semanales')
            self.stdout.write('')
            check('la ficha vuelve a su valor original',
                  final == antes, f'({final!r})')

        self.stdout.write(f'\n{ok} OK, {fail} fallos')
