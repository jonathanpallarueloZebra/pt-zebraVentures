import { Component, OnInit, signal, computed, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDividerModule } from '@angular/material/divider';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { AssignmentRuleService } from '@app/shared/services/assignment-rule.service';
import { EntityTypeService } from '@app/shared/services/entity-type.service';
import { EntityRecordService } from '@app/shared/services/entity-record.service';
import { AssignmentRule, AssignmentPattern, WorkerFieldOption } from '@app/shared/interfaces/assignment.interface';
import { EntityTypeDef, EntityRecord } from '@app/shared/interfaces/entity-field.interface';
import { ZbButtonComponent } from '@app/shared/components/zb-button/zb-button.component';
import { ZbPaginatorComponent } from '@app/shared/components/zb-paginator/zb-paginator.component';
import { forkJoin } from 'rxjs';

@Component({
  selector: 'app-assignments-config',
  standalone: true,
  imports: [
    CommonModule,
    MatTableModule, MatButtonModule, MatIconModule,
    MatSlideToggleModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatCardModule,
    MatProgressSpinnerModule, MatTooltipModule, MatDividerModule,
    MatSnackBarModule,
    ZbButtonComponent, ZbPaginatorComponent,
  ],
  templateUrl: './assignments-config.component.html',
  styleUrl: './assignments-config.component.scss',
})
export class AssignmentsConfigComponent implements OnInit {
  rules = signal<AssignmentRule[]>([]);
  patterns = signal<AssignmentPattern[]>([]);
  workerFields = signal<WorkerFieldOption[]>([]);
  entityTypes = signal<EntityTypeDef[]>([]);
  entityRecordsMap = signal<Record<string, EntityRecord[]>>({});

  loading = signal(true);
  importing = signal(false);
  dragOver = signal(false);
  page = signal(0);
  readonly pageSize = 10;
  pagedRules = computed(() => this.rules().slice(this.page() * this.pageSize, (this.page() + 1) * this.pageSize));
  totalPages = computed(() => Math.max(1, Math.ceil(this.rules().length / this.pageSize)));

  editingId = signal<number | null>(null);
  editForm = signal<Partial<AssignmentRule>>({});
  creating = signal(false);
  createForm = signal<Partial<AssignmentRule>>({});

  // Chat state
  chatOpen = signal(false);
  chatMessages = signal<{role: string; content: string}[]>([]);
  chatInput = signal('');
  chatLoading = signal(false);
  chatProposal = signal<Partial<AssignmentRule> | null>(null);
  @ViewChild('chatScroll') chatScroll?: ElementRef<HTMLDivElement>;

  planningScopeEt = computed(() => this.entityTypes().find(e => e.is_planning_scope));
  planningScopeRecords = computed(() => {
    const et = this.planningScopeEt();
    if (!et) return [];
    return this.entityRecordsMap()[et.slug] ?? [];
  });

  // Worker fields filtered by type
  booleanFields = computed(() => this.workerFields().filter(f => f.field_type === 'boolean'));
  shiftFields = computed(() => this.workerFields().filter(f =>
    (f.field_type === 'entity_select' || f.field_type === 'multi_entity_select') && f.target_entity === 'shift'));
  numberFields = computed(() => this.workerFields().filter(f => f.field_type === 'number'));
  conditionFields = computed(() => this.workerFields().filter(f =>
    f.field_type === 'boolean' || f.field_type === 'select' || f.field_type === 'catalog_select'));

  displayedColumns = ['name', 'pattern', 'active', 'actions'];

  // Días de la semana para el patrón 'weekday' (0=Lunes..6=Domingo)
  readonly weekdays = [
    { value: 0, label: 'Lunes' },
    { value: 1, label: 'Martes' },
    { value: 2, label: 'Miércoles' },
    { value: 3, label: 'Jueves' },
    { value: 4, label: 'Viernes' },
    { value: 5, label: 'Sábado' },
    { value: 6, label: 'Domingo' },
  ];

  constructor(
    private assignmentService: AssignmentRuleService,
    private entityTypeService: EntityTypeService,
    private entityRecordService: EntityRecordService,
    private snackBar: MatSnackBar,
  ) {}

  ngOnInit(): void {
    forkJoin({
      patterns: this.assignmentService.getPatterns(),
      workerFields: this.assignmentService.getWorkerFields(),
      entityTypes: this.entityTypeService.getAll(),
    }).subscribe(({ patterns, workerFields, entityTypes }) => {
      this.patterns.set(patterns);
      this.workerFields.set(workerFields);
      this.entityTypes.set(entityTypes);

      if (entityTypes.length) {
        forkJoin(
          entityTypes.reduce((acc, et) => {
            acc[et.slug] = this.entityRecordService.getAll(et.slug);
            return acc;
          }, {} as Record<string, any>)
        ).subscribe(map => this.entityRecordsMap.set(map as Record<string, EntityRecord[]>));
      }

      this.load();
    });
  }

