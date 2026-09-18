import { Component, OnInit, signal, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { MatIconModule } from '@angular/material/icon';
import { ZbSkeletonComponent } from '@app/shared/components/zb-skeleton/zb-skeleton.component';
import { ZbPageHeaderComponent } from '@app/shared/components/zb-page-header/zb-page-header.component';
import { AuthService } from '@app/auth/services/auth.service';
import { PlanningService, OvertimeRow, WeekStatus } from '@app/shared/services/planning.service';
import { AbsenceService } from '@app/shared/services/absence.service';
import { WorkerService } from '@app/shared/services/worker.service';
import { Worker } from '@app/shared/interfaces/worker.interface';
import { AbsenceRequest } from '@app/shared/interfaces/absence.interface';

/** Un aviso de la fila "Urgente a resolver" (Figma 2422:16488). */
interface UrgentAlert {
  type: 'error' | 'warning' | 'info';
  icon: string;          // material icon
  text: string;
  actionLabel: string;   // "Resolver" / "Planificar"
  week: string;          // lunes de la semana destino (YYYY-MM-DD) → /schedule?week=
  scope?: number | null; // tienda pendiente → /schedule?scope=; sin ella, la 1ª
}

/** Acceso directo a una planificación semanal (Figma 2435:23208). */
interface PlanShortcut {
  range: string;         // "29/06 - 05/07"
  label: string;         // "Semana en curso" / "Semana próxima"
  week: string;          // lunes (YYYY-MM-DD)
}

/** Acceso directo a planificación, con su estado real (nº de tiendas pendientes). */
interface PlanShortcutView extends PlanShortcut {
  pending: number;       // ámbitos sin planificar (0 = semana completa)
  total: number;         // ámbitos totales
  pendingNames?: string[];  // códigos de las tiendas que faltan ("T03"…)
}

/** Tarjeta-stat de la fila tertiary (Figma 2464:44128). */
interface WeekStat {
  value: number;
  label: string;         // "Esta Semana" / "Próxima"
  range: string;         // "26/06 - 27/06"
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    MatIconModule,
    ZbSkeletonComponent,
    ZbPageHeaderComponent,
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
  private authService = inject(AuthService);
  private planningService = inject(PlanningService);
  private absenceService = inject(AbsenceService);
  private workerService = inject(WorkerService);
  private router = inject(Router);

  isAdmin = computed(() => !!this.authService.currentUser()?.is_staff);
  myWorker = signal<Worker | null>(null);

  loading = signal(true);
  profileReady = signal(!!this.authService.currentUser());

  /** Fila 1 — avisos urgentes ordenados por severidad. */
  urgentAlerts = signal<UrgentAlert[]>([]);
  /** Fila 2A — accesos a planificación (esta / próxima semana) con su estado. */
  planShortcuts = signal<PlanShortcutView[]>([]);
  /** Fila 2B — horas extra por empleado (esta semana). */
  overtimeRows = signal<OvertimeRow[]>([]);
  overtimeRange = signal('');
  /** Fila 3A — ausencias esta / próxima semana. */
  absenceStats = signal<WeekStat[]>([]);
  /** Fila 3B — empleados ETT esta / próxima semana. */
  ettStats = signal<WeekStat[]>([]);

  ngOnInit(): void {
    if (!this.authService.currentUser()) {
      this.authService.getProfile().subscribe({
        next: () => { this.profileReady.set(true); this.init(); },
        error: () => this.loading.set(false),
      });
    } else {
      this.profileReady.set(true);
      this.init();
    }
  }

  private init(): void {
    const [thisWeek, nextWeek] = this.weekRanges();

    // Accesos a planificación — visibles de inmediato (la navegación no depende
    // del backend); el estado real (tiendas pendientes) llega en initAdmin.
    this.planShortcuts.set([
      { range: thisWeek.label, label: 'Semana en curso', week: thisWeek.monday, pending: 0, total: 0 },
      { range: nextWeek.label, label: 'Semana próxima', week: nextWeek.monday, pending: 0, total: 0 },
    ]);
    this.overtimeRange.set(thisWeek.label);

    if (this.isAdmin()) {
      this.initAdmin(thisWeek, nextWeek);
    } else {
      this.initEmployee(thisWeek, nextWeek);
    }
  }

  private initAdmin(thisWeek: WeekRange, nextWeek: WeekRange): void {
    forkJoin({
      absences: this.absenceService.getRequests({ status: 'approved' }),
      workers: this.workerService.getActive(),
      // Horas extra reales de la semana en curso (suma del plan vs contrato),
      // agregando todos los ámbitos. Un fallo aquí no debe tumbar el panel.
      overtime: this.planningService.getOvertime(thisWeek.monday).pipe(
        catchError(() => of({ start: thisWeek.monday, rows: [] as OvertimeRow[] })),
      ),
      // Estado de planificación de ambas semanas (cuántas tiendas faltan).
      weeks: this.planningService.getWeekStatus([thisWeek.monday, nextWeek.monday]).pipe(
        catchError(() => of({ weeks: [] as WeekStatus[] })),
      ),
    }).subscribe({
      next: ({ absences, workers, overtime, weeks }) => {
        this.buildAbsenceStats(absences, thisWeek, nextWeek);

        const statusOf = (monday: string) => weeks.weeks.find(w => w.start === monday);
        this.buildUrgentAlerts(statusOf(thisWeek.monday), statusOf(nextWeek.monday), thisWeek, nextWeek);
        this.buildPlanShortcuts(statusOf(thisWeek.monday), statusOf(nextWeek.monday), thisWeek, nextWeek);

        this.overtimeRows.set(overtime.rows);
        this.buildEttStats(workers, absences, thisWeek, nextWeek);

        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  private initEmployee(thisWeek: WeekRange, nextWeek: WeekRange): void {
    this.planningService.getMyWorker().subscribe({
      next: (worker) => {
        this.myWorker.set(worker);
        this.absenceService.getRequests({ worker: worker.id }).subscribe({
          next: (reqs) => {
            const approved = reqs.filter(a => a.status === 'approved');
            this.buildAbsenceStats(approved, thisWeek, nextWeek);
            this.urgentAlerts.set([]);
            this.overtimeRows.set([]);
            this.ettStats.set([]);
            this.loading.set(false);
          },
          error: () => this.loading.set(false),
        });
      },
      error: () => this.loading.set(false),
    });
  }

  /** Avisos urgentes a partir del estado real de planificación.
   *  Solo se avisa de lo que falta: una semana ya planificada no genera aviso.
   *  La semana en curso sin planificar es un error (ya está empezada); la
   *  próxima es un aviso. */
  private buildUrgentAlerts(
    current: WeekStatus | undefined,
    next: WeekStatus | undefined,
    thisWeek: WeekRange,
    nextWeek: WeekRange,
  ): void {
    const alerts: UrgentAlert[] = [];
    // Se nombran las tiendas que faltan (hasta 3) para no tener que entrar a
    // buscarlas: "faltan T03, T07" es accionable, "faltan 2 de 15" no.
    const pendingText = (s: WeekStatus) => {
      if (s.planned_scopes === 0) return 'sin planificar';
      const names = s.pending_names ?? [];
      if (!names.length) return `faltan ${s.pending_scopes} de ${s.total_scopes}`;
      const shown = names.slice(0, 3).join(', ');
      const extra = names.length > 3 ? ` y ${names.length - 3} más` : '';
      return `${names.length === 1 ? 'falta' : 'faltan'} ${shown}${extra}`;
    };

    if (current && current.pending_scopes > 0) {
      alerts.push({
        type: 'error',
        icon: 'error',
        text: `Semana en curso ${thisWeek.label}: ${pendingText(current)}`,
        actionLabel: 'Resolver',
        week: thisWeek.monday,
        scope: current.first_pending_scope ?? null,
      });
    }
    if (next && next.pending_scopes > 0) {
      alerts.push({
        type: 'warning',
        icon: 'warning',
        text: `Semana próxima ${nextWeek.label}: ${pendingText(next)}`,
        actionLabel: 'Planificar',
        week: nextWeek.monday,
        scope: next.first_pending_scope ?? null,
      });
    }
    this.urgentAlerts.set(alerts);
  }

  /** Accesos a planificación anotados con las tiendas que faltan por planificar. */
  private buildPlanShortcuts(
    current: WeekStatus | undefined,
    next: WeekStatus | undefined,
    thisWeek: WeekRange,
    nextWeek: WeekRange,
  ): void {
    this.planShortcuts.set([
      {
        range: thisWeek.label, label: 'Semana en curso', week: thisWeek.monday,
        pending: current?.pending_scopes ?? 0, total: current?.total_scopes ?? 0,
        pendingNames: current?.pending_names ?? [],
      },
      {
        range: nextWeek.label, label: 'Semana próxima', week: nextWeek.monday,
        pending: next?.pending_scopes ?? 0, total: next?.total_scopes ?? 0,
        pendingNames: next?.pending_names ?? [],
      },
    ]);
  }

  /** Cuenta ausencias que solapan cada rango semanal (dato real).
   *  Una ausencia indefinida (end_date null) solapa desde su inicio en adelante. */
  private buildAbsenceStats(absences: AbsenceRequest[], thisWeek: WeekRange, nextWeek: WeekRange): void {
    const count = (w: WeekRange) =>
      absences.filter(a => a.start_date <= w.sunday && (!a.end_date || w.monday <= a.end_date)).length;
    this.absenceStats.set([
      { value: count(thisWeek), label: 'Esta Semana', range: thisWeek.label },
      { value: count(nextWeek), label: 'Próxima', range: nextWeek.label },
    ]);
  }

  /** Cuenta empleados ETT disponibles cada semana: activos con
   *  tipo_contrato='ett' menos los que tienen una ausencia aprobada que
   *  solapa la semana. `workers` ya viene filtrado a activos (getActive).
   *  El valor de un catalog_select se guarda como código en custom_data. */
  private buildEttStats(
    workers: Worker[],
    absences: AbsenceRequest[],
    thisWeek: WeekRange,
    nextWeek: WeekRange,
  ): void {
    const ett = workers.filter(w => w.custom_data?.['tipo_contrato'] === 'ett');
    const available = (w: WeekRange) =>
      ett.filter(worker => !absences.some(a =>
        a.worker === worker.id && a.start_date <= w.sunday && (!a.end_date || w.monday <= a.end_date),
      )).length;
    this.ettStats.set([
      { value: available(thisWeek), label: 'Esta Semana', range: thisWeek.label },
      { value: available(nextWeek), label: 'Próxima', range: nextWeek.label },
    ]);
  }

  /** Abre el planificador en esa semana. Con `scope`, además selecciona la
   *  tienda pendiente: el aviso "Resolver" lleva directo a lo que falta en vez
   *  de dejar al usuario buscando cuál era. */
  goToPlan(week: string, scope?: number | null): void {
    const queryParams: Record<string, string | number> = { week };
    if (scope) queryParams['scope'] = scope;
    this.router.navigate(['/schedule'], { queryParams });
  }

  // ── Utilidades de fecha ────────────────────────────────────────────────

  /** [semana en curso, semana próxima] con lunes/domingo y etiqueta "dd/mm - dd/mm". */
  private weekRanges(): [WeekRange, WeekRange] {
    const today = new Date();
    const monday = new Date(today);
    monday.setDate(today.getDate() - ((today.getDay() + 6) % 7)); // lunes de esta semana
    const nextMonday = new Date(monday);
    nextMonday.setDate(monday.getDate() + 7);
    return [this.rangeFrom(monday), this.rangeFrom(nextMonday)];
  }

  private rangeFrom(monday: Date): WeekRange {
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    return {
      monday: this.iso(monday),
      sunday: this.iso(sunday),
      label: `${this.dm(monday)} - ${this.dm(sunday)}`,
    };
  }

  private iso(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  private dm(d: Date): string {
    return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`;
  }
}

interface WeekRange {
  monday: string;  // YYYY-MM-DD
  sunday: string;  // YYYY-MM-DD
  label: string;   // "dd/mm - dd/mm"
}
