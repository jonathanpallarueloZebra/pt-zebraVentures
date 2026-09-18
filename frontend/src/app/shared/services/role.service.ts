import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';
import { Role } from '../interfaces/role.interface';

@Injectable({ providedIn: 'root' })
export class RoleService {
  private readonly url = `${environment.apiUrl}/roles`;

  constructor(private http: HttpClient) {}

  getAll(): Observable<Role[]> {
    return this.http.get<Role[]>(`${this.url}/`);
  }

  getById(id: number): Observable<Role> {
    return this.http.get<Role>(`${this.url}/${id}/`);
  }

  create(data: Partial<Role>): Observable<Role> {
    return this.http.post<Role>(`${this.url}/`, data);
  }

  update(id: number, data: Partial<Role>): Observable<Role> {
    return this.http.patch<Role>(`${this.url}/${id}/`, data);
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.url}/${id}/`);
  }
}
