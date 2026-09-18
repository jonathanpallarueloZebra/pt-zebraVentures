import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, shareReplay, tap } from 'rxjs';
import { environment } from '@env/environment';
import { EntityField } from '../interfaces/entity-field.interface';

@Injectable({ providedIn: 'root' })
export class EntityFieldService {
  private readonly url = `${environment.apiUrl}/entity-fields`;
  private cache = new Map<string, Observable<EntityField[]>>();

  constructor(private http: HttpClient) {}

  /** Campos ACTIVOS de una entidad (los formularios no deben ofrecer los
   *  retirados). El panel de administración usa su propio endpoint sin filtrar
   *  para poder gestionarlos y reactivarlos. */
  getAll(entityType?: string): Observable<EntityField[]> {
    const key = entityType ?? '__all__';
    if (!this.cache.has(key)) {
      const params = entityType ? `?entity_type=${entityType}&active=1` : '?active=1';
      this.cache.set(key, this.http.get<EntityField[]>(`${this.url}/${params}`).pipe(shareReplay(1)));
    }
    return this.cache.get(key)!;
  }

  /** TODOS los campos, incluidos los desactivados. Solo para el panel de
   *  administración, que necesita verlos para poder reactivarlos. */
  getAllIncludingInactive(entityType?: string): Observable<EntityField[]> {
    const params = entityType ? `?entity_type=${entityType}` : '';
    return this.http.get<EntityField[]>(`${this.url}/${params}`);
  }

  getByEntity(entityType: string): Observable<EntityField[]> {
    return this.http.get<EntityField[]>(`${this.url}/by-entity/${entityType}/`);
  }

  create(data: Partial<EntityField>): Observable<EntityField> {
    return this.http.post<EntityField>(`${this.url}/`, data).pipe(tap(() => this.invalidate()));
  }

  update(id: number, data: Partial<EntityField>): Observable<EntityField> {
    return this.http.patch<EntityField>(`${this.url}/${id}/`, data).pipe(tap(() => this.invalidate()));
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`).pipe(tap(() => this.invalidate()));
  }

  invalidate(): void {
    this.cache.clear();
  }
}
