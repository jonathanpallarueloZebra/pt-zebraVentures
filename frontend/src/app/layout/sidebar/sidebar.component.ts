import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { SidebarService } from '@app/shared/services/sidebar.service';
import { AuthService } from '@app/auth/services/auth.service';
import { BrandingService } from '@app/shared/services/branding.service';
import { EntityTypeService } from '@app/shared/services/entity-type.service';
import { EntityTypeDef } from '@app/shared/interfaces/entity-field.interface';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, MatIconModule, MatListModule],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss',
})
export class SidebarComponent implements OnInit {
  sidebar         = inject(SidebarService);
  brandingService = inject(BrandingService);
  private authService      = inject(AuthService);
  private entityTypeService = inject(EntityTypeService);

  isStaff = computed(() => !!this.authService.currentUser()?.is_staff);

  /** Todos los EntityType del backend (para leer icon de worker/shift y las entidades EAV) */
  private allEntityTypes = signal<EntityTypeDef[]>([]);

  readonly fixedTopItems = [
    { icon: 'home',           label: 'Inicio',        route: '/dashboard' },
    { icon: 'calendar_month', label: 'Planificador',  route: '/schedule' },
    { icon: 'rule',           label: 'Restricciones', route: '/restrictions' },
    { icon: 'event_busy',     label: 'Ausencias',     route: '/absences' },
  ];

  /** Configuración: Empleados + Turnos + entidades EAV con show_in_sidebar.
   *  Los hijos de Configuración van SIN icono (solo texto): así todas las
   *  anclas del submenú se ven coherentes (icon:'' → el HTML no pinta icono). */
  configChildren = computed(() => {
    const all = this.allEntityTypes();
    return [
      { label: 'Empleados', route: '/employees',      icon: '' },
      { label: 'Turnos',    route: '/entities/shift', icon: '' },
      ...all
        .filter(t => t.show_in_sidebar && t.slug !== 'worker' && t.slug !== 'shift')
        .map(t => ({ label: t.name, route: `/entities/${t.slug}`, icon: '' })),
      // Días de cierre: gestión trasladada de adminZebra al panel de cliente.
      { label: 'Días de cierre', route: '/closed-days', icon: '' },
    ];
  });

  readonly employeeItems = [
    { icon: 'dashboard', label: 'Mi Panel', route: '/dashboard' },
    { icon: 'person', label: 'Mi perfil', route: '/profile' },
  ];

  expandedGroup: string | null = 'Configuración';

  ngOnInit(): void {
    this.entityTypeService.getAll().subscribe({
      next: types => this.allEntityTypes.set(types),
      error: () => {},
    });
  }

  toggleGroup(label: string): void {
    this.expandedGroup = this.expandedGroup === label ? null : label;
  }

  onNavigate(): void {
    this.sidebar.closeMobile();
  }

  onLogout(): void {
    this.authService.logout();
  }
}
