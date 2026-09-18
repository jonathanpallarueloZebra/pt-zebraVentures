import {
  Component, Input, Output, EventEmitter, forwardRef,
  ChangeDetectorRef, ChangeDetectionStrategy,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

@Component({
  selector: 'zb-search-input',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './zb-search-input.component.html',
  styleUrl: './zb-search-input.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [{
    provide: NG_VALUE_ACCESSOR,
    useExisting: forwardRef(() => ZbSearchInputComponent),
    multi: true,
  }],
})
export class ZbSearchInputComponent implements ControlValueAccessor {
  @Input() placeholder = 'Buscar';
  @Input() autocomplete = 'off';
  @Output() search = new EventEmitter<string>();

  value = '';
  isDisabled = false;

  constructor(private cdr: ChangeDetectorRef) {}

  private onChange: (v: string) => void = () => {};
  private onTouched: () => void = () => {};

  writeValue(v: string): void          { this.value = v ?? ''; this.cdr.markForCheck(); }
  registerOnChange(fn: (v: string) => void): void { this.onChange = fn; }
  registerOnTouched(fn: () => void): void         { this.onTouched = fn; }
  setDisabledState(d: boolean): void   { this.isDisabled = d; this.cdr.markForCheck(); }

  handleInput(event: Event): void {
    const v = (event.target as HTMLInputElement).value;
    this.value = v;
    this.onChange(v);
  }

  handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter') this.search.emit(this.value);
  }

  handleBlur(): void { this.onTouched(); }

  clear(): void {
    this.value = '';
    this.onChange('');
    this.search.emit('');
  }
}
