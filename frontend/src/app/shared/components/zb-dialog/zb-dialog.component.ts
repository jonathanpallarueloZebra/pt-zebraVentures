import {
  Component, Input, Output, EventEmitter, ChangeDetectionStrategy,
  effect, model, HostListener,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { ZbButtonComponent, ZbButtonVariant } from '../zb-button/zb-button.component';

export type ZbDialogMode = 'default' | 'danger' | 'warning' | 'info';

@Component({
  selector: 'zb-dialog',
  standalone: true,
  imports: [CommonModule, MatIconModule, ZbButtonComponent],
  templateUrl: './zb-dialog.component.html',
  styleUrl: './zb-dialog.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ZbDialogComponent {
  /** Two-way open state — use [(open)]="flag" or [open]/(openChange). */
  open = model<boolean>(false);

  @Input() title        = '';
  @Input() message      = '';
  /** When true, message is rendered as innerHTML instead of text. Only use with trusted strings. */
  @Input() html         = false;
  @Input() mode: ZbDialogMode = 'default';
  @Input() confirmLabel = 'Confirmar';
  @Input() cancelLabel  = 'Cancelar';
  @Input() saving       = false;

  @Output() confirm = new EventEmitter<void>();
  @Output() cancel  = new EventEmitter<void>();
  @Output() closed  = new EventEmitter<void>();

  constructor() {
    effect((onCleanup) => {
      const isOpen = this.open();
      if (typeof document === 'undefined') return;
      document.body.style.overflow = isOpen ? 'hidden' : '';
      onCleanup(() => { document.body.style.overflow = ''; });
    });
  }

  @HostListener('document:keydown.escape')
  onEscape(): void { if (this.open()) this.onCancel(); }

  // 'info' va alineado a la izquierda como 'default': sin icono, el título
  // centrado quedaba descolgado, y su contenido son listas (se leen mejor a la
  // izquierda). Los modos con icono (danger/warning) sí van centrados.
  get isCentered(): boolean {
    return this.mode !== 'default' && this.mode !== 'info';
  }

  get iconName(): string {
    if (this.mode === 'danger')  return 'error';
    if (this.mode === 'warning') return 'warning';
    // 'info' NO lleva icono: es un aviso informativo (p.ej. "secciones sin
    // personal") y el icono le daba un peso visual de alerta que no le toca.
    return '';
  }

  get confirmVariant(): ZbButtonVariant {
    return this.mode === 'danger' ? 'danger' : 'primary';
  }

  onConfirm(): void { this.confirm.emit(); }

  onCancel(): void {
    this.cancel.emit();
    this.open.set(false);
    this.closed.emit();
  }
}
