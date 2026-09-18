import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';
import { ClosedDay } from '../interfaces/closed-day.interface';

@Injectable({ providedIn: 'root' })
export class ClosedDayService {
  private readonly url = `${environment.apiUrl}/planning/closed-days`;

  constructor(private http: HttpClient) {}

  getAll(): Observable<ClosedDay[]> {
    return this.http.get<ClosedDay[]>(`${this.url}/`);
  }

  create(data: Partial<ClosedDay>): Observable<ClosedDay> {
    return this.http.post<ClosedDay>(`${this.url}/`, data);
  }

  update(id: number, data: Partial<ClosedDay>): Observable<ClosedDay> {
    return this.http.patch<ClosedDay>(`${this.url}/${id}/`, data);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`);
  }
}
