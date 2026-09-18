"""
Generate all frontend files for planificador_turnos-client.
Run from the client root: python _generate_frontend.py
"""
import os

BASE = 'src'


def write_file(path, content):
    full = os.path.join(BASE, path) if not path.startswith(BASE) else path
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(content.lstrip('\n'))
    print(f'  OK: {full}')


# =============================================================================
# INDEX.HTML
# =============================================================================
write_file('../src/index.html', '''<!doctype html>
<html lang="es" data-theme="light">
<head>
  <meta charset="utf-8">
  <title>Planificador de Turnos</title>
  <base href="/">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/x-icon" href="favicon.ico">
  <link href="https://fonts.googleapis.com/css2?family=Red+Hat+Display:wght@300;400;500;600;700;800&family=Red+Hat+Text:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
</head>
<body>
  <app-root></app-root>
</body>
</html>
''')

# =============================================================================
# DESIGN TOKENS
# =============================================================================
write_file('styles/_tokens.scss', r'''// Design tokens - Brand primitives
// Change these to rebrand the entire app.

:root {
  // Brand
  --c-brand: #FCCF3F;
  --c-brand-dark: #D3A203;

  // Greys
  --c-grey-50: #FAFAFA;
  --c-grey-100: #F1F2F3;
  --c-grey-200: #D6D8DC;
  --c-grey-300: #B3B6BD;
  --c-grey-400: #9599A3;
  --c-grey-500: #767C89;
  --c-grey-600: #5C616A;
  --c-grey-700: #42454C;
  --c-grey-800: #27292E;
  --c-grey-900: #0D0E0F;

  // Purple (accent)
  --c-purple-50: #F5F3FF;
  --c-purple-100: #EDE9FE;
  --c-purple-200: #DDD6FE;
  --c-purple-300: #C4B5FD;
  --c-purple-400: #A78BFA;
  --c-purple-500: #8B5CF6;
  --c-purple-600: #7C3AED;
  --c-purple-700: #6D28D9;
  --c-purple-800: #5B21B6;
  --c-purple-900: #4C1D95;

  // Red (error)
  --c-red-50: #FEF2F2;
  --c-red-100: #FEE2E2;
  --c-red-200: #FECACA;
  --c-red-300: #FCA5A5;
  --c-red-400: #F87171;
  --c-red-500: #EF4444;
  --c-red-600: #DC2626;
  --c-red-700: #B91C1C;

  // Green (success)
  --c-green-50: #F0FDF4;
  --c-green-100: #DCFCE7;
  --c-green-300: #86EFAC;
  --c-green-500: #22C55E;
  --c-green-700: #15803D;

  // Blue (info)
  --c-blue-50: #EFF6FF;
  --c-blue-100: #DBEAFE;
  --c-blue-500: #3B82F6;
  --c-blue-700: #1D4ED8;

  // Typography
  --ff-display: 'Red Hat Display', sans-serif;
  --ff-body: 'Red Hat Text', sans-serif;
  --fw-light: 300;
  --fw-regular: 400;
  --fw-medium: 500;
  --fw-semibold: 600;
  --fw-bold: 700;
  --fw-extrabold: 800;
  --fs-12: 0.75rem;
  --fs-13: 0.8125rem;
  --fs-14: 0.875rem;
  --fs-16: 1rem;
  --fs-18: 1.125rem;
  --fs-20: 1.25rem;
  --fs-24: 1.5rem;
  --fs-28: 1.75rem;
  --fs-32: 2rem;
  --lh-paragraph: 1.5;
  --lh-title: 1.2;

  // Spacing
  --sp-xxs: 2px;
  --sp-xs: 4px;
  --sp-s: 8px;
  --sp-m: 16px;
  --sp-l: 24px;
  --sp-xl: 32px;
  --sp-2xl: 40px;
  --sp-3xl: 48px;

  // Radii
  --br-small: 4px;
  --br-default: 8px;
  --br-large: 12px;
  --br-rounded: 100px;

  // Shadows
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);

  // Transitions
  --transition-fast: 150ms ease;
  --transition-normal: 300ms ease;
  --transition-slow: 500ms ease;
}
''')

write_file('styles/_themes.scss', r'''// Semantic theme tokens for light and dark modes.
// Components must ONLY use these variables, never raw hex values.

[data-theme='light'] {
  --fondo-pagina: var(--c-grey-50);
  --fondo-header: #ffffff;
  --fondo-card: #ffffff;
  --fondo-sidebar: var(--c-grey-900);

  --texto-principal: var(--c-grey-900);
  --texto-secundario: var(--c-grey-600);
  --texto-desactivado: var(--c-grey-400);

  --borde-general: var(--c-grey-200);
  --borde-hover: var(--c-grey-300);

  --color-acento: var(--c-brand);
  --color-acento-dark: var(--c-brand-dark);
  --color-acento-texto: var(--c-grey-900);

  --input-fondo: #ffffff;
  --input-borde: var(--c-grey-200);
  --input-foco-borde: var(--c-blue-500);

  --sidebar-fondo: var(--c-grey-900);
  --sidebar-texto: var(--c-grey-300);
  --sidebar-texto-activo: #ffffff;
  --sidebar-item-hover: var(--c-grey-800);
  --sidebar-item-activo: var(--c-grey-700);
  --sidebar-borde: var(--c-grey-700);

  --color-error: var(--c-red-500);
  --color-exito: var(--c-green-500);
  --color-warning: var(--c-brand);
  --color-info: var(--c-blue-500);

  --color-error-bg: var(--c-red-50);
  --color-exito-bg: var(--c-green-50);
  --color-warning-bg: #FFFBEB;
  --color-info-bg: var(--c-blue-50);
}

[data-theme='dark'] {
  --fondo-pagina: var(--c-grey-900);
  --fondo-header: var(--c-grey-800);
  --fondo-card: var(--c-grey-800);
  --fondo-sidebar: #0A0A0B;

  --texto-principal: var(--c-grey-100);
  --texto-secundario: var(--c-grey-400);
  --texto-desactivado: var(--c-grey-600);

  --borde-general: var(--c-grey-700);
  --borde-hover: var(--c-grey-600);

  --color-acento: var(--c-brand);
  --color-acento-dark: var(--c-brand-dark);
  --color-acento-texto: var(--c-grey-900);

  --input-fondo: var(--c-grey-800);
  --input-borde: var(--c-grey-700);
  --input-foco-borde: var(--c-blue-500);

  --sidebar-fondo: #0A0A0B;
  --sidebar-texto: var(--c-grey-400);
  --sidebar-texto-activo: #ffffff;
  --sidebar-item-hover: var(--c-grey-800);
  --sidebar-item-activo: var(--c-grey-700);
  --sidebar-borde: var(--c-grey-800);

  --color-error: var(--c-red-400);
  --color-exito: var(--c-green-300);
  --color-warning: var(--c-brand);
  --color-info: var(--c-blue-500);

  --color-error-bg: rgba(239, 68, 68, 0.1);
  --color-exito-bg: rgba(34, 197, 94, 0.1);
  --color-warning-bg: rgba(252, 207, 63, 0.1);
  --color-info-bg: rgba(59, 130, 246, 0.1);
}
''')

# =============================================================================
# GLOBAL STYLES
# =============================================================================
write_file('styles.scss', r'''@use '@angular/material' as mat;
@import 'styles/tokens';
@import 'styles/themes';

// Angular Material custom theme
html {
  @include mat.theme((
    color: (
      theme-type: light,
      primary: mat.$yellow-palette,
      tertiary: mat.$violet-palette,
    ),
    typography: Red Hat Text,
    density: 0,
  ));
}

// -- Reset & base --

*,
*::before,
*::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html {
  font-size: 16px;
  scroll-behavior: smooth;
}

body {
  font-family: var(--ff-body);
  font-weight: var(--fw-regular);
  font-size: var(--fs-14);
  line-height: var(--lh-paragraph);
  color: var(--texto-principal);
  background-color: var(--fondo-pagina);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

h1, h2, h3, h4, h5, h6 {
  font-family: var(--ff-display);
  font-weight: var(--fw-bold);
  line-height: var(--lh-title);
  color: var(--texto-principal);
}

h1 { font-size: var(--fs-28); }
h2 { font-size: var(--fs-24); }
h3 { font-size: var(--fs-20); }
h4 { font-size: var(--fs-18); }

a {
  color: var(--color-acento-dark);
  text-decoration: none;
  transition: color var(--transition-fast);
}

a:hover {
  color: var(--color-acento);
}

// -- Utility classes --

.page-container {
  padding: var(--sp-l);
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-l);
  flex-wrap: wrap;
  gap: var(--sp-m);
}

.page-title {
  font-family: var(--ff-display);
  font-size: var(--fs-24);
  font-weight: var(--fw-bold);
}

.card-surface {
  background: var(--fondo-card);
  border: 1px solid var(--borde-general);
  border-radius: var(--br-default);
  padding: var(--sp-l);
  box-shadow: var(--shadow-sm);
}

.text-secondary {
  color: var(--texto-secundario);
}

.text-disabled {
  color: var(--texto-desactivado);
}

// -- Scrollbar --

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--c-grey-300);
  border-radius: var(--br-rounded);
}

::-webkit-scrollbar-thumb:hover {
  background: var(--c-grey-400);
}
''')

print('--- Styles done ---')

# =============================================================================
# INTERFACES
# =============================================================================
write_file('app/shared/interfaces/role.interface.ts', '''
export interface Role {
  id: number;
  name: string;
  description: string;
  active: boolean;
}
''')

