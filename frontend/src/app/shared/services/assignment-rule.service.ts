import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, shareReplay } from 'rxjs';
import { environment } from '@env/environment';
import { AssignmentRule, AssignmentPattern, WorkerFieldOption } from '../interfaces/assignment.interface';

@Injectable({ providedIn: 'root' })
export class AssignmentRuleService {
  private readonly url = `${environment.apiUrl}/assignments`;
  private patternsCache$?: Observable<AssignmentPattern[]>;
  private workerFieldsCache$?: Observable<WorkerFieldOption[]>;

  constructor(private http: HttpClient) {}

  getAll(): Observable<AssignmentRule[]> {
    return this.http.get<AssignmentRule[]>(`${this.url}/`);
  }

  create(data: Partial<AssignmentRule>): Observable<AssignmentRule> {
    return this.http.post<AssignmentRule>(`${this.url}/`, data);
  }

  update(id: number, data: Partial<AssignmentRule>): Observable<AssignmentRule> {
    return this.http.patch<AssignmentRule>(`${this.url}/${id}/`, data);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`);
  }

  getPatterns(): Observable<AssignmentPattern[]> {
    if (!this.patternsCache$) {
      this.patternsCache$ = this.http.get<AssignmentPattern[]>(`${this.url}/patterns/`).pipe(shareReplay(1));
    }
    return this.patternsCache$;
  }

  getWorkerFields(): Observable<WorkerFieldOption[]> {
    if (!this.workerFieldsCache$) {
      this.workerFieldsCache$ = this.http.get<WorkerFieldOption[]>(`${this.url}/worker_fields/`).pipe(shareReplay(1));
    }
    return this.workerFieldsCache$;
  }

  chat(message: string, history: {role: string; content: string}[]): Observable<{response: string}> {
    return this.http.post<{response: string}>(`${this.url}/chat/`, { message, history });
  }
}
