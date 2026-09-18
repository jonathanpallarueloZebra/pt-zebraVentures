import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';
import { RestDay } from '../interfaces/rest-day.interface';

@Injectable({ providedIn: 'root' })
export class RestDayService {
  private readonly url = `${environment.apiUrl}/rest-days`;

  constructor(private http: HttpClient) {}

  getAll(): Observable<RestDay[]> {
    return this.http.get<RestDay[]>(`${this.url}/all/`);
  }

  getWeekly(startDate: string): Observable<RestDay[]> {
    return this.http.get<RestDay[]>(`${this.url}/weekly/?start=${startDate}`);
  }

  create(data: { workerId: number; date: string; reason?: string }): Observable<RestDay> {
    return this.http.post<RestDay>(`${this.url}/`, data);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`);
  }
}
