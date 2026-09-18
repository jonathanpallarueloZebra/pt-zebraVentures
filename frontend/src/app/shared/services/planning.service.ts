import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';
import { WeeklyPlan, DayPlan, ValidationResult } from '../interfaces/planning.interface';
import { Worker } from '../interfaces/worker.interface';

export interface ShiftEntry {
  worker_id: number;
  worker_name: string;
  shift_type: string;
  start: string;
  end: string;
  areas: string[];
}

/** Fila de horas extra: horas del plan vs. contrato (GET /planning/overtime/). */
export interface OvertimeRow {
  worker_id: number;
  name: string;
  worked: number;
  contract: number;
  overtime: number;
}

/** Estado de planificación de una semana, agregando todos los ámbitos. */
export interface WeekStatus {
  start: string;
  total_scopes: number;
  planned_scopes: number;
  pending_scopes: number;
  /** Códigos de las tiendas que faltan por planificar ("T03", "T07"…). */
  pending_names?: string[];
  /** ID de la primera tienda pendiente, para navegar directo a ella. */
  first_pending_scope?: number | null;
  planned: boolean;
  /**
   * `{scope_id: 'error'|'warning'}` de las tiendas con problemas en su plan
   * guardado. Permite marcar con ▲/● TODAS las tiendas del selector, no solo la
   * abierta (su plan es el único que el front tiene cargado).
   */
  scope_severities?: Record<string, 'error' | 'warning'>;
}

// ── Diagnóstico de planificación (GET /planning/diagnostics/) ──────────────
export interface DiagWorker { worker_id: number; name: string; areas?: string[]; start?: string; end?: string; in_scope?: boolean; reason?: string; }
/** Los no asignados de un día agrupados por la causa que les impidió entrar. */
export interface DiagReason { reason: string; count: number; workers: DiagWorker[]; }
/** Trabajadores de un turno agrupados por sección (encargado primero).
 *  El tope de área es POR TURNO, así que `used`/`cap` viven aquí. */
export interface DiagGroup { area: string; used: number; cap: number | null; workers: DiagWorker[]; }
export interface DiagShift { code: string; label: string; count: number; groups: DiagGroup[]; }
export interface DiagDay {
  date: string; day_name: string; closed: boolean; has_plan: boolean;
  assigned: number; shifts: DiagShift[];
  unassigned: DiagWorker[]; unassigned_by_reason: DiagReason[]; absent: DiagWorker[];
}
/** Sección×turno sin cubrir. `staff` = personas que podrían cubrirlo (0 = hueco
 *  estructural: no existe ese personal, no lo puede resolver el planificador). */
export interface DiagGap { area: string; shift: string; staff: number; }
export interface DiagScope {
  scope: number; scope_name: string; has_plan: boolean;
  eligible: number; fixed_staff: number;
  total_assignments: number; workers_with_shift: number;
  without_shift: DiagWorker[]; days: DiagDay[];
  gaps_coverable: DiagGap[]; gaps_structural: DiagGap[];
}

export interface BulkGenerationResult {
  scope: number;
  status: 'success' | 'error';
  plan?: DayPlan[];
  warnings?: string[];
  error?: string;
}

@Injectable({ providedIn: 'root' })
export class PlanningService {
  private readonly url = `${environment.apiUrl}/planning`;
  private readonly restrictionsUrl = `${environment.apiUrl}/restrictions`;
  private readonly workersUrl = `${environment.apiUrl}/workers`;

  /** Drafts survive component destruction: key = "startDate_scopeId" */
  private _drafts = new Map<string, DayPlan[]>();

  constructor(private http: HttpClient) {}

  // ── Draft management ──────────────────────────────────────────────────
  getDraft(startDate: string, scopeId: number): DayPlan[] | undefined {
    return this._drafts.get(`${startDate}_${scopeId}`);
  }

  setDraft(startDate: string, scopeId: number, plan: DayPlan[]): void {
    this._drafts.set(`${startDate}_${scopeId}`, plan);
  }

  clearDraft(startDate: string, scopeId: number): void {
    this._drafts.delete(`${startDate}_${scopeId}`);
  }

  hasDraft(startDate: string, scopeId: number): boolean {
    return this._drafts.has(`${startDate}_${scopeId}`);
  }