write_file('app/shared/interfaces/worker.interface.ts', '''
export interface WorkerPreference {
  shift_type: 'morning' | 'afternoon' | 'night';
}

export interface Worker {
  id: number;
  name: string;
  role: number;
  role_name: string;
  active: boolean;
  preferredShifts: WorkerPreference[];
  user?: number | null;
}
''')

write_file('app/shared/interfaces/floor.interface.ts', '''
export interface Floor {
  id: number;
  name: string;
  short_name: string | null;
  description: string;
  order: number;
  active: boolean;
  required_role: number | null;
  required_role_name: string | null;
}
''')

write_file('app/shared/interfaces/shift.interface.ts', '''
export interface Shift {
  id: number;
  name: string;
  start_time: string;
  end_time: string;
  applicable_days: number[];
  active: boolean;
}
''')

write_file('app/shared/interfaces/restriction.interface.ts', '''
export interface Restriction {
  id: number;
  name: string;
  description: string;
  type: string;
  parameters: Record<string, any>;
  active: boolean;
}

export interface RestrictionViolation {
  restrictionId: number;
  restrictionName: string;
  message: string;
  severity: 'warning' | 'error';
  dayDate?: string;
  shift?: string;
}

export interface ValidationResult {
  isValid: boolean;
  violations: RestrictionViolation[];
}
''')

write_file('app/shared/interfaces/planning.interface.ts', '''
export interface ShiftAssignment {
  workerId: number;
  workerName: string;
  start: string;
  end: string;
  floors: string[];
}

export interface DayPlan {
  date: string;
  dayName: string;
  morning: ShiftAssignment[];
  afternoon: ShiftAssignment[];
  night: ShiftAssignment[];
  rest: number[];
}

export interface WeeklyPlan {
  start: string;
  plan: DayPlan[];
}
''')

write_file('app/shared/interfaces/rest-day.interface.ts', '''
export interface RestDay {
  id: number;
  workerId: number;
  worker_name: string;
  date: string;
  reason: string | null;
}
''')

write_file('app/shared/interfaces/absence.interface.ts', '''
export interface AbsenceType {
  id: number;
  name: string;
  requires_approval: boolean;
  active: boolean;
}

export interface AbsenceRequest {
  id: number;
  worker: number;
  worker_name: string;
  type: number;
  type_name: string;
  start_date: string;
  end_date: string;
  reason: string;
  status: 'pending' | 'approved' | 'rejected';
  reviewed_by: number | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  created_at: string;
}
''')

write_file('app/shared/interfaces/index.ts', '''
export * from './role.interface';
export * from './worker.interface';
export * from './floor.interface';
export * from './shift.interface';
export * from './restriction.interface';
export * from './planning.interface';
export * from './rest-day.interface';
export * from './absence.interface';
''')

print('--- Interfaces done ---')

# =============================================================================
# SERVICES
# =============================================================================
write_file('app/shared/services/role.service.ts', '''
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';
import { Role } from '../interfaces/role.interface';

@Injectable({ providedIn: 'root' })
export class RoleService {
  private readonly url = `${environment.apiUrl}/roles`;

  constructor(private http: HttpClient) {}

  getAll(): Observable<Role[]> {
    return this.http.get<Role[]>(`${this.url}/`);
  }

  getById(id: number): Observable<Role> {
    return this.http.get<Role>(`${this.url}/${id}/`);
  }

  create(data: Partial<Role>): Observable<Role> {
    return this.http.post<Role>(`${this.url}/`, data);
  }

  update(id: number, data: Partial<Role>): Observable<Role> {
    return this.http.put<Role>(`${this.url}/${id}/`, data);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`);
  }
}
''')

write_file('app/shared/services/worker.service.ts', '''
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';
import { Worker } from '../interfaces/worker.interface';

@Injectable({ providedIn: 'root' })
export class WorkerService {
  private readonly url = `${environment.apiUrl}/workers`;

  constructor(private http: HttpClient) {}

  getActive(): Observable<Worker[]> {
    return this.http.get<Worker[]>(`${this.url}/`);
  }

  getAll(): Observable<Worker[]> {
    return this.http.get<Worker[]>(`${this.url}/all/`);
  }

  getRoles(): Observable<string[]> {
    return this.http.get<string[]>(`${this.url}/roles/`);
  }

  getById(id: number): Observable<Worker> {
    return this.http.get<Worker>(`${this.url}/${id}/`);
  }

  create(data: any): Observable<Worker> {
    return this.http.post<Worker>(`${this.url}/`, data);
  }

  update(id: number, data: any): Observable<Worker> {
    return this.http.put<Worker>(`${this.url}/${id}/`, data);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`);
  }
}
''')

write_file('app/shared/services/floor.service.ts', '''
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';
import { Floor } from '../interfaces/floor.interface';

@Injectable({ providedIn: 'root' })
export class FloorService {
  private readonly url = `${environment.apiUrl}/floors`;

  constructor(private http: HttpClient) {}

  getAll(): Observable<Floor[]> {
    return this.http.get<Floor[]>(`${this.url}/`);
  }

  create(data: Partial<Floor>): Observable<Floor> {
    return this.http.post<Floor>(`${this.url}/`, data);
  }

  update(id: number, data: Partial<Floor>): Observable<Floor> {
    return this.http.put<Floor>(`${this.url}/${id}/`, data);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`);
  }
}
''')

write_file('app/shared/services/shift.service.ts', '''
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';
import { Shift } from '../interfaces/shift.interface';

@Injectable({ providedIn: 'root' })
export class ShiftService {
  private readonly url = `${environment.apiUrl}/shifts`;

  constructor(private http: HttpClient) {}

  getAll(): Observable<Shift[]> {
    return this.http.get<Shift[]>(`${this.url}/`);
  }

  create(data: Partial<Shift>): Observable<Shift> {
    return this.http.post<Shift>(`${this.url}/`, data);
  }

  update(id: number, data: Partial<Shift>): Observable<Shift> {
    return this.http.put<Shift>(`${this.url}/${id}/`, data);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`);
  }
}
''')

write_file('app/shared/services/restriction.service.ts', '''
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';
import { Restriction, ValidationResult } from '../interfaces/restriction.interface';

@Injectable({ providedIn: 'root' })
export class RestrictionService {
  private readonly url = `${environment.apiUrl}/restrictions`;

  constructor(private http: HttpClient) {}

  getAll(): Observable<Restriction[]> {
    return this.http.get<Restriction[]>(`${this.url}/`);
  }

  create(data: Partial<Restriction>): Observable<Restriction> {
    return this.http.post<Restriction>(`${this.url}/`, data);
  }

  update(id: number, data: Partial<Restriction>): Observable<Restriction> {
    return this.http.put<Restriction>(`${this.url}/${id}/`, data);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`);
  }

  validate(plan: any[]): Observable<ValidationResult> {
    return this.http.post<ValidationResult>(`${this.url}/validate/`, { plan });
  }

  getConstraints(): Observable<any> {
    return this.http.get(`${this.url}/constraints/`);
  }
}
''')

write_file('app/shared/services/planning.service.ts', '''
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';
import { WeeklyPlan, DayPlan } from '../interfaces/planning.interface';

@Injectable({ providedIn: 'root' })
export class PlanningService {
  private readonly url = `${environment.apiUrl}/planning`;

  constructor(private http: HttpClient) {}

  getWeeklyPlan(startDate: string): Observable<WeeklyPlan> {
    return this.http.get<WeeklyPlan>(`${this.url}/weekly-plan/?start=${startDate}`);
  }

  saveWeeklyPlan(start: string, plan: DayPlan[]): Observable<WeeklyPlan> {
    return this.http.post<WeeklyPlan>(`${this.url}/weekly-plan/`, { start, plan });
  }

  generateSchedule(startDate: string): Observable<DayPlan[]> {
    return this.http.post<DayPlan[]>(`${this.url}/schedule/generate/`, { startDate });
  }
}
''')

write_file('app/shared/services/rest-day.service.ts', '''
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';
import { RestDay } from '../interfaces/rest-day.interface';

@Injectable({ providedIn: 'root' })
export class RestDayService {
  private readonly url = `${environment.apiUrl}/rest-days`;

  constructor(private http: HttpClient) {}

  getAll(): Observable<RestDay[]> {
    return this.http.get<RestDay[]>(`${this.url}/all/`);
  }

  getWeekly(startDate: string): Observable<RestDay[]> {
    return this.http.get<RestDay[]>(`${this.url}/weekly/?start=${startDate}`);
  }

  create(data: { workerId: number; date: string; reason?: string }): Observable<RestDay> {
    return this.http.post<RestDay>(`${this.url}/`, data);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`);
  }
}
''')

write_file('app/shared/services/absence.service.ts', '''
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';
import { AbsenceType, AbsenceRequest } from '../interfaces/absence.interface';

@Injectable({ providedIn: 'root' })
export class AbsenceService {
  private readonly url = `${environment.apiUrl}/absences`;

  constructor(private http: HttpClient) {}

  getTypes(): Observable<AbsenceType[]> {
    return this.http.get<AbsenceType[]>(`${this.url}/types/`);
  }

  getRequests(params?: { status?: string; worker?: number }): Observable<AbsenceRequest[]> {
    let query = '';
    if (params) {
      const parts: string[] = [];
      if (params.status) parts.push(`status=${params.status}`);
      if (params.worker) parts.push(`worker=${params.worker}`);
      if (parts.length) query = '?' + parts.join('&');
    }
    return this.http.get<AbsenceRequest[]>(`${this.url}/requests/${query}`);
  }

  createRequest(data: Partial<AbsenceRequest>): Observable<AbsenceRequest> {
    return this.http.post<AbsenceRequest>(`${this.url}/requests/`, data);
  }

  approve(id: number): Observable<AbsenceRequest> {
    return this.http.patch<AbsenceRequest>(`${this.url}/requests/${id}/approve/`, {});
  }

  reject(id: number): Observable<AbsenceRequest> {
    return this.http.patch<AbsenceRequest>(`${this.url}/requests/${id}/reject/`, {});
  }
}
''')

