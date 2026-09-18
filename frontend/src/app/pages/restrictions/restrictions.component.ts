import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { forkJoin } from 'rxjs';
import { RestrictionService } from '@app/shared/services/restriction.service';
import { WorkerService } from '@app/shared/services/worker.service';
import { EntityTypeService } from '@app/shared/services/entity-type.service';
import { EntityRecordService } from '@app/shared/services/entity-record.service';
import { Restriction, EngineSchema } from '@app/shared/interfaces/restriction.interface';
import { EntityTypeDef, EntityRecord } from '@app/shared/interfaces/entity-field.interface';
import { Worker } from '@app/shared/interfaces/worker.interface';
import { ZbPageHeaderComponent } from '@app/shared/components/zb-page-header/zb-page-header.component';
import { ZbToggleComponent } from '@app/shared/components/zb-toggle/zb-toggle.component';
import { ZbEmptyStateComponent } from '@app/shared/components/zb-empty-state/zb-empty-state.component';
import { ZbPaginatorComponent } from '@app/shared/components/zb-paginator/zb-paginator.component';
import { ZbTableToolbarComponent } from '@app/shared/components/zb-table-toolbar/zb-table-toolbar.component';
import { ZbFilterMenuComponent, ZbFilterDef } from '@app/shared/components/zb-filter-menu/zb-filter-menu.component';
import { ZbSidepanelComponent } from '@app/shared/components/zb-sidepanel/zb-sidepanel.component';
import { ZbDialogComponent } from '@app/shared/components/zb-dialog/zb-dialog.component';
import { ZbSelectComponent, ZbSelectOption } from '@app/shared/components/zb-select/zb-select.component';
import { ZbInputComponent } from '@app/shared/components/zb-input/zb-input.component';
import { ZbButtonComponent } from '@app/shared/components/zb-button/zb-button.component';
import { ZbCheckboxComponent } from '@app/shared/components/zb-checkbox/zb-checkbox.component';
import { ZbIconComponent } from '@app/shared/components/zb-icon/zb-icon.component';

/** Tipo de restricción según quién puede tocarla. */
type RestrictionKind = 'fixed' | 'custom';

@Component({
  selector: 'app-restrictions',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatTableModule, MatSnackBarModule,
    ZbPageHeaderComponent, ZbToggleComponent,
    ZbEmptyStateComponent, ZbPaginatorComponent,
    ZbTableToolbarComponent, ZbFilterMenuComponent,
    ZbSidepanelComponent, ZbDialogComponent,
    ZbSelectComponent, ZbInputComponent, ZbButtonComponent, ZbCheckboxComponent,
    ZbIconComponent,
  ],
  templateUrl: './restrictions.component.html',
  styleUrl: './restrictions.component.scss',
})
export class RestrictionsComponent implements OnInit {
  restrictions = signal<Restriction[]>([]);
  engineSchema = signal<Record<string, EngineSchema>>({});
  workers = signal<Worker[]>([]);
  entityTypes = signal<EntityTypeDef[]>([]);
  scopeRecordsList = signal<EntityRecord[]>([]);
  loading = signal(true);

  page = signal(0);
  // Sin selector "Mostrar" en el toolbar: son pocas restricciones y caben de
  // una. El paginador solo aparece si algún día pasan de 25.
  pageSize = signal(25);

  /** Filtro Fijas / Personalizables (null = todas). */
  filterValues = signal<Record<string, string | number | null>>({ kind: null });

  filteredRestrictions = computed(() => {
    const kind = this.filterValues()['kind'];
    const all = this.restrictions();
    const list = kind
      ? all.filter(r => (kind === 'custom' ? r.customizable : !r.customizable))
      : all;
    // Sin filtro las dos clases van agrupadas y en orden: primero las fijas
    // (las define Zebra) y después las personalizables, para que se vean como
    // dos bloques distintos y no intercaladas por nombre.
    return [...list].sort((a, b) =>
      Number(!!a.customizable) - Number(!!b.customizable)
      || a.name.localeCompare(b.name, 'es'));
  });

  totalPages = computed(() =>
    Math.max(1, Math.ceil(this.filteredRestrictions().length / this.pageSize())));

