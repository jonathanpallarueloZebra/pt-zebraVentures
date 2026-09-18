import { Component, EventEmitter, OnInit, Output, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { MatTooltipModule } from '@angular/material/tooltip';
import { forkJoin } from 'rxjs';
import { ClosedDayService } from '@app/shared/services/closed-day.service';
import { EntityTypeService } from '@app/shared/services/entity-type.service';
import { EntityRecordService } from '@app/shared/services/entity-record.service';
import { ClosedDay } from '@app/shared/interfaces/closed-day.interface';
import { EntityRecord, EntityTypeDef } from '@app/shared/interfaces/entity-field.interface';
import { ZbButtonComponent } from '@app/shared/components/zb-button/zb-button.component';
import { ZbDialogComponent } from '@app/shared/components/zb-dialog/zb-dialog.component';
import { ZbCheckboxComponent } from '@app/shared/components/zb-checkbox/zb-checkbox.component';
import { ZbSidepanelComponent } from '@app/shared/components/zb-sidepanel/zb-sidepanel.component';

/** Todos los cierres de una misma fecha, agrupados para la tabla y la edición. */
interface ClosedDayGroup {
  date: string;
  reason: string;
  days: ClosedDay[];
}

@Component({
  selector: 'app-closed-days-config',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatIconModule, MatSnackBarModule, MatTableModule, MatTooltipModule,
    ZbButtonComponent, ZbDialogComponent, ZbCheckboxComponent, ZbSidepanelComponent,
  ],
  templateUrl: './closed-days-config.component.html',
  styleUrl: './closed-days-config.component.scss',
})
export class ClosedDaysConfigComponent implements OnInit {
  /** Nº de días de cierre gestionados — para el subtítulo de la página padre. */
  @Output() countChange = new EventEmitter<number>();

  loading = signal(true);
  saving = signal(false);
  closedDays = signal<ClosedDay[]>([]);
  scopeEntityType = signal<EntityTypeDef | null>(null);
  scopeRecords = signal<EntityRecord[]>([]);

  displayedColumns = ['date', 'scope', 'reason', 'actions'];

  // Form del side-panel. En ALTA la selección de ámbito es múltiple
  // (global + varias tiendas → se crea un cierre por cada una). En EDICIÓN
  // solo se edita el ámbito único del cierre existente.
  form = signal<{ date: string; global: boolean; scope_ids: number[]; reason: string }>({
    date: '', global: true, scope_ids: [], reason: '',
  });

  // ── Side-panel crear/editar (patrón del sistema: absences/entity-records) ──
  showPanel = false;
  /** null = alta; grupo (todos los cierres de una fecha) = edición. */
  editingGroup: ClosedDayGroup | null = null;
  panelTitle = 'Nuevo día de cierre';

  sortedClosedDays = computed(() =>
    [...this.closedDays()].sort((a, b) => a.date.localeCompare(b.date)),
  );

  /** Los cierres agrupados por fecha: una fila por día con todos sus ámbitos.
   *  El backend guarda un registro por (fecha, ámbito), pero de cara al usuario
   *  "el 10/08 cierran T01..T08" es un único día de cierre. */
  groupedClosedDays = computed<ClosedDayGroup[]>(() => {
    const byDate = new Map<string, ClosedDayGroup>();
    for (const cd of this.sortedClosedDays()) {
      let g = byDate.get(cd.date);
      if (!g) {
        g = { date: cd.date, reason: cd.reason || '', days: [] };
        byDate.set(cd.date, g);
      }
      g.days.push(cd);
      if (!g.reason && cd.reason) g.reason = cd.reason;
    }
    return [...byDate.values()];
  });

  /** Etiqueta del ámbito de una fila agrupada: "Global", "T01, T02" o "8 tiendas". */
  groupScopeLabel(g: ClosedDayGroup): string {
    if (g.days.some(d => !d.scope_entity_id)) return this.scopeLabel(0);
    const names = g.days.map(d => this.scopeLabel(d.scope_entity_id));
    if (names.length > 3) return `${names.length} ${this.scopeName().toLowerCase()}s`;
    return names.join(', ');
  }

  /** Nombre de la entidad de ámbito (p. ej. "Tienda", "Sede"). Variable, no
   *  hardcodeado: sale del EntityType con is_planning_scope. Fallback "Ámbito". */
  scopeName = computed(() => this.scopeEntityType()?.name || 'Ámbito');

