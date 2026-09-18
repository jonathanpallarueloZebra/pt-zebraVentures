import {
  Component, Input, Output, EventEmitter, ChangeDetectionStrategy,
} from '@angular/core';
import { CommonModule } from '@angular/common';

export type RangeInputMode = 'time' | 'date';

@Component({
  selector: 'zb-range-input',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './zb-range-input.component.html',
  styleUrl: './zb-range-input.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ZbRangeInputComponent {
  // 'time': shows clock icon, placeholder "HH:MM - HH:MM"
  // 'date': shows calendar icon, placeholder "DD-MM - DD-MM"
  @Input() mode: RangeInputMode = 'time';

  // The displayed value — parent sets this after picker interaction
  @Input() value?: string;

  @Input() placeholder?: string;  // overrides default if provided
  @Input() disabled = false;
  @Input() error = false;

  // Emit when user clicks (parent opens the picker)
  @Output() open = new EventEmitter<void>();

  get icon(): string { return this.mode === 'time' ? 'schedule' : 'calendar_today'; }

  get defaultPlaceholder(): string {
    return this.mode === 'time' ? 'HH:MM - HH:MM' : 'DD-MM - DD-MM';
  }

  get displayValue(): string {
    return this.value ?? this.placeholder ?? this.defaultPlaceholder;
  }

  get isEmpty(): boolean { return !this.value; }
}
