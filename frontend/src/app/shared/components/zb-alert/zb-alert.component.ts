import { Component, Input, Output, EventEmitter, HostBinding } from '@angular/core';
import { CommonModule } from '@angular/common';

export type AlertType = 'warning' | 'info' | 'success' | 'error';
export type AlertSize = 'default' | 'compact';

@Component({
  selector: 'zb-alert',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './zb-alert.component.html',
  styleUrl: './zb-alert.component.scss',
})
export class ZbAlertComponent {
  @Input({ required: true }) type: AlertType = 'info';
  @Input({ required: true }) title!: string;
  @Input() description?: string;
  @Input() size: AlertSize = 'default';
  @Input() dismissible = true;
  @Output() dismissed = new EventEmitter<void>();

  @HostBinding('class') get hostClass() {
    return `alert--${this.type} alert--${this.size}`;
  }

  readonly typeIcons: Record<AlertType, string> = {
    warning: 'warning',
    info:    'info',
    success: 'check_circle',
    error:   'error_outline',
  };
}