  // ── Confirmación de borrado (zb-dialog, no confirm() nativo) ──
  showDeleteConfirm = false;
  deleteConfirmMessage = '';
  private pendingDelete: ClosedDayGroup | null = null;

  constructor(
    private closedDayService: ClosedDayService,
    private entityTypeService: EntityTypeService,
    private entityRecordService: EntityRecordService,
    private snackBar: MatSnackBar,
  ) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    forkJoin({
      closedDays: this.closedDayService.getAll(),
      entityTypes: this.entityTypeService.getAll(),
    }).subscribe({
      next: ({ closedDays, entityTypes }) => {
        this.closedDays.set(closedDays);
        this.countChange.emit(closedDays.length);
        const scopeEt = entityTypes.find(et => et.is_planning_scope) ?? null;
        this.scopeEntityType.set(scopeEt);
        if (scopeEt) {
          this.entityRecordService.getAll(scopeEt.slug).subscribe(records => this.scopeRecords.set(records));
        }
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  scopeLabel(scopeEntityId: number): string {
    if (!scopeEntityId) return 'Global (todos los ámbitos)';
    const et = this.scopeEntityType();
    const rec = this.scopeRecords().find(r => r.id === scopeEntityId);
    if (!rec) return `#${scopeEntityId}`;
    const displayField = et?.display_field || 'nombre';
    return rec.data?.[displayField] || rec.data?.['nombre'] || rec.data?.['name'] || `#${scopeEntityId}`;
  }

  updateForm(key: 'date' | 'reason', value: any): void {
    this.form.update(f => ({ ...f, [key]: value }));
  }

  // ── Selección de ámbito (checkboxes) ────────────────────────────
  /** ¿Está marcada la tienda `id`? */
  isScopeChecked(id: number): boolean {
    return this.form().scope_ids.includes(id);
  }

  /** Marca/desmarca "Global (todas)". Al marcar global se limpian las tiendas. */
  toggleGlobal(checked: boolean): void {
    this.form.update(f => ({ ...f, global: checked, scope_ids: checked ? [] : f.scope_ids }));
  }

  /** Marca/desmarca una tienda. Marcar una tienda desactiva "Global". */
  toggleScope(id: number, checked: boolean): void {
    this.form.update(f => {
      const scope_ids = checked
        ? [...f.scope_ids, id]
        : f.scope_ids.filter(x => x !== id);
      return { ...f, scope_ids, global: checked ? false : (scope_ids.length === 0 ? true : f.global) };
    });
  }

  /** Abre el side-panel en modo alta (formulario vacío, global por defecto). */
  openCreate(): void {
    this.editingGroup = null;
    this.panelTitle = 'Nuevo día de cierre';
    this.form.set({ date: '', global: true, scope_ids: [], reason: '' });
    this.showPanel = true;
  }

  /** Abre el side-panel en modo edición con TODOS los ámbitos de esa fecha
   *  marcados (el día de cierre son las N filas que comparten fecha). */
  openEdit(g: ClosedDayGroup): void {
    this.editingGroup = g;
    const global = g.days.some(d => !d.scope_entity_id);
    const scope_ids = g.days.map(d => d.scope_entity_id).filter(id => !!id);
    this.panelTitle = 'Editar día de cierre';
    this.form.set({ date: g.date, global, scope_ids, reason: g.reason || '' });
    this.showPanel = true;
  }

  cancelPanel(): void {
    this.showPanel = false;
  }

  /** Guarda desde el side-panel. ALTA: crea un cierre por ámbito seleccionado
   *  (global → 1 con scope 0; N tiendas → N cierres). EDICIÓN: actualiza el
   *  cierre existente con su ámbito único. */
  save(): void {
    const f = this.form();
    if (!f.date) {
      this.snackBar.open('Selecciona una fecha', 'Cerrar', { duration: 4000 });
      return;
    }
    // Ámbitos a los que aplicar: global → [0]; si no, las tiendas marcadas.
    const scopeIds = f.global ? [0] : f.scope_ids;
    if (!scopeIds.length) {
      this.snackBar.open(`Selecciona al menos una ${this.scopeName().toLowerCase()} o "Global"`, 'Cerrar', { duration: 4000 });
      return;
    }

    // Choque con cierres ya existentes en esa fecha que NO son de este grupo
    // (p. ej. mover el día 10 al 11 cuando el 11 ya tiene esa tienda). El
    // backend respondería 400 por unique_together y el forkJoin dejaría el
    // guardado a medias, así que se avisa antes de enviar nada.
    const ownIds = new Set((this.editingGroup?.days ?? []).map(d => d.id));
    const clashes = this.closedDays().filter(
      c => c.date === f.date && !ownIds.has(c.id) && scopeIds.includes(c.scope_entity_id),
    );
    if (clashes.length) {
      const names = clashes.map(c => this.scopeLabel(c.scope_entity_id)).join(', ');
      console.warn('[closed-days] choque con cierres existentes', clashes);
      this.snackBar.open(`Ya existe un día de cierre el ${f.date} en: ${names}`, 'Cerrar', { duration: 5000 });
      return;
    }

    this.saving.set(true);

    if (this.editingGroup === null) {
      // ALTA: un create por cada ámbito (forkJoin para esperar a todos).
      const reqs = scopeIds.map(id => this.closedDayService.create({
        date: f.date, scope_entity_id: id, reason: f.reason || '',
      }));
      forkJoin(reqs).subscribe({
        next: (res) => {
          this.saving.set(false);
          this.showPanel = false;
          const n = reqs.length;
          this.snackBar.open(n === 1 ? 'Día de cierre añadido' : `${n} días de cierre añadidos`, 'Cerrar', { duration: 3000 });
          this.load();
        },
        error: (err) => this.onSaveError(err),
      });
    } else {
      // EDICIÓN: sincronizar el conjunto de ámbitos del día. Los que ya estaban
      // y siguen marcados se actualizan (fecha/motivo), los nuevos se crean y
      // los desmarcados se borran. El unique_together (date, scope_entity_id)
      // obliga a que no haya duplicados.
      const before = this.editingGroup.days;
      const wanted = new Set(scopeIds);
      const keep = before.filter(d => wanted.has(d.scope_entity_id));
      const toDelete = before.filter(d => !wanted.has(d.scope_entity_id));
      const existingScopes = new Set(before.map(d => d.scope_entity_id));
      const toCreate = scopeIds.filter(id => !existingScopes.has(id));


      const reqs = [
        ...keep.map(d => this.closedDayService.update(d.id, {
          date: f.date, scope_entity_id: d.scope_entity_id, reason: f.reason || '',
        })),
        ...toCreate.map(id => this.closedDayService.create({
          date: f.date, scope_entity_id: id, reason: f.reason || '',
        })),
        ...toDelete.map(d => this.closedDayService.delete(d.id)),
      ];
      forkJoin(reqs).subscribe({
        next: (res) => {
          this.saving.set(false);
          this.showPanel = false;
          this.snackBar.open('Día de cierre actualizado', 'Cerrar', { duration: 3000 });
          this.load();
        },
        error: (err) => {
          console.error('[closed-days] error al guardar', err, err?.error);
          this.onSaveError(err);
        },
      });
    }
  }

  private onSaveError(err: any): void {
    this.saving.set(false);
    const msg = err?.error?.date?.[0] || err?.error?.non_field_errors?.[0] || 'No se pudo guardar';
    this.snackBar.open(msg, 'Cerrar', { duration: 5000 });
  }

  /** Botón Eliminar del side-panel (modo edición) → abre confirmación. */
  removeFromPanel(): void {
    if (this.editingGroup) this.remove(this.editingGroup);
  }

  /** Abre la confirmación de borrado (modal del sistema). Borra el día entero,
   *  es decir todos los ámbitos de esa fecha. */
  remove(g: ClosedDayGroup): void {
    this.pendingDelete = g;
    const n = g.days.length;
    this.deleteConfirmMessage = n > 1
      ? `¿Eliminar el día de cierre del ${g.date} en ${n} ${this.scopeName().toLowerCase()}s? Esta acción no se puede deshacer.`
      : `¿Eliminar el día de cierre del ${g.date}? Esta acción no se puede deshacer.`;
    this.showDeleteConfirm = true;
  }

  /** Confirmado → borra todos los cierres de esa fecha (y cierra el panel). */
  confirmDelete(): void {
    this.showDeleteConfirm = false;
    const g = this.pendingDelete;
    if (!g) return;
    this.pendingDelete = null;
    forkJoin(g.days.map(d => this.closedDayService.delete(d.id))).subscribe(() => {
      this.showPanel = false;
      this.load();
    });
  }
}
