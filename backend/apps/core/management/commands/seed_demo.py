# -*- coding: utf-8 -*-
"""Seed de la empresa DEMO «VESTIA Moda» — cadena ficticia de retail de moda.

Monta una instalación completa para enseñar el producto con TODAS sus
posibilidades: catálogos, tiendas (ámbito), secciones (pills), turnos con días
operativos (apertura, cierre y domingo comercial),
~35 empleados con polivalencia/contratos por horas/volantes/ETT, reglas de
rotación, las restricciones de los 5 motores, días de cierre, ausencias en los
tres estados y los planes de la semana actual y la siguiente de la primera
tienda (VGV), ya hechos y sin avisos. El resto de tiendas arranca sin planificar.

NO lo ejecuta `migrate`. Uso:

    python manage.py seed_demo            # crea todo (idempotente)
    python manage.py seed_demo --reset    # borra los datos demo y los recrea

Las fechas son relativas a HOY, así la demo nunca caduca.
"""
import datetime as dt

from django.core.management.base import BaseCommand

DEMO = {"_demo": True}  # marca en custom_data/data para poder resetear

ZONAS = [
    ("madrid_centro", "Madrid Centro", "#0EA5E9"),
    ("madrid_norte", "Madrid Norte", "#8B5CF6"),
    ("madrid_sur", "Madrid Sur", "#F59E0B"),
    ("zaragoza", "Zaragoza", "#10B981"),
]
CONTRATOS = [
    ("plantilla", "Plantilla fija"),
    ("volante", "Volante (cubre su zona)"),
    ("ett", "ETT"),
]
TIENDAS = [
    # codigo, nombre, zona, centro comercial
    ("VGV", "VESTIA Gran Vía", "madrid_centro", "Calle (flagship, abre domingos)"),
    ("VPN", "VESTIA Plaza Norte", "madrid_norte", "CC Plaza Norte 2"),
    ("VXA", "VESTIA Xanadú", "madrid_sur", "CC Xanadú"),
    ("VOG", "VESTIA Outlet Getafe", "madrid_sur", "Parque Nassica"),
    ("VZA", "VESTIA Puerto Venecia", "zaragoza", "CC Puerto Venecia"),
]
SECCIONES = ["Caja", "Probadores", "Planta Mujer", "Planta Hombre",
             "Niño", "Almacén", "Visual", "Encargado"]

SHIFTS = [
    # nombre, inicio, fin, weekdays (0=L .. 6=D)
    # Solo los turnos que usa la tienda con planificación: la pantalla pinta
    # TODOS los turnos en la parrilla de la tienda abierta y avisa de «falta
    # plantilla» por cada uno que nadie cubre, así que un turno de otra tienda
    # (partido, nocturno, horario especial) bastaba para que VGV no saliera limpia.
    ("Apertura", dt.time(9, 30), dt.time(16, 30), [0, 1, 2, 3, 4, 5]),
    ("Cierre", dt.time(15, 30), dt.time(22, 30), [0, 1, 2, 3, 4, 5]),
    ("Domingo Comercial", dt.time(11, 0), dt.time(21, 0), [6]),
]

WORKER_FIELDS = [
    dict(key="zona", label="Zona", field_type="catalog_select", kind_code="zona_movilidad",
         show_in_list=True, show_as_filter=True, order=1),
    dict(key="tienda", label="Tienda", field_type="entity_select", target_entity="tienda",
         show_in_list=True, order=2,
         depends_on="zona", depends_on_field="zona",
         help_text="Se filtra por la zona elegida. Vacío para volantes y ETT (cubren su zona)"),
    dict(key="secciones", label="Secciones (orden = prioridad)", field_type="multi_entity_select",
         target_entity="seccion", allow_priority=True, order=3,
         help_text="La primera sección es su puesto principal; el resto, polivalencia"),
    dict(key="tipo_contrato", label="Tipo de contrato", field_type="catalog_select",
         kind_code="tipo_contrato", show_in_list=True, order=4),
    dict(key="horas_semanales", label="Horas semanales", field_type="number",
         default_value="40", order=5, help_text="Contrato: 20/24/30/40h. Umbral del tope de horas"),
    dict(key="rotacion", label="Rotación", field_type="select",
         options=["fijo", "semanal"], order=6),
    dict(key="jornada_reducida", label="Jornada reducida", field_type="boolean", order=7),
    dict(key="turnos_max_semana", label="Turnos máx./semana", field_type="number", order=8,
         help_text="Tope individual de turnos (parciales). Vacío = tope general"),
    dict(key="nivel", label="Nivel", field_type="select",
         options=["encargado", "segundo", "dependiente", "visual", "almacen"], order=9),
    dict(key="proveedor_ett", label="Proveedor ETT", field_type="select",
         options=["Adecco", "Randstad", "Manpower"], order=10,
         visible_when_field="tipo_contrato", visible_when_value="ett"),
    dict(key="turno_base", label="Turno base", field_type="entity_select",
         target_entity="shift", order=11),
    dict(key="turno_alternativo", label="Turno alternativo", field_type="entity_select",
         target_entity="shift", order=12,
         visible_when_field="rotacion", visible_when_value="semanal",
         help_text="Con rotación semanal: cada semana alterna con el turno base"),
    dict(key="turno_sabado", label="Turno de sábado", field_type="entity_select",
         target_entity="shift", order=13,
         help_text="Si se define, el sábado la persona pasa a este turno (regla weekday)"),
]

