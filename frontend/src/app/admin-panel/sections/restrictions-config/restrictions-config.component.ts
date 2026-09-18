import { Component, OnInit, signal, computed, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDividerModule } from '@angular/material/divider';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { RestrictionService, WorkerFieldDef } from '@app/shared/services/restriction.service';
import { WorkerService } from '@app/shared/services/worker.service';
import { ShiftService } from '@app/shared/services/shift.service';
import { EntityTypeService } from '@app/shared/services/entity-type.service';
import { EntityRecordService } from '@app/shared/services/entity-record.service';
import { CatalogService } from '@app/shared/services/catalog.service';
import { Restriction, EngineSchema, EngineType } from '@app/shared/interfaces/restriction.interface';
import { Worker } from '@app/shared/interfaces/worker.interface';

import { EntityTypeDef, EntityRecord } from '@app/shared/interfaces/entity-field.interface';
import { ZbButtonComponent } from '@app/shared/components/zb-button/zb-button.component';
import { ZbPaginatorComponent } from '@app/shared/components/zb-paginator/zb-paginator.component';
import { forkJoin } from 'rxjs';

@Component({
  selector: 'app-restrictions-config',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatTableModule, MatButtonModule, MatIconModule,
    MatSlideToggleModule, MatCheckboxModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatCardModule,
    MatProgressSpinnerModule, MatTooltipModule, MatDividerModule,
    MatExpansionModule, MatSnackBarModule,
    ZbButtonComponent, ZbPaginatorComponent,
  ],
  templateUrl: './restrictions-config.component.html',
  styleUrl: './restrictions-config.component.scss',
})
export class RestrictionsConfigComponent implements OnInit {
  restrictions = signal<Restriction[]>([]);
  engineSchema = signal<Record<string, EngineSchema>>({});
  shiftSlots = signal<{code: string; label: string}[]>([]);
  workers = signal<Worker[]>([]);
  entityTypes = signal<EntityTypeDef[]>([]);
  entityRecordsMap = signal<Record<string, EntityRecord[]>>({});
  workerFields = signal<WorkerFieldDef[]>([]);
  catalogValuesMap = signal<Record<string, {code: string; label: string}[]>>({});

  loading = signal(true);
  importing = signal(false);
  dragOver = signal(false);
  page = signal(0);
  readonly pageSize = 10;
  pagedRestrictions = computed(() => this.restrictions().slice(this.page() * this.pageSize, (this.page() + 1) * this.pageSize));
  totalPages = computed(() => Math.max(1, Math.ceil(this.restrictions().length / this.pageSize)));
  editingId = signal<number | null>(null);
  editForm = signal<Partial<Restriction>>({});
  creating = signal(false);
  createForm = signal<Partial<Restriction>>({});

  /** Records of the planning-scope entity (e.g. tiendas) for scope_records selector */
  planningScopeEt = computed(() => this.entityTypes().find(e => e.is_planning_scope));
  planningScopeRecords = computed(() => {
    const et = this.planningScopeEt();
    if (!et) return [];
    return this.entityRecordsMap()[et.slug] ?? [];
  });

  displayedColumns = ['name', 'engine', 'type', 'severity', 'active', 'actions'];

  // ── Chat state ──────────────────────────────────────────────────
  chatOpen = signal(false);
  chatMessages = signal<{role: string; content: string}[]>([]);
  chatInput = signal('');
  chatLoading = signal(false);
  chatProposal = signal<Partial<Restriction> | null>(null);
  @ViewChild('chatScroll') chatScroll?: ElementRef<HTMLDivElement>;

  constructor(
    private restrictionService: RestrictionService,
    private workerService: WorkerService,
    private shiftService: ShiftService,
    private entityTypeService: EntityTypeService,
    private entityRecordService: EntityRecordService,
    private catalogService: CatalogService,
    private snackBar: MatSnackBar,
  ) {}

  ngOnInit(): void {
    this.entityTypeService.invalidate();
    this.entityRecordService.invalidate();
    this.workerService.invalidate();
    forkJoin({
      schema: this.restrictionService.getEngineSchema(),
      shifts: this.shiftService.getAll(),
      workers: this.workerService.getAll(),
      entityTypes: this.entityTypeService.getAll(),
      workerFields: this.restrictionService.getWorkerFields(),
    }).subscribe(({ schema, shifts, workers, entityTypes, workerFields }) => {
      this.engineSchema.set(schema);
      this.shiftSlots.set(shifts.map((s: any) => ({
        code: String(s.id),
        label: s.name ?? `Turno ${s.id}`,
      })));
      this.workers.set(workers);
      this.entityTypes.set(entityTypes);
      this.workerFields.set(workerFields);

      // Pre-load records for every EntityType
      if (entityTypes.length) {
        forkJoin(
          entityTypes.reduce((acc, et) => {
            acc[et.slug] = this.entityRecordService.getAll(et.slug);
            return acc;
          }, {} as Record<string, any>)
        ).subscribe(map => this.entityRecordsMap.set(map as Record<string, EntityRecord[]>));
      }

      // Pre-load catalog values for worker catalog_select fields
      const catalogCodes = workerFields
        .filter(f => (f.field_type === 'catalog_select' || f.field_type === 'multi_catalog_select') && f.kind_code)
        .map(f => f.kind_code);
      const uniqueCodes = [...new Set(catalogCodes)];
      if (uniqueCodes.length) {
        forkJoin(
          uniqueCodes.reduce((acc, code) => {
            acc[code] = this.catalogService.getValues(code);
            return acc;
          }, {} as Record<string, any>)
        ).subscribe(map => this.catalogValuesMap.set(map as Record<string, {code: string; label: string}[]>));
      }

      this.load();
    });
  }

