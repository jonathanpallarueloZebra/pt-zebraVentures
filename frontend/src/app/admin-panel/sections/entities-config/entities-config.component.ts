import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { forkJoin, of } from 'rxjs';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDividerModule } from '@angular/material/divider';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { EntityFieldService } from '@app/shared/services/entity-field.service';
import { EntityTypeService } from '@app/shared/services/entity-type.service';
import { EntityRecordService } from '@app/shared/services/entity-record.service';
import { CatalogService } from '@app/shared/services/catalog.service';
import { EntityField, EntityTypeDef, FieldType } from '@app/shared/interfaces/entity-field.interface';
import { Kind } from '@app/shared/interfaces/catalog.interface';
import { ZbButtonComponent } from '@app/shared/components/zb-button/zb-button.component';
import { MATERIAL_ICONS } from '@app/shared/constants/material-icons';

@Component({
  selector: 'app-entities-config',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatTableModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
    MatSlideToggleModule, MatCardModule, MatChipsModule,
    MatProgressSpinnerModule, MatTooltipModule, MatDividerModule, MatSnackBarModule,
    ZbButtonComponent,
  ],
  templateUrl: './entities-config.component.html',
  styleUrl: './entities-config.component.scss',
})
export class EntitiesConfigComponent implements OnInit {

  // ── Field type catalogue ────────────────────────────────────
  fieldTypes: { value: FieldType; label: string }[] = [
    { value: 'text', label: 'Texto' },
    { value: 'number', label: 'Numero' },
    { value: 'float', label: 'Decimal' },   // p.ej. 37,5 horas semanales
    { value: 'boolean', label: 'Si/No' },
    { value: 'color', label: 'Color' },
    { value: 'time', label: 'Hora' },
    { value: 'select', label: 'Seleccion fija' },
    { value: 'textarea', label: 'Texto largo' },
    { value: 'catalog_select', label: 'Seleccion de catalogo' },
    { value: 'multi_catalog_select', label: 'Seleccion multiple de catalogo' },
    { value: 'entity_select', label: 'Seleccion de entidad' },
    { value: 'multi_entity_select', label: 'Seleccion multiple de entidad' },
    { value: 'icon', label: 'Icono' },
  ];

  /** Lista curada de iconos Material (compartida con el campo de tipo `icon`). */
  materialIcons = MATERIAL_ICONS;

  // ── State ───────────────────────────────────────────────────
  entityTypes = signal<EntityTypeDef[]>([]);
  kinds = signal<Kind[]>([]);
  selectedSlug = signal<string>('');
  fields = signal<EntityField[]>([]);
  loading = signal(true);
  importing = signal(false);

  // Entity type form (create / edit)
  creatingEntityType = signal(false);
  editingEntityType = signal<EntityTypeDef | null>(null);
  etForm = signal<Partial<EntityTypeDef>>({});

  // Field form (create / edit)
  editing = signal<EntityField | null>(null);
  creating = signal(false);
  createForm = signal<Partial<EntityField>>({});

  filteredFields = computed(() =>
    this.fields().filter(f => f.entity_type === this.selectedSlug())
  );

  /** Fields of the currently selected target_entity (for display_key picker) */
  targetFields = signal<EntityField[]>([]);

  selectedEntityType = computed(() =>
    this.entityTypes().find(t => t.slug === this.selectedSlug()) ?? null
  );

  otherEntities = computed(() =>
    this.entityTypes().filter(t => t.slug !== this.selectedSlug())
  );

  displayedColumns = ['label', 'key', 'field_type', 'show_in_list', 'show_as_filter', 'active', 'actions'];

  constructor(
    private entityFieldService: EntityFieldService,
    private entityTypeService: EntityTypeService,
    private entityRecordService: EntityRecordService,
    private catalogService: CatalogService,
    private snack: MatSnackBar,
  ) {}

