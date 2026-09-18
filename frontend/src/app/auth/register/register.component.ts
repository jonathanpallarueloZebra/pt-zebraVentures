import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, MatIconModule],
  templateUrl: './register.component.html',
  styleUrl: './register.component.scss',
})
export class RegisterComponent {
  email = '';
  username = '';
  password = '';
  passwordConfirm = '';
  hidePassword = true;
  hideConfirm = true;
  error = signal('');
  loading = signal(false);

  constructor(private authService: AuthService, private router: Router) {}

  onSubmit(): void {
    if (this.password !== this.passwordConfirm) {
      this.error.set('Las contraseñas no coinciden.');
      return;
    }

    this.loading.set(true);
    this.error.set('');

    this.authService.register({
      email: this.email,
      username: this.username,
      password: this.password,
      password_confirm: this.passwordConfirm,
    }).subscribe({
      next: () => this.router.navigate(['/login']),
      error: () => {
        this.error.set('Error al registrar. Inténtalo de nuevo.');
        this.loading.set(false);
      },
    });
  }
}
