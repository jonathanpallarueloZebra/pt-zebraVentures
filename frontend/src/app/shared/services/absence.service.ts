import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, shareReplay, tap } from 'rxjs';
import { environment } from '@env/environment';
import { AbsenceType, AbsenceRequest } from '../interfaces/absence.interface';

@Injectable({ providedIn: 'root' })
export class AbsenceService {
  private readonly url = `${environment.apiUrl}/absences`;
  private requestsCache = new Map<string, Observable<AbsenceRequest[]>>();

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
    const key = query || '__all__';
    if (!this.requestsCache.has(key)) {
      this.requestsCache.set(key,
        this.http.get<AbsenceRequest[]>(`${this.url}/requests/${query}`).pipe(shareReplay(1))
      );
    }
    return this.requestsCache.get(key)!;
  }

  // ── Excel: mismo patron que WorkerService ────────────────────

  /** Exporta el listado de ausencias (AC-1). */
  exportExcel(): Observable<Blob> {
    return this.http.get(`${this.url}/requests/export/`, { responseType: 'blob' });
  }

  /** Plantilla de ejemplo con los empleados vigentes precargados (AC-3/AC-4). */
  downloadImportTemplate(): Observable<Blob> {
    return this.http.get(`${this.url}/requests/import-template/`, { responseType: 'blob' });
  }

  /** Importa ausencias (AC-2). Devuelve el resumen para pintar el aviso. */
  importExcel(file: File): Observable<{ created: number; errors: string[]; total_rows: number }> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<{ created: number; errors: string[]; total_rows: number }>(
      `${this.url}/requests/import-excel/`, formData,
    ).pipe(tap(() => this.invalidate()));
  }

  /**
   * Revisa el Excel SIN importar nada: devuelve cuantas ausencias se crearian
   * y que filas fallan. Se llama al soltar el fichero, para poder avisar antes
   * de que el usuario confirme.
   */
  revisarExcel(file: File): Observable<{ created: number; errors: string[]; total_rows: number; dry_run: boolean }> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<{ created: number; errors: string[]; total_rows: number; dry_run: boolean }>(
      `${this.url}/requests/import-excel/?revisar=1`, formData,
    );
  }

  createRequest(data: Partial<AbsenceRequest>): Observable<AbsenceRequest> {
    return this.http.post<AbsenceRequest>(`${this.url}/requests/`, data).pipe(
      tap(() => this.invalidate())
    );
  }

  /** Editar una ausencia (p.ej. cerrar una indefinida poniéndole fecha fin, AC-5). */
  updateRequest(id: number, data: Partial<AbsenceRequest>): Observable<AbsenceRequest> {
    return this.http.patch<AbsenceRequest>(`${this.url}/requests/${id}/`, data).pipe(
      tap(() => this.invalidate())
    );
  }

  /** Eliminar una ausencia. */
  deleteRequest(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/requests/${id}/`).pipe(
      tap(() => this.invalidate())
    );
  }

  approve(id: number): Observable<AbsenceRequest> {
    return this.http.patch<AbsenceRequest>(`${this.url}/requests/${id}/approve/`, {}).pipe(
      tap(() => this.invalidate())
    );
  }

  reject(id: number): Observable<AbsenceRequest> {
    return this.http.patch<AbsenceRequest>(`${this.url}/requests/${id}/reject/`, {}).pipe(
      tap(() => this.invalidate())
    );
  }

  invalidate(): void {
    this.requestsCache.clear();
  }
}
