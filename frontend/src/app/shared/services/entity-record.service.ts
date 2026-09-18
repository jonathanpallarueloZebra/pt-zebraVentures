import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, shareReplay, tap } from 'rxjs';
import { environment } from '@env/environment';
import { EntityRecord } from '../interfaces/entity-field.interface';

@Injectable({ providedIn: 'root' })
export class EntityRecordService {
  private readonly url = `${environment.apiUrl}/entity-records`;
  private cache = new Map<string, Observable<EntityRecord[]>>();

  constructor(private http: HttpClient) {}

  getAll(entityType?: string): Observable<EntityRecord[]> {
    const key = entityType ?? '__all__';
    if (!this.cache.has(key)) {
      const params = entityType ? `?entity_type=${entityType}` : '';
      this.cache.set(key, this.http.get<EntityRecord[]>(`${this.url}/${params}`).pipe(shareReplay(1)));
    }
    return this.cache.get(key)!;
  }

  get(id: number): Observable<EntityRecord> {
    return this.http.get<EntityRecord>(`${this.url}/${id}/`);
  }

  create(data: { entity_type: string; data: Record<string, any> }): Observable<EntityRecord> {
    return this.http.post<EntityRecord>(`${this.url}/`, data).pipe(tap(() => this.invalidate(data.entity_type)));
  }

  update(id: number, data: Partial<EntityRecord>): Observable<EntityRecord> {
    return this.http.patch<EntityRecord>(`${this.url}/${id}/`, data).pipe(tap(() => this.invalidate()));
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`).pipe(tap(() => this.invalidate()));
  }

  invalidate(entityType?: string): void {
    if (entityType) {
      this.cache.delete(entityType);
      this.cache.delete('__all__');
    } else {
      this.cache.clear();
    }
  }

  exportExcel(entityType: string): Observable<Blob> {
    return this.http.get(`${this.url}/export/?entity_type=${entityType}`, { responseType: 'blob' });
  }
  }

