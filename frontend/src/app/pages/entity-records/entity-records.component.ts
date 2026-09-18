import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatSelectModule } from '@angular/material/select';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { switchMap, forkJoin, Observable } from 'rxjs';
import { EntityTypeService } from '@app/shared/services/entity-type.service';
import { EntityRecordService } from '@app/shared/services/entity-record.service';
import { EntityFieldService } from '@app/shared/services/entity-field.service';
import { ShiftService } from '@app/shared/services/shift.service';
import { WorkerService } from '@app/shared/services/worker.service';
import { EntityTypeDef, EntityRecord, EntityField, FieldSchema } from '@app/shared/interfaces/entity-field.interface';
import { DynamicFieldsComponent } from '@app/shared/components/dynamic-fields/dynamic-fields.component';
import { ZbDialogComponent } from '@app/shared/components/zb-dialog/zb-dialog.component';
import { ColumnPrefsService } from '@app/shared/services/column-prefs.service';
import { ZbSidepanelComponent } from '@app/shared/components/zb-sidepanel/zb-sidepanel.component';
import { ZbEmptyStateComponent, EmptyStateIllustration } from '@app/shared/components/zb-empty-state/zb-empty-state.component';
import { ZbColumnMenuComponent, ZbColumnDef } from '@app/shared/components/zb-column-menu/zb-column-menu.component';
import { ZbTableToolbarComponent } from '@app/shared/components/zb-table-toolbar/zb-table-toolbar.component';
import { ZbPaginatorComponent } from '@app/shared/components/zb-paginator/zb-paginator.component';
import { ZbButtonComponent } from '@app/shared/components/zb-button/zb-button.component';
import { ZbPageHeaderComponent } from '@app/shared/components/zb-page-header/zb-page-header.component';
import { ZbCheckboxComponent } from '@app/shared/components/zb-checkbox/zb-checkbox.component';
import { ZbSelectComponent, ZbSelectOption } from '@app/shared/components/zb-select/zb-select.component';
import { sectionIconPath } from '@app/shared/constants/section-icons';
import { CatalogService } from '@app/shared/services/catalog.service';
import { SIN_ASIGNAR, valorSinAsignar } from '@app/shared/constants/filters';

@Component({
  selector: 'app-entity-records',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatTableModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule,
    MatTooltipModule,
    MatSnackBarModule,
    DynamicFieldsComponent, MatPaginatorModule, MatSelectModule, MatCheckboxModule,
    ZbSidepanelComponent, ZbEmptyStateComponent, ZbColumnMenuComponent,
    ZbTableToolbarComponent, ZbPaginatorComponent, ZbButtonComponent,
    ZbPageHeaderComponent, ZbCheckboxComponent, ZbSelectComponent,
    ZbDialogComponent,
  ],
  templateUrl: './entity-records.component.html',
  styleUrl: './entity-records.component.scss',
})
export class EntityRecordsComponent implements OnInit {
  entityType = signal<EntityTypeDef | null>(null);
  records = signal<EntityRecord[]>([]);
  loading = signal(true);
  page = signal(0);
  pageSize = signal(10);
  readonly pageSizeOptions = [10, 25, 50, 100];
  slug = '';

  /** Etiqueta del botón/panel de alta: "Nuevo turno", "Nueva sección"…
   *  Se deriva del nombre de la entidad (que viene en plural: "Turnos") para
   *  que cada maestro use su propio término en vez del genérico "registro". */
  newLabel = computed(() => {
    const name = this.entityType()?.name?.trim();
    if (!name) return 'Nuevo registro';
    const singular = this.singularize(name);
    // Femenino por terminación (Sección, Tienda) → "Nueva".
    const article = /(ción|sión|dad|tad|tienda|a)$/i.test(singular) ? 'Nueva' : 'Nuevo';
    return `${article} ${singular.toLowerCase()}`;
  });

