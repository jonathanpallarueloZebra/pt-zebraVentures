import io
import logging

from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Worker
from .serializers import WorkerSerializer

logger = logging.getLogger(__name__)


class WorkerViewSet(viewsets.ModelViewSet):
    serializer_class = WorkerSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Worker.objects.prefetch_related('preferences')
        # Only the default list is restricted to active workers (planning, etc.).
        # Detail ops (retrieve/update/patch/destroy) must reach inactive workers too,
        # otherwise a deactivated employee can't be edited, deleted or re-activated.
        if self.action == 'list':
            return qs.filter(active=True)
        return qs

    def perform_destroy(self, instance):
        user = instance.user
        instance.delete()
        if user:
            user.password_tokens.all().delete()
            user.delete()

    @action(detail=False, methods=['get'], url_path='me', permission_classes=[__import__('rest_framework.permissions', fromlist=['IsAuthenticated']).IsAuthenticated])
    def me(self, request):
        """Return the Worker profile linked to the currently authenticated user."""
        try:
            worker = Worker.objects.prefetch_related('preferences').get(user=request.user)
            serializer = self.get_serializer(worker)
            return Response(serializer.data)
        except Worker.DoesNotExist:
            return Response({'error': 'No tiene perfil de empleado.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'])
    def all(self, request):
        workers = Worker.objects.all().prefetch_related('preferences')
        serializer = self.get_serializer(workers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='import-template')
    def import_template(self, request):
        """Download an Excel template driven entirely by the EAV EntityField schema for 'worker'.

        Columns A-B are fixed (nombre, email). From C onwards, one column per active
        EntityField for entity_type='worker', in order. Each column gets:
          - entity_select / catalog_select → single dropdown referencing Referencia sheet
          - multi_entity_select / multi_catalog_select → MULTI_COLUMNS dropdown columns each
          - boolean → dropdown Sí / No
          - select  → dropdown from field.options

        MULTI_COLUMNS is the number of individual dropdown slots generated for multi fields.
        The importer reads those slots and combines non-empty values into a list.
        """
        MULTI_COLUMNS = 3  # number of dropdown slots for multi-select fields
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            from openpyxl.utils import get_column_letter
            from openpyxl.worksheet.datavalidation import DataValidation
            from openpyxl.formatting.rule import Rule
            from openpyxl.styles.differential import DifferentialStyle
        except ImportError:
            return Response(
                {'error': 'openpyxl no está instalado en el servidor.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        from apps.dynamic_fields.models import EntityField, EntityRecord, EntityType
        from apps.catalog.models import KindValue
        from apps.shifts.models import Shift as ShiftModel

        MAX_DATA_ROWS = 1001  # data validation applied to rows 2-1001

        # For entity_select/multi_entity_select fields the options may live in
        # EntityRecord (EAV) OR in a dedicated system model (e.g. Shift).
        # We always merge both sources so shifts created from either UI appear.
        def _load_entity_options(target_entity, display_key):
            """Return [(label, id)] merging Shift model + EntityRecord for system entities."""
            seen = {}  # label_lower -> (label, id) — Shift model wins on collision
            if target_entity == 'shift':
                for s in ShiftModel.objects.all().order_by('name'):
                    seen[s.name.strip().lower()] = (s.name.strip(), s.id)
            # Also include any EntityRecord entries (EAV-created via entity UI)
            for r in EntityRecord.objects.filter(entity_type=target_entity):
                label = str(r.data.get(display_key) or '').strip()
                if label and label.lower() not in seen:
                    seen[label.lower()] = (label, r.id)
            return list(seen.values())

        worker_fields = list(
            EntityField.objects.filter(entity_type='worker', active=True).order_by('order')
        )

        def _resolve_display_key(field):
            if field.display_key:
                return field.display_key
            try:
                return EntityType.objects.get(slug=field.target_entity).display_field
            except EntityType.DoesNotExist:
                return 'nombre'

        # Pre-compute options for every field that needs them
        field_options = {}   # field.key → list of label strings
        field_cat_codes = {} # field.key → [(code, label), ...]

        for field in worker_fields:
            if field.field_type in ('entity_select', 'multi_entity_select') and field.target_entity:
                dk = _resolve_display_key(field)
                pairs = _load_entity_options(field.target_entity, dk)
                field_options[field.key] = [label for label, _ in pairs if label]
            elif field.field_type in ('catalog_select', 'multi_catalog_select') and field.kind_code:
                rows_kv = list(
                    KindValue.objects.filter(kind__code=field.kind_code, active=True)
                    .order_by('order')
                    .values_list('code', 'label')
                )
                field_cat_codes[field.key] = rows_kv   # [(code, label), ...]
                field_options[field.key] = [code for code, _ in rows_kv]
            elif field.field_type == 'select' and field.options:
                field_options[field.key] = list(field.options)

        # ---- Workbook ----------------------------------------------------------
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Empleados'

        hdr_fill = PatternFill('solid', fgColor='1F497D')
        hdr_font = Font(bold=True, color='FFFFFF')

        def _set_header(sheet, row, col, text, width):
            c = sheet.cell(row=row, column=col, value=text)
            c.font = hdr_font
            c.fill = hdr_fill
            c.alignment = Alignment(horizontal='center')
            sheet.column_dimensions[get_column_letter(col)].width = width

        _set_header(ws, 1, 1, 'Nombre completo *', 28)
        _set_header(ws, 1, 2, 'Email (opcional)', 30)

        # Build the column layout, tracking start col for each field
        # field_col_start[field.key] = first column index used by that field
        field_col_start = {}  # field.key → first Excel column index
        col = 3
        for field in worker_fields:
            field_col_start[field.key] = col
            is_multi = field.field_type in ('multi_entity_select', 'multi_catalog_select')
            slots = MULTI_COLUMNS if is_multi else 1
            req_mark = ' *' if field.required else ''
            if is_multi:
                for s in range(1, slots + 1):
                    label = f'{field.label}{req_mark} {s}'
                    _set_header(ws, 1, col, label, max(len(field.label) + 6, 18))
                    col += 1
            else:
                label = field.label + req_mark
                _set_header(ws, 1, col, label, max(len(label) + 4, 18))
                col += 1

        ws.freeze_panes = 'A2'

        # ---- Referencia sheet --------------------------------------------------
        # Holds the option lists for dropdown formulas.  We record which Referencia
        # column each field uses so we can build the DataValidation formula.
        ref_ws = wb.create_sheet('Referencia')
        ref_hdr_fill = PatternFill('solid', fgColor='2F5496')

        def _ref_header(col, text):
            c = ref_ws.cell(row=1, column=col, value=text)
            c.font = hdr_font
            c.fill = ref_hdr_fill
            c.alignment = Alignment(horizontal='center')
            ref_ws.column_dimensions[get_column_letter(col)].width = max(len(text) + 4, 18)

        # field.key → column index in Referencia sheet (for the primary / code column)
        field_ref_col = {}

        ref_col = 1
        for field in worker_fields:
            if field.field_type in ('entity_select', 'multi_entity_select') and field.key in field_options:
                opts = field_options[field.key]
                _ref_header(ref_col, field.label)
                for row_i, val in enumerate(opts, 2):
                    ref_ws.cell(row=row_i, column=ref_col, value=val)
                field_ref_col[field.key] = ref_col
                ref_col += 1

            elif field.field_type in ('catalog_select', 'multi_catalog_select') and field.key in field_cat_codes:
                rows_kv = field_cat_codes[field.key]
                _ref_header(ref_col, f'{field.label} (código)')
                ref_ws.column_dimensions[get_column_letter(ref_col + 1)].width = 22
                _ref_header(ref_col + 1, f'{field.label} (etiqueta)')
                for row_i, (code, label) in enumerate(rows_kv, 2):
                    ref_ws.cell(row=row_i, column=ref_col, value=code)
                    ref_ws.cell(row=row_i, column=ref_col + 1, value=label)
                field_ref_col[field.key] = ref_col
                ref_col += 2

            elif field.field_type == 'select' and field.key in field_options:
                opts = field_options[field.key]
                _ref_header(ref_col, field.label)
                for row_i, opt in enumerate(opts, 2):
                    ref_ws.cell(row=row_i, column=ref_col, value=opt)
                field_ref_col[field.key] = ref_col
                ref_col += 1

        ref_ws.freeze_panes = 'A2'

        # ---- Data Validations (dropdowns) on Empleados sheet -------------------
        for field in worker_fields:
            start_col = field_col_start[field.key]
            is_multi = field.field_type in ('multi_entity_select', 'multi_catalog_select')
            slots = MULTI_COLUMNS if is_multi else 1

            for s in range(slots):
                col = start_col + s
                col_letter = get_column_letter(col)
                sqref = f'{col_letter}2:{col_letter}{MAX_DATA_ROWS}'

                if field.field_type == 'boolean':
                    dv = DataValidation(
                        type='list',
                        formula1='"Sí,No"',
                        allow_blank=True,
                        showDropDown=False,
                    )
                    ws.add_data_validation(dv)
                    dv.sqref = sqref

                    # Conditional formatting: green for Sí, red for No
                    si_fill = DifferentialStyle(
                        fill=PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid'),
                        font=Font(color='276221'),
                    )
                    no_fill = DifferentialStyle(
                        fill=PatternFill(start_color='FFCCCC', end_color='FFCCCC', fill_type='solid'),
                        font=Font(color='9C0006'),
                    )
                    ws.conditional_formatting.add(
                        sqref,
                        Rule(type='containsText', operator='containsText', text='Sí', dxf=si_fill),
                    )
                    ws.conditional_formatting.add(
                        sqref,
                        Rule(type='containsText', operator='containsText', text='No', dxf=no_fill),
                    )

                elif field.key in field_ref_col:
                    r_col = field_ref_col[field.key]
                    r_letter = get_column_letter(r_col)
                    n_opts = len(field_options.get(field.key, []))
                    if n_opts > 0:
                        formula = f'Referencia!${r_letter}$2:${r_letter}${n_opts + 1}'
                        dv = DataValidation(
                            type='list',
                            formula1=formula,
                            allow_blank=True,
                            showDropDown=False,
                        )
                        ws.add_data_validation(dv)
                        dv.sqref = sqref

        # ---- Serialize ---------------------------------------------------------
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename=plantilla_empleados.xlsx'
        return response

    @action(detail=False, methods=['get'], url_path='export')
    def export_excel(self, request):
        """Export all workers to Excel with human-readable values for every EAV field."""
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            from openpyxl.utils import get_column_letter
        except ImportError:
            return Response(
                {'error': 'openpyxl no está instalado en el servidor.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        from apps.dynamic_fields.models import EntityField, EntityRecord, EntityType
        from apps.catalog.models import KindValue
        from apps.shifts.models import Shift as ShiftModel

        worker_fields = list(
            EntityField.objects.filter(entity_type='worker', active=True).order_by('order')
        )

        def _resolve_display_key(field):
            if field.display_key:
                return field.display_key
            try:
                return EntityType.objects.get(slug=field.target_entity).display_field
            except EntityType.DoesNotExist:
                return 'nombre'

        # Build id→label maps for entity_select fields
        entity_label = {}   # field.key → {record_id: label_str}
        catalog_label = {}  # field.key → {code: label_str}

        for field in worker_fields:
            if field.field_type in ('entity_select', 'multi_entity_select') and field.target_entity:
                dk = _resolve_display_key(field)
                lmap = {}
                if field.target_entity == 'shift':
                    for s in ShiftModel.objects.all():
                        lmap[s.id] = s.name
                for r in EntityRecord.objects.filter(entity_type=field.target_entity):
                    if r.id not in lmap:
                        lmap[r.id] = str(r.data.get(dk) or r.data.get('nombre') or r.data.get('name') or r.id)
                entity_label[field.key] = lmap
            elif field.field_type in ('catalog_select', 'multi_catalog_select') and field.kind_code:
                catalog_label[field.key] = {
                    kv.code: kv.label
                    for kv in KindValue.objects.filter(kind__code=field.kind_code, active=True)
                }

        def _resolve_value(field, raw):
            """Convert a raw custom_data value to a human-readable string."""
            if raw is None or raw == '':
                return ''
            if field.field_type == 'boolean':
                if raw is True or str(raw).lower() in ('true', '1', 'sí', 'si'):
                    return 'Sí'
                return 'No'
            if field.field_type in ('entity_select', 'multi_entity_select'):
                lmap = entity_label.get(field.key, {})
                ids = raw if isinstance(raw, list) else [raw]
                labels = []
                for item in ids:
                    rid = item.get('value', item) if isinstance(item, dict) else item
                    try:
                        rid = int(rid)
                    except (ValueError, TypeError):
                        rid = None
                    labels.append(lmap.get(rid, str(rid) if rid else ''))
                return ', '.join(l for l in labels if l)
            if field.field_type in ('catalog_select', 'multi_catalog_select'):
                clmap = catalog_label.get(field.key, {})
                codes = raw if isinstance(raw, list) else [raw]
                return ', '.join(clmap.get(str(c), str(c)) for c in codes if c)
            if isinstance(raw, list):
                return ', '.join(str(x) for x in raw)
            return str(raw)

        # ── Build workbook ───────────────────────────────────────────
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Empleados'

        hdr_fill = PatternFill('solid', fgColor='1F497D')
        hdr_font = Font(bold=True, color='FFFFFF')

        def _hdr(col, text, width=20):
            c = ws.cell(row=1, column=col, value=text)
            c.font = hdr_font
            c.fill = hdr_fill
            c.alignment = Alignment(horizontal='center')
            ws.column_dimensions[get_column_letter(col)].width = width

        _hdr(1, 'ID', 8)
        _hdr(2, 'Nombre', 30)
        _hdr(3, 'Email', 30)
        _hdr(4, 'Activo', 10)

        col = 5
        for field in worker_fields:
            _hdr(col, field.label, max(len(field.label) + 4, 18))
            col += 1

        ws.freeze_panes = 'A2'

        # ── Write rows ────────────────────────────────────────────────
        workers_qs = Worker.objects.all().order_by('name')
        row = 2
        for w in workers_qs:
            cd = w.custom_data or {}
            ws.cell(row=row, column=1, value=w.id)
            ws.cell(row=row, column=2, value=w.name)
            ws.cell(row=row, column=3, value=getattr(w, 'email', '') or (w.user.email if w.user else ''))
            ws.cell(row=row, column=4, value='Sí' if w.active else 'No')
            col = 5
            for field in worker_fields:
                ws.cell(row=row, column=col, value=_resolve_value(field, cd.get(field.key)))
                col += 1
            row += 1

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        from datetime import date
        filename = f'empleados-{date.today().isoformat()}.xlsx'
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename={filename}'
        return response

    @action(detail=False, methods=['post'], url_path='import-excel')
    def import_excel(self, request):
        """Bulk import workers from an uploaded Excel file.

        Column layout matches the template from import-template/:
          Col A: nombre (required)
          Col B: email (optional)
          Col C+: one column per single EntityField, or MULTI_COLUMNS columns per multi field.
        """
        MULTI_COLUMNS = 3  # must match import_template
        import os
        from datetime import timedelta

        try:
            import openpyxl
        except ImportError:
            return Response(
                {'error': 'openpyxl no está instalado en el servidor.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from apps.authentication.models import PasswordToken
        from apps.email_service.service import EmailService, worker_invites_enabled
        from apps.dynamic_fields.models import EntityField, EntityRecord, EntityType
        from apps.catalog.models import KindValue
        from apps.shifts.models import Shift as ShiftModel

        User = get_user_model()
        email_service = EmailService()

        # For entity_select/multi_entity_select fields the options may live in
        # EntityRecord (EAV) OR in a dedicated system model (e.g. Shift).
        # We always merge both sources so shifts created from either UI resolve correctly.
        def _load_entity_lookup(target_entity, display_key):
            """Return {label_lower: record_id} merging Shift model + EntityRecord."""
            mapping = {}
            if target_entity == 'shift':
                # Shift model takes priority
                for s in ShiftModel.objects.all():
                    mapping[s.name.strip().lower()] = s.id
            # Merge EAV records (only fills gaps not already covered by the model)
            for r in EntityRecord.objects.filter(entity_type=target_entity):
                label = str(r.data.get(display_key) or '').strip()
                if label and label.lower() not in mapping:
                    mapping[label.lower()] = r.id
            return mapping

        # ---- Load EAV schema for worker ----------------------------------------
        worker_fields = list(
            EntityField.objects.filter(entity_type='worker', active=True).order_by('order')
        )

        def _resolve_display_key(field):
            if field.display_key:
                return field.display_key
            try:
                return EntityType.objects.get(slug=field.target_entity).display_field
            except EntityType.DoesNotExist:
                return 'nombre'

        # Build per-field lookup maps for entity_select fields: display_name → record_id
        entity_lookup = {}   # field.key → {name_lower: record_id}
        catalog_lookup = {}  # field.key → {code_lower: code}  (validates code exists)

        for field in worker_fields:
            if field.field_type in ('entity_select', 'multi_entity_select') and field.target_entity:
                dk = _resolve_display_key(field)
                entity_lookup[field.key] = _load_entity_lookup(field.target_entity, dk)

            elif field.field_type in ('catalog_select', 'multi_catalog_select') and field.kind_code:
                valid = {}
                for kv in KindValue.objects.filter(kind__code=field.kind_code, active=True):
                    valid[kv.code.lower()] = kv.code
                    valid[kv.label.lower()] = kv.code  # also accept label
                catalog_lookup[field.key] = valid

        def _parse_bool(val):
            if val is None:
                return False
            if isinstance(val, bool):
                return val
            return str(val).strip().lower() in ('sí', 'si', 'yes', 'true', '1', 's', 'y')

        def _parse_field(field, raw_val):
            """
            Parse a cell value according to the EAV field type.
            Returns (resolved_value, error_string_or_None).
            """
            if raw_val is None or str(raw_val).strip() == '':
                return None, None

            raw = str(raw_val).strip()

            if field.field_type == 'entity_select':
                lookup = entity_lookup.get(field.key, {})
                rid = lookup.get(raw.lower())
                if rid is None:
                    return None, f'"{raw}" no encontrado en {field.label}'
                return rid, None

            elif field.field_type == 'multi_entity_select':
                lookup = entity_lookup.get(field.key, {})
                ids = []
                for part in [x.strip() for x in raw.split(';') if x.strip()]:
                    rid = lookup.get(part.lower())
                    if rid is None:
                        return None, f'"{part}" no encontrado en {field.label}'
                    ids.append(rid)
                return ids if ids else None, None

            elif field.field_type == 'catalog_select':
                lookup = catalog_lookup.get(field.key, {})
                code = lookup.get(raw.lower())
                if lookup and code is None:
                    return None, f'Valor "{raw}" no válido para {field.label}'
                return raw if code is None else code, None

            elif field.field_type == 'multi_catalog_select':
                lookup = catalog_lookup.get(field.key, {})
                codes = []
                for part in [x.strip() for x in raw.split(';') if x.strip()]:
                    code = lookup.get(part.lower())
                    if lookup and code is None:
                        return None, f'Valor "{part}" no válido para {field.label}'
                    codes.append(code if code else part)
                return codes if codes else None, None

            elif field.field_type == 'boolean':
                return _parse_bool(raw_val), None

            elif field.field_type == 'float':
                # Decimal: se acepta la coma como separador (es lo que escribe
                # un usuario español y lo que exporta Excel en es-ES).
                try:
                    return float(raw.replace(',', '.')), None
                except ValueError:
                    return None, f'"{raw}" no es un número válido para {field.label}'

            elif field.field_type == 'number':
                try:
                    return float(raw) if '.' in raw else int(raw), None
                except ValueError:
                    return None, f'"{raw}" no es un número válido para {field.label}'

            else:
                # text, time, textarea, color, select
                return raw, None

        # ---- Read file ---------------------------------------------------------
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No se envió ningún archivo.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
            ws = wb.active
        except Exception:
            return Response({'error': 'Archivo Excel no válido.'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Detectar el formato leyendo la CABECERA ────────────────────────
        # Hay dos ficheros distintos en circulación y antes solo se aceptaba uno:
        #   · Plantilla de importación: Nombre | Email | campos (3 columnas por
        #     campo multi-selección).
        #   · Excel exportado desde la propia tabla: ID | Nombre | Email |
        #     Activo | campos (1 columna por campo, valores separados por comas).
        # Asumir posiciones fijas hacía que el exportado se leyera desplazado dos
        # columnas y fallara cada fila. Ahora se localiza cada campo por el
        # texto de su cabecera, así que valen los dos formatos y da igual el
        # orden de las columnas.
        header = [str(c or '').strip() for c in next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())]
        header_lower = [h.lower() for h in header]

        def _find_col(*names):
            for n in names:
                if n in header_lower:
                    return header_lower.index(n)
            return None

        name_col = _find_col('nombre', 'name')
        email_col = _find_col('email', 'correo', 'e-mail')
        # Presentes solo en el Excel exportado; sirven para identificar al
        # trabajador ya existente y respetar su estado activo/inactivo.
        id_col = _find_col('id')
        active_col = _find_col('activo', 'active')
        # Columna de inicio de cada campo EAV, por su etiqueta.
        field_cols = {}
        for f in worker_fields:
            idx = _find_col(f.label.strip().lower())
            if idx is not None:
                field_cols[f.key] = idx
        # Formato exportado: una sola columna por campo (los multi vienen con los
        # valores separados por comas). Formato plantilla: MULTI_COLUMNS por campo.
        one_col_per_field = 'id' in header_lower or 'activo' in header_lower

        if name_col is None:
            return Response(
                {'error': 'No se encuentra la columna "Nombre" en la primera fila. '
                          'Usa la plantilla de importación o el Excel exportado sin modificar la cabecera.'},
                status=status.HTTP_400_BAD_REQUEST)

        rows = list(ws.iter_rows(min_row=2, values_only=True))
        if not rows:
            return Response({'error': 'El archivo no contiene datos.'}, status=status.HTTP_400_BAD_REQUEST)

        created = 0
        updated = 0
        invited = 0
        skipped = []
        errors = []

        for i, row in enumerate(rows, start=2):
            def _cell(idx):
                return row[idx] if len(row) > idx else None

            name = str(_cell(name_col) or '').strip()
            if not name:
                continue

            email_raw = _cell(email_col) if email_col is not None else None
            email = str(email_raw or '').strip()

            # -- Parse EAV fields: cada uno en la columna de su cabecera --------
            custom_data = {}
            row_errors = []
            col_cursor = 2  # solo se usa si la cabecera no trae el campo

            for field in worker_fields:
                is_multi = field.field_type in ('multi_entity_select', 'multi_catalog_select')
                # En el Excel exportado cada campo ocupa UNA columna (los multi
                # llevan los valores separados por comas); en la plantilla, tres.
                slots = 1 if one_col_per_field else (MULTI_COLUMNS if is_multi else 1)
                if field.key in field_cols:
                    col_cursor = field_cols[field.key]

                if is_multi:
                    # Collect all non-empty slot values and parse each individually
                    combined = []
                    slot_errors = []
                    # Valores de las celdas del campo. En el Excel exportado
                    # vienen varios en UNA celda separados por comas
                    # ("Carne, Pescadería"), así que hay que partirlos.
                    valores = []
                    for s in range(slots):
                        raw = _cell(col_cursor + s)
                        if raw is None or str(raw).strip() == '':
                            continue
                        texto = str(raw).strip()
                        valores.extend(
                            [p.strip() for p in texto.split(',') if p.strip()]
                            if one_col_per_field else [texto]
                        )
                    for raw_str in valores:
                        if field.field_type == 'multi_entity_select':
                            lookup = entity_lookup.get(field.key, {})
                            rid = lookup.get(raw_str.lower())
                            if rid is None:
                                slot_errors.append(f'"{raw_str}" no encontrado en {field.label}')
                            elif rid not in combined:
                                combined.append(rid)
                        else:  # multi_catalog_select
                            lookup = catalog_lookup.get(field.key, {})
                            code = lookup.get(raw_str.lower())
                            if lookup and code is None:
                                slot_errors.append(f'Valor "{raw_str}" no válido para {field.label}')
                            else:
                                val = code if code else raw_str
                                if val not in combined:
                                    combined.append(val)
                    row_errors.extend(slot_errors)
                    if combined:
                        # Campos con prioridad: se guarda [{value, priority}] para
                        # no perder el orden de preferencia (el orden de las
                        # columnas/comas ES la prioridad). Sin prioridad, lista
                        # simple como hasta ahora.
                        if field.allow_priority:
                            custom_data[field.key] = [
                                {'value': v, 'priority': n}
                                for n, v in enumerate(combined, start=1)
                            ]
                        else:
                            custom_data[field.key] = combined
                    col_cursor += slots
                else:
                    raw = _cell(col_cursor)
                    value, err = _parse_field(field, raw)
                    if err:
                        row_errors.append(err)
                    elif value is not None:
                        custom_data[field.key] = value
                    col_cursor += 1

            if row_errors:
                errors.append(f'Fila {i} ({name}): {"; ".join(row_errors)}')
                continue

            # -- ¿Ya existe? ACTUALIZAR en vez de duplicar ----------------------
            # El Excel exportado trae la columna ID, que identifica al trabajador
            # sin ambigüedad. Si no la trae (plantilla de importación), se busca
            # por nombre exacto. Antes solo se miraba el email: al venir vacío,
            # reimportar el mismo fichero duplicaba TODA la plantilla.
            existente = None
            if id_col is not None:
                raw_id = _cell(id_col)
                try:
                    existente = Worker.objects.filter(id=int(raw_id)).first() if raw_id else None
                except (TypeError, ValueError):
                    existente = None
            if existente is None:
                existente = Worker.objects.filter(name__iexact=name).first()

            if existente is not None:
                try:
                    existente.name = name
                    # Se fusiona: los campos que el Excel no trae no se borran.
                    existente.custom_data = {**(existente.custom_data or {}), **custom_data}
                    if active_col is not None:
                        raw_act = _cell(active_col)
                        if raw_act is not None and str(raw_act).strip() != '':
                            existente.active = _parse_bool(raw_act)
                    existente.save()
                    updated += 1
                except Exception as e:
                    errors.append(f'Fila {i} ({name}): no se pudo actualizar - {e}')
                continue

            # -- Skip if email already exists -----------------------------------
            if email:
                if User.objects.filter(email=email).exists():
                    skipped.append(f'{name} ({email})')
                    continue

            # -- Create worker --------------------------------------------------
            try:
                user = None
                # Igual que en el alta individual: sin invitaciones activas no se
                # crea cuenta de usuario aunque el Excel traiga email.
                if email and worker_invites_enabled():
                    user = User.objects.create_user(
                        email=email,
                        username=email,
                        password=None,
                        is_active=False,
                    )
                    user.set_unusable_password()
                    parts = name.split()
                    user.first_name = parts[0]
                    user.last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
                    user.save()

                Worker.objects.create(name=name, user=user, custom_data=custom_data)
                created += 1

                # ── Invitación por email al importar ─────────────────────────
                # DESACTIVADO: por ahora no se invita a los empleados al
                # importarlos. En Cabrero no acceden a la aplicación, así que no
                # se crea cuenta ni se manda correo. `user` ya viene a None
                # cuando worker_invites_enabled() es False, así que este bloque
                # tampoco entraría; se deja comentado para retomarlo cuando se
                # decida abrir el acceso a los empleados.
                # TODO: revisar maquetación email y probar funcionamiento
                #
                # if user and email:
                #     token = PasswordToken.objects.create(
                #         user=user,
                #         purpose='invite',
                #         expires_at=timezone.now() + timedelta(days=7),
                #     )
                #     frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:4200').rstrip('/')
                #     setup_link = f'{frontend_url}/set-password?token={token.token}'
                #     sent = email_service.send_plain(
                #         to_email=email,
                #         subject='Configura tu cuenta',
                #         body=(
                #             f'Hola {name},\n\n'
                #             f'Se ha creado tu cuenta en el planificador de turnos.\n'
                #             f'Usa este enlace para establecer tu contraseña:\n{setup_link}\n\n'
                #             f'El enlace expira en 7 días.'
                #         ),
                #     )
                #     if sent:
                #         invited += 1

            except Exception as exc:
                errors.append(f'Fila {i} ({name}): Error - {str(exc)}')

        return Response({
            'created': created,
            'updated': updated,
            'invited': invited,
            'skipped': skipped,
            'errors': errors,
            'total_rows': len(rows),
        })