write_file('app/shared/services/theme.service.ts', '''
import { Injectable, signal } from '@angular/core';

export type Theme = 'light' | 'dark';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly STORAGE_KEY = 'theme';
  theme = signal<Theme>(this.loadTheme());

  toggle(): void {
    const next: Theme = this.theme() === 'light' ? 'dark' : 'light';
    this.theme.set(next);
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem(this.STORAGE_KEY, next);
  }

  init(): void {
    document.documentElement.setAttribute('data-theme', this.theme());
  }

  private loadTheme(): Theme {
    const stored = localStorage.getItem(this.STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') return stored;
    return 'light';
  }
}
''')

write_file('app/shared/services/sidebar.service.ts', '''
import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class SidebarService {
  collapsed = signal(false);
  mobileOpen = signal(false);

  toggleCollapse(): void {
    this.collapsed.update(v => !v);
  }

  toggleMobile(): void {
    this.mobileOpen.update(v => !v);
  }

  closeMobile(): void {
    this.mobileOpen.set(false);
  }
}
''')

print('--- Services done ---')

# =============================================================================
# LAYOUT: SHELL, NAVBAR, SIDEBAR
# =============================================================================
write_file('app/layout/shell/shell.component.ts', '''
import { Component, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NavbarComponent } from '../navbar/navbar.component';
import { SidebarComponent } from '../sidebar/sidebar.component';
import { SidebarService } from '@app/shared/services/sidebar.service';
import { ThemeService } from '@app/shared/services/theme.service';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, NavbarComponent, SidebarComponent],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss',
})
export class ShellComponent implements OnInit {
  constructor(
    public sidebar: SidebarService,
    private themeService: ThemeService,
  ) {}

  ngOnInit(): void {
    this.themeService.init();
  }
}
''')

write_file('app/layout/shell/shell.component.html', '''
<app-navbar />
<div class="shell-body" [class.sidebar-collapsed]="sidebar.collapsed()">
  <app-sidebar />
  <main class="shell-content">
    <router-outlet />
  </main>
</div>
''')

write_file('app/layout/shell/shell.component.scss', r'''
.shell-body {
  display: flex;
  min-height: calc(100vh - 56px);
}

.shell-content {
  flex: 1;
  margin-left: 240px;
  padding: var(--sp-l);
  background-color: var(--fondo-pagina);
  transition: margin-left var(--transition-normal);
  overflow-x: hidden;
}

.sidebar-collapsed .shell-content {
  margin-left: 64px;
}

@media (max-width: 768px) {
  .shell-content {
    margin-left: 0;
    padding: var(--sp-m);
  }
}
''')

write_file('app/layout/navbar/navbar.component.ts', '''
import { Component } from '@angular/core';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatMenuModule } from '@angular/material/menu';
import { SidebarService } from '@app/shared/services/sidebar.service';
import { ThemeService } from '@app/shared/services/theme.service';
import { AuthService } from '@app/auth/services/auth.service';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [MatToolbarModule, MatIconModule, MatButtonModule, MatMenuModule],
  templateUrl: './navbar.component.html',
  styleUrl: './navbar.component.scss',
})
export class NavbarComponent {
  constructor(
    public sidebar: SidebarService,
    public themeService: ThemeService,
    public authService: AuthService,
  ) {}

  onLogout(): void {
    this.authService.logout();
  }
}
''')

write_file('app/layout/navbar/navbar.component.html', '''
<mat-toolbar class="navbar">
  <button mat-icon-button (click)="sidebar.toggleCollapse()" class="menu-btn desktop-only">
    <mat-icon>menu</mat-icon>
  </button>
  <button mat-icon-button (click)="sidebar.toggleMobile()" class="menu-btn mobile-only">
    <mat-icon>menu</mat-icon>
  </button>

  <span class="brand">Planificador de Turnos</span>
  <span class="spacer"></span>

  <button mat-icon-button (click)="themeService.toggle()" matTooltip="Cambiar tema">
    <mat-icon>{{ themeService.theme() === 'light' ? 'dark_mode' : 'light_mode' }}</mat-icon>
  </button>

  <button mat-icon-button [matMenuTriggerFor]="userMenu">
    <mat-icon>account_circle</mat-icon>
  </button>
  <mat-menu #userMenu="matMenu">
    <button mat-menu-item (click)="onLogout()">
      <mat-icon>logout</mat-icon>
      <span>Cerrar sesion</span>
    </button>
  </mat-menu>
</mat-toolbar>
''')

write_file('app/layout/navbar/navbar.component.scss', r'''
.navbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000;
  height: 56px;
  background: var(--fondo-header);
  border-bottom: 1px solid var(--borde-general);
  color: var(--texto-principal);
  display: flex;
  align-items: center;
  padding: 0 var(--sp-m);
}

.brand {
  font-family: var(--ff-display);
  font-weight: var(--fw-bold);
  font-size: var(--fs-18);
  margin-left: var(--sp-s);
}

.spacer {
  flex: 1;
}

.desktop-only {
  display: inline-flex;
}

.mobile-only {
  display: none;
}

@media (max-width: 768px) {
  .desktop-only { display: none; }
  .mobile-only { display: inline-flex; }
}
''')

SIDEBAR_ITEMS = r"""
  readonly items = [
    { icon: 'dashboard', label: 'Panel General', route: '/dashboard' },
    {
      icon: 'calendar_month', label: 'Planificacion', children: [
        { icon: 'event_note', label: 'Semanal', route: '/schedule' },
        { icon: 'rule', label: 'Restricciones', route: '/restrictions' },
        { icon: 'people', label: 'Empleados', route: '/employees' },
        { icon: 'event_busy', label: 'Ausencias', route: '/absences' },
      ],
    },
    {
      icon: 'settings', label: 'Configuracion', children: [
        { icon: 'work', label: 'Roles', route: '/roles' },
        { icon: 'schedule', label: 'Turnos', route: '/shifts' },
        { icon: 'apartment', label: 'Plantas', route: '/floors' },
      ],
    },
  ];
"""

write_file('app/layout/sidebar/sidebar.component.ts', f'''
import {{ Component }} from '@angular/core';
import {{ CommonModule }} from '@angular/common';
import {{ RouterLink, RouterLinkActive }} from '@angular/router';
import {{ MatIconModule }} from '@angular/material/icon';
import {{ MatListModule }} from '@angular/material/list';
import {{ SidebarService }} from '@app/shared/services/sidebar.service';

@Component({{
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, MatIconModule, MatListModule],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss',
}})
export class SidebarComponent {{
  constructor(public sidebar: SidebarService) {{}}
{SIDEBAR_ITEMS}
  expandedGroup: string | null = null;

  toggleGroup(label: string): void {{
    this.expandedGroup = this.expandedGroup === label ? null : label;
  }}

  onNavigate(): void {{
    this.sidebar.closeMobile();
  }}
}}
''')

write_file('app/layout/sidebar/sidebar.component.html', '''
<aside class="sidebar"
  [class.collapsed]="sidebar.collapsed()"
  [class.mobile-open]="sidebar.mobileOpen()">
  <nav class="sidebar-nav">
    @for (item of items; track item.label) {
      @if (!item.children) {
        <a class="nav-item"
           [routerLink]="item.route"
           routerLinkActive="active"
           (click)="onNavigate()">
          <mat-icon>{{ item.icon }}</mat-icon>
          <span class="nav-label">{{ item.label }}</span>
        </a>
      } @else {
        <div class="nav-group" [class.expanded]="expandedGroup === item.label">
          <button class="nav-item group-toggle" (click)="toggleGroup(item.label)">
            <mat-icon>{{ item.icon }}</mat-icon>
            <span class="nav-label">{{ item.label }}</span>
            <mat-icon class="chevron">expand_more</mat-icon>
          </button>
          <div class="nav-children">
            @for (child of item.children; track child.label) {
              <a class="nav-item child"
                 [routerLink]="child.route"
                 routerLinkActive="active"
                 (click)="onNavigate()">
                <mat-icon>{{ child.icon }}</mat-icon>
                <span class="nav-label">{{ child.label }}</span>
              </a>
            }
          </div>
        </div>
      }
    }
  </nav>
</aside>

@if (sidebar.mobileOpen()) {
  <div class="sidebar-overlay" (click)="sidebar.closeMobile()"></div>
}
''')

