import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, shareReplay, map } from 'rxjs';
import { environment } from '@env/environment';
import { Kind, KindAttribute, KindValue, KindValueAttribute } from '../interfaces/catalog.interface';

@Injectable({ providedIn: 'root' })
export class CatalogService {
  private readonly url = `${environment.apiUrl}/catalog`;
  private cache = new Map<string, Observable<Kind>>();

  constructor(private http: HttpClient) {}

  getKinds(): Observable<Kind[]> {
    return this.http.get<Kind[]>(`${this.url}/kinds/`);
  }

  getKind(id: number): Observable<Kind> {
    return this.http.get<Kind>(`${this.url}/kinds/${id}/`);
  }

  getKindByCode(code: string): Observable<Kind> {
    if (!this.cache.has(code)) {
      this.cache.set(
        code,
        this.http.get<Kind>(`${this.url}/kinds/by-code/${code}/`).pipe(shareReplay(1)),
      );
    }
    return this.cache.get(code)!;
  }

  getValues(kindCode: string): Observable<KindValue[]> {
    return this.getKindByCode(kindCode).pipe(
      map(kind => kind.values.filter(v => v.active)),
    );
  }

  createKind(data: Partial<Kind>): Observable<Kind> {
    return this.http.post<Kind>(`${this.url}/kinds/`, data);
  }

  updateKind(id: number, data: Partial<Kind>): Observable<Kind> {
    return this.http.put<Kind>(`${this.url}/kinds/${id}/`, data);
  }

  deleteKind(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/kinds/${id}/`)
  }

  createValue(data: Partial<KindValue>): Observable<KindValue> {
    return this.http.post<KindValue>(`${this.url}/values/`, data);
  }

  updateValue(id: number, data: Partial<KindValue>): Observable<KindValue> {
    return this.http.put<KindValue>(`${this.url}/values/${id}/`, data);
  }

  deleteValue(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/values/${id}/`);
  }

  createAttribute(data: Partial<KindAttribute>): Observable<KindAttribute> {
    return this.http.post<KindAttribute>(`${this.url}/attributes/`, data);
  }

  updateAttribute(id: number, data: Partial<KindAttribute>): Observable<KindAttribute> {
    return this.http.put<KindAttribute>(`${this.url}/attributes/${id}/`, data);
  }

  deleteAttribute(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/attributes/${id}/`);
  }

  setValueAttribute(kindValueId: number, attributeId: number, value: string, existingId?: number): Observable<KindValueAttribute> {
    if (existingId) {
      return this.http.put<KindValueAttribute>(`${this.url}/value-attributes/${existingId}/`, {
        kind_value: kindValueId, attribute: attributeId, value,
      });
    }
    return this.http.post<KindValueAttribute>(`${this.url}/value-attributes/`, {
      kind_value: kindValueId, attribute: attributeId, value,
    });
  }

  clearCache(code?: string): void {
    if (code) this.cache.delete(code);
    else this.cache.clear();
  }
}
