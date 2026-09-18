import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { map, catchError, of } from 'rxjs';

export const superAdminGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (!authService.getAccessToken()) {
    router.navigate(['/adminzebra/login']);
    return false;
  }

  // If we already have the user loaded, check immediately
  const user = authService.currentUser();
  if (user) {
    if (user.is_superuser) return true;
    router.navigate(['/adminzebra/login']);
    return false;
  }

  // Otherwise fetch profile and check
  return authService.getProfile().pipe(
    map(u => {
      if (u.is_superuser) return true;
      router.navigate(['/adminzebra/login']);
      return false;
    }),
    catchError(() => {
      router.navigate(['/adminzebra/login']);
      return of(false);
    }),
  );
};