write_file('app/layout/sidebar/sidebar.component.scss', r'''
.sidebar {
  position: fixed;
  top: 56px;
  left: 0;
  bottom: 0;
  width: 240px;
  background: var(--sidebar-fondo);
  color: var(--sidebar-texto);
  overflow-y: auto;
  overflow-x: hidden;
  transition: width var(--transition-normal);
  z-index: 900;
  border-right: 1px solid var(--sidebar-borde);
}

.sidebar.collapsed {
  width: 64px;
}

.sidebar.collapsed .nav-label,
.sidebar.collapsed .chevron,
.sidebar.collapsed .nav-children {
  display: none;
}

.sidebar-nav {
  padding: var(--sp-s) 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--sp-s);
  padding: var(--sp-s) var(--sp-m);
  color: var(--sidebar-texto);
  text-decoration: none;
  font-size: var(--fs-14);
  font-weight: var(--fw-medium);
  cursor: pointer;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
  transition: background var(--transition-fast), color var(--transition-fast);
  min-height: 44px;
}

.nav-item:hover {
  background: var(--sidebar-item-hover);
  color: var(--sidebar-texto-activo);
}

.nav-item.active {
  background: var(--sidebar-item-activo);
  color: var(--sidebar-texto-activo);
}

.nav-item.child {
  padding-left: calc(var(--sp-m) + var(--sp-l));
  font-size: var(--fs-13);
}

.group-toggle {
  position: relative;
}

.chevron {
  margin-left: auto;
  font-size: 20px;
  transition: transform var(--transition-fast);
}

.nav-group.expanded .chevron {
  transform: rotate(180deg);
}

.nav-children {
  max-height: 0;
  overflow: hidden;
  transition: max-height var(--transition-normal);
}

.nav-group.expanded .nav-children {
  max-height: 500px;
}

.sidebar-overlay {
  display: none;
}

@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
    width: 260px;
  }

  .sidebar.mobile-open {
    transform: translateX(0);
  }

  .sidebar.collapsed {
    width: 260px;
    transform: translateX(-100%);
  }

  .sidebar.collapsed.mobile-open {
    transform: translateX(0);
  }

  .sidebar.collapsed .nav-label,
  .sidebar.collapsed .chevron,
  .sidebar.collapsed .nav-children {
    display: initial;
  }

  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 899;
  }
}
''')

print('--- Layout done ---')

# =============================================================================
# APP CONFIG (update with animations)
# =============================================================================
write_file('app/app.config.ts', '''
import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { authInterceptor } from './auth/interceptors/auth.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideAnimationsAsync(),
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor])),
  ],
};
''')

# =============================================================================
# APP ROOT COMPONENT
# =============================================================================
write_file('app/app.component.ts', '''
import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: '<router-outlet />',
})
export class AppComponent {}
''')

write_file('app/app.component.html', '''<router-outlet />
''')

write_file('app/app.component.scss', '')

# =============================================================================
# ROUTES
# =============================================================================
write_file('app/app.routes.ts', '''
import { Routes } from '@angular/router';
import { authGuard } from './auth/guards/auth.guard';
import { ShellComponent } from './layout/shell/shell.component';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./auth/login/login.component').then(m => m.LoginComponent),
  },
  {
    path: 'register',
    loadComponent: () => import('./auth/register/register.component').then(m => m.RegisterComponent),
  },
  {
    path: '',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      {
        path: 'dashboard',
        loadComponent: () => import('./pages/dashboard/dashboard.component').then(m => m.DashboardComponent),
      },
      {
        path: 'schedule',
        loadComponent: () => import('./pages/schedule/schedule.component').then(m => m.ScheduleComponent),
      },
      {
        path: 'employees',
        loadComponent: () => import('./pages/employees/employees.component').then(m => m.EmployeesComponent),
      },
      {
        path: 'roles',
        loadComponent: () => import('./pages/roles/roles.component').then(m => m.RolesComponent),
      },
      {
        path: 'shifts',
        loadComponent: () => import('./pages/shifts/shifts.component').then(m => m.ShiftsComponent),
      },
      {
        path: 'floors',
        loadComponent: () => import('./pages/floors/floors.component').then(m => m.FloorsComponent),
      },
      {
        path: 'restrictions',
        loadComponent: () => import('./pages/restrictions/restrictions.component').then(m => m.RestrictionsComponent),
      },
      {
        path: 'absences',
        loadComponent: () => import('./pages/absences/absences.component').then(m => m.AbsencesComponent),
      },
      {
        path: 'users',
        loadComponent: () => import('./users/user-list/user-list.component').then(m => m.UserListComponent),
      },
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
    ],
  },
  { path: '**', redirectTo: 'login' },
];
''')

print('--- Routes done ---')

# =============================================================================
# PAGES (feature components)
# =============================================================================

# -- Dashboard --
write_file('app/pages/dashboard/dashboard.component.ts', '''
import { Component } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [MatCardModule, MatIconModule],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent {}
''')

write_file('app/pages/dashboard/dashboard.component.html', '''
<div class="page-container">
  <div class="page-header">
    <h1 class="page-title">Panel General</h1>
  </div>

  <div class="dashboard-grid">
    <mat-card class="stat-card">
      <mat-card-content>
        <div class="stat-icon"><mat-icon>people</mat-icon></div>
        <div class="stat-info">
          <span class="stat-label">Empleados</span>
          <span class="stat-value">--</span>
        </div>
      </mat-card-content>
    </mat-card>

    <mat-card class="stat-card">
      <mat-card-content>
        <div class="stat-icon"><mat-icon>event_note</mat-icon></div>
        <div class="stat-info">
          <span class="stat-label">Planificaciones</span>
          <span class="stat-value">--</span>
        </div>
      </mat-card-content>
    </mat-card>

    <mat-card class="stat-card">
      <mat-card-content>
        <div class="stat-icon"><mat-icon>event_busy</mat-icon></div>
        <div class="stat-info">
          <span class="stat-label">Ausencias pendientes</span>
          <span class="stat-value">--</span>
        </div>
      </mat-card-content>
    </mat-card>

    <mat-card class="stat-card">
      <mat-card-content>
        <div class="stat-icon"><mat-icon>rule</mat-icon></div>
        <div class="stat-info">
          <span class="stat-label">Restricciones activas</span>
          <span class="stat-value">--</span>
        </div>
      </mat-card-content>
    </mat-card>
  </div>
</div>
''')

write_file('app/pages/dashboard/dashboard.component.scss', r'''
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: var(--sp-m);
}

.stat-card {
  background: var(--fondo-card);
  border: 1px solid var(--borde-general);
}

.stat-card mat-card-content {
  display: flex;
  align-items: center;
  gap: var(--sp-m);
  padding: var(--sp-m);
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: var(--br-default);
  background: var(--color-acento);
  color: var(--color-acento-texto);
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: var(--fs-13);
  color: var(--texto-secundario);
}

.stat-value {
  font-family: var(--ff-display);
  font-size: var(--fs-24);
  font-weight: var(--fw-bold);
}
''')

# -- Employees --
write_file('app/pages/employees/employees.component.ts', '''
import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialogModule, MatDialog } from '@angular/material/dialog';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { WorkerService } from '@app/shared/services/worker.service';
import { RoleService } from '@app/shared/services/role.service';
import { Worker } from '@app/shared/interfaces/worker.interface';
import { Role } from '@app/shared/interfaces/role.interface';

@Component({
  selector: 'app-employees',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatTableModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
    MatChipsModule, MatDialogModule, MatSlideToggleModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './employees.component.html',
  styleUrl: './employees.component.scss',
})
export class EmployeesComponent implements OnInit {
  workers = signal<Worker[]>([]);
  roles = signal<Role[]>([]);
  loading = signal(true);
  displayedColumns = ['name', 'role', 'shifts', 'active', 'actions'];

  editingId: number | null = null;
  editForm = { name: '', role: 0, preferredShifts: [] as string[] };
  showAddForm = false;
  newForm = { name: '', role: 0, preferredShifts: [] as string[] };

  shiftOptions = [
    { value: 'morning', label: 'Manana' },
    { value: 'afternoon', label: 'Tarde' },
    { value: 'night', label: 'Noche' },
  ];

  constructor(
    private workerService: WorkerService,
    private roleService: RoleService,
  ) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.roleService.getAll().subscribe(roles => this.roles.set(roles));
    this.workerService.getAll().subscribe({
      next: workers => { this.workers.set(workers); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  startEdit(w: Worker): void {
    this.editingId = w.id;
    this.editForm = {
      name: w.name,
      role: w.role,
      preferredShifts: w.preferredShifts.map(p => p.shift_type),
    };
  }

  cancelEdit(): void {
    this.editingId = null;
  }

  saveEdit(w: Worker): void {
    this.workerService.update(w.id, {
      name: this.editForm.name,
      role: this.editForm.role,
      preferredShifts: this.editForm.preferredShifts,
    }).subscribe(() => { this.editingId = null; this.load(); });
  }

  toggleActive(w: Worker): void {
    this.workerService.update(w.id, {
      name: w.name,
      role: w.role,
      active: !w.active,
      preferredShifts: w.preferredShifts.map(p => p.shift_type),
    }).subscribe(() => this.load());
  }

  deleteWorker(w: Worker): void {
    if (confirm('Eliminar a ' + w.name + '?')) {
      this.workerService.delete(w.id).subscribe(() => this.load());
    }
  }

  openAddForm(): void {
    this.showAddForm = true;
    this.newForm = { name: '', role: 0, preferredShifts: [] };
  }

  cancelAdd(): void {
    this.showAddForm = false;
  }

  saveNew(): void {
    this.workerService.create({
      name: this.newForm.name,
      role: this.newForm.role,
      preferredShifts: this.newForm.preferredShifts,
    }).subscribe(() => { this.showAddForm = false; this.load(); });
  }
}
''')

