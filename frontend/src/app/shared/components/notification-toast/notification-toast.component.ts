import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { NotificationService } from '@app/shared/services/notification.service';

@Component({
  selector: 'app-notification-toast',
  standalone: true,
  imports: [CommonModule, MatIconModule],
  template: `
    <div class="toast-container">
      @for (n of notificationService.notifications(); track n.id) {
        <div class="toast-item" [class]="n.type" [class.dismissing]="n.dismissing" [class.has-detail]="!!n.detail">
          <mat-icon class="toast-icon">{{ getIcon(n.type) }}</mat-icon>
          <div class="toast-body">
            <span class="toast-message">{{ n.message }}</span>
            @if (n.detail) {
              <span class="toast-detail">{{ n.detail }}</span>
            }
            @if (n.action) {
              <button class="toast-action" (click)="onAction(n.id, n.action!.callback)">{{ n.action.label }}</button>
            }
          </div>
          <button class="toast-close" (click)="notificationService.dismiss(n.id)">
            <mat-icon>close</mat-icon>
          </button>
        </div>
      }
    </div>
  `,
  styles: [`
    .toast-container {
      position: fixed;
      top: 16px;
      right: 16px;
      z-index: 10000;
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-width: 420px;
      pointer-events: none;
    }
    .toast-item {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 12px 16px;
      border-radius: 8px;
      background: #323232;
      color: #fff;
      font-size: 14px;
      box-shadow: 0 4px 12px rgba(0,0,0,.25);
      animation: slideIn 0.3s ease;
      pointer-events: all;
    }
    .toast-item.dismissing {
      animation: slideOut 0.3s ease forwards;
    }
    .toast-item.success { background: #2e7d32; }
    .toast-item.error { background: #c62828; }
    .toast-item.warning { background: #e65100; }
    .toast-item.info { background: #1565c0; }
    .toast-icon { font-size: 20px; width: 20px; height: 20px; flex-shrink: 0; margin-top: 1px; }
    .toast-body { flex: 1; display: flex; flex-direction: column; gap: 4px; }
    .toast-message { line-height: 1.4; }
    .toast-detail { font-size: 12px; opacity: .85; line-height: 1.4; white-space: pre-line; }
    .toast-action {
      background: rgba(255,255,255,.2);
      border: 1px solid rgba(255,255,255,.3);
      color: #fff;
      font-size: 12px;
      font-weight: 600;
      padding: 4px 12px;
      border-radius: 4px;
      cursor: pointer;
      align-self: flex-start;
      margin-top: 4px;
      transition: background .15s;
    }
    .toast-action:hover { background: rgba(255,255,255,.35); }
    .toast-close {
      background: none;
      border: none;
      color: rgba(255,255,255,.7);
      cursor: pointer;
      padding: 0;
      display: flex;
      flex-shrink: 0;
    }
    .toast-close:hover { color: #fff; }
    .toast-close mat-icon { font-size: 18px; width: 18px; height: 18px; }
    @keyframes slideIn {
      from { transform: translateX(100%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
      from { transform: translateX(0); opacity: 1; }
      to { transform: translateX(100%); opacity: 0; }
    }
  `],
})
export class NotificationToastComponent {
  constructor(public notificationService: NotificationService) {}

  getIcon(type: string): string {
    switch (type) {
      case 'success': return 'check_circle';
      case 'error': return 'error';
      case 'warning': return 'warning';
      default: return 'info';
    }
  }

  onAction(id: number, callback: () => void): void {
    callback();
    this.notificationService.dismiss(id);
  }
}