  /**
   * IDs de los ámbitos con borrador SIN GUARDAR en esa semana.
   *
   * Sirve para avisar antes de generar: el backend solo respeta los planes
   * GUARDADOS al repartir, así que un borrador de otra tienda no reserva a
   * nadie y la misma persona puede acabar asignada dos veces el mismo día.
   */
  draftScopeIds(startDate: string): number[] {
    const prefijo = `${startDate}_`;
    return [...this._drafts.keys()]
      .filter(k => k.startsWith(prefijo))
      .map(k => Number(k.slice(prefijo.length)))
      .filter(n => Number.isFinite(n));
  }

  getWeeklyPlan(startDate: string, scope = 0): Observable<WeeklyPlan> {
    const q = scope ? `?start=${startDate}&scope=${scope}` : `?start=${startDate}`;
    return this.http.get<WeeklyPlan>(`${this.url}/weekly-plan/${q}`);
  }

  saveWeeklyPlan(start: string, plan: DayPlan[], scope = 0): Observable<WeeklyPlan> {
    return this.http.post<WeeklyPlan>(`${this.url}/weekly-plan/`, { start, plan, scope });
  }

  generateSchedule(startDate: string, scope = 0): Observable<{plan: DayPlan[]; warnings: string[]}> {
    return this.http.post<{plan: DayPlan[]; warnings: string[]}>(`${this.url}/schedule/generate/`, { startDate, scope });
  }

  generateBulk(startDate: string, scopes: number[]): Observable<{results: BulkGenerationResult[]}> {
    return this.http.post<{results: BulkGenerationResult[]}>(`${this.url}/schedule/generate-bulk/`, { startDate, scopes });
  }

  validatePlan(plan: DayPlan[], scopeRecordId?: number): Observable<ValidationResult> {
    const body: any = { plan };
    if (scopeRecordId) body.scope_record_id = scopeRecordId;
    return this.http.post<ValidationResult>(`${this.restrictionsUrl}/validate/`, body);
  }

  copyFromPreviousWeek(startDate: string, scope = 0): Observable<WeeklyPlan> {
    return this.http.post<WeeklyPlan>(`${this.url}/weekly-plan/copy-previous/`, { start: startDate, scope });
  }

  /** Get all shift assignments for a given month (YYYY-MM), optionally filtered by worker. */
  getMonthPlan(month: string, workerId?: number): Observable<Record<string, ShiftEntry[]>> {
    let url = `${this.url}/weekly-plan/month/?month=${month}`;
    if (workerId) url += `&worker=${workerId}`;
    return this.http.get<Record<string, ShiftEntry[]>>(url);
  }

  /** Get the Worker profile linked to the currently authenticated user. */
  getMyWorker(): Observable<Worker> {
    return this.http.get<Worker>(`${this.workersUrl}/me/`);
  }

  /** Horas extra de una semana (todos los ámbitos si no se pasa scope).
   *  Solo devuelve quien excede su contrato, de mayor a menor exceso. */
  getOvertime(start: string, scope?: number): Observable<{ start: string; rows: OvertimeRow[] }> {
    const q = scope !== undefined ? `?start=${start}&scope=${scope}` : `?start=${start}`;
    return this.http.get<{ start: string; rows: OvertimeRow[] }>(`${this.url}/overtime/${q}`);
  }

  /** Diagnóstico de la planificación guardada de una semana. Solo lectura:
   *  no genera nada. Sin `scope` devuelve todos los ámbitos. */
  getDiagnostics(start: string, scope?: number): Observable<{ start: string; scopes: DiagScope[] }> {
    const q = scope !== undefined ? `?start=${start}&scope=${scope}` : `?start=${start}`;
    return this.http.get<{ start: string; scopes: DiagScope[] }>(`${this.url}/diagnostics/${q}`);
  }

  /** Estado de planificación de una o varias semanas (lunes en ISO). */
  getWeekStatus(starts: string[]): Observable<{ weeks: WeekStatus[] }> {
    const q = starts.map(s => `start=${s}`).join('&');
    return this.http.get<{ weeks: WeekStatus[] }>(`${this.url}/week-status/?${q}`);
  }
}
