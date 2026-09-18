import {
  Component, Input, Output, EventEmitter, HostListener,
  ElementRef, forwardRef, ChangeDetectorRef, ChangeDetectionStrategy,
  OnChanges, SimpleChanges,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { ZbIconComponent } from '@app/shared/components/zb-icon/zb-icon.component';

export interface ZbSelectOption {
  label: string;
  value: any;
  disabled?: boolean;
  /** Nombre de icono Material opcional; si se indica, se pinta a la izquierda
   *  del label (en la opción y en el trigger). Usado por campos de tipo `icon`. */
  icon?: string;
  /** Ruta de un SVG opcional (p.ej. 'icons/sections/fruteria.svg'); si se indica,
   *  se pinta como <img> a la izquierda del label. Alternativa a `icon` para
   *  iconos que no son de la fuente Material (SVG propios del Figma). */
  iconSrc?: string;
}

@Component({
  selector: 'zb-select',
  standalone: true,
  imports: [CommonModule, FormsModule, ZbIconComponent],
  templateUrl: './zb-select.component.html',
  styleUrl: './zb-select.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [{
    provide: NG_VALUE_ACCESSOR,
    useExisting: forwardRef(() => ZbSelectComponent),
    multi: true,
  }],
})
export class ZbSelectComponent implements ControlValueAccessor, OnChanges {
  @Input() label?: string;
  @Input() placeholder = 'Selecciona una opción';
  @Input() options: ZbSelectOption[] = [];
  @Input() error?: string;
  @Input() hint?: string;
  @Input() searchable = false;
  @Input() allowAdd = false;
  @Input() allowDelete = false;

  @Output() addItem  = new EventEmitter<string>();
  @Output() deleteItem = new EventEmitter<ZbSelectOption>();

  selectedOption: ZbSelectOption | null = null;
  isOpen = false;
  isDisabled = false;
  searchQuery = '';

  constructor(private el: ElementRef, private cdr: ChangeDetectorRef) {}

  private onChange: (v: any) => void = () => {};
  private onTouched: () => void = () => {};

  /** Valor recibido del formulario, SIN resolver contra `options`.
   *
   *  Hay que conservarlo: las opciones suelen llegar por HTTP (catálogos,
   *  registros de entidad) DESPUÉS de que ngModel escriba el valor guardado.
   *  Si solo guardásemos el objeto resuelto, el find() fallaría en ese primer
   *  writeValue y el campo se quedaría vacío para siempre aunque el dato
   *  exista. Guardando el valor crudo podemos re-resolver cuando lleguen. */
  private currentValue: any = null;

  writeValue(v: any): void {
    this.currentValue = v;
    this.resolveSelected();
  }

  /** Re-resuelve la opción cuando cambian las opciones disponibles (p.ej. al
   *  responder el servicio que las carga) o el valor. */
  ngOnChanges(changes: SimpleChanges): void {
    if (changes['options']) this.resolveSelected();
  }

  private resolveSelected(): void {
    const v = this.currentValue;
    this.selectedOption =
      v === null || v === undefined
        ? null
        // Comparación laxa a propósito: los ids de entidad llegan como number
        // desde el backend pero pueden venir como string desde el formulario.
        : this.options.find(o => o.value === v || String(o.value) === String(v)) ?? null;
    this.cdr.markForCheck();
  }

  registerOnChange(fn: (v: any) => void): void  { this.onChange = fn; }
  registerOnTouched(fn: () => void): void        { this.onTouched = fn; }
  setDisabledState(d: boolean): void { this.isDisabled = d; this.cdr.markForCheck(); }

  get displayLabel(): string {
    return this.selectedOption?.label ?? '';
  }

  /** Texto tecleado en el buscador del desplegable.
   *
   *  El componente es OnPush: hay que marcarlo explícitamente, porque el
   *  evento `input` por sí solo no basta para que se recalcule
   *  `filteredOptions` en la vista. */
  onSearch(value: string): void {
    this.searchQuery = value ?? '';
    this.cdr.markForCheck();
  }

  /** Compara ignorando mayúsculas y acentos: buscar "panaderia" debe
   *  encontrar "Panadería". */
  private normalize(s: string): string {
    return (s ?? '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '');   // marcas diacríticas
  }

  get filteredOptions(): ZbSelectOption[] {
    const q = this.normalize(this.searchQuery).trim();
    if (!q) return this.options;
    return this.options.filter(o => this.normalize(o.label).includes(q));
  }

  toggle(): void {
    if (this.isDisabled) return;
    this.isOpen = !this.isOpen;
    if (!this.isOpen) { this.searchQuery = ''; this.onTouched(); }
    this.cdr.markForCheck();
  }

  select(opt: ZbSelectOption): void {
    if (opt.disabled) return;
    this.selectedOption = opt;
    // Mantener sincronizado el valor crudo: si luego cambian las opciones,
    // resolveSelected() debe re-resolver contra lo último elegido, no contra
    // el valor con el que se inicializó el campo.
    this.currentValue = opt.value;
    this.onChange(opt.value);
    this.isOpen = false;
    this.searchQuery = '';
    this.cdr.markForCheck();
  }

  isSelected(opt: ZbSelectOption): boolean {
    return this.selectedOption?.value === opt.value;
  }

  onAddItem(): void {
    if (this.searchQuery.trim()) {
      this.addItem.emit(this.searchQuery.trim());
      this.searchQuery = '';
      this.cdr.markForCheck();
    }
  }

  onDeleteItem(opt: ZbSelectOption, event: MouseEvent): void {
    event.stopPropagation();
    this.deleteItem.emit(opt);
    if (this.selectedOption?.value === opt.value) {
      this.selectedOption = null;
      this.onChange(null);
    }
    this.cdr.markForCheck();
  }

  // Close when clicking outside
  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (!this.el.nativeElement.contains(event.target)) {
      if (this.isOpen) {
        this.isOpen = false;
        this.searchQuery = '';
        this.onTouched();
        this.cdr.markForCheck();
      }
    }
  }

  // Keyboard: Escape closes
  @HostListener('keydown.escape')
  onEscape(): void {
    this.isOpen = false;
    this.searchQuery = '';
    this.cdr.markForCheck();
  }
}
