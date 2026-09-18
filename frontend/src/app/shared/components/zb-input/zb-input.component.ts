import {
  Component, Input, forwardRef, ChangeDetectorRef, ChangeDetectionStrategy,
  ViewChild, ElementRef, AfterViewInit,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

@Component({
  selector: 'zb-input',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './zb-input.component.html',
  styleUrl: './zb-input.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [{
    provide: NG_VALUE_ACCESSOR,
    useExisting: forwardRef(() => ZbInputComponent),
    multi: true,
  }],
})
export class ZbInputComponent implements ControlValueAccessor, AfterViewInit {
  @Input() label?: string;
  @Input() placeholder = '';
  @Input() type: 'text' | 'email' | 'password' | 'number' | 'search' | 'tel' = 'text';
  @Input() error?: string;   // if set → error state + message below
  @Input() hint?: string;    // helper text (shown only when no error)
  @Input() iconLeft?: string;
  @Input() iconRight?: string;
  @Input() autocomplete?: string;
  /**
   * Salto de las flechas y granularidad admitida en `type="number"`.
   *
   * Sin esto el navegador usa 1 y rechaza los decimales: un campo de horas no
   * podía valer 37,5. Con `step="0.5"` las flechas van de media en media hora,
   * que es la unidad real de un contrato.
   */
  @Input() step?: string | number;
  @Input() id?: string;
  /**
   * Teclado numérico en móvil sin usar `type="number"`.
   *
   * Con `type="number"` el navegador considera "37," un valor INVÁLIDO y
   * devuelve cadena vacía mientras escribes: eso reescribe el input y el cursor
   * salta al principio, así que era imposible teclear la coma decimal. Con
   * `type="text"` + `inputmode="decimal"` el texto se conserva tal cual y el
   * móvil sigue mostrando el teclado numérico.
   */
  @Input() inputmode?: string;

  value = '';
  isDisabled = false;

  constructor(private cdr: ChangeDetectorRef) {}

  private onChange: (v: string) => void = () => {};
  private onTouched: () => void = () => {};

  /** Referencia al <input> nativo, para escribirle solo cuando hace falta. */
  @ViewChild('nativo') nativo?: ElementRef<HTMLInputElement>;

  /**
   * El valor se escribe en el elemento AQUÍ, no con `[value]="value"`.
   *
   * Con ese binding, Angular reescribía el input en cada ciclo de detección y el
   * cursor saltaba al principio: al teclear la coma decimal ("37,") el valor
   * volvía transformado y era imposible seguir escribiendo. Escribiéndolo solo
   * cuando el cambio viene de FUERA (writeValue) el cursor se queda donde está.
   */
  writeValue(v: string): void {
    this.value = v ?? '';
    const el = this.nativo?.nativeElement;
    // Solo si difiere: asignar el mismo valor también movería el cursor.
    if (el && el.value !== this.value) el.value = this.value;
    this.cdr.markForCheck();
  }

  /**
   * Valor inicial: `writeValue` llega ANTES de que exista la vista, así que ahí
   * el @ViewChild aún es undefined y el input nacería vacío.
   */
  ngAfterViewInit(): void {
    const el = this.nativo?.nativeElement;
    if (el && this.value && el.value !== this.value) el.value = this.value;
  }

  registerOnChange(fn: (v: string) => void): void  { this.onChange = fn; }
  registerOnTouched(fn: () => void): void           { this.onTouched = fn; }
  setDisabledState(isDisabled: boolean): void {
    this.isDisabled = isDisabled;
    this.cdr.markForCheck();
  }

  handleInput(event: Event): void {
    const v = (event.target as HTMLInputElement).value;
    this.value = v;
    this.onChange(v);
  }

  handleBlur(): void { this.onTouched(); }
}