  ngOnInit(): void {
    this.entityTypeService.invalidate();
    this.entityFieldService.invalidate();
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.catalogService.getKinds().subscribe(kinds => this.kinds.set(kinds));
    this.entityTypeService.getAll().subscribe({
      next: types => {
        this.entityTypes.set(types);
        if (!this.selectedSlug() && types.length) {
          this.selectedSlug.set(types[0].slug);
        }
        // Incluye los desactivados: este panel es el que permite reactivarlos.
        this.entityFieldService.getAllIncludingInactive().subscribe({
          next: fields => { this.fields.set(fields); this.loading.set(false); },
          error: () => this.loading.set(false),
        });
      },
      error: () => this.loading.set(false),
    });
  }

  selectType(slug: string): void {
    this.selectedSlug.set(slug);
    this.cancelEdit(); this.cancelCreate();
    this.cancelEditEntityType();
  }

  getFieldTypeLabel(ft: string): string {
    return this.fieldTypes.find(t => t.value === ft)?.label ?? ft;
  }

  // ── Entity Type create ──────────────────────────────────────
  startCreateEntityType(): void {
    this.creatingEntityType.set(true);
    this.editingEntityType.set(null);
    this.etForm.set({ name: '', slug: '', icon: 'category', order: this.entityTypes().length, show_in_sidebar: true });
  }

  cancelCreateEntityType(): void { this.creatingEntityType.set(false); }

  onEtNameChange(name: string): void {
    const slug = name.toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
    this.etForm.update(f => ({ ...f, name, slug }));
  }

  saveCreateEntityType(): void {
    const f = this.etForm();
    if (!f.slug || !f.name) return;
    this.entityTypeService.create(f).subscribe({
      next: created => {
        this.creatingEntityType.set(false);
        this.load();
        setTimeout(() => this.selectedSlug.set(created.slug), 300);
      },
      error: () => this.snack.open('Error al crear entidad', '', { duration: 3000 }),
    });
  }

  // ── Entity Type edit ────────────────────────────────────────
  startEditEntityType(et: EntityTypeDef): void {
    this.editingEntityType.set({ ...et });
    this.creatingEntityType.set(false);
  }

  cancelEditEntityType(): void { this.editingEntityType.set(null); }

  saveEditEntityType(): void {
    const f = this.editingEntityType();
    if (!f) return;
    this.entityTypeService.update(f.slug, f).subscribe({
      next: () => { this.editingEntityType.set(null); this.load(); },
      error: () => this.snack.open('Error al guardar', '', { duration: 3000 }),
    });
  }

  updateEtField(key: string, value: any): void {
    if (this.editingEntityType()) {
      this.editingEntityType.update(f => f ? { ...f, [key]: value } : f);
    } else {
      this.etForm.update(f => ({ ...f, [key]: value }));
    }
  }

  deleteEntityType(et: EntityTypeDef): void {
    if (et.is_system) {
      this.snack.open('Las entidades del sistema no se pueden eliminar', '', { duration: 3000 });
      return;
    }
    if (!confirm(`Eliminar entidad "${et.name}" y todos sus campos y registros?`)) return;
    this.entityTypeService.delete(et.slug).subscribe({
      next: () => {
        if (this.selectedSlug() === et.slug) this.selectedSlug.set('');
        this.load();
      },
      error: () => this.snack.open('Error al eliminar', '', { duration: 3000 }),
    });
  }

  // ── Field create ────────────────────────────────────────────
  startCreate(): void {
    this.creating.set(true);
    this.createForm.set({
      entity_type: this.selectedSlug(),
      key: '', label: '', field_type: 'text',
      required: false, default_value: '', placeholder: '',
      help_text: '', allow_priority: false,
      options: [], show_in_list: false, show_as_filter: false,
      allow_unassigned_filter: false,
      order: this.filteredFields().length, active: true,
    });
    this.scrollToCard('field-create-card');
  }

  cancelCreate(): void { this.creating.set(false); }

  saveCreate(): void {
    const f = this.createForm();
    if (!f.key || !f.label) return;
    this.entityFieldService.create(f).subscribe({
      next: () => { this.creating.set(false); this.load(); },
      error: () => this.snack.open('Error al guardar campo', '', { duration: 3000 }),
    });
  }

  onCreateLabelChange(label: string): void {
    const key = label.toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
    this.createForm.update(f => ({ ...f, label, key }));
  }

