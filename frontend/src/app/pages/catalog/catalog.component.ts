import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatIconModule } from '@angular/material/icon';
import { ZbSkeletonComponent } from '@app/shared/components/zb-skeleton/zb-skeleton.component';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDividerModule } from '@angular/material/divider';
import { ZbInputComponent } from '@app/shared/components/zb-input/zb-input.component';
import { ZbToggleComponent } from '@app/shared/components/zb-toggle/zb-toggle.component';
import { ZbSelectComponent, ZbSelectOption } from '@app/shared/components/zb-select/zb-select.component';
import { concat, forkJoin, of } from 'rxjs';
import { switchMap, toArray } from 'rxjs/operators';
import { CatalogService } from '@app/shared/services/catalog.service';
import { Kind, KindAttribute, KindValue } from '@app/shared/interfaces/catalog.interface';
import { ZbPageHeaderComponent } from '@app/shared/components/zb-page-header/zb-page-header.component';
import { ZbButtonComponent } from '@app/shared/components/zb-button/zb-button.component';

@Component({
  selector: 'app-catalog',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatExpansionModule, MatIconModule, ZbSkeletonComponent,
    MatTooltipModule, MatDividerModule,
    ZbPageHeaderComponent, ZbButtonComponent,
    ZbInputComponent, ZbToggleComponent, ZbSelectComponent,
  ],
  templateUrl: './catalog.component.html',
  styleUrl: './catalog.component.scss',
})
export class CatalogComponent implements OnInit {
  kinds = signal<Kind[]>([]);
  loading = signal(true);
  saving = signal(false);

  get fieldTypeOptions(): ZbSelectOption[] {
    return this.fieldTypes.map(ft => ({ label: ft.label, value: ft.value }));
  }

  readonly fieldTypes = [
    { value: 'text', label: 'Texto' },
    { value: 'number', label: 'Número' },
    { value: 'float', label: 'Decimal' },   // p.ej. 37,5 horas semanales
    { value: 'time', label: 'Hora' },
    { value: 'color', label: 'Color' },
    { value: 'boolean', label: 'Sí/No' },
    { value: 'textarea', label: 'Texto largo' },
  ];

  // Kind create
  creatingKind = false;
  newKind = { code: '', name: '', description: '', editable: true };

  // Kind edit (inline via expansion panel header)
  editingKindId: number | null = null;
  editKind: Partial<Kind> = {};

  // Batch add-values
  addingValueTo: number | null = null;
  pendingValues: Array<{ label: string; code: string; color: string; icon: string; order: number; attrs: Record<string, string> }> = [];

  // Inline edit value
  editingValueId: number | null = null;
  editValueBase: Partial<KindValue> = {};
  editValueAttrs: Record<string, string> = {};

  // Attribute management
  addingAttrTo: number | null = null;
  newAttr: Partial<KindAttribute> = { key: '', label: '', field_type: 'text', required: false, placeholder: '', default_value: '', order: 0 };
  editingAttrId: number | null = null;
  editAttr: Partial<KindAttribute> = {};

