import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormControl } from '@angular/forms';
import { ZbButtonComponent } from '../../shared/components/zb-button/zb-button.component';
import { ZbPageHeaderComponent } from '../../shared/components/zb-page-header/zb-page-header.component';
import { ZbTableToolbarComponent } from '../../shared/components/zb-table-toolbar/zb-table-toolbar.component';
import { ZbPaginatorComponent } from '../../shared/components/zb-paginator/zb-paginator.component';
import { ZbAlertComponent } from '../../shared/components/zb-alert/zb-alert.component';
import { ZbInputComponent } from '../../shared/components/zb-input/zb-input.component';
import { ZbDatepickerComponent } from '../../shared/components/zb-datepicker/zb-datepicker.component';
import { ZbSearchInputComponent } from '../../shared/components/zb-search-input/zb-search-input.component';
import { ZbRangeInputComponent } from '../../shared/components/zb-range-input/zb-range-input.component';
import { ZbSelectComponent } from '../../shared/components/zb-select/zb-select.component';
import type { ZbSelectOption } from '../../shared/components/zb-select/zb-select.component';
import { ZbCheckboxComponent } from '../../shared/components/zb-checkbox/zb-checkbox.component';
import { ZbRadioComponent } from '../../shared/components/zb-radio/zb-radio.component';
import { ZbToggleComponent } from '../../shared/components/zb-toggle/zb-toggle.component';
import { ZbDatePickerPanelComponent } from '../../shared/components/zb-date-picker-panel/zb-date-picker-panel.component';
import type { DateRange } from '../../shared/components/zb-date-picker-panel/zb-date-picker-panel.component';
import { ZbTimePickerPanelComponent } from '../../shared/components/zb-time-picker-panel/zb-time-picker-panel.component';
import { ZbSidepanelComponent } from '../../shared/components/zb-sidepanel/zb-sidepanel.component';
import { ZbEmptyStateComponent } from '../../shared/components/zb-empty-state/zb-empty-state.component';
import { ZbColumnMenuComponent } from '../../shared/components/zb-column-menu/zb-column-menu.component';
import type { ZbColumnDef } from '../../shared/components/zb-column-menu/zb-column-menu.component';
import { ZbDialogComponent } from '../../shared/components/zb-dialog/zb-dialog.component';
import { ZbFileUploadComponent } from '../../shared/components/zb-file-upload/zb-file-upload.component';
import { ZbSkeletonComponent } from '../../shared/components/zb-skeleton/zb-skeleton.component';

@Component({
  selector: 'app-design-lab',
  standalone: true,
  imports: [
    CommonModule, ReactiveFormsModule,
    ZbButtonComponent, ZbPageHeaderComponent, ZbTableToolbarComponent,
    ZbPaginatorComponent, ZbAlertComponent, ZbInputComponent,
    ZbDatepickerComponent, ZbSearchInputComponent, ZbRangeInputComponent, ZbSelectComponent,
    ZbCheckboxComponent, ZbRadioComponent, ZbToggleComponent,
    ZbDatePickerPanelComponent, ZbTimePickerPanelComponent,
    ZbSidepanelComponent, ZbEmptyStateComponent, ZbColumnMenuComponent,
    ZbDialogComponent, ZbFileUploadComponent, ZbSkeletonComponent,
  ],
  templateUrl: './design-lab.component.html',
  styleUrl: './design-lab.component.scss',
})
export class DesignLabComponent {
  theme = signal<'light' | 'dark'>('light');

  // Input demo controls
  inputDefault  = new FormControl('texto de ejemplo');
  inputEmpty    = new FormControl('');
  inputDisabled = new FormControl({ value: 'texto desactivado', disabled: true });
  inputIcon     = new FormControl('');

  // Datepicker demo
  dateCtrl     = new FormControl('2026-06-26');
  dateEmpty    = new FormControl('');
  dateDisabled = new FormControl({ value: '2026-06-26', disabled: true });

