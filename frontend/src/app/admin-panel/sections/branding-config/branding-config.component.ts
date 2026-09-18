import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { environment } from '@env/environment';
import { Branding } from '@app/shared/interfaces/branding.interface';

@Component({
  selector: 'app-branding-config',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatCardModule, MatFormFieldModule, MatInputModule, MatSelectModule,
    MatButtonModule, MatIconModule,
    MatProgressSpinnerModule, MatSnackBarModule,
  ],
  template: `
    <div class="section">
      <h2 class="section-title">Configuracion de Marca</h2>
      <p class="section-desc">Personaliza la identidad visual de esta instancia para el cliente.</p>

      @if (loading()) {
        <div class="loading"><mat-spinner diameter="36"></mat-spinner></div>
      } @else {
        <div class="config-grid">  

          <!-- Company name & tagline -->
          <mat-card class="config-card">
            <mat-card-header>
              <mat-icon class="card-icon">business</mat-icon>
              <mat-card-title>Datos de empresa</mat-card-title>
            </mat-card-header>
            <mat-card-content>
              <mat-form-field appearance="outline" class="full">
                <mat-label>Nombre de la empresa</mat-label>
                <input matInput [(ngModel)]="form.company_name">
              </mat-form-field>
              <mat-form-field appearance="outline" class="full">
                <mat-label>Eslogan (opcional)</mat-label>
                <input matInput [(ngModel)]="form.tagline" placeholder="Gestion inteligente de turnos">
              </mat-form-field>
            </mat-card-content>
          </mat-card>

          <!-- Comportamiento del planificador -->
          <mat-card class="config-card">
            <mat-card-header>
              <mat-icon class="card-icon">date_range</mat-icon>
              <mat-card-title>Selector de fechas</mat-card-title>
            </mat-card-header>
            <mat-card-content>
              <mat-form-field appearance="outline" class="full">
                <mat-label>Modo de seleccion</mat-label>
                <mat-select [(ngModel)]="form.date_picker_mode">
                  <mat-option value="week">Por semanas</mat-option>
                  <mat-option value="range">Por rango de fechas</mat-option>
                </mat-select>
                <mat-hint>
                  Por semanas: al pulsar un dia se selecciona su semana completa.
                  Por rango: se eligen fecha de inicio y de fin.
                </mat-hint>
              </mat-form-field>
            </mat-card-content>
          </mat-card>

          <!-- Colors -->
          <mat-card class="config-card">
            <mat-card-header>
              <mat-icon class="card-icon">palette</mat-icon>
              <mat-card-title>Colores</mat-card-title>
            </mat-card-header>
            <mat-card-content>
              <div class="color-row">
                <div class="color-picker">
                  <label>Color principal</label>
                  <div class="color-input-wrap">
                    <input type="color" [(ngModel)]="form.primary_color">
                    <span class="color-hex">{{ form.primary_color }}</span>
                  </div>
                </div>
                <div class="color-picker">
                  <label>Variante oscura</label>
                  <div class="color-input-wrap">
                    <input type="color" [(ngModel)]="form.primary_dark">
                    <span class="color-hex">{{ form.primary_dark }}</span>
                  </div>
                </div>
              </div>
              <div class="color-preview">
                <div class="preview-swatch" [style.background]="form.primary_color">Principal</div>
                <div class="preview-swatch" [style.background]="form.primary_dark">Oscuro</div>
              </div>
            </mat-card-content>
          </mat-card>

          <!-- Logo -->
          <mat-card class="config-card">
            <mat-card-header>
              <mat-icon class="card-icon">image</mat-icon>
              <mat-card-title>Logo</mat-card-title>
            </mat-card-header>
            <mat-card-content>
              <div class="image-upload">
                @if (logoPreview()) {
                  <img [src]="logoPreview()" alt="Logo" class="image-preview">
                } @else {
                  <div class="image-placeholder">
                    <mat-icon>add_photo_alternate</mat-icon>
                    <span>Sin logo</span>
                  </div>
                }
                <div class="upload-actions">
                  <button mat-stroked-button (click)="logoInput.click()">
                    <mat-icon>upload</mat-icon> Subir logo
                  </button>
                  <input #logoInput type="file" accept="image/*" hidden
                    (change)="onFileSelected($event, 'logo')">
                  <span class="file-hint">PNG o SVG, fondo transparente</span>
                </div>
              </div>
            </mat-card-content>
          </mat-card>

          <!-- Favicon -->
          <mat-card class="config-card">
            <mat-card-header>
              <mat-icon class="card-icon">tab</mat-icon>
              <mat-card-title>Favicon</mat-card-title>
            </mat-card-header>
            <mat-card-content>
              <div class="image-upload">
                @if (faviconPreview()) {
                  <img [src]="faviconPreview()" alt="Favicon" class="image-preview favicon-size">
                } @else {
                  <div class="image-placeholder favicon-size">
                    <mat-icon>add_photo_alternate</mat-icon>
                  </div>
                }
                <div class="upload-actions">
                  <button mat-stroked-button (click)="faviconInput.click()">
                    <mat-icon>upload</mat-icon> Subir favicon
                  </button>
                  <input #faviconInput type="file" accept="image/*" hidden
                    (change)="onFileSelected($event, 'favicon')">
                  <span class="file-hint">32x32 px recomendado</span>
                </div>
              </div>
            </mat-card-content>
          </mat-card>

        </div>

        <div class="save-bar">
          <button mat-flat-button color="primary" (click)="save()" [disabled]="saving()" class="save-btn">
            @if (saving()) {
              Guardando...
            } @else {
              Guardar configuracion
            }
          </button>
        </div>
      }
    </div>
  `,
  styles: [`
    .section-title { font-size: 1.4rem; font-weight: 700; margin: 0 0 4px; }
    .section-desc { color: #6b7280; margin: 0 0 24px; }
    .loading { display: flex; justify-content: center; padding: 48px; }
    .config-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 20px; }
    .config-card { padding: 8px; }
    .card-icon { color: #6366f1; margin-right: 8px; }
    .full { width: 100%; }
    mat-card-content { padding-top: 12px !important; }

    .color-row { display: flex; gap: 24px; flex-wrap: wrap; }
    .color-picker {
      display: flex; flex-direction: column; gap: 6px;
      label { font-size: 0.85rem; color: #6b7280; }
    }
    .color-input-wrap { display: flex; align-items: center; gap: 8px; }
    .color-input-wrap input[type="color"] {
      width: 48px; height: 40px; padding: 2px; border: 1px solid #d1d5db;
      border-radius: 8px; cursor: pointer; background: #fff;
    }
    .color-hex { font-family: monospace; font-size: 0.85rem; color: #374151; }
    .color-preview { display: flex; gap: 12px; margin-top: 16px; }
    .preview-swatch {
      padding: 8px 16px; border-radius: 8px; color: white;
      font-size: 0.85rem; font-weight: 500; text-shadow: 0 1px 2px rgba(0,0,0,.3);
    }

    .image-upload { display: flex; align-items: center; gap: 20px; }
    .image-preview { height: 64px; max-width: 200px; object-fit: contain; border-radius: 8px; border: 1px solid #e5e7eb; padding: 4px; }
    .image-preview.favicon-size { height: 40px; max-width: 40px; }
    .image-placeholder {
      width: 120px; height: 64px; border: 2px dashed #d1d5db; border-radius: 8px;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      color: #9ca3af; font-size: 0.75rem;
      mat-icon { font-size: 28px; width: 28px; height: 28px; }
    }
    .image-placeholder.favicon-size { width: 48px; height: 48px; }
    .upload-actions { display: flex; flex-direction: column; gap: 4px; }
    .file-hint { font-size: 0.75rem; color: #9ca3af; }

    .save-bar { margin-top: 32px; display: flex; justify-content: flex-end; }
    .save-btn {
      height: 44px; font-size: 0.95rem; padding: 0 24px;
      display: flex; align-items: center; gap: 8px;
    }
  `],
})
export class BrandingConfigComponent implements OnInit {
  private readonly url = `${environment.apiUrl}/branding/`;

