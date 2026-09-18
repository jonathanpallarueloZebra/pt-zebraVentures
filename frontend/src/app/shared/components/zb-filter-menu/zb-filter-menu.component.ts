import {
  Component, Input, Output, EventEmitter, HostListener,
  ElementRef, ChangeDetectorRef, ChangeDetectionStrategy,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ZbSelectComponent, ZbSelectOption } from '@app/shared/components/zb-select/zb-select.component';
import { ZbIconComponent } from '@app/shared/components/zb-icon/zb-icon.component';

/** Un filtro del menú: su clave, etiqueta y opciones del desplegable. */
export interface ZbFilterDef {
  key: string;
  label: string;
  options: ZbSelectOption[];
}

/**
 * Menú de FILTROS del toolbar (mismo patrón/estilos que zb-column-menu):
 * un botón "Filtros ▾" con contador de filtros activos que abre un panel con
 * los selects dentro. Mantiene el toolbar compacto (Mostrar · Columnas ·
 * Filtros + botones) en vez de tener N selects sueltos que descuadran.
 *
 * `values` es un mapa {key: valor|null}. Emite `valuesChange` al cambiar uno y
 * `reset` al limpiar todos.
 */
@Component({
  selector: 'zb-filter-menu',
  standalone: true,
  imports: [CommonModule, FormsModule, ZbSelectComponent, ZbIconComponent],
  templateUrl: './zb-filter-menu.component.html',
  styleUrl: './zb-filter-menu.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ZbFilterMenuComponent {
  @Input() filters: ZbFilterDef[] = [];
  /** Mapa de valores activos por clave (null/'' = sin filtrar). */
  @Input() values: Record<string, string | number | null> = {};
  @Input() label = 'Filtros';
  @Input() menuTitle = 'Filtrar por';

  /**
   * Claves que NO cuentan para el contador del botón ni habilitan "Limpiar".
   * Para filtros que siempre tienen valor (p.ej. Estado activos/inactivos en
   * empleados): sin esto el botón mostraría un "1" permanente que hace pensar
   * que hay un filtro puesto cuando es el estado por defecto.
   */
  @Input() uncountedKeys: string[] = [];

  @Output() valuesChange = new EventEmitter<Record<string, string | number | null>>();
  @Output() reset = new EventEmitter<void>();

  isOpen = false;

  constructor(private el: ElementRef, private cdr: ChangeDetectorRef) {}

  /** Nº de filtros con valor (para el contador del botón), sin contar los de
   *  `uncountedKeys`. */
  get activeCount(): number {
    return Object.entries(this.values)
      .filter(([k]) => !this.uncountedKeys.includes(k))
      .filter(([, v]) => v !== null && v !== '' && v !== undefined)
      .length;
  }

  valueOf(key: string): string | number | null {
    const v = this.values[key];
    return v === undefined ? null : v;
  }

  toggle(): void {
    this.isOpen = !this.isOpen;
    this.cdr.markForCheck();
  }

  onFilterChange(key: string, value: string | number | null): void {
    this.valuesChange.emit({ ...this.values, [key]: value });
  }

  onReset(): void {
    this.reset.emit();
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (this.isOpen && !this.el.nativeElement.contains(event.target)) {
      this.isOpen = false;
      this.cdr.markForCheck();
    }
  }

  @HostListener('keydown.escape')
  onEscape(): void {
    if (this.isOpen) {
      this.isOpen = false;
      this.cdr.markForCheck();
    }
  }
}
