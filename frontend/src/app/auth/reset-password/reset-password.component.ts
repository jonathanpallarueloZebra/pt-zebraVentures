import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { AuthService } from '@app/auth/services/auth.service';

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, MatIconModule],
  templateUrl: './reset-password.component.html',
  styleUrl: './reset-password.component.scss',
})
export class ResetPasswordComponent implements OnInit {
  token = '';
  password = '';
  passwordConfirm = '';
  hidePassword = true;
  hideConfirm = true;
  loading = signal(false);
  success = signal(false);
  error = signal('');
  tokenValid = signal(false);
  validating = signal(true);

  constructor(private authService: AuthService, private route: ActivatedRoute, private router: Router) {}

  ngOnInit(): void {
    this.token = this.route.snapshot.queryParamMap.get('token') || '';
    if (!this.token) {
      this.error.set('Token no proporcionado.');
      this.validating.set(false);
      return;
    }
    this.authService.validateToken(this.token).subscribe({
      next: (res) => {
        this.tokenValid.set(res.valid);
        if (!res.valid) this.error.set('Token inválido o expirado.');
        this.validating.set(false);
      },
      error: () => {
        this.error.set('Error al validar token.');
        this.validating.set(false);
      },
    });
  }

  onSubmit(): void {
    if (this.password !== this.passwordConfirm) {
      this.error.set('Las contraseñas no coinciden.');
      return;
    }
    this.loading.set(true);
    this.error.set('');
    this.authService.resetPassword(this.token, this.password, this.passwordConfirm).subscribe({
      next: () => {
        this.success.set(true);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.error || 'Error al restablecer contraseña.');
        this.loading.set(false);
      },
    });
  }
}