  /**
   * Título del panel de edición: "Editar turno: Sábado Mañana".
   *
   * Antes era "Editar registro #160": el ID interno no dice nada y obligaba a
   * bajar hasta el campo Nombre para saber qué se estaba editando.
   *
   * El nombre sale del `display_field` de la entidad (el mismo que usa la
   * tabla), así que funciona igual en Turnos, Tiendas o Secciones sin tratar
   * cada maestro por separado. Se captura al ABRIR el panel: si el usuario
   * cambia el nombre dentro, el título no se mueve (AC-5).
   */
  editTitle = computed(() => {
    const tipo = this.singularize(this.entityType()?.name?.trim() || 'registro')
      .toLowerCase();
    const nombre = this.editingName();
    return nombre ? `Editar ${tipo}: ${nombre}` : `Editar ${tipo}`;
  });

  /** Nombre del registro con el que se abrió el panel de edición. */
  private editingName = signal('');

  /**
   * Ilustración del empty state (Figma 2139:7847 turnos · 2139:8257 tiendas).
   * Solo turnos y tiendas tienen glifo propio en el diseño; el resto de
   * maestros (EAV) se quedan con el icono genérico en círculo.
   * El slug de tienda es configurable, así que se mira también el nombre.
   */
  emptyIllustration = computed<EmptyStateIllustration | undefined>(() => {
    if (this.slug === 'shift') return 'schedule';
    const name = (this.entityType()?.name ?? '').toLowerCase();
    if (this.slug === 'store' || /tienda/.test(name)) return 'store';
    if (/turno/.test(name)) return 'schedule';
    return undefined;
  });

  /**
   * Título del empty state. Con ilustración se usa el copy de Figma
   * ("Añade turnos/tiendas para empezar", en plural y minúscula); sin ella
   * se mantiene el genérico anterior.
   */
  emptyTitle = computed(() => {
    if (!this.emptyIllustration()) return 'Sin registros';
    const name = this.entityType()?.name?.trim();
    return `Añade ${name ? name.toLowerCase() : 'registros'} para empezar`;
  });

  /** Plural→singular para los nombres de entidad más comunes en español. */
  private singularize(name: string): string {
    if (/(ciones|siones)$/i.test(name)) return name.replace(/ones$/i, 'ón');
    if (/es$/i.test(name) && /[lrndjsz]es$/i.test(name)) return name.slice(0, -2);
    if (/s$/i.test(name) && !/[aeiou]s$/i.test(name.slice(0, -1))) return name.slice(0, -1);
    if (/s$/i.test(name)) return name.slice(0, -1);
    return name;
  }

  // ── Filters (dashboard-style: one dropdown per field with show_as_filter=true) ──
  /** { fieldKey: selectedValue | null } */
  activeFilters = signal<Record<string, string | null>>({});

  /** Options per filter field, populated after refLookups are ready */
  filterOptions = signal<Record<string, { value: string; label: string }[]>>({});

  /** Fields that have show_as_filter enabled */
  filterableFields = computed(() => this.fieldSchema().filter(f => f.show_as_filter));

  filteredRecords = computed(() => {
    const filters = this.activeFilters();
    const all = this.records();
    const active = Object.entries(filters).filter(([, v]) => v !== null && v !== '');
    if (!active.length) return all;
    return all.filter(rec => active.every(([key, value]) => {
      const recVal = rec.data[key];
      // "Sin asignar": en vez de comparar el valor, pide que NO haya ninguno.
      if (value === SIN_ASIGNAR) return valorSinAsignar(recVal);
      if (recVal === null || recVal === undefined) return false;
      const schema = this.fieldSchema().find(f => f.key === key);
      if (schema?.field_type === 'boolean') {
        const boolVal = recVal === true || recVal === 'true';
        return value === 'true' ? boolVal : !boolVal;
      }
      if (schema?.field_type === 'entity_select' || schema?.field_type === 'multi_entity_select'
        || schema?.field_type === 'catalog_select' || schema?.field_type === 'multi_catalog_select') {
        if (Array.isArray(recVal)) return recVal.map(String).includes(value!);
        return String(recVal) === value;
      }
      return String(recVal).toLowerCase().includes(value!.toLowerCase());
    }));
  });

