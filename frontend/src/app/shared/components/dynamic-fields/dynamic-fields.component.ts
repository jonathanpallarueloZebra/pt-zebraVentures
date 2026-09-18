import { Component, Input, Output, EventEmitter, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTooltipModule } from '@angular/material/tooltip';
import { FieldSchema } from '@app/shared/interfaces/entity-field.interface';
import { KindValue } from '@app/shared/interfaces/catalog.interface';
import { SECTION_ICONS, sectionIconPath } from '@app/shared/constants/section-icons';
import { MATERIAL_ICONS } from '@app/shared/constants/material-icons';
import { CatalogService } from '@app/shared/services/catalog.service';
import { EntityRecordService } from '@app/shared/services/entity-record.service';
import { EntityFieldService } from '@app/shared/services/entity-field.service';
import { EntityTypeService } from '@app/shared/services/entity-type.service';
import { ZbInputComponent } from '@app/shared/components/zb-input/zb-input.component';
import { ZbSelectComponent, ZbSelectOption } from '@app/shared/components/zb-select/zb-select.component';
import { ZbToggleComponent } from '@app/shared/components/zb-toggle/zb-toggle.component';
import { ZbCheckboxComponent } from '@app/shared/components/zb-checkbox/zb-checkbox.component';
import { ZbButtonComponent } from '@app/shared/components/zb-button/zb-button.component';
import { ZbTimeInputComponent } from '@app/shared/components/zb-time-input/zb-time-input.component';

export interface PriorityItem { value: any; priority: number; }

