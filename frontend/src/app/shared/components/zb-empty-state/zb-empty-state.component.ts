import { Component, Input, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { SafeHtml } from '@angular/platform-browser';

/** Glifos disponibles para la ilustración de empty state (Figma 2138:7849).
 *  Cada valor es un fichero en `public/icons/empty-states/`.
 *
 *  Son los ocho tipos del frame `empty-state_img` (2135:13386) del diseño:
 *  add-worker, add-schedule, add-work-center, add-role, add-zone, no-results,
 *  restriccion y work-break. Aquí se nombran por su glifo central, que es lo
 *  que cambia entre ellos. */
export type EmptyStateIllustration =
  | 'person_outline'  // add-worker
  | 'schedule'        // add-schedule
  | 'store'           // add-work-center
  | 'work'            // add-role
  | 'place'           // add-zone
  | 'rule'            // restriccion
  | 'search'          // no-results
  | 'event_busy';     // work-break

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
  /**
   * Oculta el «+» de la ilustración. En el diseño lo llevan todas salvo
   * `work-break`, que tiene esa capa oculta (2377:18241), y `no-results`, que
   * en su lugar muestra un aspa.
   */
  @Input() sinPlus = false;
}