write_file('app/pages/employees/employees.component.html', '''
<div class="page-container">
  <div class="page-header">
    <h1 class="page-title">Empleados</h1>
    <button mat-flat-button color="primary" (click)="openAddForm()">
      <mat-icon>add</mat-icon> Nuevo empleado
    </button>
  </div>

  @if (showAddForm) {
    <div class="card-surface form-card">
      <h3>Nuevo empleado</h3>
      <div class="form-row">
        <mat-form-field appearance="outline">
          <mat-label>Nombre</mat-label>
          <input matInput [(ngModel)]="newForm.name">
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Rol</mat-label>
          <mat-select [(ngModel)]="newForm.role">
            @for (role of roles(); track role.id) {
              <mat-option [value]="role.id">{{ role.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Turnos preferidos</mat-label>
          <mat-select [(ngModel)]="newForm.preferredShifts" multiple>
            @for (s of shiftOptions; track s.value) {
              <mat-option [value]="s.value">{{ s.label }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      </div>
      <div class="form-actions">
        <button mat-button (click)="cancelAdd()">Cancelar</button>
        <button mat-flat-button color="primary" (click)="saveNew()" [disabled]="!newForm.name || !newForm.role">Guardar</button>
      </div>
    </div>
  }

  @if (loading()) {
    <div class="loading-container">
      <mat-spinner diameter="40"></mat-spinner>
    </div>
  } @else {
    <div class="card-surface">
      <table mat-table [dataSource]="workers()" class="full-width">
        <ng-container matColumnDef="name">
          <th mat-header-cell *matHeaderCellDef>Nombre</th>
          <td mat-cell *matCellDef="let w">
            @if (editingId === w.id) {
              <mat-form-field appearance="outline" class="inline-field">
                <input matInput [(ngModel)]="editForm.name">
              </mat-form-field>
            } @else {
              {{ w.name }}
            }
          </td>
        </ng-container>

        <ng-container matColumnDef="role">
          <th mat-header-cell *matHeaderCellDef>Rol</th>
          <td mat-cell *matCellDef="let w">
            @if (editingId === w.id) {
              <mat-form-field appearance="outline" class="inline-field">
                <mat-select [(ngModel)]="editForm.role">
                  @for (role of roles(); track role.id) {
                    <mat-option [value]="role.id">{{ role.name }}</mat-option>
                  }
                </mat-select>
              </mat-form-field>
            } @else {
              {{ w.role_name }}
            }
          </td>
        </ng-container>

        <ng-container matColumnDef="shifts">
          <th mat-header-cell *matHeaderCellDef>Turnos preferidos</th>
          <td mat-cell *matCellDef="let w">
            @if (editingId === w.id) {
              <mat-form-field appearance="outline" class="inline-field">
                <mat-select [(ngModel)]="editForm.preferredShifts" multiple>
                  @for (s of shiftOptions; track s.value) {
                    <mat-option [value]="s.value">{{ s.label }}</mat-option>
                  }
                </mat-select>
              </mat-form-field>
            } @else {
              @for (p of w.preferredShifts; track p.shift_type) {
                <span class="chip">{{ p.shift_type }}</span>
              }
            }
          </td>
        </ng-container>

        <ng-container matColumnDef="active">
          <th mat-header-cell *matHeaderCellDef>Estado</th>
          <td mat-cell *matCellDef="let w">
            <mat-slide-toggle [checked]="w.active" (change)="toggleActive(w)"></mat-slide-toggle>
          </td>
        </ng-container>

        <ng-container matColumnDef="actions">
          <th mat-header-cell *matHeaderCellDef></th>
          <td mat-cell *matCellDef="let w">
            @if (editingId === w.id) {
              <button mat-icon-button color="primary" (click)="saveEdit(w)"><mat-icon>check</mat-icon></button>
              <button mat-icon-button (click)="cancelEdit()"><mat-icon>close</mat-icon></button>
            } @else {
              <button mat-icon-button (click)="startEdit(w)"><mat-icon>edit</mat-icon></button>
              <button mat-icon-button color="warn" (click)="deleteWorker(w)"><mat-icon>delete</mat-icon></button>
            }
          </td>
        </ng-container>

        <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
        <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
      </table>
    </div>
  }
</div>
''')

write_file('app/pages/employees/employees.component.scss', r'''
.form-card {
  margin-bottom: var(--sp-l);
}

.form-card h3 {
  margin-bottom: var(--sp-m);
}

.form-row {
  display: flex;
  gap: var(--sp-m);
  flex-wrap: wrap;
}

.form-row mat-form-field {
  flex: 1;
  min-width: 200px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-s);
  margin-top: var(--sp-m);
}

.full-width {
  width: 100%;
}

.inline-field {
  width: 100%;
}

.chip {
  display: inline-block;
  padding: 2px 8px;
  background: var(--color-acento);
  color: var(--color-acento-texto);
  border-radius: var(--br-rounded);
  font-size: var(--fs-12);
  font-weight: var(--fw-medium);
  margin-right: 4px;
}

.loading-container {
  display: flex;
  justify-content: center;
  padding: var(--sp-2xl);
}
''')

# -- Roles --
write_file('app/pages/roles/roles.component.ts', '''
import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { RoleService } from '@app/shared/services/role.service';
import { Role } from '@app/shared/interfaces/role.interface';

@Component({
  selector: 'app-roles',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatTableModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSlideToggleModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './roles.component.html',
  styleUrl: './roles.component.scss',
})
export class RolesComponent implements OnInit {
  roles = signal<Role[]>([]);
  loading = signal(true);
  displayedColumns = ['name', 'description', 'active', 'actions'];
  showAdd = false;
  newRole = { name: '', description: '' };

  constructor(private roleService: RoleService) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.roleService.getAll().subscribe({
      next: r => { this.roles.set(r); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  saveNew(): void {
    this.roleService.create(this.newRole).subscribe(() => {
      this.showAdd = false;
      this.newRole = { name: '', description: '' };
      this.load();
    });
  }

  deleteRole(r: Role): void {
    if (confirm('Eliminar rol ' + r.name + '?')) {
      this.roleService.delete(r.id).subscribe(() => this.load());
    }
  }
}
''')

write_file('app/pages/roles/roles.component.html', '''
<div class="page-container">
  <div class="page-header">
    <h1 class="page-title">Roles</h1>
    <button mat-flat-button color="primary" (click)="showAdd = true">
      <mat-icon>add</mat-icon> Nuevo rol
    </button>
  </div>

  @if (showAdd) {
    <div class="card-surface form-card">
      <div class="form-row">
        <mat-form-field appearance="outline">
          <mat-label>Nombre</mat-label>
          <input matInput [(ngModel)]="newRole.name">
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Descripcion</mat-label>
          <input matInput [(ngModel)]="newRole.description">
        </mat-form-field>
      </div>
      <div class="form-actions">
        <button mat-button (click)="showAdd = false">Cancelar</button>
        <button mat-flat-button color="primary" (click)="saveNew()" [disabled]="!newRole.name">Guardar</button>
      </div>
    </div>
  }

  @if (loading()) {
    <div class="loading-container"><mat-spinner diameter="40"></mat-spinner></div>
  } @else {
    <div class="card-surface">
      <table mat-table [dataSource]="roles()" class="full-width">
        <ng-container matColumnDef="name">
          <th mat-header-cell *matHeaderCellDef>Nombre</th>
          <td mat-cell *matCellDef="let r">{{ r.name }}</td>
        </ng-container>
        <ng-container matColumnDef="description">
          <th mat-header-cell *matHeaderCellDef>Descripcion</th>
          <td mat-cell *matCellDef="let r">{{ r.description }}</td>
        </ng-container>
        <ng-container matColumnDef="active">
          <th mat-header-cell *matHeaderCellDef>Activo</th>
          <td mat-cell *matCellDef="let r">
            <span class="chip" [class.chip-active]="r.active" [class.chip-inactive]="!r.active">
              {{ r.active ? 'Activo' : 'Inactivo' }}
            </span>
          </td>
        </ng-container>
        <ng-container matColumnDef="actions">
          <th mat-header-cell *matHeaderCellDef></th>
          <td mat-cell *matCellDef="let r">
            <button mat-icon-button color="warn" (click)="deleteRole(r)"><mat-icon>delete</mat-icon></button>
          </td>
        </ng-container>
        <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
        <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
      </table>
    </div>
  }
</div>
''')

write_file('app/pages/roles/roles.component.scss', r'''
.form-card { margin-bottom: var(--sp-l); }
.form-row { display: flex; gap: var(--sp-m); flex-wrap: wrap; }
.form-row mat-form-field { flex: 1; min-width: 200px; }
.form-actions { display: flex; justify-content: flex-end; gap: var(--sp-s); margin-top: var(--sp-m); }
.full-width { width: 100%; }
.loading-container { display: flex; justify-content: center; padding: var(--sp-2xl); }
.chip { display: inline-block; padding: 2px 10px; border-radius: var(--br-rounded); font-size: var(--fs-12); font-weight: var(--fw-medium); }
.chip-active { background: var(--color-exito-bg); color: var(--c-green-700); }
.chip-inactive { background: var(--color-error-bg); color: var(--c-red-600); }
''')

# -- Shifts --
write_file('app/pages/shifts/shifts.component.ts', '''
import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ShiftService } from '@app/shared/services/shift.service';
import { Shift } from '@app/shared/interfaces/shift.interface';

@Component({
  selector: 'app-shifts',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatTableModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatCheckboxModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './shifts.component.html',
  styleUrl: './shifts.component.scss',
})
export class ShiftsComponent implements OnInit {
  shifts = signal<Shift[]>([]);
  loading = signal(true);
  displayedColumns = ['name', 'start_time', 'end_time', 'days', 'actions'];
  showAdd = false;
  newShift = { name: '', start_time: '07:00', end_time: '15:00', applicable_days: [] as number[] };
  dayLabels = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'];

  constructor(private shiftService: ShiftService) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.shiftService.getAll().subscribe({
      next: s => { this.shifts.set(s); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  toggleDay(day: number): void {
    const i = this.newShift.applicable_days.indexOf(day);
    if (i >= 0) this.newShift.applicable_days.splice(i, 1);
    else this.newShift.applicable_days.push(day);
  }

  saveNew(): void {
    this.shiftService.create(this.newShift).subscribe(() => {
      this.showAdd = false;
      this.newShift = { name: '', start_time: '07:00', end_time: '15:00', applicable_days: [] };
      this.load();
    });
  }

  deleteShift(s: Shift): void {
    if (confirm('Eliminar turno ' + s.name + '?')) {
      this.shiftService.delete(s.id).subscribe(() => this.load());
    }
  }

  dayNames(days: number[]): string {
    return days.map(d => this.dayLabels[d] || '').join(', ');
  }
}
''')

