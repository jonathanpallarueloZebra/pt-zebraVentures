import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';
import { environment } from '@env/environment';

interface AuthTokens {
  access: string;
  refresh: string;
}

interface User {
  id: number;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_superuser: boolean;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly apiUrl = `${environment.apiUrl}/auth`;
  private readonly ACCESS_KEY = 'access_token';
  private readonly REFRESH_KEY = 'refresh_token';

  private readonly USER_KEY = 'current_user';

  currentUser = signal<User | null>(this.loadUserFromStorage());
  isAuthenticated = computed(() => !!this.getAccessToken());
  isStaff = computed(() => !!this.currentUser()?.is_staff);

  private loadUserFromStorage(): User | null {
    try {
      const raw = sessionStorage.getItem(this.USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  }

  constructor(private http: HttpClient, private router: Router) {}

  login(email: string, password: string): Observable<AuthTokens> {
    return this.http.post<AuthTokens>(`${this.apiUrl}/login/`, { email, password }).pipe(
      tap(tokens => this.storeTokens(tokens))
    );
  }

  register(data: { email: string; username: string; password: string; password_confirm: string }): Observable<any> {
    return this.http.post(`${this.apiUrl}/register/`, data);
  }

  refreshToken(): Observable<AuthTokens> {
    const refresh = this.getRefreshToken();
    return this.http.post<AuthTokens>(`${this.apiUrl}/refresh/`, { refresh }).pipe(
      tap(tokens => this.storeTokens(tokens))
    );
  }

  logout(): void {
    localStorage.removeItem(this.ACCESS_KEY);
    localStorage.removeItem(this.REFRESH_KEY);
    sessionStorage.removeItem(this.USER_KEY);
    this.currentUser.set(null);
    this.router.navigate(['/login']);
  }

  getAccessToken(): string | null {
    return localStorage.getItem(this.ACCESS_KEY);
  }

  getRefreshToken(): string | null {
    return localStorage.getItem(this.REFRESH_KEY);
  }

  getProfile(): Observable<User> {
    return this.http.get<User>(`${this.apiUrl}/profile/`).pipe(
      tap(user => {
        this.currentUser.set(user);
        sessionStorage.setItem(this.USER_KEY, JSON.stringify(user));
      })
    );
  }

  updateProfile(data: Partial<User>): Observable<User> {
    return this.http.patch<User>(`${this.apiUrl}/profile/`, data).pipe(
      tap(user => this.currentUser.set(user))
    );
  }

  changePassword(data: { old_password: string; new_password: string; new_password_confirm: string }): Observable<any> {
    return this.http.post(`${this.apiUrl}/change-password/`, data);
  }

  forgotPassword(email: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/forgot-password/`, { email });
  }

  resetPassword(token: string, password: string, password_confirm: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/reset-password/`, { token, password, password_confirm });
  }

  setPassword(token: string, password: string, password_confirm: string): Observable<any> {
    return this.http.post(`${this.apiUrl}/set-password/`, { token, password, password_confirm });
  }

  validateToken(token: string): Observable<{ valid: boolean; purpose?: string; email?: string }> {
    return this.http.get<{ valid: boolean; purpose?: string; email?: string }>(`${this.apiUrl}/validate-token/?token=${token}`);
  }

  private storeTokens(tokens: AuthTokens): void {
    localStorage.setItem(this.ACCESS_KEY, tokens.access);
    localStorage.setItem(this.REFRESH_KEY, tokens.refresh);
  }
}
