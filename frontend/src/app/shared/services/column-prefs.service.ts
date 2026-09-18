import { Injectable } from '@angular/core';

/**
 * Persiste, por entidad (slug), qué columnas ve cada usuario en sus tablas.
 * Cliente-only (localStorage), siguiendo el patrón de ThemeService.
 * El valor por defecto (cuando no hay preferencia guardada) es el conjunto
 * de campos con `show_in_list` configurado en adminZebra.
 */
@Injectable({ providedIn: 'root' })
export class ColumnPrefsService {
  private readonly PREFIX = 'zb:columns:';

  /** Devuelve los ids de columnas visibles guardados, o null si no hay preferencia. */
  get(slug: string): string[] | null {
    try {
      const raw = localStorage.getItem(this.PREFIX + slug);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.map(String) : null;
    } catch {
      return null;
    }
  }

  set(slug: string, visibleKeys: string[]): void {
    try {
      localStorage.setItem(this.PREFIX + slug, JSON.stringify(visibleKeys));
    } catch {
      /* almacenamiento no disponible — se ignora */
    }
  }

  /** Borra la preferencia → la tabla vuelve a los valores por defecto (show_in_list). */
  clear(slug: string): void {
    try {
      localStorage.removeItem(this.PREFIX + slug);
    } catch {
      /* almacenamiento no disponible — se ignora */
    }
  }
}
