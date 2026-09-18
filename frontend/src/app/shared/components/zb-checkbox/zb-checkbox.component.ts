import {
  Component, Input, forwardRef, ChangeDetectorRef, ChangeDetectionStrategy,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

@Component({
  selector: 'zb-checkbox',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './zb-checkbox.component.html',
  styleUrl: './zb-checkbox.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [{
    provide: NG_VALUE_ACCESSOR,
    useExisting: forwardRef(() => ZbCheckboxComponent),
    multi: true,
  }],
})
export class ZbCheckboxComponent implements ControlValueAccessor {
  @Input() label?: string;

  checked = false;
  isDisabled = false;

  constructor(private cdr: ChangeDetectorRef) {}

  private onChange: (v: boolean) => void = () => {};
  private onTouched: () => void = () => {};

  writeValue(v: boolean): void       { this.checked = !!v; this.cdr.markForCheck(); }
  registerOnChange(fn: (v: boolean) => void): void { this.onChange = fn; }
  registerOnTouched(fn: () => void): void          { this.onTouched = fn; }
  setDisabledState(d: boolean): void { this.isDisabled = d; this.cdr.markForCheck(); }

  handleChange(event: Event): void {
    this.checked = (event.target as HTMLInputElement).checked;
    this.onChange(this.checked);
  }

  handleBlur(): void { this.onTouched(); }
}
