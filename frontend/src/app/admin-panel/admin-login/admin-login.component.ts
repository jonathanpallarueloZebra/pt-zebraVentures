import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { AuthService } from '@app/auth/services/auth.service';

@Component({
  selector: 'app-admin-login',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatCardModule, MatFormFieldModule, MatInputModule,
    MatButtonModule, MatIconModule,
  ],
  template: `
    <div class="admin-login-container">
      <mat-card class="admin-login-card">
        <mat-card-header>
          <mat-icon class="admin-icon">admin_panel_settings</mat-icon>
          <mat-card-title>Panel de Administracion</mat-card-title>
          <mat-card-subtitle>Acceso exclusivo para configuracion interna</mat-card-subtitle>
        </mat-card-header>

        <mat-card-content>
          @if (error()) {
            <div class="error-banner">
              <mat-icon>error</mat-icon>
              {{ error() }}
            </div>
          }

          <form (ngSubmit)="onSubmit()">
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Email</mat-label>
              <input matInput type="email" [(ngModel)]="email" name="email" required>
              <mat-icon matPrefix>email</mat-icon>
            </mat-form-field>

            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Contraseña</mat-label>
              <input matInput [type]="hidePassword ? 'password' : 'text'"
                [(ngModel)]="password" name="password" required>
              <mat-icon matPrefix>lock</mat-icon>
              <button mat-icon-button matSuffix type="button" (click)="hidePassword = !hidePassword">
                <mat-icon>{{ hidePassword ? 'visibility' : 'visibility_off' }}</mat-icon>
              </button>
            </mat-form-field>

            <button mat-flat-button color="primary" type="submit"
              class="full-width login-btn" [disabled]="loading()">
              @if (loading()) {
                Verificando...
              } @else {
                Acceder
              }
            </button>
          </form>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .admin-login-container {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%);
    }
    .admin-login-card {
      width: 100%;
      max-width: 420px;
      padding: 2rem;
    }
    mat-card-header {
      display: flex;
      flex-direction: column;
      align-items: center;
      margin-bottom: 1.5rem;
    }
    .admin-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: #6366f1;
      margin-bottom: 0.5rem;
    }
    mat-card-title { font-size: 1.3rem !important; text-align: center; }
    mat-card-subtitle { text-align: center; }
    .full-width { width: 100%; }
    .login-btn { height: 48px; font-size: 1rem; margin-top: 0.5rem; }
    .error-banner {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
      background: #fef2f2;
      border: 1px solid #fecaca;
      color: #dc2626;
      border-radius: 8px;
      margin-bottom: 1rem;
      font-size: 0.875rem;
    }
    .error-banner mat-icon { font-size: 20px; width: 20px; height: 20px; }
  `],
})
export class AdminLoginComponent {
  email = '';
  password = '';
  hidePassword = true;
  error = signal('');
  loading = signal(false);

  constructor(private authService: AuthService, private router: Router) {}

  onSubmit(): void {
    this.loading.set(true);
    this.error.set('');

    this.authService.login(this.email, this.password).subscribe({
      next: () => {
        // Now verify the user is superuser
        this.authService.getProfile().subscribe({
          next: user => {
            if (user.is_superuser) {
              this.router.navigate(['/adminzebra']);
            } else {
              this.error.set('No tienes permisos de administrador.');
              this.loading.set(false);
            }
          },
          error: () => {
            this.error.set('Error al verificar permisos.');
            this.loading.set(false);
          },
        });
      },
      error: () => {
        this.error.set('Credenciales incorrectas.');
        this.loading.set(false);
      },
    });
  }
}