  constructor(private catalogService: CatalogService) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.catalogService.getKinds().pipe(
      switchMap(list => {
        if (!list.length) return of([]);
        return forkJoin(list.map(k => this.catalogService.getKind(k.id)));
      }),
    ).subscribe({
      next: kinds => {
        const sorted = [...kinds].sort((a, b) => a.name.localeCompare(b.name));
        this.kinds.set(sorted);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  // ── Kind CRUD ──────────────────────────────────────────────
  onNewKindNameChange(name: string): void {
    const code = name.toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
    this.newKind = { ...this.newKind, name, code };
  }

  saveNewKind(): void {
    if (!this.newKind.code || !this.newKind.name) return;
    this.saving.set(true);
    this.catalogService.createKind(this.newKind).subscribe({
      next: () => { this.creatingKind = false; this.newKind = { code: '', name: '', description: '', editable: true }; this.saving.set(false); this.load(); },
      error: () => this.saving.set(false),
    });
  }

  startEditKind(kind: Kind): void {
    this.editingKindId = kind.id;
    this.editKind = { name: kind.name, description: kind.description };
  }

  saveEditKind(kind: Kind): void {
    this.saving.set(true);
    this.catalogService.updateKind(kind.id, { ...kind, ...this.editKind }).subscribe({
      next: () => { this.editingKindId = null; this.saving.set(false); this.catalogService.clearCache(kind.code); this.load(); },
      error: () => this.saving.set(false),
    });
  }

  deleteKind(kind: Kind): void {
    if (!confirm(`Eliminar la categoria "${kind.name}" y todos sus valores?`)) return;
    this.catalogService.deleteKind(kind.id).subscribe(() => {
      this.catalogService.clearCache(kind.code);
      this.load();
    });
  }

  // ── Add values (batch) ─────────────────────────────────────
  onPendingLabelChange(index: number, label: string): void {
    const code = label.toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
    this.pendingValues[index] = { ...this.pendingValues[index], label, code };
  }

  startAddValue(kind: Kind): void {
    this.addingValueTo = kind.id;
    this.editingValueId = null;
    this.pendingValues = [this.emptyPendingValue(kind)];
  }

  addAnotherValue(kind: Kind): void {
    this.pendingValues = [...this.pendingValues, this.emptyPendingValue(kind)];
  }

  removePendingValue(index: number): void {
    this.pendingValues = this.pendingValues.filter((_, i) => i !== index);
    if (!this.pendingValues.length) this.addingValueTo = null;
  }

  cancelAddValue(): void { this.addingValueTo = null; this.pendingValues = []; }

  saveAllPendingValues(kind: Kind): void {
    const valid = this.pendingValues.filter(v => v.code && v.label);
    if (!valid.length) return;
    this.saving.set(true);
    const saves$ = valid.map(v =>
      this.catalogService.createValue({ kind: kind.id, label: v.label, code: v.code, color: v.color, icon: v.icon, order: v.order }).pipe(
        switchMap(created => {
          const calls = kind.attributes.map(a =>
            this.catalogService.setValueAttribute(created.id, a.id, v.attrs[a.key] ?? '')
          );
          return calls.length ? forkJoin(calls) : of([]);
        }),
      )
    );
    concat(...saves$).pipe(toArray()).subscribe({
      next: () => {
        this.addingValueTo = null;
        this.pendingValues = [];
        this.saving.set(false);
        this.catalogService.clearCache(kind.code);
        this.load();
      },
      error: () => this.saving.set(false),
    });
  }

  private emptyPendingValue(kind: Kind): { label: string; code: string; color: string; icon: string; order: number; attrs: Record<string, string> } {
    const attrs: Record<string, string> = {};
    kind.attributes.forEach(a => attrs[a.key] = a.default_value ?? '');
    return { label: '', code: '', color: '#000000', icon: '', order: kind.values.length + this.pendingValues.length + 1, attrs };
  }

  // ── Edit value ─────────────────────────────────────────────
  startEditValue(kind: Kind, val: KindValue): void {
    this.editingValueId = val.id;
    this.addingValueTo = null;
    this.editValueBase = { code: val.code, label: val.label, icon: val.icon, color: val.color, order: val.order };
    this.editValueAttrs = {};
    kind.attributes.forEach(a => {
      const found = val.attributes.find(va => va.attribute_key === a.key);
      this.editValueAttrs[a.key] = found?.value ?? '';
    });
  }

  cancelEditValue(): void { this.editingValueId = null; }

  saveEditValue(kind: Kind, val: KindValue): void {
    this.saving.set(true);
    this.catalogService.updateValue(val.id, { kind: kind.id, ...this.editValueBase }).pipe(
      switchMap(updated => {
        const calls = kind.attributes.map(a => {
          const existing = val.attributes.find(va => va.attribute_key === a.key);
          return this.catalogService.setValueAttribute(
            updated.id, a.id, this.editValueAttrs[a.key] ?? '', existing?.id
          );
        });
        return calls.length ? forkJoin(calls) : of([]);
      }),
    ).subscribe({
      next: () => {
        this.editingValueId = null;
        this.saving.set(false);
        this.catalogService.clearCache(kind.code);
        this.load();
      },
      error: () => this.saving.set(false),
    });
  }

  // ── Toggle / Delete ────────────────────────────────────────
  toggleValueActive(kindCode: string, val: KindValue): void {
    this.catalogService.updateValue(val.id, { ...val, active: !val.active }).subscribe(() => {
      this.catalogService.clearCache(kindCode);
      this.load();
    });
  }

  deleteValue(kindCode: string, valueId: number): void {
    if (confirm('Eliminar este valor?')) {
      this.catalogService.deleteValue(valueId).subscribe(() => {
        this.catalogService.clearCache(kindCode);
        this.load();
      });
    }
  }

  // ── Attribute CRUD ──────────────────────────────────────────
  onNewAttrLabelChange(label: string): void {
    const key = label.toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
    this.newAttr = { ...this.newAttr, label, key };
  }

  startAddAttr(kind: Kind): void {
    this.addingAttrTo = kind.id;
    this.editingAttrId = null;
    this.newAttr = { key: '', label: '', field_type: 'text', required: false, placeholder: '', default_value: '', order: kind.attributes.length };
  }

  cancelAddAttr(): void { this.addingAttrTo = null; }

  saveNewAttr(kind: Kind): void {
    if (!this.newAttr.key || !this.newAttr.label) return;
    this.saving.set(true);
    this.catalogService.createAttribute({ kind: kind.id, ...this.newAttr }).subscribe({
      next: () => { this.addingAttrTo = null; this.saving.set(false); this.catalogService.clearCache(kind.code); this.load(); },
      error: () => this.saving.set(false),
    });
  }

  startEditAttr(attr: KindAttribute): void {
    this.editingAttrId = attr.id;
    this.editAttr = { key: attr.key, label: attr.label, field_type: attr.field_type, required: attr.required, placeholder: attr.placeholder, default_value: attr.default_value, order: attr.order };
  }

  saveEditAttr(kind: Kind, attr: KindAttribute): void {
    this.saving.set(true);
    this.catalogService.updateAttribute(attr.id, { kind: kind.id, ...this.editAttr }).subscribe({
      next: () => { this.editingAttrId = null; this.saving.set(false); this.catalogService.clearCache(kind.code); this.load(); },
      error: () => this.saving.set(false),
    });
  }

  deleteAttr(kind: Kind, attrId: number): void {
    if (!confirm('Eliminar este campo? Todos los valores de esta categoria perderán este dato.')) return;
    this.catalogService.deleteAttribute(attrId).subscribe(() => {
      this.catalogService.clearCache(kind.code);
      this.load();
    });
  }

  attrTypeIcon(type: string): string {
    const icons: Record<string, string> = {
      text: 'text_fields', number: 'tag', time: 'schedule',
      color: 'palette', boolean: 'toggle_on', textarea: 'notes',
    };
    return icons[type] ?? 'help_outline';
  }

  // ── Helpers ────────────────────────────────────────────────
  getAttrValue(val: KindValue, key: string): string {
    return val.attributes.find(a => a.attribute_key === key)?.value ?? '—';
  }

  formatAttrDisplay(attr: KindAttribute, val: KindValue): string {
    const v = this.getAttrValue(val, attr.key);
    if (attr.field_type === 'boolean') return v === 'true' ? 'Sí' : 'No';
    return v || '—';
  }
}
