import { Component, OnInit, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { AbsenceService } from '@app/shared/services/absence.service';
import { PlanningService } from '@app/shared/services/planning.service';
import { AbsenceType } from '@app/shared/interfaces/absence.interface';
import { Worker } from '@app/shared/interfaces/worker.interface';
import { ZbPageHeaderComponent } from '@app/shared/components/zb-page-header/zb-page-header.component';
import { ZbSelectComponent, ZbSelectOption } from '@app/shared/components/zb-select/zb-select.component';
import { ZbButtonComponent } from '@app/shared/components/zb-button/zb-button.component';

@Component({
  selector: 'app-absence-request',
  standalone: true,
  imports: [
    CommonModule, FormsModule, MatSnackBarModule,
    ZbPageHeaderComponent, ZbSelectComponent, ZbButtonComponent,
  ],
  templateUrl: './absence-request.component.html',
  styleUrl: './absence-request.component.scss',
})
export class AbsenceRequestComponent implements OnInit {
  private absenceService = inject(AbsenceService);
  private planningService = inject(PlanningService);
  private snackBar = inject(MatSnackBar);
  private router = inject(Router);

  absenceTypes = signal<AbsenceType[]>([]);
  myWorker = signal<Worker | null>(null);
  submitting = signal(false);
  loading = signal(true);

  form = { type_id: 0, start_date: '', end_date: '', reason: '' };

  get absenceTypeOptions(): ZbSelectOption[] {
    return this.absenceTypes().map(t => ({ label: t.name, value: t.id }));
  }

  ngOnInit(): void {
    this.planningService.getMyWorker().subscribe({
      next: (worker) => {
        this.myWorker.set(worker);
        this.absenceService.getTypes().subscribe({
          next: (types) => {
            this.absenceTypes.set(types.filter(t => t.active));
            this.loading.set(false);
          },
          error: () => this.loading.set(false),
        });
      },
      error: () => this.loading.set(false),
    });
  }

  submit(): void {
    const worker = this.myWorker();
    if (!worker || !this.form.type_id || !this.form.start_date || !this.form.end_date) {
      this.snackBar.open('Rellena todos los campos obligatorios', 'Cerrar', { duration: 3000 });
      return;
    }
    this.submitting.set(true);
    this.absenceService.createRequest({
      worker: worker.id,
      type: this.form.type_id,
      start_date: this.form.start_date,
      end_date: this.form.end_date,
      reason: this.form.reason,
    }).subscribe({
      next: () => {
        this.submitting.set(false);
        this.snackBar.open('Solicitud enviada correctamente', 'OK', { duration: 3000 });
        this.router.navigate(['/dashboard']);
      },
      error: () => {
        this.submitting.set(false);
        this.snackBar.open('Error al enviar la solicitud', 'Cerrar', { duration: 5000 });
      },
    });
  }

  cancel(): void {
    this.router.navigate(['/dashboard']);
  }
}
