import {
  Component, Input, Output, EventEmitter, HostListener,
  ElementRef, ChangeDetectorRef, ChangeDetectionStrategy,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ZbIconComponent } from '@app/shared/components/zb-icon/zb-icon.component';

export interface ZbColumnDef {
  /** Identificador de la columna usado por la tabla (p.ej. 'cd_role'). */
  id: string;
  /** Etiqueta legible mostrada en el menú. */
  label: string;
  /** Si es true, la columna siempre se muestra y no se puede ocultar. */
  fixed?: boolean;
}

@Component({
  selector: 'zb-column-menu',
  standalone: true,
  imports: [CommonModule, ZbIconComponent],
  templateUrl: './zb-column-menu.component.html',
  styleUrl: './zb-column-menu.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ZbColumnMenuComponent {
  /** Lista COMPLETA de columnas candidatas (incluidas las fijas). */
  @Input() columns: ZbColumnDef[] = [];
  /** Ids de columnas visibles actualmente (excluyendo las fijas). */
  @Input() visibleKeys: string[] = [];
  @Input() label = 'Columnas';
  @Input() menuTitle = 'Mostrar columnas';
  @Input() showReset = true;

  @Output() visibleKeysChange = new EventEmitter<string[]>();
  @Output() reset = new EventEmitter<void>();

  isOpen = false;

  constructor(private el: ElementRef, private cdr: ChangeDetectorRef) {}

  get toggleableColumns(): ZbColumnDef[] {
    return this.columns.filter(c => !c.fixed);
  }

  isVisible(id: string): boolean {
    return this.visibleKeys.includes(id);
  }

  toggle(): void {
    this.isOpen = !this.isOpen;
    this.cdr.markForCheck();
  }

  toggleColumn(col: ZbColumnDef): void {
    if (col.fixed) return;
    const set = new Set(this.visibleKeys);
    set.has(col.id) ? set.delete(col.id) : set.add(col.id);
    // Reconstruye preservando el orden de declaración de las columnas.
    const next = this.toggleableColumns.filter(c => set.has(c.id)).map(c => c.id);
    this.visibleKeysChange.emit(next);
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
