import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '@env/environment';
import { Branding } from '../interfaces/branding.interface';

@Injectable({ providedIn: 'root' })
export class BrandingService {
  private readonly url = `${environment.apiUrl}/branding/`;

  branding = signal<Branding>({
    company_name: 'Planificador de Turnos',
    tagline: '',
    logo_url: null,
    favicon_url: null,
    primary_color: '#EF4444',
    primary_dark: '#B91C1C',
    updated_at: '',
  });

  /**
   * false hasta que responde GET /branding/. Sirve para no pintar un logo
   * provisional y cambiarlo al llegar la respuesta: quien muestre un fallback
   * (las pantallas de auth) debe esperar a que esto sea true.
   */
  loaded = signal(false);

  constructor(private http: HttpClient) {}

  /** Call once at app startup (in AppComponent). */
  load(): void {
    this.http.get<Branding>(this.url).subscribe({
      next: data => {
        this.branding.set(data);
        this._applyColors(data);
        this._applyFavicon(data);
        this._applyTitle(data);
        this.loaded.set(true);
      },
      // Si el endpoint falla se queda el branding por defecto, pero hay que
      // desbloquear igualmente el fallback del logo o no se pinta nada.
      error: () => this.loaded.set(true),
    });
  }

  private _applyColors(b: Branding): void {
    const root = document.documentElement;
    root.style.setProperty('--color-primary', b.primary_color);
    root.style.setProperty('--color-primary-dark', b.primary_dark);
    root.style.setProperty('--color-primary-text', this._contrastColor(b.primary_color));
  }

  /** Returns #000 or #fff depending on luminance of the given hex color. */
  private _contrastColor(hex: string): string {
    const clean = hex.replace('#', '');
    const r = parseInt(clean.slice(0, 2), 16);
    const g = parseInt(clean.slice(2, 4), 16);
    const b = parseInt(clean.slice(4, 6), 16);
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminance > 0.55 ? '#000000' : '#ffffff';
  }

  private _applyTitle(b: Branding): void {
    if (b.company_name) document.title = b.company_name;
  }

  private _applyFavicon(b: Branding): void {
    if (!b.favicon_url) return;
    let link = document.querySelector<HTMLLinkElement>('link[rel~="icon"]');
    if (!link) {
      link = document.createElement('link');
      link.rel = 'icon';
      document.head.appendChild(link);
    }
    link.href = b.favicon_url;
  }
}
