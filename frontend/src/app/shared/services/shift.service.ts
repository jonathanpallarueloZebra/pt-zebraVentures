import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';
import { Shift } from '../interfaces/shift.interface';

@Injectable({ providedIn: 'root' })
export class ShiftService {
  private readonly url = `${environment.apiUrl}/shifts`;

  constructor(private http: HttpClient) {}

  /** All shifts. */
  getAll(): Observable<Shift[]> {
    return this.http.get<Shift[]>(`${this.url}/`);
  }

  /** All shifts flat (alias). */
  getFlat(): Observable<Shift[]> {
    return this.http.get<Shift[]>(`${this.url}/flat/`);
  }

  /** All shifts (alias for admin page). */
  getAllAdmin(): Observable<Shift[]> {
    return this.http.get<Shift[]>(`${this.url}/all/`);
  }

  create(data: Partial<Shift>): Observable<Shift> {
    return this.http.post<Shift>(`${this.url}/`, data);
  }

  update(id: number, data: Partial<Shift>): Observable<Shift> {
    return this.http.patch<Shift>(`${this.url}/${id}/`, data);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`);
  }
}