@Component({
  selector: 'app-dynamic-fields',
  standalone: true,
  imports: [
    CommonModule, FormsModule, MatTooltipModule,
    ZbInputComponent, ZbSelectComponent, ZbToggleComponent,
    ZbCheckboxComponent, ZbButtonComponent, ZbTimeInputComponent,
  ],
  template: `
    @for (field of fields; track field.key) {
      @if (isFieldVisible(field)) {
        <div class="field-wrapper">
          @switch (field.field_type) {

            @case ('text') {
              <zb-input
                [label]="fieldLabel(field)"
                [placeholder]="field.placeholder"
                [hint]="field.help_text"
                [error]="fieldError(field)"
                [ngModel]="values[field.key] ?? field.default_value ?? ''"
                (ngModelChange)="onInput(field.key, $event)"
              ></zb-input>
            }

            @case ('textarea') {
              <div class="native-field">
                <label class="native-field__label">{{ fieldLabel(field) }}</label>
                <textarea
                  class="native-field__textarea"
                  rows="3"
                  [placeholder]="field.placeholder"
                  [value]="values[field.key] ?? field.default_value ?? ''"
                  (input)="onInput(field.key, $any($event.target).value)"
                ></textarea>
                @if (field.help_text) { <span class="native-field__hint">{{ field.help_text }}</span> }
              </div>
            }

            @case ('number') {
              <zb-input
                type="number"
                [label]="fieldLabel(field)"
                [placeholder]="field.placeholder"
                [hint]="field.help_text"
                [error]="fieldError(field)"
                [ngModel]="values[field.key] ?? field.default_value ?? ''"
                (ngModelChange)="onInput(field.key, $event !== '' ? +$event : null)"
              ></zb-input>
            }

            <!-- DECIMAL: type="text" con inputmode decimal, NO type="number".
                 Con number el navegador da por inválido "37," mientras escribes y
                 devuelve cadena vacía: el input se reescribía y el cursor saltaba
                 al principio, así que no se podía teclear la coma. En texto el
                 valor se conserva y parseDecimal lo normaliza al guardar (acepta
                 coma y punto). En móvil sigue saliendo teclado numérico. -->
            @case ('float') {
              <zb-input
                type="text"
                inputmode="decimal"
                [label]="fieldLabel(field)"
                [placeholder]="field.placeholder"
                [hint]="field.help_text"
                [error]="fieldError(field)"
                [ngModel]="values[field.key] ?? field.default_value ?? ''"
                (ngModelChange)="onInput(field.key, parseDecimal($event))"
              ></zb-input>
            }

            @case ('color') {
              <div class="native-field">
                <label class="native-field__label">{{ fieldLabel(field) }}</label>
                <div class="color-group">
                  <input type="color"
                         [value]="values[field.key] || field.default_value || '#000000'"
                         (input)="onInput(field.key, $any($event.target).value)">
                  <span class="color-hex">{{ values[field.key] || field.default_value || '#000000' }}</span>
                </div>
                @if (field.help_text) { <span class="native-field__hint">{{ field.help_text }}</span> }
              </div>
            }

            @case ('time') {
              <zb-time-input
                [label]="fieldLabel(field)"
                [hint]="field.help_text"
                [ngModel]="values[field.key] ?? field.default_value ?? ''"
                (ngModelChange)="onInput(field.key, $event)"
              ></zb-time-input>
            }

            @case ('boolean') {
              <div class="toggle-row">
                <zb-toggle
                  [label]="fieldLabel(field)"
                  [ngModel]="values[field.key] === true || values[field.key] === 'true'"
                  (ngModelChange)="onInput(field.key, $event)"
                ></zb-toggle>
                @if (field.help_text) { <span class="native-field__hint">{{ field.help_text }}</span> }
              </div>
            }

            @case ('select') {
              <zb-select
                [label]="fieldLabel(field)"
                [placeholder]="field.placeholder || 'Selecciona una opción'"
                [options]="toSelectOptions(field.options)"
                [hint]="field.help_text"
                [error]="fieldError(field)"
                [ngModel]="values[field.key] ?? field.default_value ?? null"
                (ngModelChange)="onInput(field.key, $event)"
              ></zb-select>
            }

            @case ('icon') {
              <zb-select
                [label]="fieldLabel(field)"
                [placeholder]="field.placeholder || 'Selecciona un icono'"
                [options]="iconSelectOptions()"
                [searchable]="true"
                [hint]="field.help_text"
                [error]="fieldError(field)"
                [ngModel]="values[field.key] ?? field.default_value ?? null"
                (ngModelChange)="onInput(field.key, $event)"
              ></zb-select>
            }

            @case ('catalog_select') {
              <zb-select
                [label]="fieldLabel(field)"
                [placeholder]="field.placeholder || 'Selecciona una opción'"
                [options]="catalogToSelectOptions(field.kind_code)"
                [hint]="field.help_text"
                [error]="fieldError(field)"
                [ngModel]="values[field.key] ?? field.default_value ?? null"
                (ngModelChange)="onInput(field.key, $event)"
              ></zb-select>
            }

            @case ('multi_catalog_select') {
              @if (field.allow_priority) {
                <div class="priority-field">
                  <div class="priority-field-header">
                    <span class="priority-field-label">{{ fieldLabel(field) }}</span>
                    <span class="priority-badge">por prioridad</span>
                  </div>
                  @for (item of getPriorityItems(field.key); track $index) {
                    <div class="priority-item">
                      <span class="priority-item__label">{{ priorityLabel(item.priority) }}</span>
                      <div class="priority-row">
                        <div class="priority-select">
                          <zb-select
                            [options]="catalogToSelectOptions(field.kind_code)"
                            placeholder="Selecciona..."
                            [ngModel]="item.value"
                            (ngModelChange)="updatePriorityValue(field.key, $index, $event)"
                          ></zb-select>
                        </div>
                        <zb-button variant="icon-only" size="sm" icon="arrow_upward"
                          ariaLabel="Subir prioridad"
                          [disabled]="$index === 0"
                          (click)="movePriorityUp(field.key, $index)"></zb-button>
                        <zb-button variant="icon-only" size="sm" icon="arrow_downward"
                          ariaLabel="Bajar prioridad"
                          [disabled]="$index === getPriorityItems(field.key).length - 1"
                          (click)="movePriorityDown(field.key, $index)"></zb-button>
                        <zb-button variant="icon-only" size="sm" icon="remove_circle_outline"
                          ariaLabel="Quitar opción"
                          (click)="removePriorityItem(field.key, $index)"></zb-button>
                      </div>
                    </div>
                  }
                  <zb-button variant="secondary" size="sm" iconLeft="add"
                    (click)="addPriorityItem(field.key)">Añadir opción</zb-button>
                  @if (field.help_text) { <span class="native-field__hint">{{ field.help_text }}</span> }
                </div>
              } @else {
                <div class="checkbox-group">
                  <span class="checkbox-group__label">{{ fieldLabel(field) }}</span>
                  @for (opt of getCatalogOptions(field.kind_code); track opt.code) {
                    <zb-checkbox
                      [label]="opt.label"
                      [ngModel]="isChecked(field.key, opt.code)"
                      (ngModelChange)="onMultiToggle(field.key, opt.code, $event)"
                    ></zb-checkbox>
                  }
                  @if (field.help_text) { <span class="native-field__hint">{{ field.help_text }}</span> }
                </div>
              }
            }

            @case ('entity_select') {
              <zb-select
                [label]="fieldLabel(field)"
                [placeholder]="field.placeholder || 'Selecciona...'"
                [options]="entityToSelectOptions(field)"
                [hint]="field.help_text"
                [error]="fieldError(field)"
                [searchable]="true"
                [ngModel]="values[field.key] ?? null"
                (ngModelChange)="onInput(field.key, $event)"
              ></zb-select>
            }

            @case ('multi_entity_select') {
              @if (field.allow_priority) {
                <div class="priority-field">
                  <div class="priority-field-header">
                    <span class="priority-field-label">{{ fieldLabel(field) }}</span>
                    <span class="priority-badge">por prioridad</span>
                  </div>
                  @for (item of getPriorityItems(field.key); track $index) {
                    <div class="priority-item">
                      <span class="priority-item__label">{{ priorityLabel(item.priority) }}</span>
                      <div class="priority-row">
                        <div class="priority-select">
                          <zb-select
                            [options]="entityToSelectOptions(field)"
                            placeholder="Selecciona..."
                            [searchable]="true"
                            [ngModel]="item.value"
                            (ngModelChange)="updatePriorityValue(field.key, $index, $event)"
                          ></zb-select>
                        </div>
                        <zb-button variant="icon-only" size="sm" icon="arrow_upward"
                          ariaLabel="Subir prioridad"
                          [disabled]="$index === 0"
                          (click)="movePriorityUp(field.key, $index)"></zb-button>
                        <zb-button variant="icon-only" size="sm" icon="arrow_downward"
                          ariaLabel="Bajar prioridad"
                          [disabled]="$index === getPriorityItems(field.key).length - 1"
                          (click)="movePriorityDown(field.key, $index)"></zb-button>
                        <zb-button variant="icon-only" size="sm" icon="remove_circle_outline"
                          ariaLabel="Quitar opción"
                          (click)="removePriorityItem(field.key, $index)"></zb-button>
                      </div>
                    </div>
                  }
                  <zb-button variant="secondary" size="sm" iconLeft="add"
                    (click)="addPriorityItem(field.key)">Añadir opción</zb-button>
                  @if (field.help_text) { <span class="native-field__hint">{{ field.help_text }}</span> }
                </div>
              } @else {
                <div class="checkbox-group">
                  <span class="checkbox-group__label">{{ fieldLabel(field) }}</span>
                  @for (rec of getEntityOptions(field); track rec.id) {
                    <zb-checkbox
                      [label]="getRecordLabel(rec)"
                      [ngModel]="isChecked(field.key, rec.id)"
                      (ngModelChange)="onMultiToggle(field.key, rec.id, $event)"
                    ></zb-checkbox>
                  }
                  @if (field.help_text) { <span class="native-field__hint">{{ field.help_text }}</span> }
                </div>
              }
            }

          }
        </div>
      }
    }
  `,
  styles: [`
    /* Contenedor flex propio con gap explícito (spacing/L 24px = mismo que el
       sidepanel y .abs-form). Antes era display:contents y el gap del sidepanel
       llegaba de forma inconsistente a los field-wrapper. Ahora explícito y
       uniforme, con aire suficiente para formularios largos. */
    :host {
      display: flex;
      flex-direction: column;
      gap: var(--sp-l);
    }

    .field-wrapper {
      display: flex;
      flex-direction: column;
    }

    /* zb-input / zb-select fill grid cell */
    zb-input, zb-select { width: 100%; }

    /* ── Toggle row ──────────────────────────────────────────── */
    .toggle-row {
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding: 8px 0;
    }

    /* ── Native fields (textarea / time / color) ─────────────── */
    .native-field {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    /* Label Overline de Figma (Input/label): 12px SemiBold, MAYÚS, ls 0.12 */
    .native-field__label {
      font-family: var(--ff-body);
      font-size: var(--figma-input-label-font-size);
      font-weight: var(--fw-semibold);
      color: var(--figma-input-label-color);
      line-height: var(--figma-input-label-line-height);
      text-transform: uppercase;
      letter-spacing: var(--figma-input-label-letter-spacing);
    }
    /* textarea / time = patrón Input/text de stylesJPfigma (tokens --figma-input-*):
       pad 8 · radius 4 · borde #b3b6bd · Shadow/xs · texto 14 body/2 · focus azul+anillo */
    .native-field__textarea {
      width: 100%;
      box-sizing: border-box;
      // appearance:none quita la caja nativa del control (evita el doble borde).
      appearance: none;
      -webkit-appearance: none;
      padding: var(--figma-input-padding);
      border: var(--figma-input-border-width) solid var(--figma-input-border);
      border-radius: var(--figma-input-radius);
      background: var(--figma-input-surface);
      box-shadow: var(--figma-input-shadow);
      color: var(--figma-input-text);
      font-family: var(--ff-body);
      font-size: var(--figma-input-value-font-size);
      line-height: var(--figma-input-value-line-height);
      resize: vertical;
      outline: none;
      transition: border-color var(--transition-fast);
      // Foco = solo borde azul (como absences, sin anillo).
      &:focus { border-color: var(--figma-input-border-active); }
      &::placeholder { color: var(--figma-input-placeholder); }
    }
    .native-field__time {
      box-sizing: border-box;
      // appearance:none quita la caja nativa del control time (doble borde).
      appearance: none;
      -webkit-appearance: none;
      padding: var(--figma-input-padding);
      border: var(--figma-input-border-width) solid var(--figma-input-border);
      border-radius: var(--figma-input-radius);
      background: var(--figma-input-surface);
      box-shadow: var(--figma-input-shadow);
      color: var(--figma-input-text);
      font-family: var(--ff-body);
      font-size: var(--figma-input-value-font-size);
      line-height: var(--figma-input-value-line-height);
      outline: none;
      transition: border-color var(--transition-fast);
      // Foco = solo borde azul (como absences, sin anillo).
      &:focus { border-color: var(--figma-input-border-active); }
      // Oculta el selector NATIVO del navegador (dropdown azul de horas/minutos)
      // para que no desentone con los desplegables personalizados de la web.
      // La hora se escribe/edita directamente en el input.
      &::-webkit-calendar-picker-indicator { display: none; }
      &::-webkit-inner-spin-button,
      &::-webkit-clear-button { display: none; -webkit-appearance: none; }
    }
    .native-field__hint {
      font-size: var(--fs-12);
      color: var(--text-secondary);
      line-height: 1.4;
    }

    /* ── Color picker ────────────────────────────────────────── */
    .color-group { display: flex; align-items: center; gap: 10px; }
    .color-group input[type="color"] {
      width: 36px; height: 36px;
      border: 1px solid var(--border-high);
      border-radius: 6px; cursor: pointer; padding: 2px;
    }
    .color-hex { font-size: var(--fs-13); color: var(--text-secondary); font-family: monospace; }

    /* ── Checkbox group ──────────────────────────────────────── */
    .checkbox-group {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .checkbox-group__label {
      font-family: var(--ff-body);
      font-size: var(--figma-input-label-font-size);
      font-weight: var(--fw-semibold);
      color: var(--figma-input-label-color);
      line-height: var(--figma-input-label-line-height);
      text-transform: uppercase;
      letter-spacing: var(--figma-input-label-letter-spacing);
      margin-bottom: 2px;
    }

    /* ── Priority list — CAJA con acento azul (accent) del sistema ───── */
    .priority-field {
      display: flex;
      flex-direction: column;
      align-items: stretch;
      gap: var(--sp-s);                 // separación entre filas de prioridad
      // Caja: fondo azul muy claro + borde azul sutil + radius contenedor.
      background: var(--accent-alpha-low);           // Accent/alpha/low #0ba5ec1a
      border: 1px solid var(--border-accent);        // Border/accent (azul)
      border-radius: var(--radius-containers, 8px);  // radius/default 8
      padding: var(--sp-m);                          // 16px interior
    }
    /* El botón "Añadir opción": compacto (no ancho completo) y con un poco más
       de aire respecto a la última fila. */
    .priority-field > zb-button {
      align-self: flex-start;
      margin-top: 4px;                  // spacing/XS extra sobre el gap base
    }
    /* El hint se separa del botón. */
    .priority-field > .native-field__hint { margin-top: 4px; }
    /* El header (label + badge) se separa de la primera fila como un label
       normal separa de su input (6px, Input/label gap del Figma). */
    .priority-field-header {
      display: flex;
      align-items: center;
      gap: var(--sp-s);
      margin-bottom: 6px;
    }
    /* Label = mismo Overline que el resto de labels del panel. */
    .priority-field-label {
      font-family: var(--ff-body);
      font-size: var(--figma-input-label-font-size);
      font-weight: var(--fw-semibold);
      line-height: var(--figma-input-label-line-height);
      letter-spacing: var(--figma-input-label-letter-spacing);
      text-transform: uppercase;
      color: var(--figma-input-label-color);
    }
    /* Badge "por prioridad" = tokens de alert info (como los demás badges). */
    .priority-badge {
      font-size: var(--fs-12);
      font-weight: var(--fw-semibold);
      text-transform: uppercase;
      letter-spacing: 0.12px;
      background: var(--figma-alert-info-surface);
      color: var(--figma-alert-info-text);
      border-radius: 9999px;
      padding: 1px 8px;
    }
    /* Cada opción es una TARJETA independiente: caja blanca con su borde y su
       etiqueta de prioridad encima, para que se lea de un vistazo qué orden
       tiene cada nombre. */
    .priority-item {
      display: flex;
      flex-direction: column;
      gap: 6px;                                      // Input/label gap de Figma
      background: var(--figma-input-surface, #fff);
      border: 1px solid var(--borde-general, #d6d8dc);
      border-radius: var(--radius-containers, 8px);
      padding: var(--sp-s) var(--sp-m);
    }
    /* Etiqueta Overline (12px SemiBold MAYÚS), igual que el resto de labels. */
    .priority-item__label {
      font-family: var(--ff-body);
      font-size: var(--figma-input-label-font-size);
      font-weight: var(--fw-semibold);
      line-height: var(--figma-input-label-line-height);
      letter-spacing: var(--figma-input-label-letter-spacing);
      text-transform: uppercase;
      color: var(--figma-input-label-color);
    }
    .priority-row {
      display: flex;
      align-items: center;
      gap: var(--sp-s);
    }
    .priority-select { flex: 1; min-width: 0; }
  `],
})
export class DynamicFieldsComponent implements OnChanges {
  @Input() fields: FieldSchema[] = [];
  @Input() values: Record<string, any> = {};
  @Input() appearance: 'outline' | 'fill' = 'outline';
  @Output() valuesChange = new EventEmitter<Record<string, any>>();