  load(): void {
    this.page.set(0);
    this.loading.set(true);
    this.restrictionService.getAll().subscribe({
      next: r => { this.restrictions.set(r); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  getEngineLabel(engine: string): string {
    return this.engineSchema()[engine]?.label || engine;
  }

  toggleActive(r: Restriction): void {
    this.restrictionService.update(r.id, { active: !r.active }).subscribe(() => this.load());
  }

  // ── Create ────────────────────────────────────────────────────────────────
  startCreate(): void {
    this.creating.set(true);
    this.createForm.set({ engine: 'count' as EngineType, name: '', description: '', message: '', config: {}, severity: 'error', active: true, scope_records: [], customizable: false });
  }

  cancelCreate(): void { this.creating.set(false); }

  onCreateEngineChange(engine: EngineType): void {
    this.createForm.update(f => ({ ...f, engine, config: {} }));
  }

  saveCreate(): void {
    const f = this.createForm();
    if (!f.name?.trim()) return;
    this.restrictionService.create(f).subscribe({
      next: () => {
        this.creating.set(false);
        this.load();
        this.snackBar.open('Restricción creada', 'OK', { duration: 3000 });
      },
      error: () => this.snackBar.open('Error al crear la restricción', 'Cerrar', { duration: 5000 }),
    });
  }

  // ── Edit ──────────────────────────────────────────────────────────────────
  startEdit(r: Restriction): void {
    this.editingId.set(r.id);
    this.editForm.set({ ...r, config: { ...r.config } });
  }

  cancelEdit(): void { this.editingId.set(null); }

  saveEdit(): void {
    const f = this.editForm();
    if (!f.id) return;
    this.restrictionService.update(f.id, {
      name: f.name, description: f.description,
      engine: f.engine, config: f.config,
      severity: f.severity, active: f.active, message: f.message,
      scope_records: f.scope_records ?? [],
      customizable: f.customizable ?? false,
    }).subscribe({
      next: () => {
        this.editingId.set(null);
        this.load();
        this.snackBar.open('Restricción guardada', 'OK', { duration: 3000 });
      },
      error: () => this.snackBar.open('Error al guardar', 'Cerrar', { duration: 5000 }),
    });
  }

  // ── Delete ────────────────────────────────────────────────────────────────
  deleteRestriction(r: Restriction): void {
    if (!confirm(`Eliminar restricción "${r.name}"?`)) return;
    this.restrictionService.delete(r.id).subscribe({
      next: () => {
        this.load();
        this.snackBar.open('Restricción eliminada', 'OK', { duration: 3000 });
      },
      error: () => this.snackBar.open('Error al eliminar', 'Cerrar', { duration: 5000 }),
    });
  }

  // ── Config helpers ────────────────────────────────────────────────────────
  updateConfig(form: Partial<Restriction>, key: string, value: any): void {
    const config = { ...(form.config || {}), [key]: value };
    if (form === this.editForm()) {
      this.editForm.update(f => ({ ...f, config }));
    } else {
      this.createForm.update(f => ({ ...f, config }));
    }
  }

  updateConfigMulti(form: Partial<Restriction>, updates: Record<string, any>): void {
    const config = { ...(form.config || {}), ...updates };
    if (form === this.editForm()) {
      this.editForm.update(f => ({ ...f, config }));
    } else {
      this.createForm.update(f => ({ ...f, config }));
    }
  }

  getConfig(form: Partial<Restriction>, key: string, def: any = ''): any {
    return form.config?.[key] ?? def;
  }

  // ── Rule type (combines subject + groupBy) ────────────────────────────────
  entityNameBySlug(slug: string): string {
    if (!slug) return 'entidad';
    const et = this.entityTypes().find(e => e.slug === slug);
    return et?.name || slug;
  }

  turnoEntityName(): string {
    return 'Turno';
  }

  scopeEntityTypes(): EntityTypeDef[] {
    return this.entityTypes().filter(e => e.slug !== 'shift');
  }

  scopeEntityName(form: Partial<Restriction>): string {
    return this.entityNameBySlug(this.getConfig(form, 'scopeEntityType', ''));
  }

  matchEntityName(form: Partial<Restriction>): string {
    return this.entityNameBySlug(this.getConfig(form, 'areaEntityType', ''));
  }

  scopeRecords(form: Partial<Restriction>): EntityRecord[] {
    return this.recordsFor(this.getConfig(form, 'scopeEntityType', ''));
  }

  getRuleType(form: Partial<Restriction>): string {
    const s = this.getConfig(form, 'subject', 'workers');
    const g = this.getConfig(form, 'groupBy', 'shift');
    return `${s}__${g}`;
  }

  onRuleTypeChange(form: Partial<Restriction>, ruleType: string): void {
    const [subject, groupBy] = ruleType.split('__');
    this.updateConfigMulti(form, { subject, groupBy });
  }

  onScopeEntityChange(form: Partial<Restriction>, slug: string): void {
    const updates: Record<string, any> = { scopeEntityType: slug, filterAreaNames: [] };
    // If scope entity cleared, reset rule type to one that doesn't need it
    const rt = this.getRuleType(form);
    if (!slug && (rt === 'workers__shift_area' || rt === 'areas__shift_worker')) {
      updates['subject'] = 'workers';
      updates['groupBy'] = 'shift';
    }
    this.updateConfigMulti(form, updates);
  }

  // ── Worker field filter ───────────────────────────────────────────────────
  onFilterFieldChange(form: Partial<Restriction>, fieldKey: string): void {
    const wf = this.workerFields().find(f => f.key === fieldKey);
    this.updateConfigMulti(form, {
      filterField: fieldKey,
      filterEntityType: wf?.target_entity || '',
      filterKindCode: wf?.kind_code || '',
      filterRecordId: null,
      filterValue: null,
    });
  }

  getFilterOptions(form: Partial<Restriction>): {value: any; label: string}[] {
    const fieldKey = this.getConfig(form, 'filterField', '');
    if (!fieldKey) return [];
    const wf = this.workerFields().find(f => f.key === fieldKey);
    if (!wf) return [];
    if (wf.field_type === 'entity_select' || wf.field_type === 'multi_entity_select') {
      const records = this.recordsFor(wf.target_entity);
      const et = this.entityTypeFor(wf.target_entity);
      return records.map(r => ({ value: r.id, label: this.recordLabel(r, et) }));
    }
    if (wf.field_type === 'catalog_select' || wf.field_type === 'multi_catalog_select') {
      const values = this.catalogValuesMap()[wf.kind_code] ?? [];
      return values.map(v => ({ value: v.code, label: v.label }));
    }
    return [];
  }

  onFilterValueChange(form: Partial<Restriction>, value: any): void {
    const fieldKey = this.getConfig(form, 'filterField', '');
    const wf = this.workerFields().find(f => f.key === fieldKey);
    if (wf && (wf.field_type === 'entity_select' || wf.field_type === 'multi_entity_select')) {
      this.updateConfigMulti(form, { filterRecordId: value, filterValue: null });
    } else {
      this.updateConfigMulti(form, { filterValue: value, filterRecordId: null });
    }
  }

  getFilterValue(form: Partial<Restriction>): any {
    return this.getConfig(form, 'filterRecordId') ?? this.getConfig(form, 'filterValue') ?? null;
  }

  getFilterLabel(form: Partial<Restriction>): string {
    const fieldKey = this.getConfig(form, 'filterField', '');
    const wf = this.workerFields().find(f => f.key === fieldKey);
    if (!wf) return '';
    const val = this.getFilterValue(form);
    if (!val) return wf.label;
    const opts = this.getFilterOptions(form);
    const opt = opts.find(o => String(o.value) === String(val));
    return `${wf.label} = ${opt?.label || val}`;
  }

  recordsFor(slug: string): EntityRecord[] {
    return this.entityRecordsMap()[slug] ?? [];
  }

  recordLabel(record: EntityRecord, et: EntityTypeDef | undefined): string {
    const df = et?.display_field || 'nombre';
    return String(record.data?.[df] ?? record.data?.['nombre'] ?? record.data?.['name'] ?? `#${record.id}`);
  }

  entityTypeFor(slug: string): EntityTypeDef | undefined {
    return this.entityTypes().find(e => e.slug === slug);
  }

  scopeRecordLabel(id: number): string {
    const records = this.planningScopeRecords();
    const et = this.planningScopeEt();
    const rec = records.find(r => r.id === id);
    return rec ? this.recordLabel(rec, et) : `#${id}`;
  }

  getScopeLabel(r: Restriction): string {
    if (!r.scope_records?.length) return '';
    return r.scope_records.map(id => this.scopeRecordLabel(id)).join(', ');
  }



  // ── Worker pairs ──────────────────────────────────────────────────────────
  addWorkerPair(form: Partial<Restriction>): void {
    const pairs = [...(form.config?.['workerPairs'] || []), [null, null]];
    this.updateConfig(form, 'workerPairs', pairs);
  }

  removeWorkerPair(form: Partial<Restriction>, idx: number): void {
    const pairs = [...(form.config?.['workerPairs'] || [])];
    pairs.splice(idx, 1);
    this.updateConfig(form, 'workerPairs', pairs);
  }

  updateWorkerPair(form: Partial<Restriction>, idx: number, pos: number, value: number): void {
    const pairs = [...(form.config?.['workerPairs'] || [])];
    const pair = [...(pairs[idx] || [null, null])];
    pair[pos] = value;
    pairs[idx] = pair;
    this.updateConfig(form, 'workerPairs', pairs);
  }

  // ── Generic form field helpers ────────────────────────────────────────────
  updateField(isCreate: boolean, key: string, value: any): void {
    if (isCreate) {
      this.createForm.update(f => ({ ...f, [key]: value }));
    } else {
      this.editForm.update(f => ({ ...f, [key]: value }));
    }
  }

  onEngineChange(isCreate: boolean, value: EngineType): void {
    if (isCreate) {
      this.onCreateEngineChange(value);
    } else {
      this.editForm.update(f => ({ ...f, engine: value, config: {} }));
    }
  }

  // ── Condition engine helpers ──────────────────────────────────────────────
  getConditionJson(form: Partial<Restriction>): string {
    const filter = form.config?.['filter'];
    if (!filter) return '';
    try { return JSON.stringify(filter, null, 2); } catch { return ''; }
  }

  setConditionJson(form: Partial<Restriction>, raw: string): void {
    if (!raw.trim()) { this.updateConfig(form, 'filter', null); return; }
    try {
      const parsed = JSON.parse(raw);
      this.updateConfig(form, 'filter', parsed);
    } catch {
      this.snackBar.open('JSON de condición inválido', 'Cerrar', { duration: 4000 });
    }
  }

  // ── Display helpers ───────────────────────────────────────────────────────
  getConfigSummary(r: Restriction): string {
    const c = r.config || {};
    const scopeName = this.entityNameBySlug(c['scopeEntityType'] || '');
    switch (r.engine) {
      case 'count': {
        const ops: Record<string, string> = { lte: 'máx', gte: 'mín' };
        const op = ops[c['operator']] || '?';
        const th = c['threshold'] || '?';
        const ruleTypes: Record<string, string> = {
          'workers__shift': `${op} ${th} trabajadores por turno`,
          'workers__shift_area': `${op} ${th} trabajadores por turno y ${scopeName.toLowerCase()}`,
          'shifts__day_worker': `${op} ${th} turnos al día por trabajador`,
          'areas__shift_worker': `${op} ${th} ${scopeName.toLowerCase()}s por trabajador en turno`,
        };
        const key = `${c['subject'] || 'workers'}__${c['groupBy'] || 'shift'}`;
        let s = ruleTypes[key] || `${op} ${th}`;
        if (c['filterField']) {
          const wf = this.workerFields().find(f => f.key === c['filterField']);
          s += ` · ${wf?.label || c['filterField']}`;
        }
        return s;
      }
      case 'exclusion': {
        const types: Record<string, string> = {
          consecutive_shifts: 'Turnos consecutivos',
          worker_pair: `${(c['workerPairs'] || []).length} pareja(s)`,
          rest_conflict: 'Descanso en turno',
        };
        return types[c['exclusionType']] || c['exclusionType'] || '';
      }
      case 'match': {
        const matchScope = this.entityNameBySlug(c['areaEntityType'] || '');
        const types: Record<string, string> = {
          worker_preference: 'Preferencia de turno',
          area_role: `Entidad requerida por ${matchScope.toLowerCase()}`,
          area_membership: 'Pertenece a la polivalencia del trabajador',
        };
        return types[c['matchType']] || c['matchType'] || '';
      }
      case 'closed_day': {
        return 'Bloquea asignaciones en días de cierre';
      }
      case 'condition': {
        const scopeLabels: Record<string, string> = {
          per_shift: 'por turno', per_day: 'por día',
          per_day_worker: 'por trabajador/día', per_week_worker: 'por trabajador/semana',
          per_week_worker_hours: 'horas por trabajador/semana',
          per_week_worker_shift: 'por trabajador/semana/turno',
          per_shift_worker: 'por trabajador/turno', per_shift_area: 'por turno/área',
        };
        const op = c['operator'] === 'lte' ? 'máx' : c['operator'] === 'gte' ? 'mín' : '=';
        const scope = scopeLabels[c['scope'] || 'per_shift'] || c['scope'];
        const hasFilter = c['filter'] && Object.keys(c['filter']).length > 0;
        return `${op} ${c['threshold'] ?? '?'} ${scope}${hasFilter ? ' + filtro' : ''}`;
      }
      default: return '';
    }
  }

  getWorkerName(id: number): string {
    return this.workers().find(w => w.id === id)?.name || `Trabajador ${id}`;
  }

  // ── Template download ──────────────────────────────────────────────────────

  downloadTemplate(): void {
    const shifts = this.shiftSlots();
    const shift1 = shifts[0]?.code ?? 'SHIFT_ID';
    const shift2 = shifts[1]?.code ?? 'SHIFT_ID_2';
    const shiftLabel1 = shifts[0]?.label ?? 'Turno 1';
    const shiftLabel2 = shifts[1]?.label ?? 'Turno 2';

    const scopeEts = this.scopeEntityTypes();
    const scopeSlug = scopeEts[0]?.slug ?? 'ENTITY_SLUG';
    const scopeName = scopeEts[0]?.name ?? 'Entidad';

    const entityFields = this.workerFields();
    const entitySelField = entityFields.find(f => f.field_type === 'entity_select' || f.field_type === 'multi_entity_select');
    const catalogField = entityFields.find(f => f.field_type === 'catalog_select' || f.field_type === 'multi_catalog_select');
    const catalogVals = catalogField ? (this.catalogValuesMap()[catalogField.kind_code] ?? []) : [];
    const firstCatalogVal = catalogVals[0]?.code ?? 'CATALOG_CODE';

    const template = [
      {
        _DOC: '═══════════════════════════════════════════════════════════════════════',
        _INFO: 'Plantilla de restricciones — elimina los campos _DOC e _INFO antes de importar.',
        _ENGINES: 'Hay 3 motores: "count" (conteo), "exclusion" (exclusión), "match" (coincidencia).',
        _SEVERITY: '"error" bloquea el guardado del plan. "warning" avisa pero permite guardar.',
        _SHIFTS: `IDs de turnos en esta instancia: ${shifts.map(s => `${s.code}="${s.label}"`).join(', ')}.`,
        name: '__LEER_INSTRUCCIONES_ARRIBA__',
        engine: 'count',
        severity: 'error',
        active: false,
        description: '',
        message: '',
        config: {},
      },

      // ──────────────────────────────────────────────────────
      // MOTOR: COUNT
      // ──────────────────────────────────────────────────────
      {
        _DOC: 'COUNT / Máx. trabajadores por turno (sin filtro). El más simple.',
        name: `Máximo 3 trabajadores por turno`,
        engine: 'count',
        severity: 'error',
        active: true,
        description: 'Ningún turno puede tener más de 3 trabajadores asignados.',
        message: '',
        config: {
          _DOC_subject: '"workers"=contar personas, "shifts"=contar turnos por día/trabajador, "areas"=contar areas por trabajador.',
          subject: 'workers',
          _DOC_groupBy: '"shift"=por turno, "shift_area"=por turno+entidad-scope, "day_worker"=por día+trabajador, "shift_worker"=por turno+trabajador.',
          groupBy: 'shift',
          _DOC_operator: '"lte"=máximo (≤), "gte"=mínimo (≥).',
          operator: 'lte',
          threshold: 3,
        },
      },

      {
        _DOC: 'COUNT / Mín. trabajadores por turno filtrados por campo del trabajador (entity_select).',
        name: `Mínimo 2 trabajadores de ${entitySelField?.label ?? 'Rol'} X por turno`,
        engine: 'count',
        severity: 'warning',
        active: true,
        description: '',
        message: '',
        config: {
          subject: 'workers',
          groupBy: 'shift',
          operator: 'gte',
          threshold: 2,
          _DOC_filterField: `Clave del campo del trabajador por el que filtrar. Campos disponibles: ${entityFields.map(f => f.key).join(', ')}.`,
          filterField: entitySelField?.key ?? 'WORKER_FIELD_KEY',
          _DOC_filterEntityType: 'Slug de la entidad que apunta ese campo (se rellena automáticamente al importar si usas el panel).',
          filterEntityType: entitySelField?.target_entity ?? 'ENTITY_SLUG',
          _DOC_filterRecordId: 'ID numérico del registro de entidad por el que filtrar. Usa null si filtras por catalog_select.',
          filterRecordId: null,
          _DOC_filterValue: 'Código del catálogo por el que filtrar. Usa null si filtras por entity_select.',
          filterValue: null,
        },
      },

      {
        _DOC: 'COUNT / Mín. trabajadores por turno filtrados por campo de catálogo.',
        name: `Mínimo 1 trabajador de contrato "${firstCatalogVal}" por turno`,
        engine: 'count',
        severity: 'warning',
        active: true,
        description: '',
        message: '',
        config: {
          subject: 'workers',
          groupBy: 'shift',
          operator: 'gte',
          threshold: 1,
          filterField: catalogField?.key ?? 'WORKER_CATALOG_FIELD_KEY',
          filterEntityType: '',
          filterRecordId: null,
          filterValue: firstCatalogVal,
        },
      },

      {
        _DOC: `COUNT / Máx. trabajadores por turno y ${scopeName} (scope entity). Requiere que tengas una entidad marcada con "Ámbito de planificación".`,
        name: `Máximo 2 trabajadores por turno por ${scopeName}`,
        engine: 'count',
        severity: 'error',
        active: true,
        description: '',
        message: '',
        config: {
          subject: 'workers',
          groupBy: 'shift_area',
          operator: 'lte',
          threshold: 2,
          _DOC_scopeEntityType: `Slug de la entidad que actúa como scope (ej: "${scopeSlug}"). Debe tener "Ámbito de planificación" activo.`,
          scopeEntityType: scopeSlug,
        },
      },

      {
        _DOC: 'COUNT / Máx. 1 turno por día por trabajador (evita que el mismo trabajador esté en dos turnos el mismo día).',
        name: 'Máximo 1 turno por día por trabajador',
        engine: 'count',
        severity: 'error',
        active: true,
        description: 'Un trabajador no puede tener más de un turno asignado el mismo día.',
        message: '',
        config: {
          subject: 'shifts',
          groupBy: 'day_worker',
          operator: 'lte',
          threshold: 1,
        },
      },

      {
        _DOC: `COUNT / Máx. áreas por trabajador en un turno (subject="areas", groupBy="shift_worker"). Útil si tienes áreas/secciones asignables dentro del turno.`,
        name: 'Máximo 2 secciones por trabajador en un turno',
        engine: 'count',
        severity: 'warning',
        active: true,
        description: '',
        message: '',
        config: {
          subject: 'areas',
          groupBy: 'shift_worker',
          operator: 'lte',
          threshold: 2,
          scopeEntityType: scopeSlug,
        },
      },

      // ──────────────────────────────────────────────────────
      // MOTOR: EXCLUSION
      // ──────────────────────────────────────────────────────
      {
        _DOC: `EXCLUSION / Turnos consecutivos: si alguien trabajó el turno "${shiftLabel2}" no puede estar en "${shiftLabel1}" al día siguiente.`,
        name: `No turno de ${shiftLabel1} tras ${shiftLabel2} del día anterior`,
        engine: 'exclusion',
        severity: 'error',
        active: true,
        description: '',
        message: '',
        config: {
          exclusionType: 'consecutive_shifts',
          _DOC_shiftA: `ID del turno "anterior" (noche/tarde). IDs disponibles: ${shifts.map(s => `${s.code}="${s.label}"`).join(', ')}.`,
          shiftA: shift2,
          _DOC_shiftB: 'ID del turno "siguiente" (mañana). Detecta cuando shiftA anoche → shiftB hoy.',
          shiftB: shift1,
        },
      },

      {
        _DOC: 'EXCLUSION / Pareja de trabajadores incompatibles: no pueden coincidir en el mismo turno el mismo día.',
        name: 'Trabajadores incompatibles: Ana y Carlos',
        engine: 'exclusion',
        severity: 'warning',
        active: true,
        description: '',
        message: '',
        config: {
          exclusionType: 'worker_pair',
          _DOC_workerPairs: 'Array de pares [idA, idB]. Cada par no puede coincidir en el mismo turno. Los IDs son los IDs numéricos de los trabajadores.',
          workerPairs: [[2, 3]],
        },
      },

      {
        _DOC: 'EXCLUSION / Conflicto con descanso: marca error si un trabajador tiene descanso oficial y también está asignado a un turno ese día.',
        name: 'No asignar trabajadores en día de descanso oficial',
        engine: 'exclusion',
        severity: 'error',
        active: true,
        description: '',
        message: '',
        config: {
          exclusionType: 'rest_conflict',
        },
      },

      // ──────────────────────────────────────────────────────
      // MOTOR: MATCH
      // ──────────────────────────────────────────────────────
      {
        _DOC: 'MATCH / Preferencia de turno: avisa si un trabajador está asignado a un turno que no es de su preferencia (según su campo "turno preferido").',
        name: 'Respetar turno preferido del trabajador',
        engine: 'match',
        severity: 'warning',
        active: true,
        description: '',
        message: '',
        config: {
          matchType: 'worker_preference',
        },
      },

      {
        _DOC: `MATCH / Rol requerido por entidad-area: cada registro de la entidad "${scopeName}" puede definir un rol requerido; este motor verifica que haya al menos un trabajador con ese rol asignado en cada turno de esa entidad.`,
        name: `Rol requerido por ${scopeName}`,
        engine: 'match',
        severity: 'error',
        active: true,
        description: '',
        message: '',
        config: {
          matchType: 'area_role',
          _DOC_areaEntityType: `Slug de la entidad que define el requisito de rol. Ej: "${scopeSlug}".`,
          areaEntityType: scopeSlug,
          _DOC_workerRoleField: 'Clave del campo del trabajador que contiene su rol (entity_select → roles).',
          workerRoleField: entitySelField?.key ?? 'rol',
          _DOC_areaRoleField: `Clave del campo dentro del registro de ${scopeName} que indica qué rol se requiere.`,
          areaRoleField: 'required_role',
        },
      },

      {
        _DOC: `MATCH / Polivalencia: la sección/rol asignada en el horario debe estar entre TODOS los valores de un campo multi-selección del trabajador (no solo el principal). Útil para validar ediciones manuales.`,
        name: 'La sección asignada debe estar en la polivalencia del trabajador',
        engine: 'match',
        severity: 'warning',
        active: true,
        description: '',
        message: '',
        config: {
          matchType: 'area_membership',
          _DOC_workerField: `Clave del campo multi-selección del trabajador con sus secciones/roles posibles. Campos disponibles: ${entityFields.map(f => f.key).join(', ')}.`,
          workerField: entitySelField?.key ?? 'WORKER_FIELD_KEY',
        },
      },

      {
        _DOC: 'CLOSED_DAY / Sin configuración: se dispara si hay alguna asignación en una fecha marcada como día de cierre (festivo local, cierre puntual). Gestiona las fechas en Panel Interno > Días de cierre.',
        name: 'No asignar en días de cierre',
        engine: 'closed_day',
        severity: 'error',
        active: true,
        description: 'Ningún trabajador puede tener un turno asignado en una fecha marcada como cierre.',
        message: '',
        config: {},
      },
      // ───────────────────────────────────────────────────────
      // MOTOR: CONDITION (avanzado)
      // ───────────────────────────────────────────────────────
      {
        _DOC: 'CONDITION / Mín 2 trabajadores de contrato "plantilla" por turno. Filtro AND sobre campo EAV de catálogo.',
        name: `Mínimo 2 trabajadores plantilla por turno`,
        engine: 'condition',
        severity: 'warning',
        active: true,
        description: '',
        message: '',
        config: {
          _DOC_scope: '"per_shift"|"per_day"|"per_day_worker"|"per_week_worker"|"per_shift_worker"|"per_shift_area"',
          scope: 'per_shift',
          _DOC_dayOfWeek: 'null=todos | 0=lun | 1=mar | 2=mie | 3=jue | 4=vie | 5=sab | 6=dom',
          dayOfWeek: null,
          operator: 'gte',
          threshold: 2,
          filter: {
            field: catalogField?.key ?? 'tipo_de_contrato',
            op: 'eq',
            value: firstCatalogVal,
          },
        },
      },

      {
        _DOC: 'CONDITION / Máx 5 turnos en la semana por trabajador (agregado semanal, no posible con COUNT).',
        name: 'Máximo 5 turnos por trabajador en la semana',
        engine: 'condition',
        severity: 'error',
        active: true,
        description: '',
        message: '',
        config: {
          scope: 'per_week_worker',
          dayOfWeek: null,
          operator: 'lte',
          threshold: 5,
          filter: null,
        },
      },

      {
        _DOC: 'CONDITION / Mínimo 1 trabajador de zona X (entity_select) los sábados por turno. Combina day_of_week + filtro entity_select.',
        name: `Mínimo 1 trabajador de ${entitySelField?.label ?? 'Zona'} X los sábados`,
        engine: 'condition',
        severity: 'warning',
        active: true,
        description: '',
        message: '',
        config: {
          scope: 'per_shift',
          dayOfWeek: 5,
          operator: 'gte',
          threshold: 1,
          filter: {
            field: entitySelField?.key ?? 'zona',
            op: 'eq',
            _DOC_value: 'ID numérico del registro de entidad. Cogélo de los datos de la entidad.',
            value: null,
          },
        },
      },

      {
        _DOC: 'CONDITION / Árbol AND complejo: trabajadores de tipo plantilla O sustituto, Y de una zona concreta, con mín 1 por turno.',
        name: 'Mínimo 1 plantilla/sustituto de zona X por turno',
        engine: 'condition',
        severity: 'error',
        active: true,
        description: '',
        message: '',
        config: {
          scope: 'per_shift',
          dayOfWeek: null,
          operator: 'gte',
          threshold: 1,
          filter: {
            and: [
              {
                or: [
                  { field: catalogField?.key ?? 'tipo_de_contrato', op: 'eq', value: 'plantilla' },
                  { field: catalogField?.key ?? 'tipo_de_contrato', op: 'eq', value: 'sustituto' },
                ],
              },
              {
                field: entitySelField?.key ?? 'zona',
                op: 'eq',
                value: null,
              },
            ],
          },
        },
      },

      {
        _DOC: 'CONDITION / Excluir trabajadores: NO deben aparecer en ningún turno trabajadores de un tipo concreto (nin = not-in).',
        name: 'No asignar trabajadores ETT en domingos',
        engine: 'condition',
        severity: 'error',
        active: true,
        description: '',
        message: '',
        config: {
          scope: 'per_shift',
          dayOfWeek: 6,
          operator: 'lte',
          threshold: 0,
          filter: {
            field: catalogField?.key ?? 'tipo_de_contrato',
            op: 'eq',
            value: 'ett',
          },
        },
      },

      {
        _DOC: `CONDITION / Máx 3 turnos de ${shiftLabel1} por trabajador por semana. Usa scope per_week_worker_shift con targetShift.`,
        name: `Máximo 3 turnos de ${shiftLabel1} por trabajador/semana`,
        engine: 'condition',
        severity: 'error',
        active: true,
        description: '',
        message: '',
        config: {
          scope: 'per_week_worker_shift',
          _DOC_targetShift: `ID del turno a limitar. IDs disponibles: ${shifts.map(s => `${s.code}="${s.label}"`).join(', ')}.`,
          targetShift: shift1,
          dayOfWeek: null,
          operator: 'lte',
          threshold: 3,
          filter: null,
        },
      },

      {
        _DOC: 'CONDITION / Máx 6 trabajadores por día globalmente (scope per_day). Útil para límites de aforo diario.',
        name: 'Máximo 6 trabajadores diferentes por día',
        engine: 'condition',
        severity: 'error',
        active: true,
        description: '',
        message: '',
        config: {
          scope: 'per_day',
          dayOfWeek: null,
          operator: 'lte',
          threshold: 6,
          filter: null,
        },
      },

      {
        _DOC: `CONDITION / Mín 1 trabajador por turno y ${scopeName} (scope per_shift_area). Verifica cobertura por área dentro de cada turno.`,
        name: `Mínimo 1 trabajador por turno y ${scopeName}`,
        engine: 'condition',
        severity: 'warning',
        active: true,
        description: '',
        message: '',
        config: {
          scope: 'per_shift_area',
          dayOfWeek: null,
          operator: 'gte',
          threshold: 1,
          filter: null,
        },
      },
    ];

    const blob = new Blob([JSON.stringify(template, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'plantilla-restricciones.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  // ── Export / Import ───────────────────────────────────────────────────────

  /** Export a single restriction as JSON file (strips id so it can be reimported) */
  exportOne(r: Restriction): void {
    const { id, ...data } = r;
    this.downloadJson([data], `restriccion-${r.name.trim().replace(/\s+/g, '_')}.json`);
  }

  /** Export all restrictions as a JSON array */
  exportAll(): void {
    const data = this.restrictions().map(({ id, ...rest }) => rest);
    this.downloadJson(data, 'restricciones.json');
  }

  private downloadJson(data: any, filename: string): void {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  /** Triggered by the hidden file input */
  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.dragOver.set(true);
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.dragOver.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.dragOver.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (!file) return;
    this.processImportFile(file);
  }

  onImportFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    input.value = ''; // reset so same file can be re-selected
    this.processImportFile(file);
  }

  private processImportFile(file: File): void {
    const reader = new FileReader();
    reader.onload = () => {
      let parsed: any;
      try {
        parsed = JSON.parse(reader.result as string);
      } catch {
        this.snackBar.open('El archivo no es un JSON válido', 'Cerrar', { duration: 5000 });
        return;
      }

      // Accept both a single object and an array
      const items: Partial<Restriction>[] = Array.isArray(parsed) ? parsed : [parsed];
      const valid = items.filter(i => i.name && i.engine);
      if (!valid.length) {
        this.snackBar.open('El JSON no contiene restricciones válidas (se requiere name y engine)', 'Cerrar', { duration: 6000 });
        return;
      }
      this.importing.set(true);
      let done = 0;
      let errors = 0;
      const validEngines = ['count', 'exclusion', 'match', 'condition', 'closed_day'];
      for (const item of valid) {
        if (!validEngines.includes(item.engine as string)) {
          errors++;
          if (done + errors === valid.length) this.finishImport(done, errors);
          continue;
        }
        // Strip _DOC* keys from config
        const cleanConfig: Record<string, any> = {};
        for (const [k, v] of Object.entries(item.config || {})) {
          if (!k.startsWith('_DOC')) cleanConfig[k] = v;
        }
        const payload: Partial<Restriction> = {
          name: item.name,
          description: item.description || '',
          message: item.message || '',
          engine: item.engine,
          config: cleanConfig,
          severity: item.severity || 'error',
          active: item.active ?? true,
          scope_records: item.scope_records ?? [],
          customizable: item.customizable ?? false,
        };
        this.restrictionService.create(payload).subscribe({
          next: () => {
            done++;
            if (done + errors === valid.length) this.finishImport(done, errors);
          },
          error: () => {
            errors++;
            if (done + errors === valid.length) this.finishImport(done, errors);
          },
        });
      }
    };
    reader.readAsText(file);
  }

  private finishImport(done: number, errors: number): void {
    this.importing.set(false);
    const msg = errors === 0
      ? `${done} restricción(es) importada(s) correctamente`
      : `${done} importada(s), ${errors} con error`;
    this.snackBar.open(msg, 'OK', { duration: 5000 });
    this.load();
  }

  // ── Chat methods ─────────────────────────────────────────────────

  toggleChat(): void {
    this.chatOpen.update(v => !v);
    if (this.chatOpen() && this.chatMessages().length === 0) {
      this.chatMessages.set([{
        role: 'assistant',
        content: '¡Hola! Describe la restricción que quieres crear en lenguaje normal. Por ejemplo:\n\n• "Quiero que haya mínimo 2 pescaderos por turno"\n• "Que un trabajador no pueda hacer más de 5 turnos a la semana"\n• "No asignar a Pedro y María en el mismo turno"',
      }]);
    }
  }

  sendChat(): void {
    const msg = this.chatInput().trim();
    if (!msg || this.chatLoading()) return;

    this.chatMessages.update(m => [...m, { role: 'user', content: msg }]);
    this.chatInput.set('');
    this.chatLoading.set(true);
    this.chatProposal.set(null);
    this.scrollChat();

    const history = this.chatMessages().slice(0, -1); // exclude last user msg, API adds it
    this.restrictionService.chat(msg, history).subscribe({
      next: res => {
        const reply = res.response;
        this.chatMessages.update(m => [...m, { role: 'assistant', content: reply }]);
        this.chatLoading.set(false);

        // Try to extract JSON proposal from reply
        const jsonMatch = reply.match(/```json\s*([\s\S]*?)```/);
        if (jsonMatch) {
          try {
            const parsed = JSON.parse(jsonMatch[1]);
            this.chatProposal.set(parsed);
          } catch { /* not valid JSON */ }
        }
        this.scrollChat();
      },
      error: () => {
        this.chatMessages.update(m => [...m, {
          role: 'assistant',
          content: 'Lo siento, ha ocurrido un error al procesar tu mensaje. Inténtalo de nuevo.',
        }]);
        this.chatLoading.set(false);
        this.scrollChat();
      },
    });
  }

  applyChatProposal(): void {
    const proposal = this.chatProposal();
    if (!proposal) return;

    this.restrictionService.create({
      name: proposal.name || 'Nueva restricción',
      description: proposal.description || '',
      engine: proposal.engine || 'count',
      config: proposal.config || {},
      severity: proposal.severity || 'error',
      message: proposal.message || '',
      scope_records: proposal.scope_records || [],
      active: proposal.active ?? true,
      customizable: proposal.customizable ?? false,
    } as Partial<Restriction>).subscribe({
      next: () => {
        this.chatMessages.update(m => [...m, {
          role: 'assistant',
          content: '✅ ¡Restricción creada correctamente! Ya aparece en la tabla.',
        }]);
        this.chatProposal.set(null);
        this.load();
        this.scrollChat();
        this.snackBar.open('Restricción creada desde el chat', 'OK', { duration: 3000 });
      },
      error: () => {
        this.chatMessages.update(m => [...m, {
          role: 'assistant',
          content: '❌ Error al crear la restricción. Revisa los datos e inténtalo de nuevo.',
        }]);
        this.scrollChat();
      },
    });
  }

  clearChat(): void {
    this.chatMessages.set([]);
    this.chatProposal.set(null);
    this.chatOpen.set(false);
  }

  private scrollChat(): void {
    setTimeout(() => {
      const el = this.chatScroll?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    }, 50);
  }

  formatChatMessage(content: string): string {
    // Convert markdown-ish text to HTML
    let html = content
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/```json\s*([\s\S]*?)```/g, '<pre class="chat-code">$1</pre>')
      .replace(/```([\s\S]*?)```/g, '<pre class="chat-code">$1</pre>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
    return html;
  }
}
