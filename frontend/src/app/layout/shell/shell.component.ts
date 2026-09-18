import { Component, OnInit, computed } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NavbarComponent } from '../navbar/navbar.component';
import { SidebarComponent } from '../sidebar/sidebar.component';
import { SidebarService } from '@app/shared/services/sidebar.service';
import { ThemeService } from '@app/shared/services/theme.service';
import { AuthService } from '@app/auth/services/auth.service';
import { NotificationToastComponent } from '@app/shared/components/notification-toast/notification-toast.component';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, NavbarComponent, SidebarComponent, NotificationToastComponent],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss',
})
export class ShellComponent implements OnInit {
  isStaff = computed(() => !!this.authService.currentUser()?.is_staff);

  constructor(
    public sidebar: SidebarService,
    private themeService: ThemeService,
    private authService: AuthService,
  ) {}

  ngOnInit(): void {
    this.themeService.init();
    if (!this.authService.currentUser()) {
      this.authService.getProfile().subscribe();
    }
  }
}