write_file('app/pages/shifts/shifts.component.html', '''
<div class="page-container">
  <div class="page-header">
    <h1 class="page-title">Turnos</h1>
    <button mat-flat-button color="primary" (click)="showAdd = true">
      <mat-icon>add</mat-icon> Nuevo turno
    </button>
  </div>

  @if (showAdd) {
    <div class="card-surface form-card">
      <div class="form-row">
        <mat-form-field appearance="outline">
          <mat-label>Nombre</mat-label>
          <input matInput [(ngModel)]="newShift.name">
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Hora inicio</mat-label>
          <input matInput type="time" [(ngModel)]="newShift.start_time">
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Hora fin</mat-label>
          <input matInput type="time" [(ngModel)]="newShift.end_time">
        </mat-form-field>
      </div>
      <div class="days-row">
        <span class="days-label">Dias aplicables:</span>
        @for (day of [0,1,2,3,4,5,6]; track day) {
          <mat-checkbox
            [checked]="newShift.applicable_days.includes(day)"
            (change)="toggleDay(day)">
            {{ dayLabels[day] }}
          </mat-checkbox>
        }
      </div>
      <div class="form-actions">
        <button mat-button (click)="showAdd = false">Cancelar</button>
        <button mat-flat-button color="primary" (click)="saveNew()" [disabled]="!newShift.name">Guardar</button>
      </div>
    </div>
  }

  @if (loading()) {
    <div class="loading-container"><mat-spinner diameter="40"></mat-spinner></div>
  } @else {
    <div class="card-surface">
      <table mat-table [dataSource]="shifts()" class="full-width">
        <ng-container matColumnDef="name">
          <th mat-header-cell *matHeaderCellDef>Nombre</th>
          <td mat-cell *matCellDef="let s">{{ s.name }}</td>
        </ng-container>
        <ng-container matColumnDef="start_time">
          <th mat-header-cell *matHeaderCellDef>Inicio</th>
          <td mat-cell *matCellDef="let s">{{ s.start_time }}</td>
        </ng-container>
        <ng-container matColumnDef="end_time">
          <th mat-header-cell *matHeaderCellDef>Fin</th>
          <td mat-cell *matCellDef="let s">{{ s.end_time }}</td>
        </ng-container>
        <ng-container matColumnDef="days">
          <th mat-header-cell *matHeaderCellDef>Dias</th>
          <td mat-cell *matCellDef="let s">{{ dayNames(s.applicable_days) }}</td>
        </ng-container>
        <ng-container matColumnDef="actions">
          <th mat-header-cell *matHeaderCellDef></th>
          <td mat-cell *matCellDef="let s">
            <button mat-icon-button color="warn" (click)="deleteShift(s)"><mat-icon>delete</mat-icon></button>
          </td>
        </ng-container>
        <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
        <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
      </table>
    </div>
  }
</div>
''')

write_file('app/pages/shifts/shifts.component.scss', r'''
.form-card { margin-bottom: var(--sp-l); }
.form-row { display: flex; gap: var(--sp-m); flex-wrap: wrap; }
.form-row mat-form-field { flex: 1; min-width: 180px; }
.days-row { display: flex; align-items: center; gap: var(--sp-m); flex-wrap: wrap; margin-top: var(--sp-s); }
.days-label { font-weight: var(--fw-medium); font-size: var(--fs-14); }
.form-actions { display: flex; justify-content: flex-end; gap: var(--sp-s); margin-top: var(--sp-m); }
.full-width { width: 100%; }
.loading-container { display: flex; justify-content: center; padding: var(--sp-2xl); }
''')

# -- Floors --
write_file('app/pages/floors/floors.component.ts', '''
import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { FloorService } from '@app/shared/services/floor.service';
import { RoleService } from '@app/shared/services/role.service';
import { Floor } from '@app/shared/interfaces/floor.interface';
import { Role } from '@app/shared/interfaces/role.interface';

@Component({
  selector: 'app-floors',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatTableModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './floors.component.html',
  styleUrl: './floors.component.scss',
})
export class FloorsComponent implements OnInit {
  floors = signal<Floor[]>([]);
  roles = signal<Role[]>([]);
  loading = signal(true);
  displayedColumns = ['name', 'short_name', 'order', 'required_role', 'actions'];
  showAdd = false;
  newFloor = { name: '', short_name: '', order: 0, required_role: null as number | null };

  constructor(private floorService: FloorService, private roleService: RoleService) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.roleService.getAll().subscribe(r => this.roles.set(r));
    this.floorService.getAll().subscribe({
      next: f => { this.floors.set(f); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  saveNew(): void {
    this.floorService.create(this.newFloor).subscribe(() => {
      this.showAdd = false;
      this.newFloor = { name: '', short_name: '', order: 0, required_role: null };
      this.load();
    });
  }

  deleteFloor(f: Floor): void {
    if (confirm('Eliminar planta ' + f.name + '?')) {
      this.floorService.delete(f.id).subscribe(() => this.load());
    }
  }
}
''')

write_file('app/pages/floors/floors.component.html', '''
<div class="page-container">
  <div class="page-header">
    <h1 class="page-title">Plantas</h1>
    <button mat-flat-button color="primary" (click)="showAdd = true">
      <mat-icon>add</mat-icon> Nueva planta
    </button>
  </div>

  @if (showAdd) {
    <div class="card-surface form-card">
      <div class="form-row">
        <mat-form-field appearance="outline">
          <mat-label>Nombre</mat-label>
          <input matInput [(ngModel)]="newFloor.name">
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Nombre corto</mat-label>
          <input matInput [(ngModel)]="newFloor.short_name">
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Orden</mat-label>
          <input matInput type="number" [(ngModel)]="newFloor.order">
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Rol requerido</mat-label>
          <mat-select [(ngModel)]="newFloor.required_role">
            <mat-option [value]="null">Ninguno</mat-option>
            @for (role of roles(); track role.id) {
              <mat-option [value]="role.id">{{ role.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      </div>
      <div class="form-actions">
        <button mat-button (click)="showAdd = false">Cancelar</button>
        <button mat-flat-button color="primary" (click)="saveNew()" [disabled]="!newFloor.name">Guardar</button>
      </div>
    </div>
  }

  @if (loading()) {
    <div class="loading-container"><mat-spinner diameter="40"></mat-spinner></div>
  } @else {
    <div class="card-surface">
      <table mat-table [dataSource]="floors()" class="full-width">
        <ng-container matColumnDef="name">
          <th mat-header-cell *matHeaderCellDef>Nombre</th>
          <td mat-cell *matCellDef="let f">{{ f.name }}</td>
        </ng-container>
        <ng-container matColumnDef="short_name">
          <th mat-header-cell *matHeaderCellDef>Corto</th>
          <td mat-cell *matCellDef="let f">{{ f.short_name }}</td>
        </ng-container>
        <ng-container matColumnDef="order">
          <th mat-header-cell *matHeaderCellDef>Orden</th>
          <td mat-cell *matCellDef="let f">{{ f.order }}</td>
        </ng-container>
        <ng-container matColumnDef="required_role">
          <th mat-header-cell *matHeaderCellDef>Rol requerido</th>
          <td mat-cell *matCellDef="let f">{{ f.required_role_name || '-' }}</td>
        </ng-container>
        <ng-container matColumnDef="actions">
          <th mat-header-cell *matHeaderCellDef></th>
          <td mat-cell *matCellDef="let f">
            <button mat-icon-button color="warn" (click)="deleteFloor(f)"><mat-icon>delete</mat-icon></button>
          </td>
        </ng-container>
        <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
        <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
      </table>
    </div>
  }
</div>
''')

write_file('app/pages/floors/floors.component.scss', r'''
.form-card { margin-bottom: var(--sp-l); }
.form-row { display: flex; gap: var(--sp-m); flex-wrap: wrap; }
.form-row mat-form-field { flex: 1; min-width: 160px; }
.form-actions { display: flex; justify-content: flex-end; gap: var(--sp-s); margin-top: var(--sp-m); }
.full-width { width: 100%; }
.loading-container { display: flex; justify-content: center; padding: var(--sp-2xl); }
''')