  /** Opciones del zb-select de un filtro: "Todos" + "Sin asignar" (si la
   *  configuracion del campo lo activa) + las del campo. */
  filterSelectOptions(f: FieldSchema): ZbSelectOption[] {
    return [
      { value: null, label: `${f.label}: todos` },
      ...(f.allow_unassigned_filter ? [{ value: SIN_ASIGNAR, label: 'Sin asignar' }] : []),
      ...(this.filterOptions()[f.key] || []),
    ];
  }

  pagedRecords = computed(() => this.filteredRecords().slice(this.page() * this.pageSize(), (this.page() + 1) * this.pageSize()));

  totalPages = computed(() => Math.max(1, Math.ceil(this.filteredRecords().length / this.pageSize())));

  showAdd = signal(false);
  newData = signal<Record<string, any>>({});

  editingId = signal<number | null>(null);
  editData = signal<Record<string, any>>({});

  fieldSchema = signal<FieldSchema[]>([]);

  /** Constant weekday labels for shift operating_days UI. */
  readonly WEEKDAY_LABELS: { value: number; label: string }[] = [
    { value: 0, label: 'Lunes' },
    { value: 1, label: 'Martes' },
    { value: 2, label: 'Miércoles' },
    { value: 3, label: 'Jueves' },
    { value: 4, label: 'Viernes' },
    { value: 5, label: 'Sábado' },
    { value: 6, label: 'Domingo' },
  ];

  /** Maps "targetSlug::displayKey" → { recordId → label } */
  private refLookup = signal<Record<string, Record<number, string>>>({});

  /** Maps field key → lookup key ("targetSlug::displayKey") */
  fieldLookupKey: Record<string, string> = {};

  // ── Configurable columns (persisted per slug in localStorage) ──
  /** All active fields offered in the column menu. */
  candidateColumns = computed<ZbColumnDef[]>(() =>
    this.fieldSchema().map(f => ({ id: 'cd_' + f.key, label: f.label }))
  );
  /** Default visible set = fields flagged show_in_list in adminZebra. */
  private defaultVisibleColumns = computed(() =>
    this.fieldSchema().filter(f => f.show_in_list).map(f => 'cd_' + f.key)
  );
  /** Live user selection (seeded from prefs ?? default on load). */
  visibleColumns = signal<string[]>([]);

  displayedColumns = computed(() => {
    const cols = [...this.visibleColumns()];
    // En turnos, añade una columna "Vigencia" (estado vigente/caducado) justo
    // antes de Acciones. Solo aplica a la entidad shift.
    if (this.slug === 'shift') cols.push('validity');
    return [...cols, 'actions'];
  });

  /** Estado de vigencia de un turno para la celda "Vigencia" (tabla de turnos). */
  validityStatus(row: EntityRecord): { code: 'normal' | 'active' | 'expired' | 'future'; label: string; range: string } {
    const from: string | null = row.data['_valid_from'] || null;
    const to: string | null = row.data['_valid_to'] || null;
    const range = (from || to)
      ? `${from ? this.fmtDate(from) : '—'} → ${to ? this.fmtDate(to) : '—'}`
      : '';
    if (!from && !to) return { code: 'normal', label: 'Siempre activo', range };
    const today = new Date().toISOString().slice(0, 10);
    if (to && to < today) return { code: 'expired', label: 'Caducado', range };
    if (from && from > today) return { code: 'future', label: 'Programado', range };
    return { code: 'active', label: 'Vigente', range };
  }

  /** Formatea 'YYYY-MM-DD' → 'DD/MM/YYYY' para mostrar en la celda. */
  private fmtDate(iso: string): string {
    const [y, m, d] = iso.split('-');
    return d && m && y ? `${d}/${m}/${y}` : iso;
  }

  constructor(
    private route: ActivatedRoute,
    private entityTypeService: EntityTypeService,
    private entityRecordService: EntityRecordService,
    private entityFieldService: EntityFieldService,
    private shiftService: ShiftService,
    private workerService: WorkerService,
    private snack: MatSnackBar,
    private columnPrefs: ColumnPrefsService,
    private catalogService: CatalogService,
  ) {}

