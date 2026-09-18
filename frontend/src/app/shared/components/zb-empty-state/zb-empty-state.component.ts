import { Component, Input, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { SafeHtml } from '@angular/platform-browser';

/** Glifos disponibles para la ilustración de empty state (Figma 2138:7849).
 *  Cada valor es un fichero en `public/icons/empty-states/`. */
export type EmptyStateIllustration = 'person_outline' | 'schedule' | 'store';

@Component({
  selector: 'zb-empty-state',
  standalone: true,
  imports: [CommonModule, MatIconModule],
  templateUrl: './zb-empty-state.component.html',
  styleUrl: './zb-empty-state.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ZbEmptyStateComponent {
  /** Nombre del ligature de Material Icons (p.ej. 'person_add', 'inbox'). */
  @Input() icon = 'inbox';
  @Input() title = '';
  @Input() subtitle = '';
  /** Escape hatch: SVG inline (DomSanitizer) que reemplaza al ligature si se proporciona. */
  @Input() iconSvg?: SafeHtml;
  /**
   * Ilustración de Figma (2138:7849) en vez del icono en círculo: caja de
   * 200×200 con blob + glifo + "ring" con el plus. El valor es el glifo
   * central y se corresponde con `public/icons/empty-states/<valor>.svg`.
   * Al usarla se ignoran `icon`/`iconSvg`.
   */
  @Input() illustration?: EmptyStateIllustration;
}
