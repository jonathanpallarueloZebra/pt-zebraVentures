import { Component, OnInit, computed, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatMenuModule } from '@angular/material/menu';
import { MatBadgeModule } from '@angular/material/badge';
import { MatTooltipModule } from '@angular/material/tooltip';
import { SidebarService } from '@app/shared/services/sidebar.service';
import { ThemeService } from '@app/shared/services/theme.service';
import { AuthService } from '@app/auth/services/auth.service';
import { BrandingService } from '@app/shared/services/branding.service';
import { AbsenceService } from '@app/shared/services/absence.service';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [
    CommonModule, RouterLink,
    MatToolbarModule, MatIconModule, MatButtonModule,
    MatMenuModule, MatBadgeModule, MatTooltipModule,
  ],
  templateUrl: './navbar.component.html',
  styleUrl: './navbar.component.scss',
})
export class NavbarComponent implements OnInit {
  sidebar = inject(SidebarService);
  themeService = inject(ThemeService);
  authService = inject(AuthService);
  brandingService = inject(BrandingService);
  private absenceService = inject(AbsenceService);
  private router = inject(Router);

  isStaff = computed(() => !!this.authService.currentUser()?.is_staff);
  pendingCount = signal(0);

  ngOnInit(): void {
    this.authService.getProfile().subscribe(() => {
      if (this.isStaff()) {
        this.loadPendingCount();
      }
    });
  }

  loadPendingCount(): void {
    this.absenceService.getRequests({ status: 'pending' }).subscribe(list => {
      this.pendingCount.set(list.length);
    });
  }

  goToAbsences(): void {
    this.router.navigate(['/absences']);
  }

  onLogout(): void {
    this.authService.logout();
  }
}