# nombre, tienda, zona, secciones, contrato, horas, rotacion, base, alt, extras
PLANTILLA = [
    # ── VGV · Gran Vía (flagship) ────────────────────────────────────────
    # Dos fijos por sección (uno de Apertura y otro de Cierre, 40h, de lunes a
    # viernes): son los 16 que dejan las 80 celdas sección×turno×día cubiertas.
    ("Carmen Roca", "VGV", "madrid_centro", ["Encargado", "Caja"], "plantilla", 40,
     "fijo", "Apertura", None, {"nivel": "encargado"}),
    ("Iván Soler", "VGV", "madrid_centro", ["Encargado", "Planta Hombre"], "plantilla", 40,
     "fijo", "Cierre", None, {"nivel": "segundo"}),
    ("Nuria Bailo", "VGV", "madrid_centro", ["Caja", "Probadores"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Alba Cortés", "VGV", "madrid_centro", ["Caja", "Niño"], "plantilla", 40,
     "fijo", "Cierre", None, {"pref": "Cierre"}),
    ("Lara Peiró", "VGV", "madrid_centro", ["Probadores", "Caja"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Hugo Zalba", "VGV", "madrid_centro", ["Probadores", "Planta Hombre"], "plantilla", 40,
     "fijo", "Cierre", None, {}),
    ("Sonia Vidal", "VGV", "madrid_centro", ["Planta Mujer", "Probadores"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Elsa Marín", "VGV", "madrid_centro", ["Planta Mujer", "Caja"], "plantilla", 40,
     "fijo", "Cierre", None, {}),
    ("Óscar Pina", "VGV", "madrid_centro", ["Planta Hombre", "Almacén"], "plantilla", 40,
     "fijo", "Apertura", None, {"pref": "Apertura"}),
    ("Rafa Tello", "VGV", "madrid_centro", ["Planta Hombre", "Caja"], "plantilla", 40,
     "fijo", "Cierre", None, {}),
    ("Julia Andreu", "VGV", "madrid_centro", ["Niño", "Probadores"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Lidia Mena", "VGV", "madrid_centro", ["Niño", "Caja"], "plantilla", 40,
     "fijo", "Cierre", None, {}),
    ("Mario Gracia", "VGV", "madrid_centro", ["Almacén", "Planta Hombre"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Gabi Noval", "VGV", "madrid_centro", ["Almacén", "Planta Hombre"], "plantilla", 40,
     "fijo", "Cierre", None, {}),
    ("Diego Antúnez", "VGV", "madrid_centro", ["Visual", "Planta Hombre"], "plantilla", 40,
     "fijo", "Apertura", None, {"nivel": "visual"}),
    ("Inma Castán", "VGV", "madrid_centro", ["Visual", "Planta Mujer"], "plantilla", 40,
     "fijo", "Cierre", None, {}),
    # Refuerzos de fin de semana (la parrilla solo pinta lunes a viernes).
    ("Teo Lasheras", "VGV", "madrid_centro", ["Caja"], "plantilla", 24,
     "fijo", "Apertura", None, {"jornada_reducida": True, "turnos_max_semana": 3}),
    ("Aroa Pinilla (findes)", "VGV", "madrid_centro", ["Caja", "Probadores"], "plantilla", 20,
     "fijo", "Domingo Comercial", None,
     {"jornada_reducida": True, "nota": "equipo de domingos del flagship"}),
    ("Nico Bes (findes)", "VGV", "madrid_centro", ["Planta Hombre", "Caja"], "plantilla", 20,
     "fijo", "Domingo Comercial", None,
     {"jornada_reducida": True, "nota": "equipo de domingos del flagship"}),
    # ── VPN · Plaza Norte ────────────────────────────────────────────────
    ("Berta Lain", "VPN", "madrid_norte", ["Encargado", "Caja"], "plantilla", 40,
     "semanal", "Apertura", "Cierre", {"nivel": "encargado"}),
    ("Raúl Denia", "VPN", "madrid_norte", ["Encargado", "Almacén"], "plantilla", 40,
     "semanal", "Cierre", "Apertura", {"nivel": "segundo"}),
    ("Aitana Buera", "VPN", "madrid_norte", ["Caja", "Probadores"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Leire Campo", "VPN", "madrid_norte", ["Planta Mujer", "Niño"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Pau Ginés", "VPN", "madrid_norte", ["Caja", "Planta Hombre"], "plantilla", 30,
     "fijo", "Cierre", None, {"turnos_max_semana": 4}),
    ("Vera Otal", "VPN", "madrid_norte", ["Probadores", "Planta Mujer"], "plantilla", 20,
     "fijo", "Cierre", None, {"jornada_reducida": True, "turnos_max_semana": 2}),
    ("Diego Used", "VPN", "madrid_norte", ["Almacén", "Visual"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Alba Sierra", "VPN", "madrid_norte", ["Visual", "Planta Mujer"], "plantilla", 40,
     "semanal", "Cierre", "Apertura", {}),
    ("Jon Alastuey", "VPN", "madrid_norte", ["Niño", "Probadores"], "plantilla", 40,
     "fijo", "Cierre", None, {}),
    ("Rocío Pardo", "VPN", "madrid_norte", ["Caja", "Almacén"], "plantilla", 40,
     "semanal", "Apertura", "Cierre", {}),
    ("Nacho Vera", "VPN", "madrid_norte", ["Planta Hombre", "Visual"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Mar Clavería", "VPN", "madrid_norte", ["Caja", "Niño"], "ett", 20,
     "fijo", "Cierre", None, {"turnos_max_semana": 3}),
    # ── VXA · Xanadú ─────────────────────────────────────────────────────
    ("Gema Puértolas", "VXA", "madrid_sur", ["Encargado", "Caja"], "plantilla", 40,
     "semanal", "Apertura", "Cierre", {"nivel": "encargado"}),
    ("Héctor Bara", "VXA", "madrid_sur", ["Encargado", "Planta Hombre"], "plantilla", 40,
     "semanal", "Cierre", "Apertura", {"nivel": "segundo"}),
    ("Noa Ferrández", "VXA", "madrid_sur", ["Caja", "Probadores"], "plantilla", 40,
     "fijo", "Apertura", None, {"incompatible": "Ciro Laguna"}),
    ("Ciro Laguna", "VXA", "madrid_sur", ["Caja", "Almacén"], "plantilla", 40,
     "fijo", "Cierre", None, {"nota": "incompatible con Noa Ferrández"}),
    ("Irene Salas", "VXA", "madrid_sur", ["Planta Mujer", "Visual"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Bruno Yagüe", "VXA", "madrid_sur", ["Planta Hombre", "Niño"], "plantilla", 24,
     "fijo", "Cierre", None, {"turnos_max_semana": 3}),
    ("Lola Bergua", "VXA", "madrid_sur", ["Caja", "Planta Mujer"], "plantilla", 40,
     "semanal", "Apertura", "Cierre", {}),
    ("Unai Gracia", "VXA", "madrid_sur", ["Almacén", "Planta Hombre"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Carla Oliván", "VXA", "madrid_sur", ["Probadores", "Caja"], "plantilla", 30,
     "fijo", "Cierre", None, {"turnos_max_semana": 4}),
    ("Nerea Used", "VXA", "madrid_sur", ["Visual", "Planta Mujer"], "plantilla", 40,
     "semanal", "Cierre", "Apertura", {}),
    ("Marcos Lahoz", "VXA", "madrid_sur", ["Niño", "Probadores"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Sara Mainar", "VXA", "madrid_sur", ["Almacén", "Visual"], "volante", 40,
     "semanal", "Cierre", "Apertura", {}),
    ("Pau Lacasta", "VXA", "madrid_sur", ["Caja", "Niño"], "ett", 20,
     "fijo", "Cierre", None, {"turnos_max_semana": 3}),
    # ── VOG · Outlet Getafe ──────────────────────────────────────────
    ("Rosa Bescós", "VOG", "madrid_sur", ["Encargado", "Caja"], "plantilla", 40,
     "fijo", "Apertura", None, {"nivel": "encargado"}),
    ("Samu Ordás", "VOG", "madrid_sur", ["Caja", "Planta Hombre"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Cloe Naval", "VOG", "madrid_sur", ["Planta Mujer", "Caja"], "plantilla", 40,
     "fijo", "Cierre", None, {}),
    ("Íker Sesé", "VOG", "madrid_sur", ["Almacén", "Planta Hombre"], "plantilla", 40,
     "fijo", "Cierre", None, {}),
    ("Ada Monreal", "VOG", "madrid_sur", ["Probadores", "Niño"], "plantilla", 20,
     "fijo", "Apertura", None, {"jornada_reducida": True, "turnos_max_semana": 2}),
    ("Hugo Prat", "VOG", "madrid_sur", ["Caja", "Almacén"], "plantilla", 40,
     "semanal", "Apertura", "Cierre", {}),
    ("Elsa Roy", "VOG", "madrid_sur", ["Planta Mujer", "Visual"], "plantilla", 40,
     "fijo", "Cierre", None, {}),
    ("Tomás Lerín", "VOG", "madrid_sur", ["Planta Hombre", "Niño"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Vega Solano", "VOG", "madrid_sur", ["Visual", "Probadores"], "plantilla", 40,
     "semanal", "Cierre", "Apertura", {}),
    ("Adrián Mur", "VOG", "madrid_sur", ["Encargado", "Planta Hombre"], "plantilla", 40,
     "semanal", "Cierre", "Apertura", {"nivel": "segundo"}),
    ("Lucía Bada", "VOG", "madrid_sur", ["Caja", "Probadores"], "ett", 24,
     "fijo", "Cierre", None, {"turnos_max_semana": 3}),
    # ── VZA · Puerto Venecia ─────────────────────────────────────────────
    ("Paula Aísa", "VZA", "zaragoza", ["Encargado", "Caja"], "plantilla", 40,
     "semanal", "Apertura", "Cierre", {"nivel": "encargado"}),
    ("Jorge Used", "VZA", "zaragoza", ["Encargado", "Almacén"], "plantilla", 40,
     "semanal", "Cierre", "Apertura", {"nivel": "segundo"}),
    ("Celia Fanlo", "VZA", "zaragoza", ["Caja", "Probadores"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Dani Ubieto", "VZA", "zaragoza", ["Planta Hombre", "Caja"], "plantilla", 40,
     "fijo", "Cierre", None, {}),
    ("Sara Buil", "VZA", "zaragoza", ["Planta Mujer", "Niño"], "plantilla", 30,
     "fijo", "Apertura", None, {"turnos_max_semana": 4}),
    ("Pablo Sanz", "VZA", "zaragoza", ["Almacén", "Planta Hombre"], "plantilla", 40,
     "fijo", "Cierre", None, {}),
    ("Nuria Allué", "VZA", "zaragoza", ["Visual", "Planta Mujer"], "plantilla", 40,
     "semanal", "Apertura", "Cierre", {}),
    ("Beltrán Orús", "VZA", "zaragoza", ["Niño", "Probadores"], "plantilla", 40,
     "fijo", "Apertura", None, {}),
    ("Inés Lahoz", "VZA", "zaragoza", ["Caja", "Visual"], "plantilla", 40,
     "semanal", "Cierre", "Apertura", {}),
    ("Víctor Pano", "VZA", "zaragoza", ["Probadores", "Almacén"], "plantilla", 40,
     "fijo", "Cierre", None, {}),
    ("Clara Sin", "VZA", "zaragoza", ["Caja", "Niño"], "ett", 20,
     "fijo", "Apertura", None, {"turnos_max_semana": 3}),
    # ── Volantes (sin tienda: cubren su zona) ────────────────────────────
    ("Marta Egea (volante)", None, "madrid_centro", ["Caja", "Planta Mujer", "Probadores"],
     "volante", 40, "fijo", "Apertura", None, {}),
    ("Rubén Cased (volante)", None, "madrid_sur", ["Caja", "Planta Hombre", "Almacén"],
     "volante", 40, "fijo", "Cierre", None, {}),
    ("Pilar Ansó (volante)", None, "zaragoza", ["Caja", "Planta Mujer"],
     "volante", 40, "fijo", "Apertura", None, {}),
    # ── ETT (campaña) ────────────────────────────────────────────────────
    ("Sara Millán (Adecco)", None, "madrid_centro", ["Caja"], "ett", 40,
     "fijo", "Cierre", None, {"proveedor_ett": "Adecco"}),
    ("Hugo Prat (Randstad)", None, "madrid_sur", ["Caja", "Almacén"], "ett", 40,
     "fijo", "Apertura", None, {"proveedor_ett": "Randstad"}),
    # ── Situaciones especiales ───────────────────────────────────────────
    ("Vega Lanuza", "VPN", "madrid_norte", ["Caja", "Planta Mujer"], "plantilla", 40,
     "fijo", "Apertura", None, {"baja": True, "nota": "de baja médica (ausencia aprobada)"}),
    ("Omar Cajal", "VXA", "madrid_sur", ["Almacén"], "plantilla", 40,
     "fijo", "Apertura", None, {"inactivo": True, "nota": "excedencia"}),
]


class Command(BaseCommand):
    help = "Seed de la empresa DEMO «VESTIA Moda» (retail de moda). NO lo ejecuta migrate."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Borra los datos demo antes de recrearlos.")
        parser.add_argument("--admin-email", default="",
                            help="Crea (o reactiva) un superusuario con este correo. "
                                 "Si se omite se usa DEMO_ADMIN_EMAIL del entorno.")
        parser.add_argument("--admin-password", default="",
                            help="Contrasena del superusuario. Por defecto "
                                 "DEMO_ADMIN_PASSWORD del entorno.")
        parser.add_argument("--base-limpia", action="store_true",
                            help="Se conserva por compatibilidad (la aplicacion lo "
                                 "pasa): la planificacion de VGV ya sale siempre "
                                 "sin huecos ni violaciones.")

    # ────────────────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        if opts["reset"]:
            self._reset()
        self._admin(opts["admin_email"], opts["admin_password"])
        # El branding NO se toca: lo fija cada despliegue (logo y colores de
        # Zebra) y un reseteo de la demo no debe cambiarle la marca a la
        # instalacion. Los datos de abajo son de una empresa ficticia, pero la
        # marca de la aplicacion es la del producto.
        self._catalogos()
        self._entidades()
        tiendas = self._tiendas()
        secciones = self._secciones()
        shifts = self._turnos()
        self._campos_worker()
        workers = self._empleados(tiendas, secciones, shifts)
        self._reglas_asignacion()
        self._restricciones(tiendas, workers)
        self._dias_cierre(tiendas)
        self._ausencias(workers)
        self._planes(tiendas, shifts, workers)
        self.stdout.write(self.style.SUCCESS(
            "\nDemo «VESTIA Moda» lista. Abre /schedule: VGV trae las dos semanas "
            "planificadas y sin avisos; el resto de tiendas, sin planificar."))

    # ────────────────────────────────────────────────────────────────────
    def _admin(self, email, password):
        """Superusuario para entrar a la demo.

        El `--reset` NO borra usuarios: si lo hiciera, cada reseteo dejaria la
        demo sin nadie con quien entrar. Aqui solo se asegura de que la cuenta
        existe y de que la contrasena es la esperada, porque quien ensena la
        demo puede haberla cambiado por el camino.
        """
        import os
        from apps.authentication.models import CustomUser

        email = email or os.getenv("DEMO_ADMIN_EMAIL", "")
        password = password or os.getenv("DEMO_ADMIN_PASSWORD", "")
        if not email or not password:
            self.stdout.write("= sin --admin-email/--admin-password: no se toca ningun usuario")
            return

        user = CustomUser.objects.filter(email=email).first()
        if user is None:
            CustomUser.objects.create_superuser(
                email=email, username=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"creado: superusuario {email}"))
            return

        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save(update_fields=["password", "is_staff", "is_superuser", "is_active"])
        self.stdout.write(f"= superusuario {email} ya existia: contrasena y permisos repuestos")

    # ────────────────────────────────────────────────────────────────────
    def _reset(self):
        from apps.absences.models import AbsenceRequest
        from apps.assignments.models import AssignmentRule
        from apps.catalog.models import Kind
        from apps.dynamic_fields.models import EntityField, EntityRecord, EntityType
        from apps.planning.models import ClosedDay, WeeklyPlan
        from apps.restrictions.models import Restriction
        from apps.shifts.models import Shift
        from apps.workers.models import Worker, WorkerPreference

        demo_workers = Worker.objects.filter(custom_data___demo=True)
        AbsenceRequest.objects.filter(worker__in=demo_workers).delete()
        WorkerPreference.objects.filter(worker__in=demo_workers).delete()
        demo_records = EntityRecord.objects.filter(data___demo=True)
        scope_ids = list(demo_records.filter(entity_type_id="tienda").values_list("id", flat=True))
        WeeklyPlan.objects.filter(scope_entity_id__in=scope_ids).delete()
        ClosedDay.objects.filter(scope_entity_id__in=scope_ids + [0]).delete()
        n_w, _ = demo_workers.delete()
        n_r, _ = demo_records.delete()
        n_s, _ = Shift.objects.filter(custom_data___demo=True).delete()
        Restriction.objects.filter(description__startswith="[DEMO]").delete()
        AssignmentRule.objects.filter(description__startswith="[DEMO]").delete()
        EntityField.objects.filter(help_text__startswith="[DEMO]").delete()
        EntityField.objects.filter(
            entity_type__in=["tienda", "seccion"]).delete()
        EntityField.objects.filter(
            entity_type="worker",
            key__in=[f["key"] for f in WORKER_FIELDS]).delete()
        EntityType.objects.filter(slug__in=["tienda", "seccion"], is_system=False).delete()
        Kind.objects.filter(code__in=["zona_movilidad", "tipo_contrato"]).delete()
        self.stdout.write(self.style.WARNING(
            f"reset: {n_w} workers, {n_r} registros, {n_s} turnos demo borrados"))

    def _catalogos(self):
        from apps.catalog.models import Kind, KindValue
        zona, _ = Kind.objects.get_or_create(
            code="zona_movilidad",
            defaults={"name": "Zona de movilidad", "icon": "map",
                      "description": "Dónde pueden rotar volantes y ETT"})
        for i, (code, label, color) in enumerate(ZONAS, 1):
            KindValue.objects.get_or_create(kind=zona, code=code,
                                            defaults={"label": label, "color": color, "order": i})
        contrato, _ = Kind.objects.get_or_create(
            code="tipo_contrato",
            defaults={"name": "Tipo de contrato", "icon": "badge"})
        for i, (code, label) in enumerate(CONTRATOS, 1):
            KindValue.objects.get_or_create(kind=contrato, code=code,
                                            defaults={"label": label, "order": i})
        self.stdout.write("catálogos: zona_movilidad, tipo_contrato")

    def _entidades(self):
        from apps.dynamic_fields.models import EntityField, EntityType
        EntityType.objects.get_or_create(slug="tienda", defaults=dict(
            name="Tienda", icon="storefront", order=1, display_field="codigo",
            is_planning_scope=True, show_in_sidebar=True))
        EntityType.objects.get_or_create(slug="seccion", defaults=dict(
            name="Sección", icon="badge", order=2, display_field="nombre",
            show_in_schedule=True, show_in_sidebar=True))
        tienda_fields = [
            dict(key="codigo", label="Código", field_type="text", required=True,
                 show_in_list=True, order=1),
            dict(key="nombre", label="Nombre", field_type="text", show_in_list=True, order=2),
            dict(key="zona", label="Zona", field_type="catalog_select",
                 kind_code="zona_movilidad", show_in_list=True, show_as_filter=True, order=3),
            dict(key="centro", label="Ubicación", field_type="text", order=4),
        ]
        for f in tienda_fields:
            EntityField.objects.get_or_create(entity_type="tienda", key=f["key"], defaults=f)
        EntityField.objects.get_or_create(
            entity_type="seccion", key="nombre",
            defaults=dict(label="Nombre", field_type="text", required=True,
                          show_in_list=True, order=1))
        self.stdout.write("entidades: tienda (ámbito), seccion (pills)")

    def _tiendas(self):
        from apps.dynamic_fields.models import EntityRecord
        out = {}
        for codigo, nombre, zona, centro in TIENDAS:
            rec = EntityRecord.objects.filter(
                entity_type_id="tienda", data__codigo=codigo).first()
            if not rec:
                rec = EntityRecord.objects.create(
                    entity_type_id="tienda",
                    data={"codigo": codigo, "nombre": nombre, "zona": zona,
                          "centro": centro, "active": True, **DEMO})
            out[codigo] = rec
        self.stdout.write(f"tiendas: {len(out)}")
        return out

    def _secciones(self):
        from apps.dynamic_fields.models import EntityRecord
        out = {}
        for nombre in SECCIONES:
            rec = EntityRecord.objects.filter(
                entity_type_id="seccion", data__nombre=nombre).first()
            if not rec:
                rec = EntityRecord.objects.create(
                    entity_type_id="seccion", data={"nombre": nombre, **DEMO})
            out[nombre] = rec
        self.stdout.write(f"secciones: {len(out)}")
        return out

    def _turnos(self):
        from apps.shift_days.models import ShiftDay
        from apps.shifts.models import Shift
        out = {}
        for name, start, end, days in SHIFTS:
            shift, _ = Shift.objects.get_or_create(
                name=name, defaults={"start_time": start, "end_time": end,
                                     "custom_data": dict(DEMO)})
            # Los dias operativos se reponen SIEMPRE, no solo al crear el
            # turno. Un turno sin filas en ShiftDay lo toma el generador como
            # activo todos los dias (ver `_shift_weekdays`), y entonces el
            # cuadrante pedia Domingo Comercial un lunes
            # a diario: cientos de huecos imposibles de cubrir.
            ShiftDay.objects.filter(shift=shift).exclude(weekday__in=days).delete()
            for wd in days:
                ShiftDay.objects.get_or_create(shift=shift, weekday=wd)
            out[name] = shift
        self.stdout.write(f"turnos: {len(out)} (domingo solo el flagship; "
                          "inventario nocturno cruza medianoche)")
        return out

    def _campos_worker(self):
        from apps.dynamic_fields.models import EntityField
        for f in WORKER_FIELDS:
            EntityField.objects.update_or_create(
                entity_type="worker", key=f["key"],
                defaults={k: v for k, v in f.items() if k != "key"})
        # La tabla de /entities/shift saca sus columnas de los EntityFields de
        # 'shift' (nombre / hora_llegada / hora_salida son las claves que mapea
        # el cliente); sin ellos la tabla de Turnos sale vacía.
        for f in [
            dict(key="nombre", label="Nombre", field_type="text", required=True,
                 show_in_list=True, order=1),
            dict(key="hora_llegada", label="Hora llegada", field_type="time",
                 show_in_list=True, order=2),
            dict(key="hora_salida", label="Hora salida", field_type="time",
                 show_in_list=True, order=3),
        ]:
            EntityField.objects.update_or_create(
                entity_type="shift", key=f["key"],
                defaults={k: v for k, v in f.items() if k != "key"})
        self.stdout.write(f"campos del trabajador: {len(WORKER_FIELDS)} · campos de turno: 3")

    def _empleados(self, tiendas, secciones, shifts):
        from apps.workers.models import Worker, WorkerPreference
        out = {}
        for (name, tcode, zona, secs, contrato, horas,
             rotacion, base, alt, extra) in PLANTILLA:
            cd = {
                "zona": zona, "tipo_contrato": contrato, "horas_semanales": horas,
                "rotacion": rotacion,
                "secciones": [{"value": secciones[s].id, "priority": i + 1}
                              for i, s in enumerate(secs)],
                "turno_base": str(shifts[base].id),
                **DEMO,
            }
            if tcode:
                cd["tienda"] = tiendas[tcode].id
            if alt:
                cd["turno_alternativo"] = str(shifts[alt].id)
            if extra.get("turno_sabado"):
                cd["turno_sabado"] = str(shifts[extra["turno_sabado"]].id)
            for k in ("jornada_reducida", "turnos_max_semana", "nivel", "proveedor_ett"):
                if k in extra:
                    cd[k] = extra[k]
            worker, created = Worker.objects.get_or_create(
                name=name, defaults={"custom_data": cd,
                                     "active": not extra.get("inactivo", False)})
            if created and extra.get("pref"):
                WorkerPreference.objects.get_or_create(
                    worker=worker, shift_type=str(shifts[extra["pref"]].id))
            out[name] = worker
        self.stdout.write(f"empleados: {len(out)} "
                          "(volantes, ETT, parciales 20/24/30h, 1 baja, 1 excedencia)")
        return out

    def _reglas_asignacion(self):
        from apps.assignments.models import AssignmentRule
        reglas = [
            dict(name="Rotación semanal apertura/cierre",
                 description="[DEMO] Quien tiene rotación=semanal alterna cada semana su "
                             "turno base con el alternativo (encargadas cruzadas).",
                 config={"conditionField": "rotacion", "conditionValue": "semanal",
                         "overrideField": "turno_alternativo", "pattern": "alternate_weekly"},
                 priority=10),
            dict(name="Turno de sábado",
                 description="[DEMO] Los sábados, quien tiene turno_sabado definido pasa a "
                             "ese turno (el visual refuerza el cierre del sábado).",
                 config={"conditionField": "", "conditionValue": "",
                         "overrideField": "turno_sabado", "pattern": "weekday", "weekday": 5},
                 priority=20),
        ]
        for r in reglas:
            AssignmentRule.objects.get_or_create(name=r["name"], defaults=r)
        self.stdout.write("reglas de asignación: rotación semanal + turno de sábado")

    def _restricciones(self, tiendas, workers):
        from apps.restrictions.models import Restriction
        noa, ciro = workers["Noa Ferrández"].id, workers["Ciro Laguna"].id
        reglas = [
            dict(name="Elegibilidad por tienda y zona", engine="condition", severity="error",
                 message="{worker} no puede trabajar en esta tienda (fuera de su ámbito)",
                 config={"scopeMatch": {"rules": [
                     {"workerField": "tienda", "matchType": "id"},
                     {"workerField": "zona", "scopeField": "zona", "matchType": "field",
                      "requireField": "tipo_contrato", "requireValue": "volante"},
                     {"workerField": "zona", "scopeField": "zona", "matchType": "field",
                      "requireField": "tipo_contrato", "requireValue": "ett"},
                 ]}},
                 description="[DEMO] Plantilla solo en su tienda; volantes y ETT en su zona."),
            dict(name="Máximo 1 turno por día", engine="count", severity="error",
                 message="{worker}: {count} turnos el mismo día (máx {limit})",
                 config={"subject": "shifts", "groupBy": "day_worker",
                         "operator": "lte", "threshold": 1},
                 description="[DEMO] Nadie hace dos turnos el mismo día."),
            dict(name="Máximo 2 ETT por turno", engine="count", severity="warning",
                 message="{shift}: {count} trabajadores ETT (máx {limit})",
                 config={"subject": "workers", "groupBy": "shift", "operator": "lte",
                         "threshold": 2, "filterField": "tipo_contrato", "filterValue": "ett"},
                 description="[DEMO] No concentrar refuerzo ETT en el mismo turno."),
            dict(name="Mínimo 1 persona de Caja por turno", engine="count", severity="warning",
                 message="{area}: {count} (mín {limit}) en {shift}",
                 config={"subject": "workers", "groupBy": "shift_area", "operator": "gte",
                         "threshold": 1, "filterAreaNames": ["Caja"], "skipEmptyShifts": True},
                 description="[DEMO] Un turno con gente y sin nadie de caja no puede vender "
                             "(los turnos que la tienda no usa ese día no cuentan)."),
            dict(name="Máximo 1 encargado por turno", engine="count", severity="warning",
                 message="{area}: {count} (máx {limit}) en {shift}",
                 config={"subject": "workers", "groupBy": "shift_area", "operator": "lte",
                         "threshold": 1, "filterAreaNames": ["Encargado"]},
                 description="[DEMO] Las encargadas van cruzadas: una por turno."),
            dict(name="Tope de horas semanales por contrato", engine="condition",
                 severity="warning",
                 message="{worker}: {count}h esta semana (contrato: {limit}h)",
                 config={"scope": "per_week_worker_hours", "operator": "lte",
                         "threshold": 40, "thresholdField": "horas_semanales"},
                 description="[DEMO] Suma la duración real de cada turno (el nocturno "
                             "cruza medianoche y también computa bien)."),
            dict(name="Tope de turnos semanales", engine="condition",
                 severity="warning",
                 message="{worker}: {count} turnos en la semana (máx {limit})",
                 config={"scope": "per_week_worker", "operator": "lte",
                         "threshold": 5, "thresholdField": "turnos_max_semana"},
                 description="[DEMO] Semana de 5 días para jornada completa; los parciales "
                             "tienen su tope individual (turnos_max_semana). El generador "
                             "reparte los descansos automáticamente con estos topes."),
            dict(name="Noa Ferrández y Ciro Laguna no coinciden", engine="exclusion",
                 severity="error",
                 message="{worker1} y {worker2} son incompatibles en {shift}",
                 config={"exclusionType": "worker_pair", "workerPairs": [[noa, ciro]]},
                 description="[DEMO] Pareja incompatible real (con sus IDs)."),
            dict(name="No asignar en día de descanso", engine="exclusion", severity="error",
                 config={"exclusionType": "rest_conflict"},
                 description="[DEMO] Alguien marcado en descanso no puede tener turno."),
            dict(name="Respetar turno preferido", engine="match", severity="warning",
                 config={"matchType": "worker_preference"},
                 description="[DEMO] Avisa si se asigna a alguien fuera de su turno preferido."),
            dict(name="La sección asignada debe estar en la polivalencia", engine="match",
                 severity="warning",
                 config={"matchType": "area_membership", "workerField": "secciones"},
                 description="[DEMO] La pill asignada tiene que estar entre sus secciones."),
            dict(name="No asignar en días de cierre", engine="closed_day", severity="error",
                 config={},
                 description="[DEMO] Festivos y cierres (Panel Interno → Días de cierre)."),
        ]
        for r in reglas:
            Restriction.objects.get_or_create(name=r["name"], defaults=r)
        self.stdout.write(f"restricciones: {len(reglas)} (los 5 motores)")

    def _dias_cierre(self, tiendas):
        from apps.planning.models import ClosedDay
        today = dt.date.today()

        def proxima(mes, dia):
            d = dt.date(today.year, mes, dia)
            return d if d >= today else dt.date(today.year + 1, mes, dia)

        cierres = [
            (proxima(12, 25), 0, "Navidad (todas las tiendas)"),
            (proxima(1, 1), 0, "Año Nuevo (todas las tiendas)"),
            (proxima(10, 12), tiendas["VZA"].id, "Fiestas del Pilar (solo Zaragoza)"),
        ]
        for date, scope, reason in cierres:
            ClosedDay.objects.get_or_create(date=date, scope_entity_id=scope,
                                            defaults={"reason": reason})
        self.stdout.write("días de cierre: Navidad y Año Nuevo globales + Pilar (VZA)")

    def _ausencias(self, workers):
        from apps.absences.models import AbsenceRequest, AbsenceType
        tipos = {}
        for name, aprueba in [("Vacaciones", True), ("Baja médica", False),
                              ("Asuntos propios", True), ("Formación", True)]:
            tipos[name], _ = AbsenceType.objects.get_or_create(
                name=name, defaults={"requires_approval": aprueba})
        today = dt.date.today()
        monday = today - dt.timedelta(days=today.weekday())
        solicitudes = [
            # (worker, tipo, inicio, fin, estado, motivo)
            ("Teo Lasheras", "Vacaciones", monday + dt.timedelta(days=7),
             monday + dt.timedelta(days=13), "approved",
             "Semana de vacaciones"),
            ("Vega Lanuza", "Baja médica", today - dt.timedelta(days=10),
             today + dt.timedelta(days=20), "approved", "Baja de larga duración"),
            ("Alba Cortés", "Asuntos propios", monday + dt.timedelta(days=9),
             monday + dt.timedelta(days=9), "pending", "Cita médica por la tarde"),
            ("Pau Ginés", "Formación", monday - dt.timedelta(days=4),
             monday - dt.timedelta(days=3), "rejected", "Curso de visual merchandising"),
        ]
        n = 0
        for wname, tipo, ini, fin, estado, motivo in solicitudes:
            _, created = AbsenceRequest.objects.get_or_create(
                worker=workers[wname], type=tipos[tipo], start_date=ini,
                defaults={"end_date": fin, "status": estado, "reason": motivo})
            n += int(created)
        self.stdout.write(f"ausencias: 4 tipos, {n} solicitudes nuevas "
                          "(aprobada/pendiente/rechazada, relativas a hoy)")

    def _planes(self, tiendas, shifts, workers):
        from apps.dynamic_fields.models import EntityRecord
        from apps.planning.models import WeeklyPlan
        today = dt.date.today()
        monday = today - dt.timedelta(days=today.weekday())
        next_monday = monday + dt.timedelta(days=7)

        # sección principal (prioridad 1) de cada worker → pill del horario
        sec_names = {r.id: r.data.get("nombre") for r in
                     EntityRecord.objects.filter(entity_type_id="seccion")}
        primary = {}
        for w in workers.values():
            secs = (w.custom_data or {}).get("secciones") or []
            if secs:
                primary[w.id] = sec_names.get(secs[0]["value"])

        # Solo VGV: es la tienda que se enseña y la que tiene que salir perfecta.
        # El resto queda sin planificar a propósito (la demo arranca de ahí).
        scope = tiendas["VGV"].id
        for start in (monday, next_monday):
            plan = self._plan_vgv(start, shifts, workers, primary)
            WeeklyPlan.objects.update_or_create(
                start_date=start, scope_entity_id=scope,
                defaults={"plan_json": plan})
        self.stdout.write("planes: semana actual y siguiente solo para VGV, "
                          "sin huecos ni violaciones (el resto de tiendas sin planificar)")

    def _plan_vgv(self, start, shifts, workers, primary):
        """Cuadrante de Gran Vía montado a mano, sin pasar por el generador.

        La pantalla da por vacante cualquier celda sección×turno×día sin nadie
        cuando hay personal de esa sección en ese turno. Con un solo fijo por
        pareja basta que descanse un día laborable para que salte el aviso, y el
        generador reparte los descansos como le conviene. Aquí los 16 fijos
        (dos por sección) trabajan su turno de lunes a viernes y descansan el
        fin de semana, así que no queda hueco posible.
        """
        from apps.absences.models import AbsenceRequest
        from apps.planning.schedule_generator import empty_week

        base = {name: (tc, secs, hs, b)
                for name, tc, _z, secs, _c, hs, _r, b, _a, _x in PLANTILLA}
        vgv = [n for n, (tc, *_r) in base.items() if tc == "VGV"]
        fijos = [n for n in vgv if base[n][2] == 40]
        horario = {s.name: s for s in shifts.values()}

        def asignacion(name, turno):
            w, sh = workers[name], horario[turno]
            return {"workerId": w.id, "workerName": w.name,
                    "start": sh.start_time.strftime("%H:%M"),
                    "end": sh.end_time.strftime("%H:%M"),
                    "areas": [primary[w.id]] if primary.get(w.id) else []}

        ausentes = {}
        for a in AbsenceRequest.objects.filter(status="approved", worker__in=[workers[n] for n in vgv]):
            d = a.start_date
            while d <= a.end_date:
                ausentes.setdefault(d.isoformat(), set()).add(a.worker_id)
                d += dt.timedelta(days=1)

        plan = empty_week(start)
        for i, day in enumerate(plan):
            if i < 5:
                trabajan = [(n, base[n][3]) for n in fijos]
            elif i == 5:
                trabajan = [("Teo Lasheras", "Apertura")]
            else:
                trabajan = [("Aroa Pinilla (findes)", "Domingo Comercial"),
                            ("Nico Bes (findes)", "Domingo Comercial")]
            trabajan = [(n, t) for n, t in trabajan
                        if workers[n].id not in ausentes.get(day["date"], set())]
            for n, t in trabajan:
                day[str(horario[t].id)].append(asignacion(n, t))
            hoy = {workers[n].id for n, _ in trabajan}
            day["rest"] = sorted({workers[n].id for n in vgv} - hoy)
        return plan
