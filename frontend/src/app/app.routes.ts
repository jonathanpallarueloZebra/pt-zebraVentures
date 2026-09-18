import { Routes } from '@angular/router';
import { authGuard } from './auth/guards/auth.guard';
import { superAdminGuard } from './auth/guards/super-admin.guard';
import { staffGuard } from './auth/guards/staff.guard';
import { unsavedChangesGuard } from './shared/guards/unsaved-changes.guard';
import { ShellComponent } from './layout/shell/shell.component';

export const routes: Routes = [
  // ── Design Lab (dev only) ─────────────────────────────────
  {
    path: 'lab',
    loadComponent: () => import('./pages/design-lab/design-lab.component').then(m => m.DesignLabComponent),
  },
  // ── Admin panel (internal) ────────────────────────────────
  {
    path: 'adminzebra/login',
    loadComponent: () => import('./admin-panel/admin-login/admin-login.component').then(m => m.AdminLoginComponent),
  },
  {
    path: 'adminzebra',
    canActivate: [superAdminGuard],
    loadComponent: () => import('./admin-panel/admin-shell/admin-shell.component').then(m => m.AdminShellComponent),
  },
  // ── Public auth ───────────────────────────────────────────
  {
    path: 'login',
    loadComponent: () => import('./auth/login/login.component').then(m => m.LoginComponent),
  },
  {
    path: 'register',
    loadComponent: () => import('./auth/register/register.component').then(m => m.RegisterComponent),
  },
  {
    path: 'forgot-password',
    loadComponent: () => import('./auth/forgot-password/forgot-password.component').then(m => m.ForgotPasswordComponent),
  },
  {
    path: 'reset-password',
    loadComponent: () => import('./auth/reset-password/reset-password.component').then(m => m.ResetPasswordComponent),
  },
  {
    path: 'set-password',
    loadComponent: () => import('./auth/set-password/set-password.component').then(m => m.SetPasswordComponent),
  },
  // ── Client app ────────────────────────────────────────────
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
        path: 'profile',
        loadComponent: () => import('./pages/profile/profile.component').then(m => m.ProfileComponent),
      },
      {
        path: 'absence-request',
        loadComponent: () => import('./pages/absence-request/absence-request.component').then(m => m.AbsenceRequestComponent),
      },
      {
        path: 'schedule',
        canActivate: [staffGuard],
        // Con un borrador sin guardar, salir por el menú avisa igual que el
        // botón Cancelar (antes se perdía en silencio).
        canDeactivate: [unsavedChangesGuard],
        loadComponent: () => import('./pages/schedule/schedule.component').then(m => m.ScheduleComponent),
      },
      {
        path: 'employees',
        canActivate: [staffGuard],
        loadComponent: () => import('./pages/employees/employees.component').then(m => m.EmployeesComponent),
      },
      {
        path: 'entities/:slug',
        canActivate: [staffGuard],
        loadComponent: () => import('./pages/entity-records/entity-records.component').then(m => m.EntityRecordsComponent),
      },
      {
        path: 'planificacion',
        canActivate: [staffGuard],
        loadComponent: () => import('./pages/planificacion/planificacion.component').then(m => m.PlanificacionComponent),
      },
      {
        path: 'restrictions',
        canActivate: [staffGuard],
        loadComponent: () => import('./pages/restrictions/restrictions.component').then(m => m.RestrictionsComponent),
      },
      {
        path: 'closed-days',
        canActivate: [staffGuard],
        loadComponent: () => import('./pages/closed-days/closed-days.component').then(m => m.ClosedDaysPageComponent),
      },
      {
        path: 'absences',
        canActivate: [staffGuard],
        loadComponent: () => import('./pages/absences/absences.component').then(m => m.AbsencesComponent),
      },
      {
        path: 'catalog',
        canActivate: [staffGuard],
        loadComponent: () => import('./pages/catalog/catalog.component').then(m => m.CatalogComponent),
      },
      {
        path: 'users',
        canActivate: [staffGuard],
        loadComponent: () => import('./users/user-list/user-list.component').then(m => m.UserListComponent),
      },
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
    ],
  },
  { path: '**', redirectTo: 'login' },
];

