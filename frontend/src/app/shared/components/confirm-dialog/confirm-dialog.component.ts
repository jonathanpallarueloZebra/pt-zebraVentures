import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';

export interface ConfirmDialogData {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  type?: 'confirm' | 'warning' | 'error' | 'success';
}

@Component({
  selector: 'app-confirm-dialog',
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatIconModule, MatDialogModule],
  template: `
    <div class="dialog-wrapper" [class.warning]="data.type === 'warning'" [class.error]="data.type === 'error'" [class.success]="data.type === 'success'">
      <div class="dialog-icon">
        <mat-icon>{{ iconName }}</mat-icon>
      </div>
      <h2 mat-dialog-title>{{ data.title }}</h2>
      <mat-dialog-content>
        <p [innerHTML]="data.message"></p>
      </mat-dialog-content>
      <mat-dialog-actions align="end">
        @if (data.type === 'confirm') {
          <button mat-button (click)="dialogRef.close(false)">{{ data.cancelText || 'Cancelar' }}</button>
          <button mat-flat-button color="warn" (click)="dialogRef.close(true)">{{ data.confirmText || 'Eliminar' }}</button>
        } @else {
          <button mat-flat-button color="primary" (click)="dialogRef.close(false)">Entendido</button>
        }
      </mat-dialog-actions>
    </div>
  `,
  styles: [`
    .dialog-wrapper { text-align: center; padding: 8px 0; }
    .dialog-icon { margin-bottom: 8px; }
    .dialog-icon mat-icon { font-size: 48px; width: 48px; height: 48px; color: #f44336; }
    .dialog-wrapper.warning .dialog-icon mat-icon { color: #ff9800; }
    .dialog-wrapper.error .dialog-icon mat-icon { color: #f44336; }
    .dialog-wrapper.success .dialog-icon mat-icon { color: #4caf50; }
    h2 { margin: 0 0 8px; font-size: 20px; font-weight: 600; }
    p { margin: 0; color: #555; font-size: 14px; line-height: 1.6; text-align: left; }
    mat-dialog-actions { justify-content: center !important; padding-top: 16px; }
  `],
})
export class ConfirmDialogComponent {
  iconName: string;

  constructor(
    public dialogRef: MatDialogRef<ConfirmDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: ConfirmDialogData,
  ) {
    this.iconName = data.type === 'success' ? 'check_circle'
      : data.type === 'error' ? 'error'
      : data.type === 'warning' ? 'warning'
      : 'help_outline';
  }
}
