import {
  Component, Input, Output, EventEmitter, HostListener,
  ChangeDetectionStrategy, effect, model,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ZbButtonComponent } from '../zb-button/zb-button.component';

// Footer action layouts (matches Figma "_sidepanel-actions"):
//   create → Cancelar + Guardar
//   edit   → Eliminar (izq) + Cancelar + Guardar
//   view   → Editar (única acción)
export type ZbSidepanelMode = 'create' | 'edit' | 'view';

@Component({
  selector: 'zb-sidepanel',
  standalone: true,
  imports: [CommonModule, ZbButtonComponent],
  templateUrl: './zb-sidepanel.component.html',
  styleUrl: './zb-sidepanel.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ZbSidepanelComponent {
  /** Estado abierto/cerrado — soporta two-way: [open]/(openChange) o [(open)] con una propiedad. */
  open = model<boolean>(false);

  @Input() title = '';
  @Input() mode: ZbSidepanelMode = 'create';
  @Input() width = '600px';

  @Input() saveLabel = 'Guardar';
  @Input() cancelLabel = 'Cancelar';
  @Input() deleteLabel = 'Eliminar';
  @Input() editLabel = 'Editar';

  @Input() saving = false;
  @Input() saveDisabled = false;
  /** Oculta el botón Eliminar del pie en `mode="edit"`. Para registros que no se
   *  pueden borrar (p.ej. una restricción original, que solo se desactiva): un
   *  botón que al pulsarlo solo avisa de que no se puede es peor que no tenerlo. */
  @Input() showDelete = true;
  @Input() showClose = true;
  @Input() closeOnScrim = true;
  @Input() closeOnEscape = true;
  /** When true, close() is a no-op — use to block closing while confirming unsaved changes. */
  @Input() preventClose = false;

  @Output() save = new EventEmitter<void>();
  @Output() cancel = new EventEmitter<void>();
  @Output() delete = new EventEmitter<void>();
  @Output() edit = new EventEmitter<void>();
  /** Se emite tras cualquier cierre (scrim / Escape / X / Cancelar). */
  @Output() closed = new EventEmitter<void>();

  constructor() {
    // Bloquea el scroll del body mientras el panel está abierto.
    effect((onCleanup) => {
      const isOpen = this.open();
      if (typeof document === 'undefined') return;
      document.body.style.overflow = isOpen ? 'hidden' : '';
      onCleanup(() => { document.body.style.overflow = ''; });
    });
  }

  close(): void {
    if (!this.open() || this.preventClose) return;
    this.open.set(false);
    this.closed.emit();
  }

  onScrim(): void {
    if (this.closeOnScrim) this.close();
  }

  onCancel(): void {
    this.cancel.emit();
    this.close();
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.open() && this.closeOnEscape) this.close();
  }
}
