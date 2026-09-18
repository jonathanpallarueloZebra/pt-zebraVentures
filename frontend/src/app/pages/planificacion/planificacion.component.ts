import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ZbPageHeaderComponent } from '@app/shared/components/zb-page-header/zb-page-header.component';
import { ZbButtonComponent } from '@app/shared/components/zb-button/zb-button.component';
import { ZbIconComponent } from '@app/shared/components/zb-icon/zb-icon.component';
import { PlanningService, DiagScope, DiagDay } from '@app/shared/services/planning.service';

/**
 * Diagnóstico de la planificación (/planificacion).
 *
 * Vista de SOLO LECTURA: muestra, para la semana elegida, cómo ha quedado el
 * plan de cada tienda —quién entra en cada turno con su horario y área, quién
 * queda sin asignar y quién no está disponible—. Es la versión en pantalla de
 * la traza que el generador vuelca por consola.
 *
 * No genera ni modifica planes: eso se sigue haciendo desde /schedule.
 */
@Component({
  selector: 'app-planificacion',
  standalone: true,
  imports: [CommonModule, FormsModule, ZbPageHeaderComponent, ZbButtonComponent, ZbIconComponent],
  templateUrl: './planificacion.component.html',
  styleUrl: './planificacion.component.scss',
})
export class PlanificacionComponent implements OnInit {
  private planning = inject(PlanningService);

  loading = signal(false);
  error = signal('');
  scopes = signal<DiagScope[]>([]);
  /** Semana consultada (lunes en ISO). */
  week = signal(this.mondayOf(new Date()));
  /** Ámbito desplegado; null = ninguno. */
  expanded = signal<number | null>(null);

  // ── Totales de la semana ────────────────────────────────────────────────
  totals = computed(() => {
    const s = this.scopes();
    return {
      tiendas: s.length,
      planificadas: s.filter(x => x.has_plan && x.total_assignments > 0).length,
      vacias: s.filter(x => x.has_plan && x.total_assignments === 0).length,
      asignaciones: s.reduce((a, x) => a + x.total_assignments, 0),
    };
  });

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.planning.getDiagnostics(this.week()).subscribe({
      next: r => { this.scopes.set(r.scopes); this.loading.set(false); },
      error: () => {
        this.error.set('No se pudo cargar el diagnóstico de esta semana.');
        this.loading.set(false);
      },
    });
  }

  toggle(scope: number): void {
    this.expanded.set(this.expanded() === scope ? null : scope);
  }

  shiftWeek(deltaWeeks: number): void {
    const d = new Date(this.week() + 'T00:00:00');
    d.setDate(d.getDate() + deltaWeeks * 7);
    this.week.set(this.iso(d));
    this.load();
  }

  onWeekChange(value: string): void {
    if (!value) return;
    this.week.set(this.mondayOf(new Date(value + 'T00:00:00')));
    this.load();
  }

  /** Estado de una tienda, para el badge de la tabla. */
  statusOf(s: DiagScope): { code: string; label: string } {
    if (!s.has_plan) return { code: 'none', label: 'Sin planificar' };
    if (s.total_assignments === 0) return { code: 'empty', label: 'Plan vacío' };
    return { code: 'ok', label: 'Planificada' };
  }

  /** Días con turnos, excluyendo los cerrados (no aportan al diagnóstico). */
  openDays(s: DiagScope): DiagDay[] {
    return s.days.filter(d => !d.closed);
  }

  /** Rango legible "dd/mm - dd/mm" de la semana mostrada. */
  weekLabel = computed(() => {
    const a = new Date(this.week() + 'T00:00:00');
    const b = new Date(a); b.setDate(a.getDate() + 6);
    return `${this.dm(a)} - ${this.dm(b)}`;
  });

  /** Un área está al tope (o por encima) → se marca en la vista. */
  areaFull(used: number, cap: number | null): boolean {
    return cap !== null && cap !== undefined && used >= cap;
  }

  // ── Fechas ───────────────────────────────────────────────────────────────
  private mondayOf(d: Date): string {
    const m = new Date(d);
    m.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    return this.iso(m);
  }
  private iso(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
  private dm(d: Date): string {
    return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`;
  }
}