  /**
   * Marca con * los campos que la configuración (EntityField.required) define
   * como obligatorios, y pinta el error en los que falten cuando se intenta
   * guardar. La lista NO se escribe aquí: sale del `required` que viene en el
   * field_schema, el mismo que valida el backend.
   */
  @Input() markRequired = false;

  /**
   * Pinta el error en los obligatorios vacíos. Se enciende al intentar guardar,
   * no antes: marcar en rojo un formulario recién abierto y aún sin tocar es
   * agresivo y no aporta nada.
   */
  @Input() showRequiredErrors = false;

  /** Etiqueta del campo, con * si es obligatorio (AC-1). */
  fieldLabel(field: FieldSchema): string {
    return this.markRequired && field.required ? `${field.label} *` : field.label;
  }

  /** Mensaje de error del campo, si es obligatorio y está vacío (AC-2). */
  fieldError(field: FieldSchema): string | undefined {
    if (!this.showRequiredErrors || !this.markRequired) return undefined;
    return this.isMissing(field) ? 'Este campo es obligatorio' : undefined;
  }

  /**
   * Un obligatorio está sin rellenar. Mismo criterio que el backend
   * (`_missing_required`): vacíos son null, '', [] y {}. El 0 y el false SÍ son
   * valores válidos — "0 turnos" o un toggle en "no" están rellenos.
   */
  private isMissing(field: FieldSchema): boolean {
    if (!field.required) return false;
    // Un campo oculto por `visible_when` no se puede rellenar: no se exige.
    if (!this.isFieldVisible(field)) return false;
    const v = this.values[field.key] ?? field.default_value ?? null;
    if (v === null || v === undefined || v === '') return true;
    if (Array.isArray(v)) return v.length === 0;
    if (typeof v === 'object') return Object.keys(v).length === 0;
    return false;
  }