# -- Restrictions --
write_file('app/pages/restrictions/restrictions.component.ts', '''
import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { RestrictionService } from '@app/shared/services/restriction.service';
import { Restriction } from '@app/shared/interfaces/restriction.interface';

@Component({
  selector: 'app-restrictions',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatTableModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
    MatSlideToggleModule, MatProgressSpinnerModule,
  ],
  templateUrl: './restrictions.component.html',
  styleUrl: './restrictions.component.scss',
})
export class RestrictionsComponent implements OnInit {
  restrictions = signal<Restriction[]>([]);
  loading = signal(true);
  displayedColumns = ['name', 'type', 'active', 'actions'];

  restrictionTypes = [
    { value: 'max_workers_per_floor', label: 'Max trabajadores por planta' },
    { value: 'min_workers_per_floor', label: 'Min trabajadores por planta' },
    { value: 'no_empty_floors', label: 'Sin plantas vacias' },
    { value: 'night_morning_conflict', label: 'Conflicto noche-manana' },
    { value: 'max_shifts_per_day', label: 'Max turnos por dia' },
    { value: 'max_floors_per_worker', label: 'Max plantas por trabajador' },
    { value: 'no_rest_workers_in_shifts', label: 'Sin descanso en turnos' },
  ];

  showAdd = false;
  newRestriction = { name: '', type: '', description: '', parameters: '{}' };

  constructor(private restrictionService: RestrictionService) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.restrictionService.getAll().subscribe({
      next: r => { this.restrictions.set(r); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  saveNew(): void {
    let params = {};
    try { params = JSON.parse(this.newRestriction.parameters); } catch {}
    this.restrictionService.create({
      name: this.newRestriction.name,
      type: this.newRestriction.type,
      description: this.newRestriction.description,
      parameters: params,
    }).subscribe(() => {
      this.showAdd = false;
      this.newRestriction = { name: '', type: '', description: '', parameters: '{}' };
      this.load();
    });
  }

  deleteRestriction(r: Restriction): void {
    if (confirm('Eliminar restriccion ' + r.name + '?')) {
      this.restrictionService.delete(r.id).subscribe(() => this.load());
    }
  }
}
''')

write_file('app/pages/restrictions/restrictions.component.html', '''
<div class="page-container">
  <div class="page-header">
    <h1 class="page-title">Restricciones</h1>
    <button mat-flat-button color="primary" (click)="showAdd = true">
      <mat-icon>add</mat-icon> Nueva restriccion
    </button>
  </div>

  @if (showAdd) {
    <div class="card-surface form-card">
      <div class="form-row">
        <mat-form-field appearance="outline">
          <mat-label>Nombre</mat-label>
          <input matInput [(ngModel)]="newRestriction.name">
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Tipo</mat-label>
          <mat-select [(ngModel)]="newRestriction.type">
            @for (t of restrictionTypes; track t.value) {
              <mat-option [value]="t.value">{{ t.label }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      </div>
      <mat-form-field appearance="outline" class="full-width-field">
        <mat-label>Descripcion</mat-label>
        <input matInput [(ngModel)]="newRestriction.description">
      </mat-form-field>
      <mat-form-field appearance="outline" class="full-width-field">
        <mat-label>Parametros (JSON)</mat-label>
        <textarea matInput [(ngModel)]="newRestriction.parameters" rows="3"></textarea>
      </mat-form-field>
      <div class="form-actions">
        <button mat-button (click)="showAdd = false">Cancelar</button>
        <button mat-flat-button color="primary" (click)="saveNew()" [disabled]="!newRestriction.name || !newRestriction.type">Guardar</button>
      </div>
    </div>
  }

  @if (loading()) {
    <div class="loading-container"><mat-spinner diameter="40"></mat-spinner></div>
  } @else {
    <div class="card-surface">
      <table mat-table [dataSource]="restrictions()" class="full-width">
        <ng-container matColumnDef="name">
          <th mat-header-cell *matHeaderCellDef>Nombre</th>
          <td mat-cell *matCellDef="let r">{{ r.name }}</td>
        </ng-container>
        <ng-container matColumnDef="type">
          <th mat-header-cell *matHeaderCellDef>Tipo</th>
          <td mat-cell *matCellDef="let r">{{ r.type }}</td>
        </ng-container>
        <ng-container matColumnDef="active">
          <th mat-header-cell *matHeaderCellDef>Activo</th>
          <td mat-cell *matCellDef="let r">
            <span class="chip" [class.chip-active]="r.active" [class.chip-inactive]="!r.active">
              {{ r.active ? 'Si' : 'No' }}
            </span>
          </td>
        </ng-container>
        <ng-container matColumnDef="actions">
          <th mat-header-cell *matHeaderCellDef></th>
          <td mat-cell *matCellDef="let r">
            <button mat-icon-button color="warn" (click)="deleteRestriction(r)"><mat-icon>delete</mat-icon></button>
          </td>
        </ng-container>
        <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
        <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
      </table>
    </div>
  }
</div>
''')

write_file('app/pages/restrictions/restrictions.component.scss', r'''
.form-card { margin-bottom: var(--sp-l); }
.form-row { display: flex; gap: var(--sp-m); flex-wrap: wrap; }
.form-row mat-form-field { flex: 1; min-width: 200px; }
.full-width-field { width: 100%; margin-top: var(--sp-s); }
.form-actions { display: flex; justify-content: flex-end; gap: var(--sp-s); margin-top: var(--sp-m); }
.full-width { width: 100%; }
.loading-container { display: flex; justify-content: center; padding: var(--sp-2xl); }
.chip { display: inline-block; padding: 2px 10px; border-radius: var(--br-rounded); font-size: var(--fs-12); font-weight: var(--fw-medium); }
.chip-active { background: var(--color-exito-bg); color: var(--c-green-700); }
.chip-inactive { background: var(--color-error-bg); color: var(--c-red-600); }
''')

# -- Absences --
write_file('app/pages/absences/absences.component.ts', '''
import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTabsModule } from '@angular/material/tabs';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { AbsenceService } from '@app/shared/services/absence.service';
import { WorkerService } from '@app/shared/services/worker.service';
import { AbsenceType, AbsenceRequest } from '@app/shared/interfaces/absence.interface';
import { Worker } from '@app/shared/interfaces/worker.interface';

@Component({
  selector: 'app-absences',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatTableModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
    MatTabsModule, MatChipsModule, MatProgressSpinnerModule,
  ],
  templateUrl: './absences.component.html',
  styleUrl: './absences.component.scss',
})
export class AbsencesComponent implements OnInit {
  requests = signal<AbsenceRequest[]>([]);
  types = signal<AbsenceType[]>([]);
  workers = signal<Worker[]>([]);
  loading = signal(true);
  displayedColumns = ['worker', 'type', 'dates', 'status', 'actions'];
  statusFilter = '';

  showAdd = false;
  newRequest = { worker: 0, type: 0, start_date: '', end_date: '', reason: '' };

  constructor(
    private absenceService: AbsenceService,
    private workerService: WorkerService,
  ) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.absenceService.getTypes().subscribe(t => this.types.set(t));
    this.workerService.getActive().subscribe(w => this.workers.set(w));
    const params = this.statusFilter ? { status: this.statusFilter } : undefined;
    this.absenceService.getRequests(params).subscribe({
      next: r => { this.requests.set(r); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  filterByStatus(status: string): void {
    this.statusFilter = status;
    this.load();
  }

  saveNew(): void {
    this.absenceService.createRequest(this.newRequest).subscribe(() => {
      this.showAdd = false;
      this.newRequest = { worker: 0, type: 0, start_date: '', end_date: '', reason: '' };
      this.load();
    });
  }

  approve(id: number): void {
    this.absenceService.approve(id).subscribe(() => this.load());
  }

  reject(id: number): void {
    this.absenceService.reject(id).subscribe(() => this.load());
  }
}
''')

write_file('app/pages/absences/absences.component.html', '''
<div class="page-container">
  <div class="page-header">
    <h1 class="page-title">Ausencias</h1>
    <button mat-flat-button color="primary" (click)="showAdd = true">
      <mat-icon>add</mat-icon> Nueva solicitud
    </button>
  </div>

  @if (showAdd) {
    <div class="card-surface form-card">
      <h3>Nueva solicitud de ausencia</h3>
      <div class="form-row">
        <mat-form-field appearance="outline">
          <mat-label>Empleado</mat-label>
          <mat-select [(ngModel)]="newRequest.worker">
            @for (w of workers(); track w.id) {
              <mat-option [value]="w.id">{{ w.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Tipo</mat-label>
          <mat-select [(ngModel)]="newRequest.type">
            @for (t of types(); track t.id) {
              <mat-option [value]="t.id">{{ t.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      </div>
      <div class="form-row">
        <mat-form-field appearance="outline">
          <mat-label>Fecha inicio</mat-label>
          <input matInput type="date" [(ngModel)]="newRequest.start_date">
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Fecha fin</mat-label>
          <input matInput type="date" [(ngModel)]="newRequest.end_date">
        </mat-form-field>
      </div>
      <mat-form-field appearance="outline" class="full-width-field">
        <mat-label>Motivo</mat-label>
        <textarea matInput [(ngModel)]="newRequest.reason" rows="2"></textarea>
      </mat-form-field>
      <div class="form-actions">
        <button mat-button (click)="showAdd = false">Cancelar</button>
        <button mat-flat-button color="primary" (click)="saveNew()"
          [disabled]="!newRequest.worker || !newRequest.type || !newRequest.start_date || !newRequest.end_date">
          Enviar solicitud
        </button>
      </div>
    </div>
  }

  <div class="filter-bar">
    <button mat-stroked-button [class.active-filter]="statusFilter === ''" (click)="filterByStatus('')">Todas</button>
    <button mat-stroked-button [class.active-filter]="statusFilter === 'pending'" (click)="filterByStatus('pending')">Pendientes</button>
    <button mat-stroked-button [class.active-filter]="statusFilter === 'approved'" (click)="filterByStatus('approved')">Aprobadas</button>
    <button mat-stroked-button [class.active-filter]="statusFilter === 'rejected'" (click)="filterByStatus('rejected')">Rechazadas</button>
  </div>

  @if (loading()) {
    <div class="loading-container"><mat-spinner diameter="40"></mat-spinner></div>
  } @else {
    <div class="card-surface">
      <table mat-table [dataSource]="requests()" class="full-width">
        <ng-container matColumnDef="worker">
          <th mat-header-cell *matHeaderCellDef>Empleado</th>
          <td mat-cell *matCellDef="let r">{{ r.worker_name }}</td>
        </ng-container>
        <ng-container matColumnDef="type">
          <th mat-header-cell *matHeaderCellDef>Tipo</th>
          <td mat-cell *matCellDef="let r">{{ r.type_name }}</td>
        </ng-container>
        <ng-container matColumnDef="dates">
          <th mat-header-cell *matHeaderCellDef>Fechas</th>
          <td mat-cell *matCellDef="let r">{{ r.start_date }} - {{ r.end_date }}</td>
        </ng-container>
        <ng-container matColumnDef="status">
          <th mat-header-cell *matHeaderCellDef>Estado</th>
          <td mat-cell *matCellDef="let r">
            <span class="status-chip" [attr.data-status]="r.status">
              {{ r.status === 'pending' ? 'Pendiente' : r.status === 'approved' ? 'Aprobada' : 'Rechazada' }}
            </span>
          </td>
        </ng-container>
        <ng-container matColumnDef="actions">
          <th mat-header-cell *matHeaderCellDef></th>
          <td mat-cell *matCellDef="let r">
            @if (r.status === 'pending') {
              <button mat-icon-button color="primary" (click)="approve(r.id)" matTooltip="Aprobar">
                <mat-icon>check_circle</mat-icon>
              </button>
              <button mat-icon-button color="warn" (click)="reject(r.id)" matTooltip="Rechazar">
                <mat-icon>cancel</mat-icon>
              </button>
            }
          </td>
        </ng-container>
        <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
        <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
      </table>
    </div>
  }
</div>
''')

