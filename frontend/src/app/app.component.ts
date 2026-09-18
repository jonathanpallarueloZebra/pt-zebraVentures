import { Component, OnInit, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { BrandingService } from '@app/shared/services/branding.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: '<router-outlet />',
})
export class AppComponent implements OnInit {
  private brandingService = inject(BrandingService);

  ngOnInit(): void {
    // Se carga aqui (y no en el shell) para que las pantallas de auth, que
    // quedan fuera del shell, tengan tambien el logo/colores de la marca.
    // El endpoint GET /api/branding/ es publico, no requiere sesion.
    this.brandingService.load();
  }
}