  /** Check if this slug is backed by a dedicated model (not pure EAV). */
  private get isModelBacked(): boolean { return this.slug === 'shift' || this.slug === 'worker'; }

  /** Convert a Shift API response to the EntityRecord shape used by the template. */
  private shiftToRecord(s: any): EntityRecord {
    return {
      id: s.id,
      entity_type: 'shift',
      entity_type_slug: 'shift',
      data: {
        ...s.custom_data,
        nombre: s.name, hora_llegada: s.start_time, hora_salida: s.end_time,
        _operating_days: s.operating_days || [],
        _valid_from: s.valid_from ?? null,
        _valid_to: s.valid_to ?? null,
        // Turno con inicio y sin fin = indefinido → checkbox marcado al editar.
        _indefinite: !!s.valid_from && !s.valid_to,
      },
      field_schema: s.field_schema ?? [],
      created_at: s.created_at ?? '',
      updated_at: s.updated_at ?? '',
    };
  }

  /** Convert entity-record data back to Shift API shape. */
  private recordDataToShift(data: Record<string, any>): any {
    // _indefinite es solo un flag de UI del checkbox; no se persiste (una
    // vigencia sin fin ya se representa con valid_to = null).
    const { nombre, hora_llegada, hora_salida, _display_nombre, _operating_days,
            _valid_from, _valid_to, _indefinite, ...rest } = data;
    return {
      name: nombre, start_time: hora_llegada, end_time: hora_salida,
      valid_from: _valid_from || null,
      // Indefinida → sin fecha de fin; si no, la que haya puesto el usuario.
      valid_to: _indefinite ? null : (_valid_to || null),
      custom_data: rest, operating_days: _operating_days || [],
    };
  }

  /** Convert a Worker API response to the EntityRecord shape used by the template. */
  private workerToRecord(w: any): EntityRecord {
    return {
      id: w.id,
      entity_type: 'worker',
      entity_type_slug: 'worker',
      data: { ...w.custom_data, nombre: w.name },
      field_schema: w.field_schema ?? [],
      created_at: w.created_at ?? '',
      updated_at: w.updated_at ?? '',
    };
  }

  /** Convert entity-record data back to Worker API shape. */
  private recordDataToWorker(data: Record<string, any>): any {
    const { nombre, activo, ...rest } = data;
    return { name: nombre, active: activo ?? true, custom_data: rest };
  }

