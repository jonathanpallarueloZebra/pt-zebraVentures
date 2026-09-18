import {
  Component, Input, Output, EventEmitter, ViewChild, ElementRef,
  forwardRef, ChangeDetectorRef, ChangeDetectionStrategy,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

@Component({
  selector: 'zb-datepicker',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './zb-datepicker.component.html',
  styleUrl: './zb-datepicker.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [{
    provide: NG_VALUE_ACCESSOR,
    useExisting: forwardRef(() => ZbDatepickerComponent),
    multi: true,
  }],
})
export class ZbDatepickerComponent implements ControlValueAccessor {
  @ViewChild('nativeInput') nativeInput!: ElementRef<HTMLInputElement>;

  @Input() label?: string;
  @Input() error?: string;
  @Input() hint?: string;
  @Input() min?: string;  // YYYY-MM-DD
  @Input() max?: string;

  value = '';
  isDisabled = false;

  constructor(private cdr: ChangeDetectorRef) {}

  private onChange: (v: string) => void = () => {};
  private onTouched: () => void = () => {};

  writeValue(v: string): void          { this.value = v ?? ''; this.cdr.markForCheck(); }
  registerOnChange(fn: (v: string) => void): void { this.onChange = fn; }
  registerOnTouched(fn: () => void): void         { this.onTouched = fn; }
  setDisabledState(d: boolean): void   { this.isDisabled = d; this.cdr.markForCheck(); }

  handleChange(event: Event): void {
    const v = (event.target as HTMLInputElement).value;
    this.value = v;
    this.onChange(v);
  }

  handleBlur(): void { this.onTouched(); }

  openPicker(): void {
    // showPicker() is supported in modern browsers
    this.nativeInput?.nativeElement?.showPicker?.();
    this.nativeInput?.nativeElement?.focus();
  }
}