  // Search demo
  searchCtrl = new FormControl('');
  searchFilled = new FormControl('empleado');

  // Range demo
  timeRangeFilled = '07:30 - 14:30';
  dateRangeFilled = '27 Junio - 02 Julio';

  // Select demo
  selectCtrl    = new FormControl('');
  selectFilled  = new FormControl('opt2');
  selectDisabled = new FormControl({ value: 'opt1', disabled: true });

  readonly selectOptions: ZbSelectOption[] = [
    { label: 'list Item', value: 'opt1' },
    { label: 'list Item', value: 'opt2' },
    { label: 'list Item', value: 'opt3' },
    { label: 'list Item', value: 'opt4' },
    { label: 'list Item', value: 'opt5' },
  ];

  // Checkbox demo
  cbxA = new FormControl(false);
  cbxB = new FormControl(true);
  cbxDisabled = new FormControl({ value: false, disabled: true });
  cbxDisabledChecked = new FormControl({ value: true,  disabled: true });

  // Radio demo
  radioSelected = 'b';

  // Toggle demo
  tglA = new FormControl(false);
  tglB = new FormControl(true);
  tglDisabled = new FormControl({ value: false, disabled: true });
  tglDisabledOn = new FormControl({ value: true,  disabled: true });

  readonly selectRolesOptions: ZbSelectOption[] = [
    { label: 'Cajero',       value: 'cajero' },
    { label: 'Reponedor',    value: 'reponedor' },
    { label: 'Supervisor',   value: 'supervisor' },
    { label: 'Pescadería',   value: 'pescaderia' },
    { label: 'Panadería',    value: 'panaderia' },
  ];

  // Date picker demo
  dpStart = '2026-06-06';
  dpEnd   = '2026-06-13';
  dpResult = '';
  onDpApply(r: DateRange) { this.dpResult = `${r.startDate} → ${r.endDate}`; }

  // Time picker demo
  tpValue  = '09:41';
  tpResult = '09:41';
  onTpApply(v: string) { this.tpResult = v; }

  // Sidepanel demo
  panelCreateOpen = signal(false);
  panelEditOpen   = signal(false);
  panelViewOpen   = signal(false);
  panelResult     = '';
  onPanelSave()   { this.panelResult = 'Guardado'; this.panelCreateOpen.set(false); this.panelEditOpen.set(false); }
  onPanelDelete() { this.panelResult = 'Eliminado'; this.panelEditOpen.set(false); }
  onPanelEdit()   { this.panelResult = 'Editar'; this.panelViewOpen.set(false); }

  // Column menu demo
  readonly demoColumns: ZbColumnDef[] = [
    { id: 'name',      label: 'Nombre',      fixed: true },
    { id: 'role',      label: 'Rol' },
    { id: 'shiftType', label: 'Tipo turno' },
    { id: 'shift',     label: 'Turno' },
    { id: 'zone',      label: 'Zona' },
    { id: 'store',     label: 'Tienda pref.' },
    { id: 'status',    label: 'Estado' },
    { id: 'actions',   label: 'Acciones',    fixed: true },
  ];
  private readonly demoVisibleDefault = ['role', 'shiftType', 'shift', 'zone', 'store', 'status'];
  demoVisible = signal<string[]>(['role', 'shiftType', 'shift', 'zone']);
  onColsChange(keys: string[]) { this.demoVisible.set(keys); }
  onColsReset() { this.demoVisible.set([...this.demoVisibleDefault]); }

  // Dialog demo
  dlgDefault  = signal(false);
  dlgWarning  = signal(false);
  dlgDanger   = signal(false);
  dlgLastAction = '';

  // File upload demo
  fileUploadOpen = signal(false);
  uploadedFiles: string[] = [];
  onLabUpload(files: File[]) { this.uploadedFiles = files.map(f => f.name); }

  toggleTheme() {
    this.theme.update(t => t === 'light' ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', this.theme());
  }
}