  loading = signal(true);
  saving = signal(false);
  logoPreview = signal<string | null>(null);
  faviconPreview = signal<string | null>(null);

  form = {
    company_name: '', tagline: '',
    primary_color: '#EF4444', primary_dark: '#B91C1C',
    // 'range' es el defecto del backend: el comportamiento que ya tenían los
    // proyectos existentes. Si el backend aún no expone el campo, este valor
    // evita dejar el select en blanco.
    date_picker_mode: 'range',
  };
  logoFile: File | null = null;
  faviconFile: File | null = null;

  constructor(private http: HttpClient, private snackBar: MatSnackBar) {}

  ngOnInit(): void {
    this.http.get<Branding>(this.url).subscribe({
      next: data => {
        this.form.company_name = data.company_name;
        this.form.tagline = data.tagline;
        this.form.primary_color = data.primary_color;
        this.form.primary_dark = data.primary_dark;
        this.form.date_picker_mode = data.date_picker_mode || 'range';
        this.logoPreview.set(data.logo_url);
        this.faviconPreview.set(data.favicon_url);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  onFileSelected(event: Event, type: 'logo' | 'favicon'): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    if (type === 'logo') this.logoFile = file;
    else this.faviconFile = file;

    const reader = new FileReader();
    reader.onload = () => {
      if (type === 'logo') this.logoPreview.set(reader.result as string);
      else this.faviconPreview.set(reader.result as string);
    };
    reader.readAsDataURL(file);
  }

  save(): void {
    this.saving.set(true);
    const fd = new FormData();
    fd.append('company_name', this.form.company_name);
    fd.append('tagline', this.form.tagline);
    fd.append('primary_color', this.form.primary_color);
    fd.append('primary_dark', this.form.primary_dark);
    fd.append('date_picker_mode', this.form.date_picker_mode);
    if (this.logoFile) fd.append('logo', this.logoFile);
    if (this.faviconFile) fd.append('favicon', this.faviconFile);

    this.http.patch<Branding>(this.url, fd).subscribe({
      next: () => {
        this.saving.set(false);
        this.snackBar.open('Configuracion guardada', 'OK', { duration: 3000 });
      },
      error: () => {
        this.saving.set(false);
        this.snackBar.open('Error al guardar', 'Cerrar', { duration: 4000 });
      },
    });
  }
}
