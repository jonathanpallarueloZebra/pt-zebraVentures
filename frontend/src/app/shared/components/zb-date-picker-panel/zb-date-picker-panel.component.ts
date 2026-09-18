import { Component, Input, Output, EventEmitter, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DatePickerMode } from '@app/shared/interfaces/branding.interface';

export interface DateRange {
  startDate: string;
  endDate:   string;
}

interface CalDay {
  date:    string; // YYYY-MM-DD
  day:     number;
  inMonth: boolean;
}

@Component({
  selector: 'zb-date-picker-panel',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './zb-date-picker-panel.component.html',
  styleUrl: './zb-date-picker-panel.component.scss',
})
export class ZbDatePickerPanelComponent implements OnInit {
  @Input() startDate = '';
  @Input() endDate   = '';

  /**
   * Modo de selección, configurable desde Admin Zebra:
   *   'range' → dos clics: fecha de inicio y fecha de fin (comportamiento
   *             histórico y valor por defecto).
   *   'week'  → un clic: se selecciona la semana completa (lunes a domingo) a
   *             la que pertenece el día pulsado.
   *
   * Los dos modos viven en este componente en vez de duplicarlo, así que el
   * resaltado del rango y el resto de la interacción son idénticos.
   */
  @Input() mode: DatePickerMode = 'range';

  @Output() apply  = new EventEmitter<DateRange>();
  @Output() cancel = new EventEmitter<void>();

  viewYear  = new Date().getFullYear();
  viewMonth = new Date().getMonth();

  _start   = '';
  _end     = '';
  _hovered = '';

  readonly today: string = (() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  })();

  readonly MONTHS   = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
  readonly DOW_LBLS = ['L','M','X','J','V','S','D'];

  ngOnInit() {
    if (this.startDate) {
      const ref = new Date(this.startDate + 'T00:00:00');
      this.viewYear  = ref.getFullYear();
      this.viewMonth = ref.getMonth();
    }
    this._start = this.startDate;
    this._end   = this.endDate;
  }

  get monthLabel(): string { return `${this.MONTHS[this.viewMonth]} ${this.viewYear}`; }
  get startDisplay(): string { return this._start ? this._fmt(this._start) : ''; }
  get endDisplay():   string { return this._end   ? this._fmt(this._end)   : ''; }

  private _fmt(d: string): string {
    const [y, m, day] = d.split('-');
    return `${day}/${m}/${y}`;
  }

  get weeks(): CalDay[][] {
    const first    = new Date(this.viewYear, this.viewMonth, 1);
    const lastDate = new Date(this.viewYear, this.viewMonth + 1, 0).getDate();
    const startDow = (first.getDay() + 6) % 7; // 0 = Monday

    const days: CalDay[] = [];

    for (let i = startDow; i > 0; i--) {
      const d = new Date(this.viewYear, this.viewMonth, 1 - i);
      days.push({ date: this._iso(d), day: d.getDate(), inMonth: false });
    }
    for (let n = 1; n <= lastDate; n++) {
      const d = new Date(this.viewYear, this.viewMonth, n);
      days.push({ date: this._iso(d), day: n, inMonth: true });
    }
    let next = 1;
    while (days.length < 42) {
      const d = new Date(this.viewYear, this.viewMonth + 1, next++);
      days.push({ date: this._iso(d), day: d.getDate(), inMonth: false });
    }

    const weeks: CalDay[][] = [];
    for (let i = 0; i < days.length; i += 7) weeks.push(days.slice(i, i + 7));
    return weeks;
  }

  private _iso(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  }

  prevMonth() {
    if (this.viewMonth === 0) { this.viewMonth = 11; this.viewYear--; }
    else this.viewMonth--;
  }

  nextMonth() {
    if (this.viewMonth === 11) { this.viewMonth = 0; this.viewYear++; }
    else this.viewMonth++;
  }

  selectDay(day: CalDay) {
    // Modo semana: un solo clic fija lunes→domingo, sin segundo clic.
    if (this.mode === 'week') {
      const [ini, fin] = this._weekBounds(day.date);
      this._start = ini;
      this._end   = fin;
      this._hovered = '';
      return;
    }
    if (!this._start || (this._start && this._end)) {
      this._start  = day.date;
      this._end    = '';
    } else {
      if (day.date < this._start) {
        this._end   = this._start;
        this._start = day.date;
      } else {
        this._end = day.date;
      }
      this._hovered = '';
    }
  }

  /**
   * Lunes y domingo de la semana que contiene `date` (ISO `YYYY-MM-DD`).
   *
   * Misma convención que el resto de la aplicación: la semana empieza en LUNES
   * — `(getDay() + 6) % 7` convierte domingo (0) en 6.
   *
   * Se construye con `T00:00:00` (hora local, no UTC) para que un desfase de
   * zona horaria no desplace el día, y con `setDate()`, que ya resuelve por sí
   * solo las semanas que cruzan de mes o de año.
   */
  private _weekBounds(date: string): [string, string] {
    const d = new Date(date + 'T00:00:00');
    const lunes = new Date(d);
    lunes.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    const domingo = new Date(lunes);
    domingo.setDate(lunes.getDate() + 6);
    return [this._iso(lunes), this._iso(domingo)];
  }

  hoverDay(date: string) {
    // En modo semana no hay selección "a medias" que previsualizar.
    if (this.mode === 'week') return;
    if (this._start && !this._end) this._hovered = date;
  }
  clearHover() { this._hovered = ''; }

  isSelected(date: string):   boolean { return date === this._start || date === this._end; }
  isRangeStart(date: string): boolean { return !!(this._end && date === this._start); }
  isRangeEnd(date: string):   boolean { return !!(this._end && date === this._end);   }

  isInRange(date: string): boolean {
    const end = this._end || this._hovered;
    if (!this._start || !end) return false;
    const [s, e] = this._start <= end ? [this._start, end] : [end, this._start];
    return date > s && date < e;
  }

  isToday(date: string): boolean { return date === this.today; }
  canApply(): boolean { return !!(this._start && this._end); }

  onApply() { if (this.canApply()) this.apply.emit({ startDate: this._start, endDate: this._end }); }
  onCancel() { this.cancel.emit(); }
}
