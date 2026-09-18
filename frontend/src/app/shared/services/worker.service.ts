import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, shareReplay, tap } from 'rxjs';
import { environment } from '@env/environment';
import { Worker } from '../interfaces/worker.interface';

@Injectable({ providedIn: 'root' })
export class WorkerService {
  private readonly url = `${environment.apiUrl}/workers`;
  private activeCache$: Observable<Worker[]> | null = null;
  private allCache$: Observable<Worker[]> | null = null;

  constructor(private http: HttpClient) {}

  getActive(): Observable<Worker[]> {
    if (!this.activeCache$) {
      this.activeCache$ = this.http.get<Worker[]>(`${this.url}/`).pipe(shareReplay(1));
    }
    return this.activeCache$;
  }

  getAll(): Observable<Worker[]> {
    if (!this.allCache$) {
      this.allCache$ = this.http.get<Worker[]>(`${this.url}/all/`).pipe(shareReplay(1));
    }
    return this.allCache$;
  }

  getRoles(): Observable<string[]> {
    return this.http.get<string[]>(`${this.url}/roles/`);
  }

  getById(id: number): Observable<Worker> {
    return this.http.get<Worker>(`${this.url}/${id}/`);
  }

  create(data: any): Observable<Worker> {
    return this.http.post<Worker>(`${this.url}/`, data).pipe(tap(() => this.invalidate()));
  }

  update(id: number, data: any): Observable<Worker> {
    return this.http.put<Worker>(`${this.url}/${id}/`, data).pipe(tap(() => this.invalidate()));
  }

  patch(id: number, data: any): Observable<Worker> {
    return this.http.patch<Worker>(`${this.url}/${id}/`, data).pipe(tap(() => this.invalidate()));
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`).pipe(tap(() => this.invalidate()));
  }

  exportExcel(): Observable<Blob> {
    return this.http.get(`${this.url}/export/`, { responseType: 'blob' });
  }

  downloadImportTemplate(): Observable<Blob> {
    return this.http.get(`${this.url}/import-template/`, { responseType: 'blob' });
  }

  importExcel(file: File): Observable<{ created: number; errors: string[]; total_rows: number }> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<{ created: number; errors: string[]; total_rows: number }>(
      `${this.url}/import-excel/`, formData
    ).pipe(tap(() => this.invalidate()));
  }

  invalidate(): void {
    this.activeCache$ = null;
    this.allCache$ = null;
  }
}