  /** Etiquetas de los obligatorios que faltan, para el aviso del formulario. */
  missingRequiredLabels(): string[] {
    return this.fields.filter(f => this.isMissing(f)).map(f => f.label);
  }

  private catalogCache = new Map<string, KindValue[]>();
  private entityCache = new Map<string, any[]>();
  private targetFieldDefs = new Map<string, { key: string; target_entity: string }[]>();
  private autoDeps = new Map<string, { parentKey: string; targetDataKey: string }[]>();
  private displayFields = new Map<string, string>();

  constructor(
    private catalogService: CatalogService,
    private entityRecordService: EntityRecordService,
    private entityFieldService: EntityFieldService,
    private entityTypeService: EntityTypeService,
  ) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['fields']) {
      this.loadCatalogOptions();
      this.loadEntityOptions();
    }
  }

  private loadCatalogOptions(): void {
    const codes = new Set(
      this.fields
        .filter(f => (f.field_type === 'catalog_select' || f.field_type === 'multi_catalog_select') && f.kind_code)
        .map(f => f.kind_code!)
    );
    for (const code of codes) {
      if (!this.catalogCache.has(code)) {
        this.catalogService.getValues(code).subscribe(values => {
          this.catalogCache.set(code, values);
        });
      }
    }
  }

  private loadEntityOptions(): void {
    const entityFields = this.fields.filter(
      f => (f.field_type === 'entity_select' || f.field_type === 'multi_entity_select') && f.target_entity
    );
    const slugs = new Set(entityFields.map(f => f.target_entity!));
    for (const slug of slugs) {
      if (!this.entityCache.has(slug)) {
        this.entityRecordService.getAll(slug).subscribe(records => {
          this.entityCache.set(slug, records);
        });
      }
      if (!this.displayFields.has(slug)) {
        this.entityTypeService.get(slug).subscribe(et => {
          this.displayFields.set(slug, et.display_field || 'name');
        });
      }
      if (!this.targetFieldDefs.has(slug)) {
        this.entityFieldService.getAll(slug).subscribe(fields => {
          const refs = fields
            .filter(f => f.active && (f.field_type === 'entity_select' || f.field_type === 'multi_entity_select') && f.target_entity)
            .map(f => ({ key: f.key, target_entity: f.target_entity! }));
          this.targetFieldDefs.set(slug, refs);
          this.buildAutoDeps();
        });
      }
    }
  }

  /** Descubre el filtrado automático entre campos de entidad.
   *
   *  Ejemplo: el formulario tiene "tienda" y "sección"; los registros de
   *  sección guardan a qué tienda pertenecen → al elegir tienda, el
   *  desplegable de secciones se limita a las de esa tienda.
   *
   *  Un campo SOLO puede ser padre de otro si apunta a una entidad DISTINTA.
   *  Sin esa comprobación, dos campos que apuntan a la misma entidad (p.ej.
   *  "secciones" y "edificio de trabajo", ambos → seccion) se declaraban
   *  dependientes el uno del otro y el filtro cruzado dejaba la lista vacía.
   */
  private buildAutoDeps(): void {
    this.autoDeps.clear();
    const entityFields = this.fields.filter(
      f => (f.field_type === 'entity_select' || f.field_type === 'multi_entity_select') && f.target_entity
    );
    const slugToFormKeys = new Map<string, string[]>();
    for (const f of entityFields) {
      const arr = slugToFormKeys.get(f.target_entity!) ?? [];
      arr.push(f.key);
      slugToFormKeys.set(f.target_entity!, arr);
    }
    // key del campo → entidad a la que apunta (para descartar padres de la
    // misma entidad, que es lo que producía la dependencia circular).
    const keyToSlug = new Map(entityFields.map(f => [f.key, f.target_entity!]));

    for (const field of entityFields) {
      if (field.depends_on) continue;
      const targetRefs = this.targetFieldDefs.get(field.target_entity!);
      if (!targetRefs) continue;
      const deps: { parentKey: string; targetDataKey: string }[] = [];
      for (const tRef of targetRefs) {
        // Autorreferencia (la entidad tiene un campo que apunta a sí misma):
        // no genera jerarquía padre-hijo entre campos del formulario.
        if (tRef.target_entity === field.target_entity) continue;
        const parentKeys = slugToFormKeys.get(tRef.target_entity);
        if (!parentKeys) continue;
        const parentKey = parentKeys.find(
          k => k !== field.key && keyToSlug.get(k) !== field.target_entity,
        );
        if (parentKey) deps.push({ parentKey, targetDataKey: tRef.key });
      }
      if (deps.length) this.autoDeps.set(field.key, deps);
    }
  }

  // ── Option converters for zb-select ───────────────────────

  toSelectOptions(options: string[]): ZbSelectOption[] {
    return (options ?? []).map(o => ({ label: o, value: o }));
  }

  /** Opciones para un campo de tipo `icon`, con preview a la izquierda:
   *   1) "(sin icono)" para dejar el campo vacío (AC-5).
   *   2) Los iconos de SECCIÓN (SVG propios del Figma).
   *   3) Un catálogo de iconos Material (mat-icon), buscables por su nombre.
   *  El valor guardado es el nombre del icono (SVG: 'fruteria'…; Material:
   *  'store'…); al pintar, sectionIconPath() distingue si es un SVG conocido. */
  iconSelectOptions(): ZbSelectOption[] {
    return [
      { label: '(sin icono)', value: null },
      ...SECTION_ICONS.map(i => ({
        label: i.label,
        value: i.value,
        iconSrc: sectionIconPath(i.value),
      })),
      ...MATERIAL_ICONS.map(m => ({
        label: m.label,
        value: m.icon,
        icon: m.icon,
      })),
    ];
  }

  catalogToSelectOptions(kindCode?: string): ZbSelectOption[] {
    return this.getCatalogOptions(kindCode).map(o => ({ label: o.label, value: o.code }));
  }

  entityToSelectOptions(field: FieldSchema): ZbSelectOption[] {
    const opts = this.getEntityOptions(field).map(rec => ({ label: this.getRecordLabel(rec), value: rec.id }));
    // El valor ya guardado debe seguir siendo visible aunque su registro no
    // esté en la lista (p.ej. un turno extra que ha caducado y ya no se ofrece
    // para nuevas asignaciones). Sin esto el desplegable saldría en blanco y al
    // guardar se perdería el valor sin que nadie lo haya tocado.
    const current = this.values[field.key];
    // Solo tiene sentido para valores ESCALARES. En los campos por prioridad
    // (multi_entity_select) el valor es un array de {value, priority}, y colarlo
    // aquí pintaba una opción "#[object Object]" en el desplegable.
    const esEscalar = current !== null && current !== undefined && current !== ''
      && typeof current !== 'object';
    if (esEscalar && !opts.some(o => String(o.value) === String(current))) {
      const rec = (this.entityCache.get(field.target_entity!) ?? [])
        .find(r => String(r.id) === String(current));
      opts.unshift({ label: rec ? this.getRecordLabel(rec) : `#${current}`, value: current });
    }
    return opts;
  }

  // ── Multi-select helpers (checkbox mode) ──────────────────

  isChecked(key: string, value: any): boolean {
    return this.asSimpleArray(this.values[key]).map(String).includes(String(value));
  }

  onMultiToggle(key: string, value: any, checked: boolean): void {
    const current = this.asSimpleArray(this.values[key]);
    const next = checked
      ? [...current, value]
      : current.filter((v: any) => String(v) !== String(value));
    this.onInput(key, next);
  }

  // ── Existing helpers ───────────────────────────────────────

  getCatalogOptions(kindCode?: string): KindValue[] {
    return kindCode ? this.catalogCache.get(kindCode) ?? [] : [];
  }

  getEntityOptions(field: FieldSchema): any[] {
    if (!field.target_entity) return [];
    const all = this.entityCache.get(field.target_entity) ?? [];
    if (field.depends_on && field.depends_on_field) {
      const parentVal = this.values[field.depends_on];
      if (parentVal === null || parentVal === undefined || parentVal === '') return all;
      return all.filter(rec => rec.data?.[field.depends_on_field!] == parentVal);
    }
    const deps = this.autoDeps.get(field.key);
    if (deps?.length) {
      // Solo se filtra por las dependencias que el registro destino realmente
      // rellena. Si un campo de enlace está vacío en TODOS los registros (p.ej.
      // shift.tiendas sin asignar), esa dependencia se ignora en vez de dejar
      // el desplegable a cero: la dependencia automática es una comodidad
      // (acotar la lista), nunca un motivo para no poder elegir nada.
      const activeDeps = deps.filter(d => {
        const parentVal = this.values[d.parentKey];
        if (parentVal === null || parentVal === undefined || parentVal === '') return false;
        return all.some(rec => this.matchesDep(rec, d.targetDataKey, parentVal));
      });
      if (!activeDeps.length) return all;
      return all.filter(rec =>
        activeDeps.every(d => this.matchesDep(rec, d.targetDataKey, this.values[d.parentKey]))
      );
    }
    return all;
  }

  /** ¿El registro apunta al valor del padre en `dataKey`? Soporta enlaces
   *  simples (`entity_select`) y múltiples (`multi_entity_select`, array). */
  private matchesDep(rec: any, dataKey: string, parentVal: any): boolean {
    const linked = rec.data?.[dataKey];
    if (linked === null || linked === undefined || linked === '') return false;
    if (Array.isArray(linked)) {
      return linked.some((v: any) =>
        String(typeof v === 'object' && v !== null && 'value' in v ? v.value : v) === String(parentVal)
      );
    }
    return String(linked) === String(parentVal);
  }

  getRecordLabel(rec: any): string {
    const slug = rec.entity_type_slug || rec.entity_type;
    const displayKey = slug ? this.displayFields.get(slug) : undefined;
    if (displayKey && rec.data?.[displayKey] != null) return String(rec.data[displayKey]);
    return rec.data?.name ?? rec.data?.label ?? rec.data?.nombre ?? `#${rec.id}`;
  }

  asSimpleArray(val: any): any[] {
    if (!Array.isArray(val)) return val ? [val] : [];
    return val.map((item: any) =>
      typeof item === 'object' && item !== null && 'value' in item ? item.value : item
    );
  }

  /**
   * Valor de un campo `float`: número, o null si está vacío/no es numérico.
   *
   * Acepta la COMA como separador decimal, que es lo que escribe un usuario
   * español ("37,5"). Sin esto `+'37,5'` da NaN y el valor se perdía en
   * silencio. Se guarda como número, no como texto, para que el motor lo lea
   * sin conversiones y no haya pérdida de precisión.
   */
  parseDecimal(raw: any): number | null {
    if (raw === '' || raw === null || raw === undefined) return null;
    const n = typeof raw === 'number' ? raw : Number(String(raw).replace(',', '.'));
    return Number.isFinite(n) ? n : null;
  }

  onInput(key: string, value: any): void {
    const updated = { ...this.values, [key]: value };
    const cleared = new Set<string>();
    const clearDependents = (parentKey: string) => {
      for (const field of this.fields) {
        if (cleared.has(field.key)) continue;
        let isDep = field.depends_on === parentKey;
        if (!isDep) {
          const deps = this.autoDeps.get(field.key);
          isDep = !!deps?.some(d => d.parentKey === parentKey);
        }
        if (isDep) {
          updated[field.key] = field.field_type === 'multi_entity_select' ? [] : null;
          cleared.add(field.key);
          clearDependents(field.key);
        }
      }
    };
    clearDependents(key);
    this.valuesChange.emit(updated);
  }

  isFieldVisible(field: FieldSchema): boolean {
    if (!field.visible_when_field) return true;
    const currentVal = this.values[field.visible_when_field];
    const expected = field.visible_when_value ?? '';
    const norm = (v: any): string => {
      if (v === true) return 'true';
      if (v === false) return 'false';
      if (v === null || v === undefined) return '';
      return String(v);
    };
    return norm(currentVal) === norm(expected);
  }

  /** Etiqueta de la tarjeta de cada opción: "1.ª OPCIÓN (PRINCIPAL)", "2.ª OPCIÓN"…
   *  La primera se marca como principal porque es la que el generador usa
   *  como puesto preferente. */
  priorityLabel(priority: number): string {
    return priority === 1 ? '1.ª opción (principal)' : `${priority}.ª opción`;
  }

  getPriorityItems(key: string): PriorityItem[] {
    const val = this.values[key];
    if (!Array.isArray(val)) return [];
    return val.map((item: any, idx: number) =>
      typeof item === 'object' && item !== null && 'value' in item
        ? item as PriorityItem
        : { value: item, priority: idx + 1 }
    );
  }

  addPriorityItem(key: string): void {
    const items = this.getPriorityItems(key);
    const nextPriority = items.length > 0 ? Math.max(...items.map(i => i.priority)) + 1 : 1;
    this.onInput(key, [...items, { value: null, priority: nextPriority }]);
  }

  removePriorityItem(key: string, idx: number): void {
    const items = this.getPriorityItems(key).filter((_, i) => i !== idx)
      .map((item, i) => ({ ...item, priority: i + 1 }));
    this.onInput(key, items);
  }

  movePriorityUp(key: string, idx: number): void {
    if (idx === 0) return;
    const items = [...this.getPriorityItems(key)];
    [items[idx - 1], items[idx]] = [items[idx], items[idx - 1]];
    this.onInput(key, items.map((item, i) => ({ ...item, priority: i + 1 })));
  }

  movePriorityDown(key: string, idx: number): void {
    const items = [...this.getPriorityItems(key)];
    if (idx >= items.length - 1) return;
    [items[idx], items[idx + 1]] = [items[idx + 1], items[idx]];
    this.onInput(key, items.map((item, i) => ({ ...item, priority: i + 1 })));
  }

  updatePriorityValue(key: string, idx: number, value: any): void {
    const items = this.getPriorityItems(key).map((item, i) =>
      i === idx ? { ...item, value } : item
    );
    this.onInput(key, items);
  }
}
