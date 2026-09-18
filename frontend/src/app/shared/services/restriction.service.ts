import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, shareReplay } from 'rxjs';
import { environment } from '@env/environment';
import { Restriction, EngineSchema, ValidationResult } from '../interfaces/restriction.interface';

@Injectable({ providedIn: 'root' })
export class RestrictionService {
  private readonly url = `${environment.apiUrl}/restrictions`;
  private engineSchemaCache$?: Observable<Record<string, EngineSchema>>;

  constructor(private http: HttpClient) {}

  getAll(): Observable<Restriction[]> {
    return this.http.get<Restriction[]>(`${this.url}/`);
  }

  create(data: Partial<Restriction>): Observable<Restriction> {
    return this.http.post<Restriction>(`${this.url}/`, data);
  }

  update(id: number, data: Partial<Restriction>): Observable<Restriction> {
    return this.http.patch<Restriction>(`${this.url}/${id}/`, data);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`);
  }

  /** Duplicate a customizable restriction as an independent copy. */
  duplicate(id: number, data: { name?: string; scope_records?: number[] } = {}): Observable<Restriction> {
    return this.http.post<Restriction>(`${this.url}/${id}/duplicate/`, data);
  }

  getEngineSchema(): Observable<Record<string, EngineSchema>> {
    if (!this.engineSchemaCache$) {
      this.engineSchemaCache$ = this.http.get<Record<string, EngineSchema>>(`${this.url}/engine_schema/`).pipe(
        shareReplay(1),
      );
    }
    return this.engineSchemaCache$;
  }

  validate(plan: any[]): Observable<ValidationResult> {
    return this.http.post<ValidationResult>(`${this.url}/validate/`, { plan });
  }

  getConstraints(): Observable<any> {
    return this.http.get(`${this.url}/constraints/`);
  }

  getWorkerFields(): Observable<WorkerFieldDef[]> {
    return this.http.get<WorkerFieldDef[]>(`${this.url}/worker-fields/`);
  }

  chat(message: string, history: {role: string; content: string}[]): Observable<{response: string}> {
    return this.http.post<{response: string}>(`${this.url}/chat/`, { message, history });
  }
}

export interface WorkerFieldDef {
  key: string;
  label: string;
  field_type: string;
  target_entity: string;
  kind_code: string;
}
