import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';
import { Area } from '../interfaces/area.interface';

@Injectable({ providedIn: 'root' })
export class AreaService {
  private readonly url = `${environment.apiUrl}/areas`;

  constructor(private http: HttpClient) {}

  getAll(): Observable<Area[]> {
    return this.http.get<Area[]>(`${this.url}/`);
  }

  create(data: Partial<Area>): Observable<Area> {
    return this.http.post<Area>(`${this.url}/`, data);
  }

  update(id: number, data: Partial<Area>): Observable<Area> {
    return this.http.patch<Area>(`${this.url}/${id}/`, data);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`);
  }
}
