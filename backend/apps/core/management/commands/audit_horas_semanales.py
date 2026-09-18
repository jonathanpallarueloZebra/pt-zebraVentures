"""Audita el campo de contrato 'horas_semanales' tras importar el Excel.

El parser de números acepta 40, 40.5 y "40", pero un valor vacío, un texto o un
0 caen al contrato por defecto (40 h) EN SILENCIO: el sistema aparenta funcionar
mientras media plantilla se compara contra un contrato ficticio. Este comando
saca a la luz esos casos.

    python manage.py audit_horas_semanales
    python manage.py audit_horas_semanales --solo-problemas
    python manage.py audit_horas_semanales --csv huecos.csv
"""
from django.core.management.base import BaseCommand

from apps.workers.models import Worker

CONTRACT_FIELD = 'horas_semanales'
DEFAULT_CONTRACT_HOURS = 40.0

# Rango plausible para un contrato semanal. Fuera de esto casi siempre es un
# error de tecleo (4 en vez de 40, o 400 en vez de 40).
MIN_PLAUSIBLE = 1.0
MAX_PLAUSIBLE = 60.0


def classify(worker):
    """Devuelve (estado, valor_crudo, horas_efectivas) para un trabajador."""
    raw = (worker.custom_data or {}).get(CONTRACT_FIELD)

    if raw is None or str(raw).strip() == '':
        return 'VACIO', raw, DEFAULT_CONTRACT_HOURS
    try:
        value = float(str(raw).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return 'NO_NUMERICO', raw, DEFAULT_CONTRACT_HOURS
    if value <= 0:
        return 'CERO_O_NEGATIVO', raw, DEFAULT_CONTRACT_HOURS
    if value < MIN_PLAUSIBLE or value > MAX_PLAUSIBLE:
        return 'FUERA_DE_RANGO', raw, value
    return 'OK', raw, value


class Command(BaseCommand):
    help = "Audita 'horas_semanales' de los trabajadores tras importar el Excel."

    def add_arguments(self, parser):
        parser.add_argument('--solo-problemas', action='store_true',
                            help='Lista solo los trabajadores con el campo mal o vacío.')
        parser.add_argument('--csv', metavar='RUTA',
                            help='Escribe el detalle en un CSV (para mandárselo al cliente).')

    def handle(self, *args, **options):
        workers = list(Worker.objects.filter(active=True).order_by('name'))
        if not workers:
            self.stdout.write(self.style.WARNING('No hay trabajadores activos.'))
            return

        buckets = {}
        rows = []
        for w in workers:
            estado, raw, horas = classify(w)
            buckets.setdefault(estado, []).append(w)
            rows.append((w.id, w.name, estado, '' if raw is None else str(raw), horas))

        total = len(workers)
        ok = len(buckets.get('OK', []))
        problemas = total - ok

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Auditoria de "{CONTRACT_FIELD}" - {total} trabajadores activos'))
        self.stdout.write('')

        # Texto ASCII a proposito: la consola de Windows (cp1252) revienta con
        # flechas y comillas tipograficas al escribir por stdout.
        etiquetas = [
            ('OK', 'Correcto', self.style.SUCCESS),
            ('VACIO', f'Vacio -> usa {DEFAULT_CONTRACT_HOURS:g} h por defecto', self.style.ERROR),
            ('NO_NUMERICO', f'No numerico -> usa {DEFAULT_CONTRACT_HOURS:g} h por defecto', self.style.ERROR),
            ('CERO_O_NEGATIVO', f'Cero/negativo -> usa {DEFAULT_CONTRACT_HOURS:g} h por defecto', self.style.ERROR),
            ('FUERA_DE_RANGO', f'Fuera de rango ({MIN_PLAUSIBLE:g}-{MAX_PLAUSIBLE:g} h) -> revisar', self.style.WARNING),
        ]
        for clave, texto, estilo in etiquetas:
            n = len(buckets.get(clave, []))
            if n:
                self.stdout.write(f'  {estilo(f"{n:>4}")}  {texto}')

        if options['solo_problemas'] or problemas:
            detalle = [r for r in rows if r[2] != 'OK']
            if detalle:
                self.stdout.write('')
                self.stdout.write(self.style.MIGRATE_HEADING('Detalle:'))
                for wid, name, estado, raw, _horas in detalle[:60]:
                    valor = f' (valor: "{raw}")' if raw else ''
                    self.stdout.write(f'  #{wid:<5} {name[:38]:<40} {estado}{valor}')
                if len(detalle) > 60:
                    self.stdout.write(f'  ... y {len(detalle) - 60} mas (usa --csv para el listado completo)')

        if options['csv']:
            import csv
            with open(options['csv'], 'w', newline='', encoding='utf-8-sig') as fh:
                writer = csv.writer(fh, delimiter=';')
                writer.writerow(['id', 'nombre', 'estado', 'valor_excel', 'horas_efectivas'])
                writer.writerows(rows)
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(f'CSV escrito en {options["csv"]}'))

        self.stdout.write('')
        if problemas:
            self.stdout.write(self.style.ERROR(
                f'{problemas} de {total} trabajadores NO tienen un contrato valido. '
                f'Se les aplicara {DEFAULT_CONTRACT_HOURS:g} h y el control de horas extra '
                f'no sera fiable para ellos.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Los {total} trabajadores tienen horas de contrato validas.'))
