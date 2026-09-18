import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatIconModule, MatIconRegistry } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { DomSanitizer } from '@angular/platform-browser';
import { AbsenceService } from '@app/shared/services/absence.service';
import { WorkerService } from '@app/shared/services/worker.service';
import { AbsenceType, AbsenceRequest } from '@app/shared/interfaces/absence.interface';
import { KindValue } from '@app/shared/interfaces/catalog.interface';
import { CatalogService } from '@app/shared/services/catalog.service';
import { EntityFieldService } from '@app/shared/services/entity-field.service';
import { FieldSchema } from '@app/shared/interfaces/entity-field.interface';
import { DynamicFieldsComponent } from '@app/shared/components/dynamic-fields/dynamic-fields.component';
import { ZbFileUploadComponent } from '@app/shared/components/zb-file-upload/zb-file-upload.component';
import { ZbAlertComponent } from '@app/shared/components/zb-alert/zb-alert.component';
import { Worker } from '@app/shared/interfaces/worker.interface';
import { ZbPageHeaderComponent } from '@app/shared/components/zb-page-header/zb-page-header.component';
import { ZbButtonComponent } from '@app/shared/components/zb-button/zb-button.component';
import { ZbSelectComponent, ZbSelectOption } from '@app/shared/components/zb-select/zb-select.component';
import { ZbSidepanelComponent } from '@app/shared/components/zb-sidepanel/zb-sidepanel.component';
import { ZbCheckboxComponent } from '@app/shared/components/zb-checkbox/zb-checkbox.component';
import { ZbDialogComponent } from '@app/shared/components/zb-dialog/zb-dialog.component';
import { ZbTableToolbarComponent } from '@app/shared/components/zb-table-toolbar/zb-table-toolbar.component';
import { ZbPaginatorComponent } from '@app/shared/components/zb-paginator/zb-paginator.component';
import { ZbSearchInputComponent } from '@app/shared/components/zb-search-input/zb-search-input.component';
import { ZbFilterMenuComponent, ZbFilterDef } from '@app/shared/components/zb-filter-menu/zb-filter-menu.component';

/** Iconos SVG extraídos del Figma (nodo 2374:17894, Table/ausencias).
 *  Se registran localmente para usarlos como <mat-icon svgIcon="...">. */
const AUSENCIAS_ICONS: Record<string, string> = {
  'ausencias-sort':   'icons/ausencias-sort.svg',
  'ausencias-filter': 'icons/ausencias-filter.svg',
  // 'ausencias-edit' es un <svg> inline en la plantilla (mismo SVG de Figma
  // que entity-records). Las flechas del paginador las pinta <zb-paginator>.
};

@Component({
  selector: 'app-absences',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatIconModule, MatTableModule,
    ZbPageHeaderComponent, ZbButtonComponent, ZbSelectComponent,
    ZbSidepanelComponent, ZbCheckboxComponent, ZbDialogComponent,
    ZbTableToolbarComponent, ZbPaginatorComponent, ZbSearchInputComponent,
    ZbFilterMenuComponent, DynamicFieldsComponent,
    ZbFileUploadComponent, ZbAlertComponent,
  ],
  templateUrl: './absences.component.html',
  styleUrl: './absences.component.scss',
})
export class AbsencesComponent implements OnInit {
  /** Columnas de la tabla (Figma 2374:17894). Sin "Estado": no hay moderación. */
  /** Columnas fijas de la tabla. Las configurables se intercalan antes de
   *  "actions" (ver displayedColumns). */
  readonly columnasFijas = ['nombre', 'tipo', 'duracion'];

  /**
   * Columnas de la tabla: las fijas + las que el cliente marque como "Mostrar
   * en tabla" en AdminZebra (AC-2). "Acciones" siempre va al final.
   */
  displayedColumns = computed(() => [
    ...this.columnasFijas,
    ...this.columnasConfigurables().map(f => 'cd_' + f.key),
    'actions',
  ]);
  requests = signal<AbsenceRequest[]>([]);
  types = signal<AbsenceType[]>([]);
  /** Valores del catalogo 'absence_type' (AdminZebra > Catalogo). */
  tiposCatalogo = signal<KindValue[]>([]);