write_file('app/pages/absences/absences.component.scss', r'''
.form-card { margin-bottom: var(--sp-l); }
.form-card h3 { margin-bottom: var(--sp-m); }
.form-row { display: flex; gap: var(--sp-m); flex-wrap: wrap; }
.form-row mat-form-field { flex: 1; min-width: 200px; }
.full-width-field { width: 100%; margin-top: var(--sp-s); }
.form-actions { display: flex; justify-content: flex-end; gap: var(--sp-s); margin-top: var(--sp-m); }
.full-width { width: 100%; }
.loading-container { display: flex; justify-content: center; padding: var(--sp-2xl); }

.filter-bar {
  display: flex;
  gap: var(--sp-s);
  margin-bottom: var(--sp-m);
}

.active-filter {
  background: var(--color-acento);
  color: var(--color-acento-texto);
}

.status-chip {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--br-rounded);
  font-size: var(--fs-12);
  font-weight: var(--fw-medium);
}

.status-chip[data-status='pending'] {
  background: var(--color-warning-bg);
  color: var(--c-brand-dark);
}

.status-chip[data-status='approved'] {
  background: var(--color-exito-bg);
  color: var(--c-green-700);
}

.status-chip[data-status='rejected'] {
  background: var(--color-error-bg);
  color: var(--c-red-600);
}
''')

# -- Schedule (stub for now -- complex component) --
write_file('app/pages/schedule/schedule.component.ts', '''
import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { PlanningService } from '@app/shared/services/planning.service';
import { WeeklyPlan, DayPlan } from '@app/shared/interfaces/planning.interface';

@Component({
  selector: 'app-schedule',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatIconModule, MatProgressSpinnerModule],
  templateUrl: './schedule.component.html',
  styleUrl: './schedule.component.scss',
})
export class ScheduleComponent implements OnInit {
  plan = signal<DayPlan[]>([]);
  startDate = signal('');
  loading = signal(true);

  constructor(private planningService: PlanningService) {}

  ngOnInit(): void {
    this.goToWeek(this.getCurrentMonday());
  }

  goToWeek(date: string): void {
    this.startDate.set(date);
    this.loading.set(true);
    this.planningService.getWeeklyPlan(date).subscribe({
      next: wp => { this.plan.set(wp.plan); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  prevWeek(): void {
    const d = new Date(this.startDate());
    d.setDate(d.getDate() - 7);
    this.goToWeek(this.formatDate(d));
  }

  nextWeek(): void {
    const d = new Date(this.startDate());
    d.setDate(d.getDate() + 7);
    this.goToWeek(this.formatDate(d));
  }

  generate(): void {
    this.loading.set(true);
    this.planningService.generateSchedule(this.startDate()).subscribe({
      next: plan => { this.plan.set(plan); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  save(): void {
    this.loading.set(true);
    this.planningService.saveWeeklyPlan(this.startDate(), this.plan()).subscribe({
      next: () => this.loading.set(false),
      error: () => this.loading.set(false),
    });
  }

  private getCurrentMonday(): string {
    const d = new Date();
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    d.setDate(diff);
    return this.formatDate(d);
  }

  private formatDate(d: Date): string {
    return d.toISOString().split('T')[0];
  }
}
''')

write_file('app/pages/schedule/schedule.component.html', '''
<div class="page-container">
  <div class="page-header">
    <h1 class="page-title">Planificacion Semanal</h1>
    <div class="header-actions">
      <button mat-stroked-button (click)="generate()">
        <mat-icon>auto_fix_high</mat-icon> Generar
      </button>
      <button mat-flat-button color="primary" (click)="save()">
        <mat-icon>save</mat-icon> Guardar
      </button>
    </div>
  </div>

  <div class="week-nav">
    <button mat-icon-button (click)="prevWeek()"><mat-icon>chevron_left</mat-icon></button>
    <span class="week-label">Semana del {{ startDate() }}</span>
    <button mat-icon-button (click)="nextWeek()"><mat-icon>chevron_right</mat-icon></button>
  </div>

  @if (loading()) {
    <div class="loading-container"><mat-spinner diameter="40"></mat-spinner></div>
  } @else {
    <div class="schedule-grid">
      @for (day of plan(); track day.date) {
        <div class="day-column">
          <div class="day-header">
            <strong>{{ day.dayName }}</strong>
            <span class="day-date">{{ day.date }}</span>
          </div>
          @for (shift of ['morning', 'afternoon', 'night']; track shift) {
            <div class="shift-cell" [attr.data-shift]="shift">
              <span class="shift-label">{{ shift === 'morning' ? 'M' : shift === 'afternoon' ? 'T' : 'N' }}</span>
              <div class="assignments">
                @for (a of $any(day)[shift]; track a.workerId) {
                  <div class="assignment">
                    <span class="worker-name">{{ a.workerName || 'ID: ' + a.workerId }}</span>
                    <span class="worker-time">{{ a.start }}-{{ a.end }}</span>
                  </div>
                }
                @if ($any(day)[shift].length === 0) {
                  <span class="empty-cell">Sin asignar</span>
                }
              </div>
            </div>
          }
          <div class="rest-cell">
            <span class="shift-label">D</span>
            @if (day.rest.length > 0) {
              <span>{{ day.rest.length }} descanso(s)</span>
            } @else {
              <span class="empty-cell">-</span>
            }
          </div>
        </div>
      }
    </div>
  }
</div>
''')

write_file('app/pages/schedule/schedule.component.scss', r'''
.header-actions {
  display: flex;
  gap: var(--sp-s);
}

.week-nav {
  display: flex;
  align-items: center;
  gap: var(--sp-s);
  margin-bottom: var(--sp-l);
}

.week-label {
  font-family: var(--ff-display);
  font-size: var(--fs-16);
  font-weight: var(--fw-semibold);
}

.loading-container {
  display: flex;
  justify-content: center;
  padding: var(--sp-2xl);
}

.schedule-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: var(--sp-s);
  overflow-x: auto;
}

.day-column {
  background: var(--fondo-card);
  border: 1px solid var(--borde-general);
  border-radius: var(--br-default);
  overflow: hidden;
  min-width: 140px;
}

.day-header {
  padding: var(--sp-s) var(--sp-m);
  background: var(--color-acento);
  color: var(--color-acento-texto);
  text-align: center;
  display: flex;
  flex-direction: column;
}

.day-date {
  font-size: var(--fs-12);
}

.shift-cell {
  padding: var(--sp-s);
  border-bottom: 1px solid var(--borde-general);
  min-height: 60px;
}

.shift-cell[data-shift='morning'] { border-left: 3px solid var(--c-blue-500); }
.shift-cell[data-shift='afternoon'] { border-left: 3px solid var(--c-brand); }
.shift-cell[data-shift='night'] { border-left: 3px solid var(--c-purple-500); }

.shift-label {
  display: inline-block;
  font-size: var(--fs-12);
  font-weight: var(--fw-bold);
  color: var(--texto-secundario);
  margin-bottom: var(--sp-xxs);
}

.assignment {
  display: flex;
  flex-direction: column;
  padding: 2px 0;
}

.worker-name {
  font-size: var(--fs-13);
  font-weight: var(--fw-medium);
}

.worker-time {
  font-size: var(--fs-12);
  color: var(--texto-secundario);
}

.empty-cell {
  font-size: var(--fs-12);
  color: var(--texto-desactivado);
  font-style: italic;
}

.rest-cell {
  padding: var(--sp-s);
  font-size: var(--fs-13);
}

@media (max-width: 960px) {
  .schedule-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .schedule-grid {
    grid-template-columns: 1fr;
  }
}
''')

print('--- Pages done ---')
print()
print('=== ALL FRONTEND FILES GENERATED SUCCESSFULLY ===')