  // ── Field edit ──────────────────────────────────────────────
  startEdit(field: EntityField): void {
    this.editing.set({ ...field, options: [...(field.options || [])] });
    if (field.target_entity) this.loadTargetFields(field.target_entity);
    else this.targetFields.set([]);
    this.scrollToCard('field-edit-card');
  }

  /** Lleva la vista al formulario recién abierto: con muchos campos en la
   *  tabla, la tarjeta aparece fuera de pantalla y parecía que no pasaba nada
   *  al pulsar Editar / Añadir campo. */
  private scrollToCard(id: string): void {
    setTimeout(() => {
      document.getElementById(id)
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }

  cancelEdit(): void { this.editing.set(null); }

  saveEdit(): void {
    const f = this.editing();
    if (!f?.id) return;
    this.entityFieldService.update(f.id, f).subscribe({
      next: () => { this.editing.set(null); this.load(); },
      error: () => this.snack.open('Error al guardar campo', '', { duration: 3000 }),
    });
  }

  deleteField(field: EntityField): void {
    if (!confirm(`Eliminar campo "${field.label}"?`)) return;
    this.entityFieldService.delete(field.id).subscribe(() => this.load());
  }

  /** Returns the possible values for visible_when_value based on the referenced field's type. */
  getVisibleWhenOptions(fieldKey: string): { value: string; label: string }[] {
    const ref = this.filteredFields().find(f => f.key === fieldKey);
    if (!ref) return [];
    if (ref.field_type === 'boolean') {
      return [{ value: 'true', label: 'Sí (true)' }, { value: 'false', label: 'No (false)' }];
    }
    if (ref.field_type === 'select' && ref.options?.length) {
      return ref.options.map(o => ({ value: o, label: o }));
    }
    if ((ref.field_type === 'entity_select' || ref.field_type === 'multi_entity_select') && ref.target_entity) {
      const cached = this.visibleWhenRecords.get(ref.target_entity);
      if (cached) return cached;
      // Load async and cache
      this.entityRecordService.getAll(ref.target_entity).subscribe(records => {
        const opts = records.map((r: any) => ({
          value: String(r.id),
          label: r.data?.nombre || r.data?.name || r.data?.label || `#${r.id}`,
        }));
        this.visibleWhenRecords.set(ref.target_entity!, opts);
      });
      return [];
    }
    if (ref.field_type === 'catalog_select' && ref.kind_code) {
      const cached = this.visibleWhenRecords.get('catalog_' + ref.kind_code);
      if (cached) return cached;
      this.catalogService.getValues(ref.kind_code).subscribe(values => {
        const opts = values.map(v => ({ value: v.code, label: v.label }));
        this.visibleWhenRecords.set('catalog_' + ref.kind_code!, opts);
      });
      return [];
    }
    return [{ value: 'true', label: 'true' }, { value: 'false', label: 'false' }];
  }

  /** Cache for entity records used in visible_when_value dropdown */
  private visibleWhenRecords = new Map<string, { value: string; label: string }[]>();

  // ── Select options management ───────────────────────────────
  addOption(isCreate: boolean, value: string): void {
    if (!value.trim()) return;
    if (isCreate) {
      this.createForm.update(f => ({ ...f, options: [...(f.options || []), value.trim()] }));
    } else {
      this.editing.update(f => f ? { ...f, options: [...(f.options || []), value.trim()] } : f);
    }
  }

  removeOption(isCreate: boolean, idx: number): void {
    if (isCreate) {
      this.createForm.update(f => { const o = [...(f.options || [])]; o.splice(idx, 1); return { ...f, options: o }; });
    } else {
      this.editing.update(f => { if (!f) return f; const o = [...(f.options || [])]; o.splice(idx, 1); return { ...f, options: o }; });
    }
  }

  updateField(isCreate: boolean, key: string, value: any): void {
    if (isCreate) {
      this.createForm.update(f => ({ ...f, [key]: value }));
    } else {
      this.editing.update(f => f ? { ...f, [key]: value } : f);
    }
    // Al cambiar la entidad relacionada, el "campo a mostrar en tabla" que
    // hubiera elegido antes pertenece a la entidad ANTERIOR: se limpia para no
    // guardar una referencia rota (la columna caería al valor por defecto).
    if (key === 'target_entity') {
      const clear = (f: any) => (f ? { ...f, display_key: '' } : f);
      if (isCreate) this.createForm.update(clear);
      else this.editing.update(clear);

      if (value) this.loadTargetFields(value);
      else this.targetFields.set([]);
    }
  }

  loadTargetFields(slug: string): void {
    this.entityFieldService.getAll(slug).subscribe(f => this.targetFields.set(f.filter(x => x.active)));
  }

  // ── Export / Import structure ─────────────────────────────────────────────

  exportStructure(): void {
    const types = this.entityTypes();
    const allFields = this.fields();
    const exported = types.map(et => {
      const { id, record_count, ...etData } = et as any;
      const etFields = allFields
        .filter(f => f.entity_type === et.slug)
        .map(f => {
          const { id: fid, entity_type, ...fData } = f as any;
          return fData;
        });
      return { ...etData, fields: etFields };
    });
    const blob = new Blob([JSON.stringify(exported, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'estructura-entidades.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  onImportStructure(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    input.value = '';
    const reader = new FileReader();
    reader.onload = () => {
      let parsed: any[];
      try {
        const raw = JSON.parse(reader.result as string);
        parsed = Array.isArray(raw) ? raw : [raw];
      } catch {
        this.snack.open('El archivo no es un JSON válido', 'Cerrar', { duration: 5000 });
        return;
      }
      const validTypes = parsed.filter(t => t.slug && t.name);
      if (!validTypes.length) {
        this.snack.open('El JSON no contiene entidades válidas (se requiere slug y name)', 'Cerrar', { duration: 6000 });
        return;
      }
      this.importing.set(true);
      const existingSlugs = new Set(this.entityTypes().map(e => e.slug));
      const toCreate = validTypes.filter(t => !existingSlugs.has(t.slug));
      const toSkip = validTypes.filter(t => existingSlugs.has(t.slug));

      if (!toCreate.length) {
        this.importing.set(false);
        const msg = toSkip.length
          ? `Todas las entidades ya existen (${toSkip.map(t => t.slug).join(', ')}). Se importaron solo los campos nuevos.`
          : 'No se encontraron entidades nuevas para importar.';
        // Still try to import fields for existing entities
        this.importFieldsForExisting(validTypes, () => {
          this.snack.open(msg, 'OK', { duration: 6000 });
          this.load();
        });
        return;
      }

      let created = 0;
      let errors = 0;
      const checkDone = () => {
        if (created + errors < toCreate.length) return;
        this.importFieldsForExisting(validTypes, () => {
          this.importing.set(false);
          const skippedMsg = toSkip.length ? ` (${toSkip.length} ya existían)` : '';
          const msg = errors === 0
            ? `${created} entidad(es) importada(s)${skippedMsg}`
            : `${created} importada(s), ${errors} con error${skippedMsg}`;
          this.snack.open(msg, 'OK', { duration: 6000 });
          this.load();
        });
      };

      for (const t of toCreate) {
        const { fields, ...etData } = t;
        this.entityTypeService.create(etData).subscribe({
          next: () => { created++; checkDone(); },
          error: () => { errors++; checkDone(); },
        });
      }
    };
    reader.readAsText(file);
  }

  private importFieldsForExisting(types: any[], onDone: () => void): void {
    const fieldImports: Array<() => void> = [];
    for (const t of types) {
      const fields: any[] = t.fields || [];
      const existingKeys = new Set(
        this.fields().filter(f => f.entity_type === t.slug).map(f => f.key)
      );
      const newFields = fields.filter(f => f.key && f.label && !existingKeys.has(f.key));
      for (const fDef of newFields) {
        fieldImports.push(() =>
          this.entityFieldService.create({ ...fDef, entity_type: t.slug }).subscribe()
        );
      }
    }
    // Fire all field creates sequentially then call onDone
    if (!fieldImports.length) { onDone(); return; }
    let i = 0;
    const next = () => { if (i < fieldImports.length) { fieldImports[i++](); next(); } else onDone(); };
    next();
  }
}
