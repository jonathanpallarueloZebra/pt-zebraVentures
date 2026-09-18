import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { MatTableModule } from '@angular/material/table';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { ZbSkeletonComponent } from '@app/shared/components/zb-skeleton/zb-skeleton.component';
import { WorkerService } from '@app/shared/services/worker.service';
import { EntityFieldService } from '@app/shared/services/entity-field.service';
import { EntityRecordService } from '@app/shared/services/entity-record.service';
import { EntityTypeService } from '@app/shared/services/entity-type.service';
import { Worker } from '@app/shared/interfaces/worker.interface';
import { FieldSchema } from '@app/shared/interfaces/entity-field.interface';
import { DynamicFieldsComponent } from '@app/shared/components/dynamic-fields/dynamic-fields.component';
import { ColumnPrefsService } from '@app/shared/services/column-prefs.service';
import { ZbSidepanelComponent } from '@app/shared/components/zb-sidepanel/zb-sidepanel.component';
import { ZbEmptyStateComponent } from '@app/shared/components/zb-empty-state/zb-empty-state.component';
import { ZbColumnMenuComponent, ZbColumnDef } from '@app/shared/components/zb-column-menu/zb-column-menu.component';
import { ZbFilterMenuComponent, ZbFilterDef } from '@app/shared/components/zb-filter-menu/zb-filter-menu.component';
import { ZbSearchInputComponent } from '@app/shared/components/zb-search-input/zb-search-input.component';
import { ZbTableToolbarComponent } from '@app/shared/components/zb-table-toolbar/zb-table-toolbar.component';
import { ZbPaginatorComponent } from '@app/shared/components/zb-paginator/zb-paginator.component';
import { ZbButtonComponent } from '@app/shared/components/zb-button/zb-button.component';
import { ZbToggleComponent } from '@app/shared/components/zb-toggle/zb-toggle.component';
import { ZbPageHeaderComponent } from '@app/shared/components/zb-page-header/zb-page-header.component';
import { ZbInputComponent } from '@app/shared/components/zb-input/zb-input.component';
import { ZbDialogComponent, ZbDialogMode } from '@app/shared/components/zb-dialog/zb-dialog.component';
import { ZbFileUploadComponent } from '@app/shared/components/zb-file-upload/zb-file-upload.component';
import { ZbAlertComponent, AlertType } from '@app/shared/components/zb-alert/zb-alert.component';
import { ZbSelectComponent, ZbSelectOption } from '@app/shared/components/zb-select/zb-select.component';
import { CatalogService } from '@app/shared/services/catalog.service';
import { SIN_ASIGNAR, valorSinAsignar } from '@app/shared/constants/filters';

@Component({
  selector: 'app-employees',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatTableModule, MatIconModule,
    MatFormFieldModule, MatSelectModule,
    MatTooltipModule, DynamicFieldsComponent, MatSnackBarModule, ZbSkeletonComponent,
    ZbSidepanelComponent, ZbEmptyStateComponent, ZbColumnMenuComponent, ZbFilterMenuComponent,
    ZbTableToolbarComponent, ZbPaginatorComponent, ZbButtonComponent, ZbToggleComponent,
    ZbPageHeaderComponent, ZbInputComponent, ZbDialogComponent, ZbFileUploadComponent, ZbAlertComponent,
    ZbSearchInputComponent,
  ],
  templateUrl: './employees.component.html',
  styleUrl: './employees.component.scss',
})
export class EmployeesComponent implements OnInit {
  workers = signal<Worker[]>([]);
  fieldSchema = signal<FieldSchema[]>([]);
  loading = signal(true);
  page = signal(0);
  pageSize = signal(10);
  readonly pageSizeOptions = [10, 25, 50, 100];
  readonly slug = 'worker';
  readonly skRows = Array(8);

  // ── Filters (dashboard-style) ─────────────────────────────────
  activeFilters = signal<Record<string, string | null>>({});
  filterOptions = signal<Record<string, { value: string; label: string }[]>>({});
  filterableFields = computed(() => this.fieldSchema().filter(f => f.show_as_filter));

