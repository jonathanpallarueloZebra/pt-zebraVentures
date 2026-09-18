import { Component, signal } from '@angular/core';
import { ZbPageHeaderComponent } from '@app/shared/components/zb-page-header/zb-page-header.component';
import { ClosedDaysConfigComponent } from '@app/admin-panel/sections/closed-days-config/closed-days-config.component';

/**
 * Página de cliente "Días de cierre" (panel de cliente, ruta /closed-days,
 * protegida por staffGuard). Reutiliza el MISMO componente de gestión que
 * adminZebra (`app-closed-days-config`) — el CRUD vive en un único sitio, no se
 * duplica. Aquí solo se aporta la cabecera de página del cliente.
 */
@Component({
  selector: 'app-closed-days-page',
  standalone: true,
  imports: [ZbPageHeaderComponent, ClosedDaysConfigComponent],
  template: `
    <zb-page-header
      [title]="'Días de cierre'"
      [subtitle]="count() + (count() === 1 ? ' día gestionado' : ' días gestionados')"
      [showSidebarToggle]="true"
      [sidebarCollapsed]="false"></zb-page-header>
    <div class="page-container">
      <app-closed-days-config (countChange)="count.set($event)"></app-closed-days-config>
    </div>
  `,
})
export class ClosedDaysPageComponent {
  count = signal(0);
}
