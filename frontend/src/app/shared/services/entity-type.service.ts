import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, shareReplay, tap } from 'rxjs';
import { environment } from '@env/environment';
import { EntityTypeDef } from '../interfaces/entity-field.interface';

@Injectable({ providedIn: 'root' })
export class EntityTypeService {
  private readonly url = `${environment.apiUrl}/entity-types`;
  private allCache$: Observable<EntityTypeDef[]> | null = null;
  private slugCache = new Map<string, Observable<EntityTypeDef>>();

  constructor(private http: HttpClient) {}

  getAll(): Observable<EntityTypeDef[]> {
    if (!this.allCache$) {
      this.allCache$ = this.http.get<EntityTypeDef[]>(`${this.url}/`).pipe(shareReplay(1));
    }
    return this.allCache$;
  }

  get(slug: string): Observable<EntityTypeDef> {
    if (!this.slugCache.has(slug)) {
      this.slugCache.set(slug, this.http.get<EntityTypeDef>(`${this.url}/${slug}/`).pipe(shareReplay(1)));
    }
    return this.slugCache.get(slug)!;
  }

  create(data: Partial<EntityTypeDef>): Observable<EntityTypeDef> {
    return this.http.post<EntityTypeDef>(`${this.url}/`, data).pipe(tap(() => this.invalidate()));
  }

  update(slug: string, data: Partial<EntityTypeDef>): Observable<EntityTypeDef> {
    return this.http.patch<EntityTypeDef>(`${this.url}/${slug}/`, data).pipe(tap(() => this.invalidate()));
  }

  delete(slug: string): Observable<void> {
    return this.http.delete<void>(`${this.url}/${slug}/`).pipe(tap(() => this.invalidate()));
  }

  invalidate(): void {
    this.allCache$ = null;
    this.slugCache.clear();
  }
}