  ngOnInit(): void {
    this.route.paramMap.pipe(
      switchMap(params => {
        this.slug = params.get('slug') ?? '';
        this.page.set(0);
        this.loading.set(true);
        return forkJoin({
          type: this.entityTypeService.get(this.slug),
          records: this.slug === 'shift'
            ? this.shiftService.getAllAdmin()
            : this.slug === 'worker'
              ? this.workerService.getAll()
              : this.entityRecordService.getAll(this.slug),
          fields: this.entityFieldService.getAll(this.slug),
        });
      }),
    ).subscribe({
      next: ({ type, records, fields }) => {
        this.entityType.set(type);
        const mapped = this.slug === 'shift'
          ? (records as any[]).map(s => this.shiftToRecord(s))
          : this.slug === 'worker'
            ? (records as any[]).map(w => this.workerToRecord(w))
            : records as EntityRecord[];
        this.records.set(mapped);
        // Reset filters when navigating to a new entity
        this.activeFilters.set({});
        this.filterOptions.set({});
        // Build FieldSchema from EntityField list
        const schema: FieldSchema[] = fields
          .filter(f => f.active)
          .sort((a, b) => a.order - b.order)
          .map(f => ({
            key: f.key,
            label: f.label,
            field_type: f.field_type,
            required: f.required,
            default_value: f.default_value,
            placeholder: f.placeholder,
            options: f.options,
            show_in_list: f.show_in_list,
            show_as_filter: f.show_as_filter,
            allow_unassigned_filter: f.allow_unassigned_filter,
            order: f.order,
            allow_priority: f.allow_priority,
            help_text: f.help_text,
            kind_code: f.kind_code,
            target_entity: f.target_entity,
            display_key: f.display_key,
            depends_on: f.depends_on,
            depends_on_field: f.depends_on_field,
            visible_when_field: f.visible_when_field,
            visible_when_value: f.visible_when_value,
          }));
        this.fieldSchema.set(schema);
        this.seedVisibleColumns();
        const hasRefFields = fields.some(f =>
          f.active && f.show_as_filter &&
          (f.field_type === 'entity_select' || f.field_type === 'multi_entity_select') && f.target_entity
        );
        if (hasRefFields) {
          this.loadRefLookups(fields);
        } else {
          this.buildNonEntityFilterOptions(fields);
        }
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  getLabel(record: EntityRecord, key: string): string {
    if (key === 'nombre' && this.slug === 'shift') {
      return record.data['nombre'] ?? '—';
    }
    const val = record.data[key];
    if (val === null || val === undefined) return '—';
    if (typeof val === 'boolean') return val ? 'Sí' : 'No';
    const schema = this.fieldSchema().find(f => f.key === key);
    if (schema && (schema.field_type === 'entity_select' || schema.field_type === 'multi_entity_select')) {
      const lk = this.fieldLookupKey[key];
      const lookup = lk ? (this.refLookup()[lk] ?? {}) : {};
      if (Array.isArray(val)) {
        return val.map(id => lookup[id] ?? id).join(', ');
      }
      return lookup[val] ?? String(val);
    }
    // Campos de CATÁLOGO: en el registro se guarda el código
    // ('jaca_sabinanigo') y hay que pintar su etiqueta ('Jaca + Sabiñánigo').
    // Antes caían al String(val) de abajo y se veía el código crudo: sin
    // acentos, con guiones bajos y sin el separador "+".
    if (schema && (schema.field_type === 'catalog_select'
                   || schema.field_type === 'multi_catalog_select')) {
      const labels = this.catalogLabels()[schema.kind_code ?? ''] ?? {};
      if (Array.isArray(val)) {
        return val.map(c => labels[String(c)] ?? String(c)).join(', ');
      }
      return labels[String(val)] ?? String(val);
    }
    return String(val);
  }

  /**
   * `{kind_code: {codigo: etiqueta}}` de los catálogos usados en la tabla.
   *
   * Se carga para TODOS los campos de catálogo, no solo los filtrables:
   * `filterOptions` solo se rellenaba cuando el campo tenía `show_as_filter`,
   * así que una columna de catálogo sin filtro no tenía de dónde sacar la
   * etiqueta.
   */
  private catalogLabels = signal<Record<string, Record<string, string>>>({});

  private loadCatalogLabels(fields: EntityField[]): void {
    const kinds = [...new Set(
      fields
        .filter(f => f.kind_code
          && (f.field_type === 'catalog_select' || f.field_type === 'multi_catalog_select'))
        .map(f => f.kind_code!),
    )];
    for (const kind of kinds) {
      this.catalogService.getValues(kind).subscribe(values => {
        this.catalogLabels.update(m => ({
          ...m,
          [kind]: Object.fromEntries(values.map(v => [String(v.code), v.label])),
        }));
      });
    }
  }

  getColumnLabel(col: string): string {
    const key = col.slice(3);
    return this.fieldSchema().find(f => f.key === key)?.label ?? key;
  }

  /** Tipo de un campo por su clave (para decidir cómo pintar la celda). */
  fieldTypeOf(key: string): string {
    return this.fieldSchema().find(f => f.key === key)?.field_type ?? 'text';
  }

  /** Valor crudo (string) de un campo `icon` en un registro, o '' si vacío. */
  iconValue(record: EntityRecord, key: string): string {
    const v = record.data[key];
    return typeof v === 'string' ? v : '';
  }

  /** Ruta del SVG del icono de sección (o '' si el valor no es un SVG conocido,
   *  p.ej. un icono Material → se pinta como <mat-icon>, no como <img>). */
  iconSrc(record: EntityRecord, key: string): string {
    return sectionIconPath(this.iconValue(record, key));
  }

  // ── Column visibility ─────────────────────────────────────────
  private seedVisibleColumns(): void {
    const valid = new Set(this.candidateColumns().map(c => c.id));
    const saved = this.columnPrefs.get(this.slug)?.filter(id => valid.has(id));
    this.visibleColumns.set(saved && saved.length ? saved : this.defaultVisibleColumns());
  }

  onColumnsChange(keys: string[]): void {
    this.visibleColumns.set(keys);
    this.columnPrefs.set(this.slug, keys);
  }

  onColumnsReset(): void {
    this.columnPrefs.clear(this.slug);
    this.visibleColumns.set(this.defaultVisibleColumns());
  }

  // ── Pagination ────────────────────────────────────────────────
  onPageSizeChange(size: number): void {
    this.pageSize.set(size);
    this.page.set(0);
  }

  // ── Delete the record currently open in the edit panel ─────────
  deleteEditing(): void {
    const id = this.editingId();
    const rec = this.records().find(r => r.id === id);
    if (rec) this.deleteRecord(rec);
  }

  // ── Add ──────────────────────────────────────────────────────
  openAdd(): void {
    this.showAdd.set(true);
    this.newData.set({});
    this.editingId.set(null);
  }

  cancelAdd(): void { this.showAdd.set(false); }

  saveAdd(): void {
    const obs: Observable<any> = this.slug === 'shift'
      ? this.shiftService.create(this.recordDataToShift(this.newData()))
      : this.slug === 'worker'
        ? this.workerService.create(this.recordDataToWorker(this.newData()))
        : this.entityRecordService.create({ entity_type: this.slug, data: this.newData() });
    obs.subscribe({
      next: (raw: any) => {
        const created = this.slug === 'shift' ? this.shiftToRecord(raw)
          : this.slug === 'worker' ? this.workerToRecord(raw) : raw;
        this.records.update(r => [...r, created]);
        if (!this.fieldSchema().length && created.field_schema?.length) {
          this.fieldSchema.set(created.field_schema);
        }
        this.showAdd.set(false);
        this.newData.set({});
      },
      error: () => this.snack.open('Error al guardar', '', { duration: 3000 }),
    });
  }

  // ── Edit ─────────────────────────────────────────────────────
  startEdit(record: EntityRecord): void {
    this.editingId.set(record.id);
    // Nombre para el título, tomado del display_field de la entidad (mismo
    // criterio que la tabla). Se guarda ahora y no se recalcula: el título
    // refleja el nombre con el que se abrió el panel.
    const displayKey = this.entityType()?.display_field || 'nombre';
    const nombre = record.data?.[displayKey] ?? record.data?.['nombre']
      ?? record.data?.['name'] ?? '';
    this.editingName.set(String(nombre ?? '').trim());
    this.editData.set({ ...record.data });
    this.showAdd.set(false);
    if (!this.fieldSchema().length && record.field_schema?.length) {
      this.fieldSchema.set(record.field_schema);
    }
  }

  cancelEdit(): void { this.editingId.set(null); }

  saveEdit(): void {
    const id = this.editingId();
    if (!id) return;
    const obs: Observable<any> = this.slug === 'shift'
      ? this.shiftService.update(id, this.recordDataToShift(this.editData()))
      : this.slug === 'worker'
        ? this.workerService.update(id, this.recordDataToWorker(this.editData()))
        : this.entityRecordService.update(id, { data: this.editData() });
    obs.subscribe({
      next: (raw: any) => {
        const updated = this.slug === 'shift' ? this.shiftToRecord(raw)
          : this.slug === 'worker' ? this.workerToRecord(raw) : raw;
        this.records.update(r => r.map(x => x.id === id ? updated : x));
        this.editingId.set(null);
      },
      error: () => this.snack.open('Error al guardar', '', { duration: 3000 }),
    });
  }

  // ── Delete ───────────────────────────────────────────────────
  // Confirmación con zb-dialog (modal del sistema, estilos --figma-modal-*,
  // overlay de página completa por encima del sidepanel). NO usar MatDialog:
  // su overlay quedaba por DEBAJO del zb-sidepanel.
  showDeleteConfirm = false;
  private pendingDelete: EntityRecord | null = null;
  /** Modal de error de dependencias (no se puede eliminar). */
  showDeleteError = false;
  deleteErrorMessage = '';

  /** Abre la confirmación de borrado (guarda el registro pendiente). */
  deleteRecord(record: EntityRecord): void {
    this.pendingDelete = record;
    this.showDeleteConfirm = true;
  }

  /** Confirmado en la modal → ejecuta el borrado. */
  confirmDelete(): void {
    this.showDeleteConfirm = false;
    const record = this.pendingDelete;
    if (!record) return;
    this.pendingDelete = null;
    const obs = this.slug === 'shift'
      ? this.shiftService.delete(record.id)
      : this.slug === 'worker'
        ? this.workerService.delete(record.id)
        : this.entityRecordService.delete(record.id);
    obs.subscribe({
      next: () => {
        this.records.update(r => r.filter(x => x.id !== record.id));
        if (this.editingId() === record.id) this.editingId.set(null);
      },
      error: (err) => {
        const body = err?.error;
        if (body?.dependents?.length) {
          const lines = body.dependents.map((d: any) => d.label).join('<br>• ');
          this.deleteErrorMessage = `Hay dependencias:<br>• ${lines}`;
          this.showDeleteError = true;
        } else {
          this.snack.open(body?.error || 'Error al eliminar', '', { duration: 3000 });
        }
      },
    });
  }

  // ── Filter helpers ────────────────────────────────────────────
  setFilter(fieldKey: string, value: string | null): void {
    this.activeFilters.update(f => ({ ...f, [fieldKey]: value }));
    this.page.set(0);
  }

  getFilterValue(fieldKey: string): string | null {
    return this.activeFilters()[fieldKey] ?? null;
  }

  // ── Download Excel ────────────────────────────────────────────
  downloadExcel(): void {
    const slug = this.slug;
    const exportFn = slug === 'worker'
      ? this.workerService.exportExcel()
      : this.entityRecordService.exportExcel(slug);

    exportFn.subscribe(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${slug}-${new Date().toISOString().slice(0, 10)}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    });
  }

  // ── Reference resolution ─────────────────────────────────────

  toggleDay(weekday: number, target: 'new' | 'edit'): void {
    const sig = target === 'new' ? this.newData : this.editData;
    sig.update(d => {
      const days: number[] = [...(d['_operating_days'] || [])];
      const idx = days.indexOf(weekday);
      if (idx >= 0) days.splice(idx, 1); else days.push(weekday);
      return { ...d, _operating_days: days };
    });
  }

  isDaySelected(weekday: number, target: 'new' | 'edit'): boolean {
    const data = target === 'new' ? this.newData() : this.editData();
    return (data['_operating_days'] || []).includes(weekday);
  }

  /** Actualiza la fecha de vigencia (inicio/fin) del turno en el formulario. */
  setValidity(target: 'new' | 'edit', edge: 'from' | 'to', value: string): void {
    const sig = target === 'new' ? this.newData : this.editData;
    const key = edge === 'from' ? '_valid_from' : '_valid_to';
    sig.update(d => ({ ...d, [key]: value || null }));
  }

  /** Estado del checkbox "Indefinida" del turno (flag de UI _indefinite). */
  isShiftIndefinite(target: 'new' | 'edit'): boolean {
    const d = target === 'new' ? this.newData() : this.editData();
    return d['_indefinite'] === true;
  }

  /** Al marcar "Indefinida" se oculta y limpia la fecha de fin (turno vigente
   *  sin fin). El flag _indefinite recuerda la elección del usuario. */
  setShiftIndefinite(target: 'new' | 'edit', checked: boolean): void {
    const sig = target === 'new' ? this.newData : this.editData;
    sig.update(d => ({
      ...d,
      _indefinite: checked,
      _valid_to: checked ? null : d['_valid_to'],
    }));
  }

  private loadRefLookups(fields: EntityField[]): void {
    const refFields = fields.filter(f =>
      f.active && (f.field_type === 'entity_select' || f.field_type === 'multi_entity_select') && f.target_entity
    );
    if (!refFields.length) return;

    // Group by target_entity slug to avoid duplicate fetches
    const targetSlugs = [...new Set(refFields.map(f => f.target_entity!))];

    forkJoin(
      targetSlugs.map(slug =>
        forkJoin({
          type: this.entityTypeService.get(slug),
          records: slug === 'shift'
            ? this.shiftService.getAll()
            : slug === 'worker'
              ? this.workerService.getAll()
              : this.entityRecordService.getAll(slug),
        })
      )
    ).subscribe(results => {
      const typeMap = new Map<string, { type: EntityTypeDef; records: any[] }>();
      for (const r of results) typeMap.set(r.type.slug, r);

      const allLookups: Record<string, Record<number, string>> = {};

      for (const field of refFields) {
        const entry = typeMap.get(field.target_entity!);
        if (!entry) continue;
        const displayKey = field.display_key || entry.type.display_field || 'name';
        const lookupKey = `${field.target_entity}::${displayKey}`;
        this.fieldLookupKey[field.key] = lookupKey;

        if (!allLookups[lookupKey]) {
          const lk: Record<number, string> = {};
          const isModel = field.target_entity === 'shift' || field.target_entity === 'worker';
          for (const rec of entry.records) {
            lk[rec.id] = isModel ? (rec.name ?? `#${rec.id}`) : (rec.data?.[displayKey] ?? `#${rec.id}`);
          }
          allLookups[lookupKey] = lk;
        }
      }

      this.refLookup.set(allLookups);

      // Build filterOptions for entity_select fields with show_as_filter
      const opts: Record<string, { value: string; label: string }[]> = {};
      for (const field of refFields.filter(f => f.show_as_filter)) {
        const lk = this.fieldLookupKey[field.key];
        const lookup = lk ? (allLookups[lk] ?? {}) : {};
        opts[field.key] = Object.entries(lookup)
          .map(([id, label]) => ({ value: id, label: String(label) }))
          .sort((a, b) => a.label.localeCompare(b.label));
      }
      // Also build opts for non-entity filter fields (boolean, select)
      for (const field of fields.filter(f => f.show_as_filter && f.field_type !== 'entity_select' && f.field_type !== 'multi_entity_select')) {
        if (field.field_type === 'boolean') {
          opts[field.key] = [{ value: 'true', label: 'Sí' }, { value: 'false', label: 'No' }];
        } else if (field.field_type === 'select' && field.options?.length) {
          opts[field.key] = field.options.map(o => ({ value: o, label: o }));
        }
      }
      this.filterOptions.set(opts);
      this.loadCatalogFilterOptions(fields);
    });
  }

  /** Build filterOptions for non-entity filter fields (when there are no refFields to load) */
  private buildNonEntityFilterOptions(fields: EntityField[]): void {
    const opts: Record<string, { value: string; label: string }[]> = {};
    for (const field of fields.filter(f => f.show_as_filter)) {
      if (field.field_type === 'boolean') {
        opts[field.key] = [{ value: 'true', label: 'Sí' }, { value: 'false', label: 'No' }];
      } else if (field.field_type === 'select' && field.options?.length) {
        opts[field.key] = field.options.map(o => ({ value: o, label: o }));
      }
    }
    this.filterOptions.set(opts);
    this.loadCatalogFilterOptions(fields);
  }

  /** Opciones de filtro para campos catalog_select / multi_catalog_select
   *  (los valores viven en el catálogo, no en los registros). */
  private loadCatalogFilterOptions(fields: EntityField[]): void {
    // Etiquetas de TODOS los campos de catálogo (para pintar las celdas), no
    // solo de los filtrables.
    this.loadCatalogLabels(fields);
    for (const field of fields.filter(f =>
      f.show_as_filter && f.kind_code
      && (f.field_type === 'catalog_select' || f.field_type === 'multi_catalog_select'))) {
      this.catalogService.getValues(field.kind_code!).subscribe(values => {
        this.filterOptions.update(opts => ({
          ...opts,
          [field.key]: values.map(v => ({ value: v.code, label: v.label })),
        }));
      });
    }
  }
}