  /** Búsqueda por nombre (o código de empleado). Con 272 fichas, los filtros de
   *  zona/tienda no bastan para llegar a una persona concreta. */
  search = signal('');

  // ── Filtro de ESTADO (activos / inactivos) ────────────────────
  //
  // Arranca SIEMPRE en 'activo': la plantilla de trabajo son los activos, y los
  // inactivos solo interesan cuando se van a buscar. No se guarda la última
  // selección a propósito — al recargar debe volver a 'activo'.
  //
  // Va como un select más dentro del menú de "Filtros", junto a Zona/Tienda.
  // Ojo: NO es un campo de custom_data como los demás filtros de ese menú, sino
  // la columna `active` del Worker, así que lleva clave propia y se filtra
  // aparte (ver ESTADO_KEY en filteredWorkers y filterMenuDefs).
  estado = signal<'activo' | 'inactivo'>('activo');

  /** Clave del filtro de estado en el menú. Con `__` para que no choque nunca
   *  con la clave de un campo real de la entidad (que vienen del backend). */
  readonly ESTADO_KEY = '__estado';

  /** Total de empleados registrados, sea cual sea su estado (AC-2). */
  totalWorkers = computed(() => this.workers().length);

  /** Solo los que están activos (AC-3). */
  activeWorkers = computed(() => this.workers().filter(w => w.active).length);

  /** Inactivos = total - activos. */
  inactiveWorkers = computed(() => this.totalWorkers() - this.activeWorkers());

  /** Opciones del select de Estado, con el recuento de cada grupo: así se ve
   *  cuánta gente hay activa e inactiva (AC-3) sin salir del menú de filtros. */
  estadoOptions = computed<ZbSelectOption[]>(() => [
    { value: 'activo', label: `Activos (${this.activeWorkers()})` },
    { value: 'inactivo', label: `Inactivos (${this.inactiveWorkers()})` },
  ]);

  /**
   * Cambia el filtro de estado y vuelve a la primera página: con otro conjunto
   * de filas, seguir en la página 5 dejaría la tabla vacía.
   */
  setEstado(valor: 'activo' | 'inactivo'): void {
    this.estado.set(valor);
    this.page.set(0);
  }

  /** Etiqueta del estado actual, para el aviso de "sin resultados". */
  estadoLabel(): string {
    return this.estado() === 'activo' ? 'activos' : 'inactivos';
  }