  /** Página realmente visible: si `page` se queda fuera de rango (al filtrar o
   *  al reducir el tamaño de página) se acota a la última existente, en vez de
   *  mostrar una página vacía. */
  currentPage = computed(() => Math.min(this.page(), this.totalPages() - 1));

  pagedRestrictions = computed(() => {
    const size = this.pageSize();
    const from = this.currentPage() * size;
    return this.filteredRestrictions().slice(from, from + size);
  });

  displayedColumns = ['name', 'engine', 'kind', 'severity', 'scope', 'active', 'actions'];

  /** Entidad marcada como ámbito de planificación (normalmente Tienda). */
  planningScopeEt = computed(() => this.entityTypes().find(e => e.is_planning_scope));

  scopeEntityName = computed(() => this.planningScopeEt()?.name || 'Ámbito');

  filters = computed<ZbFilterDef[]>(() => [{
    key: 'kind',
    label: 'Tipo',
    options: [
      { value: '', label: 'Todas' },
      { value: 'fixed', label: 'Fijas' },
      { value: 'custom', label: 'Personalizables' },
    ],
  }]);

  // ── Edición (sidepanel) ────────────────────────────────────────────────────
  // Los paneles viven siempre en el DOM y se abren con [open] + (openChange),
  // igual que en /absences: así entran y salen con su transición.
  showEdit = signal(false);
  editing = signal<Restriction | null>(null);
  editForm = signal<Partial<Restriction>>({});
  saving = signal(false);

  // ── Duplicar (sidepanel) ───────────────────────────────────────────────────
  showDuplicate = signal(false);
  duplicating = signal<Restriction | null>(null);
  duplicateName = signal('');
  duplicateScope = signal<number[]>([]);

  // ── Eliminar (dialog) ──────────────────────────────────────────────────────
  showDeleteConfirm = signal(false);
  deleting = signal<Restriction | null>(null);

  constructor(
    private restrictionService: RestrictionService,
    private workerService: WorkerService,
    private entityTypeService: EntityTypeService,
    private entityRecordService: EntityRecordService,
    private snackBar: MatSnackBar,
  ) {}