  load(): void {
    this.page.set(0);
    this.loading.set(true);
    this.assignmentService.getAll().subscribe({
      next: r => { this.rules.set(r); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  getPatternLabel(pattern: string): string {
    return this.patterns().find(p => p.value === pattern)?.label || pattern || 'Siempre';
  }

  toggleActive(r: AssignmentRule): void {
    this.assignmentService.update(r.id, { active: !r.active }).subscribe(() => this.load());
  }

  // ── Create ─────────────────────────────────────────────────────
  startCreate(): void {
    this.creating.set(true);
    this.createForm.set({
      name: '', description: '',
      config: { pattern: 'always' },
      active: true, priority: 0, scope_records: [],
    });
  }

  cancelCreate(): void { this.creating.set(false); }

  saveCreate(): void {
    const f = this.createForm();
    if (!f.name?.trim()) return;
    this.assignmentService.create(f).subscribe({
      next: () => {
        this.creating.set(false);
        this.load();
        this.snackBar.open('Regla de asignación creada', 'OK', { duration: 3000 });
      },
      error: () => this.snackBar.open('Error al crear la regla', 'Cerrar', { duration: 5000 }),
    });
  }

  // ── Edit ───────────────────────────────────────────────────────
  startEdit(r: AssignmentRule): void {
    this.editingId.set(r.id);
    this.editForm.set({ ...r, config: { ...r.config } });
  }

  cancelEdit(): void { this.editingId.set(null); }

  saveEdit(): void {
    const f = this.editForm();
    if (!f.id) return;
    this.assignmentService.update(f.id, {
      name: f.name, description: f.description,
      config: f.config, active: f.active,
      priority: f.priority, scope_records: f.scope_records ?? [],
    }).subscribe({
      next: () => {
        this.editingId.set(null);
        this.load();
        this.snackBar.open('Regla actualizada', 'OK', { duration: 3000 });
      },
      error: () => this.snackBar.open('Error al guardar', 'Cerrar', { duration: 5000 }),
    });
  }

  deleteRule(r: AssignmentRule): void {
    if (!confirm(`¿Eliminar "${r.name}"?`)) return;
    this.assignmentService.delete(r.id).subscribe(() => this.load());
  }

  // ── Form helpers ───────────────────────────────────────────────
  updateField(isCreate: boolean, key: string, value: any): void {
    if (isCreate) {
      this.createForm.update(f => ({ ...f, [key]: value }));
    } else {
      this.editForm.update(f => ({ ...f, [key]: value }));
    }
  }

  updateConfig(form: Partial<AssignmentRule>, key: string, value: any): void {
    const config = { ...(form.config || {}), [key]: value };
    if (form === this.createForm()) {
      this.createForm.update(f => ({ ...f, config }));
    } else {
      this.editForm.update(f => ({ ...f, config }));
    }
  }

  getConfig(form: Partial<AssignmentRule>, key: string, defaultVal: any = ''): any {
    return form.config?.[key] ?? defaultVal;
  }

  getConfigSummary(r: AssignmentRule): string {
    const c = r.config || {};
    const parts: string[] = [];
    if (c['conditionField']) {
      const cf = this.workerFields().find(f => f.key === c['conditionField']);
      parts.push(`Si ${cf?.label || c['conditionField']}${c['conditionValue'] ? ' = ' + c['conditionValue'] : ''}`);
    }
    if (c['overrideField']) {
      const of2 = this.workerFields().find(f => f.key === c['overrideField']);
      parts.push(`→ ${of2?.label || c['overrideField']}`);
    }
    const pattern = this.getPatternLabel(c['pattern']);
    parts.push(`(${pattern})`);
    return parts.join(' ');
  }

  recordLabel(rec: EntityRecord, et?: EntityTypeDef): string {
    if (!et) return `#${rec.id}`;
    const display = et.display_field || 'nombre';
    return rec.data?.[display] || `#${rec.id}`;
  }

  // ── Export / Import ─────────────────────────────────────────────

  exportOne(r: AssignmentRule): void {
    const { id, ...data } = r;
    this.downloadJson([data], `asignacion-${r.name.trim().replace(/\s+/g, '_')}.json`);
  }

  exportAll(): void {
    const data = this.rules().map(({ id, ...rest }) => rest);
    this.downloadJson(data, 'asignaciones.json');
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

  downloadTemplate(): void {
    const shiftFields = this.shiftFields();
    const boolFields = this.booleanFields();
    const numFields = this.numberFields();

    const template = [
      {
        _DOC: 'Plantilla de reglas de asignación. Elimina campos _DOC antes de importar.',
        _INFO: 'Cada regla tiene: conditionField (cuándo aplica), overrideField (qué turno usar), pattern (cómo aplica temporalmente).',
        _PATTERNS: '"always" = siempre | "alternate_weekly" = alterna cada N semanas | "alternate_daily" = alterna cada N días | "weekday" = solo un día concreto (config.weekday: 0=Lun..6=Dom)',
        _WORKER_FIELDS_BOOLEAN: boolFields.map(f => f.key).join(', '),
        _WORKER_FIELDS_SHIFT: shiftFields.map(f => f.key).join(', '),
        _WORKER_FIELDS_NUMBER: numFields.map(f => f.key).join(', '),
        name: '__EJEMPLO__',
        config: {},
        active: false,
      },
      {
        _DOC: 'Rotación semanal: si turno_rotativo=true, alternar con turno_secundario cada N semanas',
        name: 'Rotación semanal',
        description: 'Alterna entre turno principal y secundario cada frecuencia_rotacion semanas',
        config: {
          conditionField: boolFields[0]?.key || 'CAMPO_BOOLEANO',
          conditionValue: 'true',
          overrideField: shiftFields[1]?.key || shiftFields[0]?.key || 'CAMPO_TURNO_ALTERNATIVO',
          pattern: 'alternate_weekly',
          frequencyField: numFields[0]?.key || 'CAMPO_NUMERICO_FRECUENCIA',
        },
        active: true,
        priority: 0,
        scope_records: [],
      },
      {
        _DOC: 'Override directo: si una condición se cumple, SIEMPRE usa el turno del campo override',
        name: 'Turno fijo por condición',
        description: 'Si la condición se cumple, siempre asigna el turno alternativo',
        config: {
          conditionField: boolFields[0]?.key || 'CAMPO_BOOLEANO',
          conditionValue: 'true',
          overrideField: shiftFields[0]?.key || 'CAMPO_TURNO',
          pattern: 'always',
        },
        active: true,
        priority: 0,
        scope_records: [],
      },
    ];

    const blob = new Blob([JSON.stringify(template, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'plantilla-asignaciones.json';
    a.click();
    URL.revokeObjectURL(url);
  }

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
    if (file) this.processImportFile(file);
  }

  onImportFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    input.value = '';
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
      const items: Partial<AssignmentRule>[] = Array.isArray(parsed) ? parsed : [parsed];
      const valid = items.filter(i => i.name && i.config);
      if (!valid.length) {
        this.snackBar.open('El JSON no contiene reglas válidas (se requiere name y config)', 'Cerrar', { duration: 6000 });
        return;
      }
      this.importing.set(true);
      let done = 0;
      let errors = 0;
      for (const item of valid) {
        const cleanConfig: Record<string, any> = {};
        for (const [k, v] of Object.entries(item.config || {})) {
          if (!k.startsWith('_DOC')) cleanConfig[k] = v;
        }
        const payload: Partial<AssignmentRule> = {
          name: item.name,
          description: item.description || '',
          config: cleanConfig,
          active: item.active ?? true,
          priority: item.priority ?? 0,
          scope_records: item.scope_records ?? [],
        };
        this.assignmentService.create(payload).subscribe({
          next: () => { done++; if (done + errors === valid.length) this.finishImport(done, errors); },
          error: () => { errors++; if (done + errors === valid.length) this.finishImport(done, errors); },
        });
      }
    };
    reader.readAsText(file);
  }

  private finishImport(done: number, errors: number): void {
    this.importing.set(false);
    const msg = errors === 0
      ? `${done} regla(s) importada(s) correctamente`
      : `${done} importada(s), ${errors} con error`;
    this.snackBar.open(msg, 'OK', { duration: 5000 });
    this.load();
  }

  // ── Chat ────────────────────────────────────────────────────────

  toggleChat(): void {
    this.chatOpen.update(v => !v);
    if (this.chatOpen() && this.chatMessages().length === 0) {
      this.chatMessages.set([{
        role: 'assistant',
        content: '¡Hola! Describe la regla de asignación que quieres crear. Por ejemplo:\n\n• "Los trabajadores con turno rotativo deben alternar cada semana"\n• "Si un empleado tiene jornada partida, siempre usar su turno especial"\n• "Alternar turno mañana/tarde cada 2 semanas para los que tengan rotación activa"',
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

    const history = this.chatMessages().slice(0, -1);
    this.assignmentService.chat(msg, history).subscribe({
      next: res => {
        this.chatMessages.update(m => [...m, { role: 'assistant', content: res.response }]);
        this.chatLoading.set(false);
        const jsonMatch = res.response.match(/```json\s*([\s\S]*?)```/);
        if (jsonMatch) {
          try { this.chatProposal.set(JSON.parse(jsonMatch[1])); } catch {}
        }
        this.scrollChat();
      },
      error: () => {
        this.chatMessages.update(m => [...m, { role: 'assistant', content: 'Error al procesar. Inténtalo de nuevo.' }]);
        this.chatLoading.set(false);
        this.scrollChat();
      },
    });
  }

  applyChatProposal(): void {
    const proposal = this.chatProposal();
    if (!proposal) return;
    this.assignmentService.create({
      name: proposal.name || 'Nueva regla',
      description: proposal.description || '',
      config: proposal.config || {},
      active: proposal.active ?? true,
      priority: proposal.priority ?? 0,
      scope_records: proposal.scope_records ?? [],
    }).subscribe({
      next: () => {
        this.chatMessages.update(m => [...m, { role: 'assistant', content: '✅ ¡Regla creada correctamente!' }]);
        this.chatProposal.set(null);
        this.load();
        this.scrollChat();
        this.snackBar.open('Regla creada desde el chat', 'OK', { duration: 3000 });
      },
      error: () => {
        this.chatMessages.update(m => [...m, { role: 'assistant', content: '❌ Error al crear la regla.' }]);
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
}
