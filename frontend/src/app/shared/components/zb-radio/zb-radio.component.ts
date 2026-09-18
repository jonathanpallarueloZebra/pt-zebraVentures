import {
  Component, Input, Output, EventEmitter, ChangeDetectionStrategy,
} from '@angular/core';
import { CommonModule } from '@angular/common';

// Radio works in groups via native [name] binding.
// In reactive forms, bind value comparison in the parent:
//   <zb-radio name="size" value="sm" [checked]="ctrl.value === 'sm'" (select)="ctrl.setValue('sm')">
@Component({
  selector: 'zb-radio',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './zb-radio.component.html',
  styleUrl: './zb-radio.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ZbRadioComponent {
  @Input() name = '';
  @Input() value: any = '';
  @Input() checked = false;
  @Input() disabled = false;
  @Input() label?: string;

  @Output() select = new EventEmitter<any>();

  handleChange(): void {
    if (!this.disabled) this.select.emit(this.value);
  }
}