  ngOnInit(): void {
    forkJoin({
      schema: this.restrictionService.getEngineSchema(),
      entityTypes: this.entityTypeService.getAll(),
      workers: this.workerService.getAll(),
    }).subscribe(({ schema, entityTypes, workers }) => {
      this.engineSchema.set(schema);
      this.entityTypes.set(entityTypes);
      this.workers.set(workers);

      const scopeEt = entityTypes.find(e => e.is_planning_scope);
      if (scopeEt) {
        this.entityRecordService.getAll(scopeEt.slug)
          .subscribe(recs => this.scopeRecordsList.set(recs));
      }
    });
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.restrictionService.getAll().subscribe({
      next: r => { this.restrictions.set(r); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  onFiltersChange(values: Record<string, string | number | null>): void {
    this.filterValues.set(values);
    this.page.set(0);
  }

  resetFilters(): void {
    this.filterValues.set({ kind: null });
    this.page.set(0);
  }

  // ── Display helpers ────────────────────────────────────────────────────────
  getEngineLabel(engine: string): string {
    return this.engineSchema()[engine]?.label || engine;
  }

  kindOf(r: Restriction): RestrictionKind {
    return r.customizable ? 'custom' : 'fixed';
  }

  recordLabel(record: EntityRecord): string {
    const df = this.planningScopeEt()?.display_field || 'nombre';
    return String(record.data?.[df] ?? record.data?.['nombre'] ?? record.data?.['name'] ?? `#${record.id}`);
  }

  scopeRecordLabel(id: number): string {
    const rec = this.scopeRecordsList().find(r => r.id === id);
    return rec ? this.recordLabel(rec) : `#${id}`;
  }

  getScopeLabel(r: Restriction): string {
    if (!r.scope_records?.length) return 'Todas';
    return r.scope_records.map(id => this.scopeRecordLabel(id)).join(', ');
  }

  scopeOptions(): ZbSelectOption[] {
    return this.scopeRecordsList().map(r => ({ value: r.id, label: this.recordLabel(r) }));
  }

  // ── Selección múltiple de ámbito (tiendas) ─────────────────────────────────
  /** Checkbox state for a scope record in the edit panel. */
  isScopeChecked(id: number): boolean {
    return (this.editForm().scope_records || []).includes(id);
  }

  toggleScope(id: number, checked: boolean): void {
    const current = this.editForm().scope_records || [];
    const next = checked ? [...current, id] : current.filter(x => x !== id);
    this.updateForm('scope_records', next);
  }

  /** Checkbox state for a scope record in the duplicate panel. */
  isDuplicateScopeChecked(id: number): boolean {
    return this.duplicateScope().includes(id);
  }

  toggleDuplicateScope(id: number, checked: boolean): void {
    this.duplicateScope.update(current =>
      checked ? [...current, id] : current.filter(x => x !== id));
  }

  getWorkerName(id: number | null): string {
    if (id == null) return 'Sin asignar';
    return this.workers().find(w => w.id === id)?.name || `Trabajador ${id}`;
  }

  workerOptions(): ZbSelectOption[] {
    return this.workers().map(w => ({ value: w.id, label: w.name }));
  }

  getConfigSummary(r: Restriction): string {
    const c = r.config || {};
    switch (r.engine) {
      case 'count': {
        const subjects: Record<string, string> = { workers: 'trabajadores', shifts: 'turnos', areas: 'áreas' };
        const ops: Record<string, string> = { lte: 'máx', gte: 'mín' };
        return `${ops[c['operator']] || ''} ${c['threshold'] ?? ''} ${subjects[c['subject']] || ''}`.trim();
      }
      case 'exclusion': {
        const types: Record<string, string> = {
          consecutive_shifts: 'Turnos consecutivos',
          worker_pair: 'Trabajadores incompatibles',
          rest_conflict: 'Descanso en turno',
        };
        const base = types[c['exclusionType']] || '';
        if (c['exclusionType'] === 'worker_pair') {
          const n = (c['workerPairs'] || []).length;
          return `${base} · ${n} pareja${n === 1 ? '' : 's'}`;
        }
        return base;
      }
      case 'match': {
        const types: Record<string, string> = {
          worker_preference: 'Preferencia de turno',
          area_role: 'Rol requerido del área',
          area_membership: 'Pertenece a la polivalencia',
        };
        return types[c['matchType']] || '';
      }
      case 'closed_day':
        return 'Bloquea días de cierre';
      case 'condition': {
        const scopes: Record<string, string> = {
          per_shift: 'por turno', per_day: 'por día',
          per_day_worker: 'por trabajador/día', per_week_worker: 'por trabajador/semana',
          per_week_worker_hours: 'horas por trabajador/semana',
          per_week_worker_shift: 'por trabajador/semana/turno',
          per_shift_worker: 'por trabajador/turno', per_shift_area: 'por turno/área',
        };
        const op = c['operator'] === 'lte' ? 'máx' : c['operator'] === 'gte' ? 'mín' : '=';
        return `${op} ${c['threshold'] ?? '?'} ${scopes[c['scope']] || c['scope'] || ''}`.trim();
      }
      default:
        return '';
    }
  }

  /** Rule type label shown read-only in the edit panel. */
  getRuleTypeLabel(r: Partial<Restriction>): string {
    const c = r.config || {};
    switch (r.engine) {
      case 'exclusion': {
        const types: Record<string, string> = {
          consecutive_shifts: 'Turnos consecutivos',
          worker_pair: 'Trabajadores incompatibles',
          rest_conflict: 'Descanso en turno',
        };
        return types[c['exclusionType']] || '—';
      }
      case 'match': {
        const types: Record<string, string> = {
          worker_preference: 'Preferencia de turno del trabajador',
          area_role: 'Rol requerido por área',
          area_membership: 'Pertenece a la polivalencia del trabajador',
        };
        return types[c['matchType']] || '—';
      }
      case 'count': {
        const subjects: Record<string, string> = { workers: 'Trabajadores', shifts: 'Turnos', areas: 'Áreas' };
        return `${subjects[c['subject']] || 'Trabajadores'} por turno`;
      }
      case 'condition': {
        const scopes: Record<string, string> = {
          per_shift: 'Por turno', per_day: 'Por día',
          per_day_worker: 'Por trabajador y día', per_week_worker: 'Por trabajador y semana',
          per_week_worker_hours: 'Horas por trabajador y semana',
          per_week_worker_shift: 'Por trabajador, semana y turno',
          per_shift_worker: 'Por trabajador y turno', per_shift_area: 'Por turno y área',
        };
        return scopes[c['scope']] || '—';
      }
      default:
        return '—';
    }
  }

  // ── Toggle activo (fijas y personalizables) ────────────────────────────────
  toggleActive(r: Restriction): void {
    const newState = !r.active;
    // Optimistic update — no reload needed
    this.restrictions.update(list => list.map(x => x.id === r.id ? { ...x, active: newState } : x));
    this.restrictionService.update(r.id, { active: newState }).subscribe({
      next: () => {
        this.snackBar.open(newState ? 'Restricción activada' : 'Restricción desactivada', 'OK', { duration: 3000 });
      },
      error: () => {
        this.restrictions.update(list => list.map(x => x.id === r.id ? { ...x, active: r.active } : x));
        this.snackBar.open('Error al cambiar estado', 'Cerrar', { duration: 5000 });
      },
    });
  }

  // ── Editar (solo personalizables) ──────────────────────────────────────────
  openEdit(r: Restriction): void {
    if (!r.customizable) return;
    this.editing.set(r);
    this.editForm.set({ ...r, config: { ...(r.config || {}) }, scope_records: [...(r.scope_records || [])] });
    this.showEdit.set(true);
  }

  closeEdit(): void {
    this.showEdit.set(false);
    this.editing.set(null);
    this.editForm.set({});
  }

  updateForm(key: keyof Restriction, value: any): void {
    this.editForm.update(f => ({ ...f, [key]: value }));
  }

  updateConfig(key: string, value: any): void {
    this.editForm.update(f => ({ ...f, config: { ...(f.config || {}), [key]: value } }));
  }

  getConfig(key: string, def: any = ''): any {
    return this.editForm().config?.[key] ?? def;
  }

  /** True when the edited restriction exposes a numeric threshold + operator. */
  hasThreshold(): boolean {
    const e = this.editForm().engine;
    return e === 'count' || e === 'condition';
  }

  /** True when the edited restriction is a worker-pair exclusion. */
  hasWorkerPairs(): boolean {
    return this.editForm().engine === 'exclusion'
      && this.getConfig('exclusionType') === 'worker_pair';
  }

  saveEdit(): void {
    const f = this.editForm();
    const r = this.editing();
    if (!r || !f.name?.trim()) return;
    this.saving.set(true);
    // Motor, tipo de regla y severidad no se envían: los define Zebra.
    // El cliente edita nombre, descripción, valores de la regla, mensaje y ámbito.
    this.restrictionService.update(r.id, {
      name: f.name.trim(),
      description: f.description ?? '',
      message: f.message ?? '',
      config: f.config ?? {},
      scope_records: f.scope_records ?? [],
    }).subscribe({
      next: updated => {
        this.restrictions.update(list => list.map(x => x.id === r.id ? { ...x, ...updated } : x));
        this.saving.set(false);
        this.closeEdit();
        this.snackBar.open('Restricción guardada', 'OK', { duration: 3000 });
      },
      error: () => {
        this.saving.set(false);
        this.snackBar.open('Error al guardar la restricción', 'Cerrar', { duration: 5000 });
      },
    });
  }

  // ── Parejas de trabajadores incompatibles ──────────────────────────────────
  workerPairs(): (number | null)[][] {
    return this.getConfig('workerPairs', []) as (number | null)[][];
  }

  addWorkerPair(): void {
    this.updateConfig('workerPairs', [...this.workerPairs(), [null, null]]);
  }

  removeWorkerPair(idx: number): void {
    const pairs = [...this.workerPairs()];
    pairs.splice(idx, 1);
    this.updateConfig('workerPairs', pairs);
  }

  updateWorkerPair(idx: number, pos: number, value: any): void {
    const pairs = this.workerPairs().map(p => [...p]);
    if (!pairs[idx]) pairs[idx] = [null, null];
    pairs[idx][pos] = value == null || value === '' ? null : Number(value);
    this.updateConfig('workerPairs', pairs);
  }

  /** Pairs missing one of the two workers — blocks saving. */
  hasIncompletePairs(): boolean {
    return this.workerPairs().some(p => p?.[0] == null || p?.[1] == null);
  }

  /** Pairs where both slots are the same worker — blocks saving. */
  hasSelfPairs(): boolean {
    return this.workerPairs().some(p => p?.[0] != null && p?.[0] === p?.[1]);
  }

  saveDisabled(): boolean {
    const f = this.editForm();
    if (!f.name?.trim()) return true;
    if (this.hasWorkerPairs() && (this.hasIncompletePairs() || this.hasSelfPairs())) return true;
    return false;
  }

  // ── Duplicar (solo personalizables) ────────────────────────────────────────
  openDuplicate(r: Restriction): void {
    if (!r.customizable) return;
    this.duplicating.set(r);
    this.duplicateName.set(`${r.name} (copia)`);
    this.duplicateScope.set([...(r.scope_records || [])]);
    this.showDuplicate.set(true);
  }

  closeDuplicate(): void {
    this.showDuplicate.set(false);
    this.duplicating.set(null);
    this.duplicateName.set('');
    this.duplicateScope.set([]);
  }

  confirmDuplicate(): void {
    const r = this.duplicating();
    if (!r) return;
    this.saving.set(true);
    this.restrictionService.duplicate(r.id, {
      name: this.duplicateName().trim() || undefined,
      scope_records: this.duplicateScope(),
    }).subscribe({
      next: copy => {
        // El orden (fijas → personalizables) lo pone filteredRestrictions.
        this.restrictions.update(list => [...list, copy]);
        this.saving.set(false);
        this.closeDuplicate();
        this.snackBar.open(`Restricción duplicada: ${copy.name}`, 'OK', { duration: 4000 });
      },
      error: () => {
        this.saving.set(false);
        this.snackBar.open('Error al duplicar la restricción', 'Cerrar', { duration: 5000 });
      },
    });
  }

  // ── Eliminar copias (solo personalizables duplicadas) ──────────────────────
  /** Only duplicates can be deleted from the client panel. */
  canDelete(r: Restriction): boolean {
    return !!r.customizable && r.duplicated_from != null;
  }

  askDelete(r: Restriction): void {
    if (!this.canDelete(r)) return;
    this.deleting.set(r);
    this.showDeleteConfirm.set(true);
  }

  /** ¿La restricción que se está editando se puede eliminar? Controla si el pie
   *  del sidepanel muestra el botón rojo: las originales no se borran, solo se
   *  desactivan con el interruptor de la tabla. */
  canDeleteEditing(): boolean {
    const r = this.editing();
    return !!r && this.canDelete(r);
  }

  /** Eliminar desde el pie del sidepanel de edición (patrón del resto de la
   *  app: botón rojo abajo a la izquierda). */
  askDeleteFromPanel(): void {
    const r = this.editing();
    if (r) this.askDelete(r);
  }

  closeDelete(): void {
    this.showDeleteConfirm.set(false);
    this.deleting.set(null);
  }

  confirmDelete(): void {
    const r = this.deleting();
    if (!r) return;
    this.saving.set(true);
    this.restrictionService.delete(r.id).subscribe({
      next: () => {
        this.restrictions.update(list => list.filter(x => x.id !== r.id));
        this.saving.set(false);
        this.closeDelete();
        this.snackBar.open('Restricción eliminada', 'OK', { duration: 3000 });
      },
      error: () => {
        this.saving.set(false);
        this.snackBar.open('Error al eliminar', 'Cerrar', { duration: 5000 });
      },
    });
  }

  saveMessage(r: Restriction, value: string): void {
    const trimmed = value.trim();
    if (trimmed === (r.message || '')) return;
    this.restrictions.update(list => list.map(x => x.id === r.id ? { ...x, message: trimmed } : x));
    this.restrictionService.update(r.id, { message: trimmed }).subscribe({
      next: () => this.snackBar.open('Mensaje guardado', 'OK', { duration: 2000 }),
      error: () => {
        this.restrictions.update(list => list.map(x => x.id === r.id ? { ...x, message: r.message } : x));
        this.snackBar.open('Error al guardar mensaje', 'Cerrar', { duration: 5000 });
      },
    });
  }
}
