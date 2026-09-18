import { Injectable, signal } from '@angular/core';

export interface NotificationAction {
  label: string;
  callback: () => void;
}

export interface AppNotification {
  id: number;
  message: string;
  detail?: string;
  type: 'success' | 'error' | 'info' | 'warning';
  timestamp: Date;
  dismissing?: boolean;
  action?: NotificationAction;
}

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private nextId = 1;
  notifications = signal<AppNotification[]>([]);

  show(message: string, type: AppNotification['type'] = 'info', duration = 6000, options?: { detail?: string; action?: NotificationAction }): void {
    const notification: AppNotification = {
      id: this.nextId++,
      message,
      detail: options?.detail,
      type,
      timestamp: new Date(),
      action: options?.action,
    };
    this.notifications.update(list => [...list, notification]);
    if (duration > 0) {
      setTimeout(() => this.dismiss(notification.id), duration);
    }
  }

  dismiss(id: number): void {
    this.notifications.update(list =>
      list.map(n => n.id === id ? { ...n, dismissing: true } : n)
    );
    setTimeout(() => {
      this.notifications.update(list => list.filter(n => n.id !== id));
    }, 300);
  }

  success(message: string, duration = 6000, options?: { detail?: string; action?: NotificationAction }): void {
    this.show(message, 'success', duration, options);
  }

  error(message: string, duration = 8000, options?: { detail?: string; action?: NotificationAction }): void {
    this.show(message, 'error', duration, options);
  }

  warning(message: string, duration = 6000, options?: { detail?: string; action?: NotificationAction }): void {
    this.show(message, 'warning', duration, options);
  }

  info(message: string, duration = 6000, options?: { detail?: string; action?: NotificationAction }): void {
    this.show(message, 'info', duration, options);
  }
}
