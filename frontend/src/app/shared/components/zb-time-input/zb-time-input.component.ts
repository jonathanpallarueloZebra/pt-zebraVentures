import {
  Component, Input, forwardRef, HostListener, ElementRef,
  ChangeDetectorRef, ChangeDetectionStrategy, ViewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

/**
 * Input de HORA como un ÚNICO desplegable (mismo patrón que los demás selects
 * de la web): trigger Input/text + icono reloj; al abrir muestra UNA sola lista
 * de horarios generados por tramos (`step`, por defecto 15 min): 00:00, 00:15…
 * Valor HH:MM (24h), usable con ngModel (ControlValueAccessor).
 */
@Component({
  selector: 'zb-time-input',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './zb-time-input.component.html',
  styleUrl: './zb-time-input.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [{
    provide: NG_VALUE_ACCESSOR,
    useExisting: forwardRef(() => ZbTimeInputComponent),
    multi: true,
  }],
})
export class ZbTimeInputComponent implements ControlValueAccessor {
  @Input() label?: string;
  @Input() hint?: string;
  @Input() placeholder = '--:--';
  /** Tramo entre opciones en minutos (15 → 00:00, 00:15, 00:30…). */
  @Input() step = 15;

  @ViewChild('panel') panelRef?: ElementRef<HTMLElement>;

  value = '';           // HH:MM (24h)
  isOpen = false;
  isDisabled = false;

  constructor(private el: ElementRef, private cdr: ChangeDetectorRef) {}

  private onChange: (v: string) => void = () => {};
  private onTouched: () => void = () => {};

  /** Lista de horarios generada por tramos: 00:00 … 23:45 (con step=15). */
  get options(): string[] {
    const step = this.step > 0 ? this.step : 15;
    const out: string[] = [];
    for (let m = 0; m < 24 * 60; m += step) {
      const h = String(Math.floor(m / 60)).padStart(2, '0');
      const min = String(m % 60).padStart(2, '0');
      out.push(`${h}:${min}`);
    }
    return out;
  }

  writeValue(v: string): void { this.value = v || ''; this.cdr.markForCheck(); }
  registerOnChange(fn: (v: string) => void): void { this.onChange = fn; }
  registerOnTouched(fn: () => void): void { this.onTouched = fn; }
  setDisabledState(d: boolean): void { this.isDisabled = d; this.cdr.markForCheck(); }

  toggle(): void {
    if (this.isDisabled) return;
    this.isOpen = !this.isOpen;
    this.cdr.markForCheck();
    if (this.isOpen) { this.scrollToSelected(); }
  }

  pick(v: string): void {
    this.value = v;
    this.onChange(v);
    this.onTouched();
    this.isOpen = false;
    this.cdr.markForCheck();
  }

  /** Al abrir, deja la opción seleccionada centrada a la vista. */
  private scrollToSelected(): void {
    setTimeout(() => {
      const active = this.panelRef?.nativeElement.querySelector<HTMLElement>('.ti-opt--active');
      active?.scrollIntoView({ block: 'center' });
    });
  }

  @HostListener('document:click', ['$event'])
  onDocClick(e: MouseEvent): void {
    if (this.isOpen && !this.el.nativeElement.contains(e.target)) {
      this.isOpen = false;
      this.onTouched();
      this.cdr.markForCheck();
    }
  }

  @HostListener('keydown.escape')
  onEscape(): void { if (this.isOpen) { this.isOpen = false; this.cdr.markForCheck(); } }
}