  /** Campos configurables de la entidad (AdminZebra > Entidades > Ausencias):
   *  observaciones, justificante y los que anada el cliente. El 'tipo' se
   *  maneja aparte porque tiene su propio desplegable en el formulario. */
  fieldSchema = signal<FieldSchema[]>([]);
  /** Valores de esos campos para la ausencia que se esta creando/editando. */
  customData: Record<string, any> = {};

  /** Campos del formulario sin el tipo (que ya tiene su propio select). */
  camposFormulario = computed(() =>
    this.fieldSchema().filter(f => f.key !== 'tipo'));

  /** Columnas configurables de la tabla (AC-2). */
  columnasConfigurables = computed(() =>
    this.fieldSchema().filter(f => f.show_in_list && f.key !== 'tipo'));
  workers = signal<Worker[]>([]);
  loading = signal(true);

  page = signal(0);
  pageSize = signal(100);
  readonly pageSizeOptions = [25, 50, 100, 200];

  /** Búsqueda por empleado: nombre o código, igual que en /employees. */
  search = signal('');

  /**
   * Filtro de estado de la ausencia, como select dentro del menu "Filtros"
   * (mismo patron que /employees: un solo boton con los selects dentro).
   *
   * Arranca en 'vigentes': por defecto las finalizadas NO se muestran; son
   * historial y ensucian el listado. No se persiste — al recargar vuelve a
   * ocultarlas.
   */
  estado = signal<'vigentes' | 'finalizadas' | 'todas'>('vigentes');

  /** Clave del filtro en el menu. Con `__` para que no choque con nada. */
  readonly ESTADO_KEY = '__estado';

  /**
   * Una ausencia está finalizada cuando su fecha de fin ya pasó.
   *
   * Una INDEFINIDA nunca lo está: no tiene fin conocido, así que sigue vigente
   * por definición (hoy son 28 de las 29 en QA — tratarlas como finalizadas
   * vaciaría la tabla).
   *
   * La comparación es por cadena YYYY-MM-DD, no con Date: así no entran en
   * juego husos ni horas, y "termina hoy" cuenta como vigente.
   */
  esFinalizada(r: AbsenceRequest): boolean {
    if (!r.end_date) return false;
    return r.end_date < this.hoyIso();
  }

  /** Hoy en YYYY-MM-DD, en hora local (no UTC: toISOString desplaza el día). */
  private hoyIso(): string {
    const d = new Date();
    const mes = String(d.getMonth() + 1).padStart(2, '0');
    const dia = String(d.getDate()).padStart(2, '0');
    return `${d.getFullYear()}-${mes}-${dia}`;
  }

  /** Nº de finalizadas, para la etiqueta del filtro. */
  finalizadasCount = computed(() => this.requests().filter(r => this.esFinalizada(r)).length);

  /**
   * Código de empleado por id, para poder buscar por código (AC-2): la ausencia
   * solo trae `worker` (id) y `worker_name`, no el código.
   *
   * Se resuelve con los workers que el componente YA carga para el select del
   * modal, así que no hay ninguna petición extra ni cambio en el backend.
   */
  private codigosPorWorker = computed<Map<number, string>>(() => {
    const m = new Map<number, string>();
    for (const w of this.workers()) {
      const cod = String((w.custom_data as any)?.codigo ?? '');
      if (cod) m.set(w.id, cod);
    }
    return m;
  });

  /**
   * Ausencias que pasan la búsqueda (AC-3). Se filtra aquí y NO en
   * `pagedRequests` para que la paginación y el contador de páginas cuenten
   * sobre el resultado filtrado.
   */
  filteredRequests = computed(() => {
    // Los dos filtros se APLICAN EN CADENA, no se excluyen (AC-4): buscar un
    // nombre no reactiva las finalizadas, y ver las finalizadas no borra la
    // busqueda.
    let lista = this.requests();
    const est = this.estado();
    if (est === 'vigentes') {
      lista = lista.filter(r => !this.esFinalizada(r));
    } else if (est === 'finalizadas') {
      lista = lista.filter(r => this.esFinalizada(r));
    }
    const q = this.normalizeText(this.search());
    if (!q) return lista;
    const codigos = this.codigosPorWorker();
    return lista.filter(r =>
      this.normalizeText(r.worker_name).includes(q)
      || this.normalizeText(codigos.get(r.worker) ?? '').includes(q));
  });

