import { Component, OnInit, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ZbSkeletonComponent } from '@app/shared/components/zb-skeleton/zb-skeleton.component';
import { AuthService } from '@app/auth/services/auth.service';
import { ThemeService } from '@app/shared/services/theme.service';
import { ZbPageHeaderComponent } from '@app/shared/components/zb-page-header/zb-page-header.component';
import { ZbInputComponent } from '@app/shared/components/zb-input/zb-input.component';
import { ZbButtonComponent } from '@app/shared/components/zb-button/zb-button.component';
import { ZbToggleComponent } from '@app/shared/components/zb-toggle/zb-toggle.component';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    ZbSkeletonComponent,
    ZbPageHeaderComponent, ZbInputComponent, ZbButtonComponent, ZbToggleComponent,
  ],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss',
})
export class ProfileComponent implements OnInit {
  themeService = inject(ThemeService);
  loading = signal(true);
  saving = signal(false);
  changingPassword = signal(false);
  showPasswordForm = false;
  profile = { email: '', username: '', first_name: '', last_name: '' };
  passwordForm = { old_password: '', new_password: '', new_password_confirm: '' };
  message = '';
  error = '';
  hideOldPassword = true;
  hideNewPassword = true;
  hideConfirmPassword = true;

  constructor(private authService: AuthService) {}

  ngOnInit(): void {
    this.authService.getProfile().subscribe({
      next: user => {
        this.profile = {
          email: user.email,
          username: user.username,
          first_name: user.first_name,
          last_name: user.last_name,
        };
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  saveProfile(): void {
    this.saving.set(true);
    this.message = '';
    this.error = '';
    this.authService.updateProfile(this.profile).subscribe({
      next: () => {
        this.message = 'Perfil actualizado correctamente.';
        this.saving.set(false);
      },
      error: () => {
        this.error = 'Error al guardar perfil.';
        this.saving.set(false);
      },
    });
  }

  changePassword(): void {
    this.changingPassword.set(true);
    this.message = '';
    this.error = '';
    this.authService.changePassword(this.passwordForm).subscribe({
      next: () => {
        this.message = 'Contraseña actualizada correctamente.';
        this.showPasswordForm = false;
        this.passwordForm = { old_password: '', new_password: '', new_password_confirm: '' };
        this.changingPassword.set(false);
      },
      error: (err) => {
        const body = err.error;
        if (body && typeof body === 'object') {
          const msgs: string[] = [];
          for (const key of Object.keys(body)) {
            const val = body[key];
            if (Array.isArray(val)) {
              msgs.push(...val);
            } else if (typeof val === 'string') {
              msgs.push(val);
            }
          }
          this.error = msgs.length ? msgs.join(' ') : 'Error al cambiar contraseña.';
        } else {
          this.error = 'Error al cambiar contraseña.';
        }
        this.changingPassword.set(false);
      },
    });
  }
}
