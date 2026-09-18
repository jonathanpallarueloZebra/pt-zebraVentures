import { Component } from '@angular/core';
import { CatalogComponent } from '@app/pages/catalog/catalog.component';

@Component({
  selector: 'app-catalog-config',
  standalone: true,
  imports: [CatalogComponent],
  template: `
    <div class="section">
      <h2 class="section-title">Configuracion del Catalogo</h2>
      <p class="section-desc">
        Gestiona los valores que definen el comportamiento del sistema: <strong>zonas geograficas</strong>,
        <strong>tiendas</strong>, tipos de contrato, tipos de jornada, franjas horarias, etc.
        Los cambios aqui se reflejan automaticamente en el panel de administracion.
      </p>
      <app-catalog />
    </div>
  `,
  styles: [`
    .section-title { font-size: 1.4rem; font-weight: 700; margin: 0 0 4px; }
    .section-desc { color: #6b7280; margin: 0 0 16px; }
  `],
})
export class CatalogConfigComponent {}
