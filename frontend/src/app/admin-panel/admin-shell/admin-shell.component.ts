import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTooltipModule } from '@angular/material/tooltip';
import { AuthService } from '@app/auth/services/auth.service';
import { BrandingConfigComponent } from '../sections/branding-config/branding-config.component';
import { CatalogConfigComponent } from '../sections/catalog-config/catalog-config.component';
import { RestrictionsConfigComponent } from '../sections/restrictions-config/restrictions-config.component';
import { EntitiesConfigComponent } from '../sections/entities-config/entities-config.component';
import { AssignmentsConfigComponent } from '../sections/assignments-config/assignments-config.component';
import { ClosedDaysConfigComponent } from '../sections/closed-days-config/closed-days-config.component';

@Component({
  selector: 'app-admin-shell',
  standalone: true,
  imports: [
    CommonModule,
    MatToolbarModule, MatButtonModule, MatIconModule,
    MatTabsModule, MatTooltipModule,
    BrandingConfigComponent, CatalogConfigComponent, RestrictionsConfigComponent, EntitiesConfigComponent,
    AssignmentsConfigComponent, ClosedDaysConfigComponent,
  ],
  template: `
    <div class="admin-layout">
      <mat-toolbar class="admin-toolbar">
        <mat-icon class="toolbar-icon">admin_panel_settings</mat-icon>
        <span class="toolbar-title">Panel Interno</span>
        <span class="spacer"></span>
        <span class="user-label">{{ authService.currentUser()?.email }}</span>
        <button mat-icon-button matTooltip="Ir a la app" (click)="goToApp()">
          <mat-icon>open_in_new</mat-icon>
        </button>
        <button mat-icon-button matTooltip="Cerrar sesion" (click)="logout()">
          <mat-icon>logout</mat-icon>
        </button>
      </mat-toolbar>

      <div class="admin-content">
        <mat-tab-group animationDuration="200ms" (selectedIndexChange)="activeTab.set($event)">
          <mat-tab>
            <ng-template mat-tab-label>
              <mat-icon class="tab-icon">palette</mat-icon> Marca
            </ng-template>
            <div class="tab-body">
              <app-branding-config />
            </div>
          </mat-tab>
          <mat-tab>
            <ng-template mat-tab-label>
              <mat-icon class="tab-icon">tune</mat-icon> Catalogo
            </ng-template>
            <div class="tab-body">
              <app-catalog-config />
            </div>
          </mat-tab>
          <mat-tab>
            <ng-template mat-tab-label>
              <mat-icon class="tab-icon">swap_horiz</mat-icon> Asignaciones
            </ng-template>
            <div class="tab-body">
              <app-assignments-config />
            </div>
          </mat-tab>
          <mat-tab>
            <ng-template mat-tab-label>
              <mat-icon class="tab-icon">gavel</mat-icon> Restricciones
            </ng-template>
            <div class="tab-body">
              <app-restrictions-config />
            </div>
          </mat-tab>
          <mat-tab>
            <ng-template mat-tab-label>
              <mat-icon class="tab-icon">dashboard_customize</mat-icon> Entidades
            </ng-template>
            <div class="tab-body">
              <app-entities-config />
            </div>
          </mat-tab>
          <mat-tab>
            <ng-template mat-tab-label>
              <mat-icon class="tab-icon">event_busy</mat-icon> Días de cierre
            </ng-template>
            <div class="tab-body">
              <app-closed-days-config />
            </div>
          </mat-tab>
        </mat-tab-group>
      </div>
    </div>
  `,
  styles: [`
    .admin-layout {
      min-height: 100vh;
      background: #f8fafc;
    }
    .admin-toolbar {
      background: #1e1b4b;
      color: white;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .toolbar-icon {
      margin-right: 8px;
    }
    .toolbar-title {
      font-weight: 600;
      font-size: 1.1rem;
    }
    .spacer { flex: 1; }
    .user-label {
      font-size: 0.85rem;
      opacity: 0.85;
      margin-right: 8px;
    }
    .admin-content {
      margin: 0 auto;
      padding: 24px;
    }
    .tab-body {
      padding: 24px 0;
    }
    .tab-icon {
      margin-right: 6px;
      font-size: 20px;
      width: 20px;
      height: 20px;
    }
  `],
})
export class AdminShellComponent {
  activeTab = signal(0);

  constructor(public authService: AuthService, private router: Router) {
    // Ensure we have user profile data
    if (!this.authService.currentUser()) {
      this.authService.getProfile().subscribe();
    }
  }

  goToApp(): void {
    this.router.navigate(['/dashboard']);
  }

  logout(): void {
    this.authService.logout();
    this.router.navigate(['/adminzebra/login']);
  }
}