  filteredWorkers = computed(() => {
    const filters = this.activeFilters();
    const active = Object.entries(filters).filter(([, v]) => v !== null && v !== '');
    const q = this.normalizeText(this.search());
    // El ESTADO se aplica primero y siempre: es el filtro base de la tabla.
    const quiereActivos = this.estado() === 'activo';
    let all = this.workers().filter(w => !!w.active === quiereActivos);
    if (q) {
      all = all.filter(w =>
        this.normalizeText(w.name).includes(q)
        || this.normalizeText(String((w.custom_data as any)?.codigo ?? '')).includes(q));
    }
    if (!active.length) return all;
    return all.filter(w => active.every(([key, value]) => {
      const recVal = (w.custom_data as any)?.[key];
      // AC-3: "Sin asignar" invierte la logica normal: en vez de comparar el
      // valor, pide que NO haya ninguno.
      if (value === SIN_ASIGNAR) return valorSinAsignar(recVal);
      // Sin este corte, un registro sin valor pasaria filtros que no cumple.
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

  /** Opciones del zb-select de un filtro: "Todos" + las del campo.
   *
   *  Los filtros se ENCADENAN: si el registro de la entidad tiene un campo que
   *  coincide con otro filtro ya activo (p.ej. la tienda guarda su `zona`), solo
   *  se ofrecen las opciones compatibles. Antes se listaban todas y se podía
   *  elegir zona "Jaca" + tienda "T02" (de Huesca), que no devuelve a nadie. */
  filterSelectOptions(f: FieldSchema): ZbSelectOption[] {
    let opts = this.filterOptions()[f.key] || [];
    const data = f.target_entity ? this.entityDataCache.get(f.target_entity) : null;
    if (data) {
      const otros = Object.entries(this.activeFilters())
        // SIN_ASIGNAR se excluye del encadenado: no es un valor del catalogo,
        // asi que compararlo contra los datos del registro no casaria nunca y
        // dejaria este desplegable vacio.
        .filter(([k, v]) => k !== f.key && v !== null && v !== '' && v !== SIN_ASIGNAR);
      if (otros.length) {
        opts = opts.filter(o => {
          const rec = data.get(Number(o.value));
          if (!rec) return true;             // sin datos: no se descarta
          return otros.every(([k, v]) => {
            const rv = rec[k];
            if (rv === undefined || rv === null) return true;  // no aplica
            return String(rv) === String(v);
          });
        });
      }
    }
    const base: ZbSelectOption[] = [{ value: null, label: `${f.label}: todos` }];
    // AC-2: "Sin asignar" solo si la configuracion del campo lo activa
    // (allow_unassigned_filter). Va primero, junto a "todos", porque no es un
    // valor mas del catalogo sino la ausencia de valor.
    if (f.allow_unassigned_filter) {
      base.push({ value: SIN_ASIGNAR, label: 'Sin asignar' });
    }
    return [...base, ...opts];
  }

  pagedWorkers = computed(() => {
    const f = this.filteredWorkers();
    const size = this.pageSize();
    // Acotamos la pagina: al desactivar al ultimo de la ultima pagina (el filtro
    // de estado lo saca de la lista) el indice se quedaba fuera de rango y la
    // tabla salia vacia estando en la pagina 3 de 2.
    const pagina = Math.min(this.page(), Math.max(0, Math.ceil(f.length / size) - 1));
    return f.slice(pagina * size, (pagina + 1) * size);
  });

  totalPages = computed(() => Math.max(1, Math.ceil(this.filteredWorkers().length / this.pageSize())));

  /** minúsculas y sin acentos, para que "muñoz" encuentre "MUÑOZ" y "peña"/"pena". */
  private normalizeText(s: string): string {
    return (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim();
  }

  /**
   * Tooltip de una celda truncada: solo se muestra si el texto es lo bastante
   * largo como para que la elipsis lo corte (la columna son 120px). Con valores
   * cortos -- un codigo, una zona -- el tooltip repetia lo que ya se lee en la
   * celda y solo molestaba al pasar el raton.
   */
  tooltipSiSeCorta(texto: string): string {
    const UMBRAL = 18;   // caracteres que caben aprox. en 120px
    return (texto || '').length > UMBRAL ? texto : '';
  }

  onSearchChange(value: string): void {
    this.search.set(value);
    this.page.set(0);   // si no, buscar desde la página 3 no muestra nada
  }

  setFilter(key: string, value: string | null): void {
    this.activeFilters.update(f => ({ ...f, [key]: value }));
    this.page.set(0);
  }

  getFilterValue(key: string): string | null {
    return this.activeFilters()[key] ?? null;
  }

  /** Definición de los filtros para el menú "Filtros" del toolbar. */
  filterMenuDefs = computed<ZbFilterDef[]>(() => [
    // Estado primero: es el filtro que más se toca y el único activo por defecto.
    { key: this.ESTADO_KEY, label: 'Estado', options: this.estadoOptions() },
    ...this.filterableFields().map(f => ({
      key: f.key,
      label: f.label,
      options: this.filterSelectOptions(f),
    })),
  ]);

  /** Valores que recibe el menú: los filtros de la entidad + el estado.
   *  El menú es un componente tonto (mapa clave→valor), así que el estado
   *  entra y sale por ahí como uno más. */
  filterMenuValues = computed<Record<string, string | number | null>>(() => ({
    ...this.activeFilters(),
    [this.ESTADO_KEY]: this.estado(),
  }));

  /** Aplica el mapa completo de valores emitido por el menú de filtros.
   *  Extrae el estado (que no es un campo de la entidad) y guarda el resto. */
  onFiltersChange(values: Record<string, string | number | null>): void {
    const { [this.ESTADO_KEY]: estadoVal, ...resto } = values;
    // Si el usuario pone "Estado: todos" (null) volvemos a 'activo': la tabla
    // no puede mezclar activos e inactivos, el estado es siempre uno de los dos.
    this.estado.set(estadoVal === 'inactivo' ? 'inactivo' : 'activo');
    this.activeFilters.set(resto as Record<string, string | null>);
    this.page.set(0);
  }

  /** Limpia todos los filtros. El estado vuelve a su valor por defecto
   *  ('activo'), que es el comportamiento de entrada a la pantalla. */
  clearFilters(): void {
    this.activeFilters.set({});
    this.estado.set('activo');
    this.page.set(0);
  }

  // entity_select resolution: slug -> { records: Map<id, label> }
  private entityLabelCache = new Map<string, Map<number, string>>();
  /** slug → (id → data cruda del registro). Se usa para encadenar filtros. */
  private entityDataCache = new Map<string, Map<number, any>>();

  editingId: number | null = null;
  editForm = { name: '' };
  editCustomData: Record<string, any> = {};
  showAddForm = false;
  newForm = { name: '', email: '' };
  newCustomData: Record<string, any> = {};

  saving = signal(false);
  saveAlert: { type: AlertType; title: string } | null = null;

  // ── Unsaved-changes guard ─────────────────────────────────────
  showUnsavedConfirm = false;
  private pendingUnsavedClose: (() => void) | null = null;
  private originalEditName = '';

  get isCreateDirty(): boolean {
    return this.newForm.name.trim() !== '' || this.newForm.email.trim() !== '';
  }
  get isEditDirty(): boolean {
    return this.editForm.name !== this.originalEditName;
  }

  onCreateCancel(): void {
    if (this.isCreateDirty) {
      this.showUnsavedConfirm = true;
      this.pendingUnsavedClose = () => {
        this.showAddForm = false;
        this.newForm = { name: '', email: '' };
        this.newCustomData = {};
      };
    }
  }

  onEditCancel(): void {
    if (this.isEditDirty) {
      this.showUnsavedConfirm = true;
      this.pendingUnsavedClose = () => {
        this.editingId = null;
        this.originalEditName = '';
      };
    }
  }

  confirmUnsavedClose(): void {
    this.showUnsavedConfirm = false;
    this.pendingUnsavedClose?.();
    this.pendingUnsavedClose = null;
  }
  private saveAlertTimer: ReturnType<typeof setTimeout> | null = null;

  private showSaveAlert(type: AlertType, title: string): void {
    if (this.saveAlertTimer) clearTimeout(this.saveAlertTimer);
    this.saveAlert = { type, title };
    this.saveAlertTimer = setTimeout(() => { this.saveAlert = null; }, 4000);
  }

  // ── Delete confirm ────────────────────────────────────────────
  showDeleteConfirm = false;
  deleteTargetWorker: Worker | null = null;
  get deleteConfirmTitle(): string {
    return this.deleteTargetWorker ? `¿Eliminar a ${this.deleteTargetWorker.name}?` : 'Eliminar empleado';
  }

  // ── Import result dialog ──────────────────────────────────────
  importResultVisible = false;
  importResultTitle = '';
  importResultMessage = '';
  importResultMode: ZbDialogMode = 'default';

  constructor(
    private workerService: WorkerService,
    private entityFieldService: EntityFieldService,
    private entityRecordService: EntityRecordService,
    private entityTypeService: EntityTypeService,
    private snackBar: MatSnackBar,
    private columnPrefs: ColumnPrefsService,
    private catalogService: CatalogService,
  ) {}

  // ── Configurable columns (persisted in localStorage, slug 'worker') ──
  /** Custom (cd_*) fields offered in the column menu. name/active/actions are structural. */
  candidateColumns = computed<ZbColumnDef[]>(() =>
    this.fieldSchema().map(f => ({ id: 'cd_' + f.key, label: f.label }))
  );
  private defaultVisibleColumns = computed(() =>
    this.fieldSchema().filter(f => f.show_in_list).map(f => 'cd_' + f.key)
  );
  visibleColumns = signal<string[]>([]);

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

  onPageSizeChange(size: number): void {
    this.pageSize.set(size);
    this.page.set(0);
  }

  ngOnInit(): void {
    forkJoin({
      fields: this.entityFieldService.getAll('worker'),
      workers: this.workerService.getAll(),
      entityTypes: this.entityTypeService.getAll(),
    }).subscribe({
      next: ({ fields, workers, entityTypes }) => {
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
        this.workers.set(workers);

        // Etiquetas de entidad para TODOS los campos entity_select del esquema.
        // No basta con los de show_in_list/show_as_filter: el usuario puede
        // activar cualquier columna desde el menú "Columnas", y sin su mapa de
        // etiquetas la celda mostraría los ids crudos ("70, 71") en vez de los
        // nombres. También hace falta en el sidepanel de edición.
        const entitySlugs = [...new Set(
          schema
            .filter(f => (f.field_type === 'entity_select' || f.field_type === 'multi_entity_select') && f.target_entity)
            .map(f => f.target_entity!)
        )];
        if (entitySlugs.length) {
          const displayFieldMap = new Map(entityTypes.map(t => [t.slug, t.display_field || 'nombre']));
          forkJoin(
            entitySlugs.reduce((acc, slug) => {
              acc[slug] = this.entityRecordService.getAll(slug);
              return acc;
            }, {} as Record<string, any>)
          ).subscribe((recordsMap: any) => {
            entitySlugs.forEach(slug => {
              const records = recordsMap[slug] ?? [];
              const labelMap = new Map<number, string>();
              const fieldsForSlug = schema.filter(f => f.target_entity === slug);
              const displayKey = fieldsForSlug.find(f => f.display_key)?.display_key
                || displayFieldMap.get(slug)
                || 'nombre';
              records.forEach((r: any) => {
                const label = r.data?.[displayKey] ?? r.data?.['nombre'] ?? r.data?.['name'] ?? `#${r.id}`;
                labelMap.set(r.id, String(label));
              });
              this.entityLabelCache.set(slug, labelMap);
              // Los DATOS completos (no solo la etiqueta) para poder encadenar
              // filtros: p.ej. mostrar solo las tiendas de la zona elegida.
              this.entityDataCache.set(slug, new Map<number, any>(
                records.map((r: any) => [r.id, r.data ?? {}])));
            });
            // Build filterOptions for entity_select filter fields
            const opts: Record<string, { value: string; label: string }[]> = {};
            for (const field of schema.filter(f => f.show_as_filter)) {
              if (field.field_type === 'boolean') {
                opts[field.key] = [{ value: 'true', label: 'Sí' }, { value: 'false', label: 'No' }];
              } else if (field.field_type === 'select' && field.options?.length) {
                opts[field.key] = field.options.map(o => ({ value: o, label: o }));
              } else if ((field.field_type === 'entity_select' || field.field_type === 'multi_entity_select') && field.target_entity) {
                const lm = this.entityLabelCache.get(field.target_entity);
                if (lm) {
                  opts[field.key] = Array.from(lm.entries())
                    .map(([id, label]) => ({ value: String(id), label }))
                    .sort((a, b) => a.label.localeCompare(b.label));
                }
              }
            }
            this.filterOptions.set(opts);
            this.loadCatalogFilterOptions(schema);
            this.loading.set(false);
          });
        } else {
          // No entity slugs — still build filter options for boolean/select fields
          const opts: Record<string, { value: string; label: string }[]> = {};
          for (const field of schema.filter(f => f.show_as_filter)) {
            if (field.field_type === 'boolean') {
              opts[field.key] = [{ value: 'true', label: 'Sí' }, { value: 'false', label: 'No' }];
            } else if (field.field_type === 'select' && field.options?.length) {
              opts[field.key] = field.options.map(o => ({ value: o, label: o }));
            }
          }
          this.filterOptions.set(opts);
          this.loadCatalogFilterOptions(schema);
          this.loading.set(false);
        }
      },
      error: () => this.loading.set(false),
    });
  }

  /** Opciones de filtro para campos catalog_select / multi_catalog_select
   *  (los valores viven en el catálogo, no en los registros). */
  private loadCatalogFilterOptions(schema: FieldSchema[]): void {
    // Etiquetas de TODOS los campos de catálogo (para pintar las celdas), no
    // solo de los que se pueden filtrar.
    this.loadCatalogLabels(schema);
    for (const field of schema.filter(f =>
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

  /** `{kind_code: {codigo: etiqueta}}` de los catálogos usados en la tabla. */
  private catalogLabels = signal<Record<string, Record<string, string>>>({});

  private loadCatalogLabels(schema: FieldSchema[]): void {
    const kinds = [...new Set(
      schema
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

  displayedColumns = computed(() => ['name', ...this.visibleColumns(), 'active', 'actions']);

  load(): void {
    this.page.set(0);
    this.loading.set(true);
    this.workerService.getAll().subscribe({
      next: workers => {
        this.workers.set(workers);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  startEdit(w: Worker): void {
    this.editingId = w.id;
    this.editForm = { name: w.name };
    this.editCustomData = { ...(w.custom_data || {}) };
    this.originalEditName = w.name;
  }

  cancelEdit(): void {
    this.editingId = null;
    this.originalEditName = '';
  }

  saveEdit(w: Worker): void {
    this.saving.set(true);
    this.workerService.update(w.id, {
      name: this.editForm.name,
      custom_data: this.editCustomData,
    }).subscribe({
      next: () => {
        this.saving.set(false);
        this.editingId = null;
        this.originalEditName = '';
        this.showSaveAlert('success', 'Empleado guardado correctamente');
        this.load();
      },
      error: () => {
        this.saving.set(false);
        this.showSaveAlert('error', 'Error al guardar el empleado');
      },
    });
  }

  toggleActive(w: Worker): void {
    const newState = !w.active;
    this.workers.update(list => list.map(x => x.id === w.id ? { ...x, active: newState } : x));
    this.workerService.patch(w.id, { active: newState }).subscribe({
      next: () => this.snackBar.open(newState ? 'Empleado activado' : 'Empleado desactivado', 'OK', { duration: 3000 }),
      error: () => {
        this.workers.update(list => list.map(x => x.id === w.id ? { ...x, active: w.active } : x));
        this.snackBar.open('Error al cambiar estado', 'Cerrar', { duration: 5000 });
      },
    });
  }

  deleteWorker(w: Worker): void {
    this.deleteTargetWorker = w;
    this.showDeleteConfirm = true;
  }

  confirmDeleteWorker(): void {
    const w = this.deleteTargetWorker;
    if (!w) return;
    this.workerService.delete(w.id).subscribe({
      next: () => {
        this.showDeleteConfirm = false;
        this.snackBar.open('Empleado eliminado', 'Cerrar', { duration: 3000 });
        if (this.editingId === w.id) this.editingId = null;
        this.load();
      },
      error: () => {
        this.showDeleteConfirm = false;
        this.snackBar.open('Error al eliminar', 'Cerrar', { duration: 5000 });
      },
    });
  }

  /** Elimina el empleado actualmente abierto en el panel de edición. */
  deleteEditing(): void {
    const w = this.getEditingWorker();
    if (w) this.deleteWorker(w);
  }

  /** Enciende los errores de obligatorios: solo tras intentar guardar, no al
   *  abrir el formulario (marcar en rojo algo aun sin tocar es agresivo). */
  mostrarErroresObligatorios = false;

  openAddForm(): void {
    this.showAddForm = true;
    this.newForm = { name: '', email: '' };
    this.newCustomData = {};
    this.mostrarErroresObligatorios = false;
  }

  cancelAdd(): void { this.showAddForm = false; }

  downloadExcel(): void {
    this.workerService.exportExcel().subscribe(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `empleados-${new Date().toISOString().slice(0, 10)}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    });
  }

  saveNew(): void {
    // AC-2/AC-3: si falta algun obligatorio no se envia nada; se encienden los
    // errores en los campos y se dice cuales faltan.
    this.mostrarErroresObligatorios = true;
    const faltan = this.camposObligatoriosQueFaltan();
    if (faltan.length) {
      this.showSaveAlert('error', `Faltan campos obligatorios: ${faltan.join(', ')}`);
      return;
    }

    this.saving.set(true);
    this.workerService.create({
      name: this.newForm.name,
      email: this.newForm.email || undefined,
      custom_data: this.newCustomData,
    }).subscribe({
      next: () => {
        this.saving.set(false);
        this.showAddForm = false;
        this.mostrarErroresObligatorios = false;
        this.showSaveAlert('success', 'Empleado creado correctamente');
        this.load();
      },
      error: (err) => {
        this.saving.set(false);
        // AC-4: el backend valida lo mismo. Si rechaza, se muestra SU mensaje
        // en vez de un "Error al crear" generico que no dice que arreglar.
        this.showSaveAlert('error', this.mensajeDeError(err, 'Error al crear el empleado'));
      },
    });
  }

  /**
   * Etiquetas de los campos obligatorios (segun la configuracion) que estan sin
   * rellenar. El "Nombre" no es un EntityField, es columna del Worker, asi que
   * se comprueba aparte.
   */
  camposObligatoriosQueFaltan(): string[] {
    const faltan: string[] = [];
    if (!this.newForm.name.trim()) faltan.push('Nombre');
    faltan.push(...this.fieldSchema()
      .filter(f => f.required
        // Un campo oculto por `visible_when` no esta en pantalla: exigirlo
        // bloquearia el boton sin que se pueda rellenar. Mismo criterio que
        // isMissing() en dynamic-fields.
        && this.campoVisible(f)
        && this.valorVacio(this.newCustomData[f.key] ?? f.default_value))
      .map(f => f.label));
    return faltan;
  }

  /** Un campo condicional solo cuenta si su condicion se cumple. */
  private campoVisible(f: FieldSchema): boolean {
    if (!f.visible_when_field) return true;
    const norm = (v: any): string => {
      if (v === true) return 'true';
      if (v === false) return 'false';
      if (v === null || v === undefined) return '';
      return String(v);
    };
    return norm(this.newCustomData[f.visible_when_field]) === norm(f.visible_when_value ?? '');
  }

  /** Mismo criterio de "vacio" que el backend: 0 y false SI son valores.
   *  Delega en el helper compartido para no tener dos definiciones de "vacio". */
  private valorVacio(v: any): boolean {
    return valorSinAsignar(v);
  }

  /** Saca un mensaje legible de un error de DRF ({campo: [mensaje]} anidado). */
  private mensajeDeError(err: any, porDefecto: string): string {
    const cuerpo = err?.error;
    if (!cuerpo || typeof cuerpo !== 'object') return porDefecto;
    const mensajes: string[] = [];
    const recorrer = (v: any) => {
      if (typeof v === 'string') { mensajes.push(v); return; }
      if (Array.isArray(v)) { v.forEach(recorrer); return; }
      if (v && typeof v === 'object') { Object.values(v).forEach(recorrer); }
    };
    recorrer(cuerpo);
    return mensajes.length ? mensajes.join(' ') : porDefecto;
  }

  customFieldDisplay(value: any, fieldKey?: string): string {
    if (value === null || value === undefined || value === '') return '–';
    if (value === true  || value === 'true')  return 'Sí';
    if (value === false || value === 'false') return 'No';

    // Resolve entity_select IDs using loaded cache
    const field = fieldKey ? this.fieldSchema().find(f => f.key === fieldKey) : undefined;
    if (field && (field.field_type === 'entity_select' || field.field_type === 'multi_entity_select') && field.target_entity) {
      const cache = this.entityLabelCache.get(field.target_entity);
      if (cache) {
        if (Array.isArray(value)) {
          return value
            .map((item: any) => {
              const id = typeof item === 'object' && item !== null ? item.value : item;
              return cache.get(Number(id)) ?? String(id);
            })
            .join(', ');
        }
        return cache.get(Number(value)) ?? String(value);
      }
    }

    // Campos de CATÁLOGO (p.ej. Zona): en la ficha se guarda el código
    // ('jaca_sabinanigo') y hay que mostrar su etiqueta ('Jaca + Sabiñánigo').
    // Sin esto se pintaba el código crudo, sin acentos ni separador.
    if (field && (field.field_type === 'catalog_select'
                  || field.field_type === 'multi_catalog_select') && field.kind_code) {
      const labels = this.catalogLabels()[field.kind_code] ?? {};
      const code = (v: any) =>
        typeof v === 'object' && v !== null && 'value' in v ? v.value : v;
      if (Array.isArray(value)) {
        return value.map(v => labels[String(code(v))] ?? String(code(v))).join(', ');
      }
      return labels[String(value)] ?? String(value);
    }

    if (Array.isArray(value)) {
      return value
        .map((item: any) => typeof item === 'object' && item !== null && 'value' in item ? item.value : item)
        .join(', ');
    }
    return String(value);
  }

  getEditingWorker(): Worker {
    return this.workers().find(w => w.id === this.editingId)!;
  }

  // ── Excel import ──────────────────────────────────────────
  showImport = false;
  importing = signal(false);

  downloadTemplate(): void {
    this.workerService.downloadImportTemplate().subscribe(blob => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'plantilla_empleados.xlsx';
      a.click();
      window.URL.revokeObjectURL(url);
    });
  }

  onFilesFromUpload(files: File[]): void {
    const file = files[0];
    if (!file) return;
    this.showImport = false;
    this.importing.set(true);
    this.workerService.importExcel(file).subscribe({
      next: (res: any) => {
        this.importing.set(false);
        this.load();
        this.displayImportResult(res);
      },
      error: (err) => {
        this.importing.set(false);
        this.snackBar.open(err.error?.error || 'Error al importar', 'Cerrar', { duration: 5000 });
      },
    });
  }

  private displayImportResult(res: { created: number; updated?: number; invited: number; skipped: string[]; errors: string[]; total_rows: number }): void {
    const hasIssues = res.skipped.length > 0 || res.errors.length > 0;
    this.importResultTitle = hasIssues ? 'Importación con incidencias' : 'Importación completada';
    // Se informa de creados Y actualizados: al reimportar el Excel exportado
    // lo normal es que no se cree ninguno y se actualicen todos.
    const partes: string[] = [];
    if (res.created) partes.push(`${res.created} creado(s)`);
    if (res.updated) partes.push(`${res.updated} actualizado(s)`);
    let msg = partes.length
      ? `${partes.join(' y ')} de ${res.total_rows} fila(s).`
      : `Ninguna fila procesada de ${res.total_rows}.`;
    if (res.invited > 0) msg += ` ${res.invited} email(s) de invitación enviado(s).`;
    if (res.skipped.length > 0) msg += ` ${res.skipped.length} fila(s) omitida(s) (ya existían).`;
    if (res.errors.length > 0) msg += ` ${res.errors.length} error(es) encontrado(s).`;
    this.importResultMessage = msg;
    this.importResultMode = hasIssues ? 'warning' : 'default';
    this.importResultVisible = true;
  }
}