  pagedRequests = computed(() => {
    const f = this.filteredRequests();
    const size = this.pageSize();
    // Acota la página: al filtrar desde la página 3 el índice se quedaría fuera
    // de rango y la tabla saldría vacía teniendo resultados.
    const pagina = Math.min(this.page(), Math.max(0, Math.ceil(f.length / size) - 1));
    return f.slice(pagina * size, (pagina + 1) * size);
  });
  totalPages = computed(() => Math.max(1, Math.ceil(this.filteredRequests().length / this.pageSize())));

  /** Minúsculas y sin acentos, para que "muñoz" encuentre "MUÑOZ" y "peña"/"pena".
   *  Mismo criterio que el buscador de /employees. */
  private normalizeText(s: string): string {
    return (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim();
  }

  onSearchChange(value: string): void {
    this.search.set(value);
    this.page.set(0);   // si no, buscar desde la página 3 no muestra nada
  }

  /** Definiciones del menu de filtros: por ahora solo el estado. */
  filterMenuDefs = computed<ZbFilterDef[]>(() => [
    { key: this.ESTADO_KEY, label: 'Estado', options: this.estadoOptions() },
  ]);

  /** Valores que recibe el menu (mapa clave -> valor). */
  filterMenuValues = computed<Record<string, string | number | null>>(() => ({
    [this.ESTADO_KEY]: this.estado(),
  }));

  /** Opciones del select, con el recuento de cada grupo. */
  estadoOptions = computed<ZbSelectOption[]>(() => {
    const total = this.requests().length;
    const fin = this.finalizadasCount();
    return [
      { value: 'vigentes', label: `Vigentes (${total - fin})` },
      { value: 'finalizadas', label: `Finalizadas (${fin})` },
      { value: 'todas', label: `Todas (${total})` },
    ];
  });

  /** Aplica lo que emite el menu de filtros. */
  onFiltersChange(values: Record<string, string | number | null>): void {
    const v = values[this.ESTADO_KEY];
    // "todos" (null) equivale a 'todas': mostrar sin filtrar por estado.
    this.estado.set(v === 'finalizadas' ? 'finalizadas' : v === 'todas' || v === null ? 'todas' : 'vigentes');
    this.page.set(0);
  }

  /** Limpia el filtro: vuelve al estado de entrada a la pantalla. */
  clearFilters(): void {
    this.estado.set('vigentes');
    this.page.set(0);
  }

  // ── Excel (AC-1/AC-2/AC-3) ───────────────────────────────────

  showImport = false;
  importando = signal(false);

  /** AC-1: exporta el listado a Excel. */
  descargarExcel(): void {
    this.absenceService.exportExcel().subscribe({
      next: blob => this.descargar(blob, `ausencias-${new Date().toISOString().slice(0, 10)}.xlsx`),
      error: () => this.avisoImport.set({ tipo: 'error', texto: 'No se pudo exportar el Excel.' }),
    });
  }

  /** AC-3: plantilla de ejemplo con los empleados vigentes precargados. */
  descargarEjemplo(): void {
    this.absenceService.downloadImportTemplate().subscribe({
      next: blob => this.descargar(blob, 'plantilla_ausencias.xlsx'),
      error: () => this.avisoImport.set({ tipo: 'error', texto: 'No se pudo descargar la plantilla.' }),
    });
  }

  private descargar(blob: Blob, nombre: string): void {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = nombre;
    a.click();
    URL.revokeObjectURL(url);
  }

  /** Aviso del resultado de la importacion (creadas / errores por fila). */
  avisoImport = signal<{ tipo: 'success' | 'warning' | 'error'; texto: string } | null>(null);
  erroresImport = signal<string[]>([]);

  // ── Revision previa: al soltar el fichero, antes de importar ──

  revisando = signal(false);
  revision = signal<{ crearian: number; filas: number; fallos: string[] } | null>(null);

  /**
   * Se llama en cuanto se suelta el Excel en el modal. Lo valida en el servidor
   * sin escribir nada, para decir de antemano cuantas ausencias entrarian y que
   * filas fallan: asi se puede corregir el fichero sin haber importado a medias.
   */
  revisarFichero(files: File[]): void {
    const file = files[0];
    if (!file) return;
    this.revisando.set(true);
    this.revision.set(null);
    this.absenceService.revisarExcel(file).subscribe({
      next: res => {
        this.revisando.set(false);
        this.revision.set({
          crearian: res.created || 0,
          filas: res.total_rows || 0,
          fallos: res.errors || [],
        });
      },
      // Si la revision falla no se bloquea la importacion: se deja al usuario
      // intentarlo y que el import normal informe.
      error: () => { this.revisando.set(false); this.revision.set(null); },
    });
  }

  /** Texto del resumen de la revision. */
  textoRevision(): string {
    const r = this.revision();
    if (!r) return '';
    const aus = (n: number) => `${n} ${n === 1 ? 'ausencia' : 'ausencias'}`;
    const fil = (n: number) => `${n} ${n === 1 ? 'fila' : 'filas'}`;
    if (!r.filas) return 'El fichero no tiene ninguna fila con datos de ausencia.';
    if (!r.fallos.length) return `Se importaran ${aus(r.crearian)}. Todo correcto.`;
    if (!r.crearian) return `Ninguna fila es valida: ${fil(r.fallos.length)} con avisos.`;
    return `Se importaran ${aus(r.crearian)}. Revisa ${fil(r.fallos.length)}:`;
  }

  /** Tipo de aviso segun lo que se haya encontrado. */
  tipoRevision(): 'success' | 'warning' | 'error' {
    const r = this.revision();
    if (!r || !r.filas) return 'warning';
    if (!r.crearian) return 'error';
    return r.fallos.length ? 'warning' : 'success';
  }

  /** AC-2: importa el Excel y muestra el resumen. */
  importarExcel(files: File[]): void {
    const file = files[0];
    if (!file) return;
    this.showImport = false;
    this.importando.set(true);
    this.revision.set(null);
    this.avisoImport.set(null);
    this.erroresImport.set([]);

    this.absenceService.importExcel(file).subscribe({
      next: res => {
        this.importando.set(false);
        this.erroresImport.set(res.errors || []);
        const creadas = res.created || 0;
        const fallos = (res.errors || []).length;
        // AC-6: se dice cuantas entraron Y cuantas fallaron; el detalle por
        // fila se lista debajo para poder corregir el fichero.
        // Singular/plural: "1 filas" cantaba.
        const nAus = (n: number) => `${n} ${n === 1 ? 'ausencia' : 'ausencias'}`;
        const nFilas = (n: number) => `${n} ${n === 1 ? 'fila' : 'filas'}`;

        if (creadas && fallos) {
          this.avisoImport.set({ tipo: 'warning',
            texto: `Se han importado ${nAus(creadas)}. ${nFilas(fallos)} `
              + `${fallos === 1 ? 'no se ha' : 'no se han'} podido importar.` });
        } else if (creadas) {
          this.avisoImport.set({ tipo: 'success',
            texto: `Se ${creadas === 1 ? 'ha' : 'han'} importado ${nAus(creadas)} correctamente.` });
        } else if (fallos) {
          this.avisoImport.set({ tipo: 'error',
            texto: `No se ha importado ninguna ausencia. ${nFilas(fallos)} con errores.` });
        } else {
          this.avisoImport.set({ tipo: 'warning',
            texto: 'El fichero no tenia ninguna fila con datos de ausencia.' });
        }
        this.load();
      },
      error: err => {
        this.importando.set(false);
        this.avisoImport.set({ tipo: 'error',
          texto: err?.error?.error || 'Error al importar el fichero.' });
      },
    });
  }

  cerrarAvisoImport(): void {
    this.avisoImport.set(null);
    this.erroresImport.set([]);
  }

  /** Etiqueta del estado actual, para el aviso de tabla vacia. */
  estadoLabel(): string {
    const e = this.estado();
    return e === 'finalizadas' ? 'finalizadas' : e === 'todas' ? '' : 'vigentes';
  }

  showAdd = false;
  /** id de la ausencia en edición; null → creando una nueva. */
  editingId: number | null = null;
  // status='approved' fijo: la empresa registra directamente (Figma: sin
  // moderación). El backend lo necesita 'approved' para que el planificador la
  // considere; no se muestra en la UI.
  // `tipo` es la ETIQUETA del catalogo (no un id): el backend resuelve el
  // AbsenceType por nombre, asi que el cliente puede anadir tipos desde
  // AdminZebra sin que aqui haya que tocar nada.
  newRequest = { worker: 0, tipo: '', start_date: '', end_date: '', indefinite: false, reason: '', status: 'approved' };

  /** Título del sidepanel según crear/editar. */
  get panelTitle(): string {
    return this.editingId === null ? 'Registrar ausencia' : 'Editar ausencia';
  }

  /**
   * Empleados del select del modal. El codigo va en la etiqueta a proposito: el
   * buscador del zb-select filtra por `label`, asi que incluyendolo se puede
   * localizar tanto por nombre como por codigo, igual que en la tabla.
   */
  get workerOptions(): ZbSelectOption[] {
    return this.workers().map(w => {
      const cod = String((w.custom_data as any)?.codigo ?? '');
      return { label: cod ? `${w.name} · ${cod}` : w.name, value: w.id };
    });
  }

  /**
   * Tipos de ausencia. Salen del CATALOGO (Kind 'absence_type'), que es lo que
   * el cliente gestiona desde AdminZebra > Catalogo, no de la tabla
   * AbsenceType. Asi anadir un tipo no necesita desarrollo.
   *
   * El valor es la etiqueta, no un id: el backend resuelve el AbsenceType por
   * nombre al guardar (ver resolver_absence_type), de forma que las ausencias
   * ya registradas siguen apuntando a su fila de siempre.
   */
  get typeOptions(): ZbSelectOption[] {
    const delCatalogo = this.tiposCatalogo();
    if (delCatalogo.length) {
      return delCatalogo.map(v => ({ label: v.label, value: v.label }));
    }
    // Respaldo: si el catalogo aun no esta configurado, se usan los tipos de
    // siempre para que la pantalla no se quede sin opciones.
    return this.types().map(t => ({ label: t.name, value: t.name }));
  }

  constructor(
    private absenceService: AbsenceService,
    private workerService: WorkerService,
    private catalogService: CatalogService,
    private entityFieldService: EntityFieldService,
    iconRegistry: MatIconRegistry,
    sanitizer: DomSanitizer,
  ) {
    for (const [name, path] of Object.entries(AUSENCIAS_ICONS)) {
      iconRegistry.addSvgIcon(name, sanitizer.bypassSecurityTrustResourceUrl(path));
    }
  }

  ngOnInit(): void {
    this.absenceService.invalidate();
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.absenceService.getTypes().subscribe(t => this.types.set(t));
    // Tipos del catalogo. Si falla (catalogo sin configurar) se deja vacio y
    // typeOptions cae al respaldo de AbsenceType.
    this.catalogService.getValues('absence_type').subscribe({
      next: v => this.tiposCatalogo.set(v),
      error: () => this.tiposCatalogo.set([]),
    });
    // Campos configurables de la entidad 'absence' (AC-1/AC-2).
    this.entityFieldService.getAll('absence').subscribe({
      next: fields => this.fieldSchema.set(
        fields.filter(f => f.active).sort((a, b) => a.order - b.order) as any),
      error: () => this.fieldSchema.set([]),
    });
    this.workerService.getActive().subscribe(w => this.workers.set(w));
    this.absenceService.getRequests().subscribe({
      next: r => { this.requests.set(r); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  setPageSize(size: number): void {
    this.pageSize.set(size);
    this.page.set(0);
  }

  /** Valor de una celda configurable, legible. */
  valorCelda(r: AbsenceRequest, f: FieldSchema): string {
    const v = (r as any).custom_data?.[f.key];
    if (v === null || v === undefined || v === '') return '—';
    if (f.field_type === 'boolean') return (v === true || v === 'true') ? 'Sí' : 'No';
    if (Array.isArray(v)) return v.join(', ');
    return String(v);
  }

  /** "27/06/26 - 02/07/26"  ·  indefinida → "27/06/26 - Indefinida". */
  formatRange(r: AbsenceRequest): string {
    const start = this.dmy(r.start_date);
    const end = r.end_date ? this.dmy(r.end_date) : 'Indefinida';
    return `${start} - ${end}`;
  }

  /** YYYY-MM-DD → DD/MM/YY. */
  private dmy(iso: string): string {
    const [y, m, d] = iso.split('-');
    return `${d}/${m}/${y.slice(2)}`;
  }

  openAdd(): void {
    this.editingId = null;
    this.resetForm();
    this.showAdd = true;
  }

  /** Abre el sidepanel precargado con los datos de la fila a editar. */
  openEdit(r: AbsenceRequest): void {
    this.editingId = r.id;
    this.newRequest = {
      worker: r.worker,
      // type_name viene del serializer; es lo que casa con el catalogo.
      tipo: r.type_name ?? '',
      start_date: r.start_date,
      end_date: r.end_date ?? '',
      indefinite: r.indefinite,
      reason: r.reason ?? '',
      status: r.status || 'approved',
    };
    this.showAdd = true;
  }

  cancelNew(): void {
    this.editingId = null;
    this.resetForm();
  }

  saveNew(): void {
    // Si es indefinida, no se envía fecha fin (el empleado no se planifica).
    // `status` es read-only en el backend (nace 'pending'); la empresa registra
    // sin moderación, así que tras crear se aprueba automáticamente para que el
    // planificador la tenga en cuenta.
    const { status: _omit, tipo, ...rest } = this.newRequest;
    const payload: any = {
      ...rest,
      // El tipo va en custom_data: es un campo configurable de la entidad
      // (catalog_select sobre 'absence_type'), no una columna fija.
      custom_data: { ...this.customData, tipo },
      end_date: this.newRequest.indefinite ? null : this.newRequest.end_date,
    };
    const editingId = this.editingId;
    const request$ = editingId === null
      ? this.absenceService.createRequest(payload)
      : this.absenceService.updateRequest(editingId, payload);
    request$.subscribe((saved: any) => {
      const id = editingId ?? saved?.id;
      const currentStatus = editingId === null ? 'pending' : (saved?.status ?? 'approved');
      const done = () => {
        this.showAdd = false;
        this.editingId = null;
        this.resetForm();
        this.load();
      };
      // Un registro nuevo nace 'pending' en el backend → lo aprobamos (sin
      // moderación en la UI). Al editar uno ya aprobado no hace falta.
      if (id && currentStatus === 'pending') {
        this.absenceService.approve(id).subscribe({ next: done, error: done });
        return;
      }
      done();
    });
  }

  // ── Confirmación de borrado ──
  showDeleteConfirm = false;

  /** "Eliminar" del sidepanel → pide confirmación (acción irreversible). */
  deleteRequest(): void {
    if (this.editingId === null) return;
    this.showDeleteConfirm = true;
  }

  confirmDelete(): void {
    if (this.editingId === null) return;
    this.absenceService.deleteRequest(this.editingId).subscribe(() => {
      this.showDeleteConfirm = false;
      this.showAdd = false;
      this.editingId = null;
      this.resetForm();
      this.load();
    });
  }

  private resetForm(): void {
    this.newRequest = { worker: 0, tipo: '', start_date: '', end_date: '', indefinite: false, reason: '', status: 'approved' };
    this.customData = {};
  }
}
