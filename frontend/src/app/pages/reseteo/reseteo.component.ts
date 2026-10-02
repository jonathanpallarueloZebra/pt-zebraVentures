import { Component, inject, signal, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { MatIconModule } from '@angular/material/icon';

import { environment } from '../../../environments/environment';

/**
 * Pantalla de reseteo de la demo.
 *
 * Marketing ensena el planificador a clientes y durante la sesion se tocan
 * datos. Desde aqui se devuelve la base a su estado de partida sin entrar al
 * servidor, con la planificacion de las dos semanas ya resuelta y sin huecos.
 *
 * El mismo reseteo corre solo cada dos dias por cron; esto es para cuando no
 * se puede esperar.
 */
@Component({
  selector: 'zb-reseteo',
  standalone: true,
  imports: [CommonModule, MatIconModule],
  templateUrl: './reseteo.component.html',
  styleUrl: './reseteo.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ReseteoComponent {
  private http = inject(HttpClient);

  /** Mientras corre, el boton se bloquea: el reseteo tarda unos segundos. */
  cargando = signal(false);
  /** Primera pulsacion pide confirmacion; la segunda ejecuta. */
  confirmando = signal(false);
  resultado = signal<{ ok: boolean; texto: string } | null>(null);

  pedirConfirmacion(): void {
    this.resultado.set(null);
    this.confirmando.set(true);
  }

  cancelar(): void {
    this.confirmando.set(false);
  }

  resetear(): void {
    this.confirmando.set(false);
    this.cargando.set(true);
    this.resultado.set(null);

    this.http.post<{ detail: string }>(`${environment.apiUrl}/core/resetear-demo/`, {})
      .subscribe({
        next: (r) => {
          this.cargando.set(false);
          this.resultado.set({ ok: true, texto: r.detail });
        },
        error: (e) => {
          this.cargando.set(false);
          this.resultado.set({
            ok: false,
            texto: e?.error?.detail ?? 'No se ha podido resetear la demo.',
          });
        },
      });
  }
}
