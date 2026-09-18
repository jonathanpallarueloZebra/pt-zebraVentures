import { Component, OnInit, OnDestroy, signal, computed, inject, HostListener } from '@angular/core';
import { BrandingService } from '@app/shared/services/branding.service';
import { DatePickerMode } from '@app/shared/interfaces/branding.interface';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, NavigationEnd } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { DragDropModule, CdkDragDrop } from '@angular/cdk/drag-drop';
import { forkJoin, Observable, Subject, of, Subscription } from 'rxjs';
import { debounceTime, switchMap, catchError, filter } from 'rxjs/operators';
import { PlanningService, BulkGenerationResult } from '@app/shared/services/planning.service';
import { NotificationService } from '@app/shared/services/notification.service';
import { WorkerService } from '@app/shared/services/worker.service';
import { ShiftService } from '@app/shared/services/shift.service';
import { EntityRecordService } from '@app/shared/services/entity-record.service';
import { EntityTypeService } from '@app/shared/services/entity-type.service';
import { EntityFieldService } from '@app/shared/services/entity-field.service';
import { CatalogService } from '@app/shared/services/catalog.service';
import { RestDayService } from '@app/shared/services/rest-day.service';
import { AbsenceService } from '@app/shared/services/absence.service';
import { ClosedDayService } from '@app/shared/services/closed-day.service';
import { RestrictionService } from '@app/shared/services/restriction.service';
import { ClosedDay } from '@app/shared/interfaces/closed-day.interface';
import { AbsenceRequest } from '@app/shared/interfaces/absence.interface';
import { DayPlan, ShiftAssignment, RestrictionViolation, RestDay } from '@app/shared/interfaces/planning.interface';
import { Worker } from '@app/shared/interfaces/worker.interface';
import { ZbPageHeaderComponent } from '@app/shared/components/zb-page-header/zb-page-header.component';
import { ZbDialogComponent, ZbDialogMode } from '@app/shared/components/zb-dialog/zb-dialog.component';
import { ZbDatePickerPanelComponent, DateRange } from '@app/shared/components/zb-date-picker-panel/zb-date-picker-panel.component';
import { DropdownFlipDirective } from '@app/shared/directives/dropdown-flip.directive';

export interface SimpleArea { id: number; name: string; active: boolean; }

/** Una regla de `scopeMatch` (elegibilidad por ámbito). Espejo de las que
 *  evalúa `worker_passes_scope_match()` en el back. */
export interface ScopeMatchRule {
  workerField: string;
  matchType?: 'id' | 'field' | 'attr';
  scopeField?: string;
  requireField?: string;
  requireValue?: string;
}

export interface TableCell {
  date: string;
  isRest: boolean;
  isOfficialRest: boolean;
  shiftName: string;
  start: string;
  end: string;
  slotCode: string;
  color: string;
}

export interface TableWorkerRow {
  worker: Worker;
  primaryPill: string;
  groupColor: string;
  days: TableCell[];
}

export interface CalendarBlock {
  id: string;
  slotCode: string;
  index: number;
  workerId: number;
  workerName: string;
  shiftName: string;
  start: string;
  end: string;
  color: string;
  row: number;
  areas: string[];
}

export interface ShiftLaneBlock {
  id: string;
  slotCode: string;
  shiftName: string;
  start: string;
  end: string;
  color: string;
  row: number;
  workers: { workerId: number; workerName: string; index: number }[];
}

export interface WorkerOption {
  worker: Worker;
  warnings: string[];
  blocked: boolean;
  blockReason: string;
}

export interface FilterDef {
  key: string;
  label: string;
  field_type: string;
  options: { value: string | number; label: string }[];
}

@Component({
  selector: 'app-schedule',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    MatIconModule, MatTooltipModule,
    MatSnackBarModule, DragDropModule,
    ZbPageHeaderComponent, ZbDialogComponent,
    ZbDatePickerPanelComponent, DropdownFlipDirective,
  ],
  templateUrl: './schedule.component.html',
  styleUrl: './schedule.component.scss',
})
export class ScheduleComponent implements OnInit, OnDestroy {
  readonly skRows = Array(8);
  /** Nº de columnas de sección de muestra para el skeleton de carga. */
  readonly skSections = Array(4);
  private alive = true;
  plan = signal<DayPlan[]>([]);
  // ── Memoización de violaciones por celda (rendimiento) ──────────────────
  // El template llama a cellViolations/workerSeverity miles de veces por
  // segundo (una por celda × trabajador × ciclo de detección de cambios).
  // Recalcular cada vez colgaba la tabla. Cacheamos el resultado por clave y
  // solo invalidamos cuando cambian las violaciones (plan) o las celdas
  // pendientes. `_cvVersion` sube en cada cambio relevante → los caches con
  // versión distinta se descartan; el resto son aciertos O(1).
  private _cvCache = new Map<string, RestrictionViolation[]>();
  private _sevCache2 = new Map<string, 'error' | 'warning' | null>();
  private _cvSig: any = null;   // firma (referencias) de la última invalidación
  /** Limpia los caches si cambió el plan o las celdas pendientes (referencias
   *  nuevas). Barato: solo compara referencias, no recorre nada. */
  private ensureViolationsCache(): void {
    const sig = { p: this.plan(), pc: this.pendingCells(), ss: this.shiftSlots() };
    if (!this._cvSig || this._cvSig.p !== sig.p || this._cvSig.pc !== sig.pc || this._cvSig.ss !== sig.ss) {
      this._cvCache.clear();
      this._sevCache2.clear();
      // Depende de la plantilla de la tienda cargada: al cambiar de tienda o de
      // semana hay que recalcular qué secciones no abren cada día.
      this._secClosedCache.clear();
      this._cvSig = sig;
    }
  }
  /**
   * Modo del selector de fechas, configurado en Admin Zebra → Marca.
   *
   * 'week' selecciona la semana completa con un clic; 'range' pide inicio y fin.
   * Si el backend no informa el campo se asume 'range', que es el
   * comportamiento previo a esta configuración (así ningún proyecto existente
   * cambia de conducta sin querer).
   */
  private brandingService = inject(BrandingService);
  datePickerMode = computed<DatePickerMode>(
    () => this.brandingService.branding().date_picker_mode ?? 'range');

  startDate = signal('');
  loading = signal(true);
  saving = signal(false);
  generating = signal(false);
  generatingAll = signal(false);
  /** Desplegable del botón "Generar" (opción "Generar todas las tiendas"). */
  generateMenuOpen = signal(false);
  editMode = signal(false);
  validating = signal(false);
  validatingCell = signal<{day: string; slot: string} | null>(null);
  /** Celdas (clave `día|slot`) modificadas desde la última validación y aún
   *  pendientes de revalidar. Mientras una celda está aquí, NO se le arrastran
   *  violations viejas que solo casan por nombre del trabajador (evita el
   *  warning fantasma al mover a alguien: su warning anterior "seguía" al
   *  worker a la celda destino hasta que llegaba la validación fresca). */
  private pendingCells = signal<Set<string>>(new Set());
  hasUnsavedChanges = signal(false);
  lastSavedAt = signal('');
  /** Timer que auto-oculta el chip "Guardado HH:MM" a los 3s. */
  private savedChipTimer: any = null;
  lastGenerationResult = signal<any>(null);
  private pendingInitialValidation = signal(false);

  /**
   * Regeneración automática por ficha desactualizada (`applyStaleIfNeeded`) en
   * curso: al terminar de validar hay que GUARDAR sola la semana, no dejarla en
   * borrador.
   *
   * Sin esto la pantalla entraba en bucle: se regeneraba al abrir, quedaba en
   * modo edición sin guardar, el plan de la BD seguía siendo el viejo (y por
   * tanto seguía `stale`), así que al volver a entrar saltaba otra vez el toast
   * y otra vez el modo edición. Nunca salía de ahí sin pulsar Guardar a mano.
   *
   * El guardado espera a la validación porque `save()` bloquea si hay errores y
   * el recuento llega por el pipe con debounce, no de inmediato.
   */
  private autoSaveAfterValidation: { startDate: string; scopeId: number } | null = null;

  /**
   * El plan guardado se calculó antes de la última edición de fichas de ESTA
   * tienda (lo dice el back en `stale`). Los avisos que se ven pueden estar ya
   * resueltos: hay que regenerar para aplicarlo.
   *
   * No se regenera solo a propósito: regenerar reasigna la semana entera y
   * borraría los ajustes hechos a mano.
   */
  planStale = signal(false);
  staleWorkers = signal<string[]>([]);

  /**
   * `{fecha: Set(workerId)}` de quien ya trabaja en OTRA tienda esa semana.
   *
   * Sin esto el diagnóstico daba por libres a los volantes que otra tienda ya
   * tenía cogidos (T01 genera primero y se queda los de la zona), y sugería
   * cubrir huecos de T02 con gente que ese día está en T01.
   */
  private busyElsewhere = signal<Record<string, Set<number>>>({});

  /** Set of scope IDs currently being generated */
  private generatingScopes = signal(new Set<number>());

  shiftSlots = signal<any[]>([]);
  /** Todos los turnos crudos del backend (sin filtrar por vigencia). Se
   *  refiltra por semana en applyShiftValidityFilter al navegar. */
  private allShiftSlotsRaw = signal<any[]>([]);
  workers = signal<Worker[]>([]);
  allWorkers = signal<Worker[]>([]); // full unfiltered list for pickers
  areas = signal<SimpleArea[]>([]);
  weeklyRestDays = signal<RestDay[]>([]);
  /** Ausencias aprobadas (incl. indefinidas) para excluir empleados del selector. */
  approvedAbsences = signal<AbsenceRequest[]>([]);

  /** ¿El trabajador `wid` tiene una ausencia aprobada que cubre la fecha `dateStr`?
   *  Una ausencia indefinida (end_date null) cubre desde start_date en adelante. */
  private isAbsentOn(wid: number, dateStr: string): boolean {
    return this.approvedAbsences().some(a => {
      if (a.worker !== wid) return false;
      if (dateStr < a.start_date) return false;        // antes de empezar
      // Indefinida (indefinite y sin end_date): cubre desde start en adelante.
      if (a.indefinite && !a.end_date) return true;
      // Normal: dentro de [start_date, end_date].
      return !!a.end_date && dateStr <= a.end_date;
    });
  }

  /** Días de cierre del negocio (festivos) para el ámbito actual o globales. */
  closedDays = signal<ClosedDay[]>([]);

  /** ¿Es `dateStr` un día de cierre? El negocio cierra los DOMINGOS y los
   *  festivos registrados (globales o de esta tienda). En esos días no hay
   *  turno que cubrir, así que NO se muestran ausencias (ni en pantalla ni en
   *  PDF): el concepto de "ausencia" no aplica con el negocio cerrado. */
  private isClosedDay(dateStr: string): boolean {
    // Domingo (getDay() === 0)
    if (new Date(dateStr + 'T00:00:00').getDay() === 0) return true;
    // Festivo registrado: global (scope 0) o de la tienda seleccionada
    const scope = this.selectedScopeId();
    return this.closedDays().some(c =>
      c.date === dateStr &&
      (c.scope_entity_id === 0 || c.scope_entity_id === scope)
    );
  }
  private pillsFieldKey = signal('');
  /** Campo EAV worker→turno base (p.ej. 'turno_base'), auto-detectado. */
  private shiftFieldKey = signal('');
  /** Campo EAV worker→ámbito de planificación (p.ej. 'tienda'), auto-detectado
   *  igual que los otros dos. Se usa para no ofrecer en el desplegable gente de
   *  otras tiendas. */
  private scopeFieldKey = signal('');

  // Scope (planning ámbito entity)
  scopeEntityName = signal('');
  scopeRecords = signal<{id: number; name: string}[]>([]);
  /** `data` completo de cada registro de ámbito (id → data). Se guarda aparte de
   *  scopeRecords porque la elegibilidad necesita otros campos (p.ej. la zona de
   *  la tienda), no solo el nombre. */
  private scopeDataById = signal<Record<number, any>>({});
  selectedScopeId = signal(0);

  /** Reglas `scopeMatch` de la restricción de elegibilidad por ámbito activa.
   *  El desplegable de empleados las aplica para no ofrecer a quien el
   *  validador del back rechazaría por estar fuera de su ámbito. */
  private scopeMatchRules = signal<ScopeMatchRule[]>([]);
  /** Turnos PROHIBIDOS a quien cumple un filtro (restricciones de error del tipo
   *  "Régimen antiguo no trabaja sábado tarde"). */
  private shiftBlocks = signal<{ shift: string; field: string; value: unknown }[]>([]);

  /**
   * Topes de plazas por sección y turno (restricciones count / shift_area /
   * lte), leídos igual que `_area_cap` en el generador.
   *
   * Con la sección al tope no se ofrece añadir más gente: el "+" desaparece.
   * Antes el botón salía siempre, dejabas meter a la cuarta persona y el error
   * aparecía después de validar — el sistema te invitaba a hacer algo que él
   * mismo iba a marcar mal.
   */
  private areaCaps = signal<{ porNombre: Map<string, number>; porDefecto: number | null }>(
    { porNombre: new Map(), porDefecto: null });

  /** EAV-driven worker filters */
  workerFilters = signal<FilterDef[]>([]);
  activeFilters = signal<Record<string, string | number>>({});

  private validateSubject = new Subject<void>();

  constructor(
    private planningService: PlanningService,
    private notificationService: NotificationService,
    private router: Router,
    private route: ActivatedRoute,
    private workerService: WorkerService,
    private shiftService: ShiftService,
    private entityRecordService: EntityRecordService,
    private entityTypeService: EntityTypeService,
    private entityFieldService: EntityFieldService,
    private catalogService: CatalogService,
    private restDayService: RestDayService,
    private absenceService: AbsenceService,
    private closedDayService: ClosedDayService,
    private restrictionService: RestrictionService,
    private snackBar: MatSnackBar,
  ) {}

  // ── Dialog state ──────────────────────────────────────────────
  showGenerateConfirm  = false;
  showGenerateAllConfirm = false;
  generateAllMessage   = '';
  showGenerationWarnings = false;
  generationWarningsTitle   = '';
  generationWarningsMessage = '';
  generationWarningsMode: ZbDialogMode = 'warning';
  showCopyConfirm  = false;
  showCopyError    = false;
  showClearConfirm = false;
  showCancelConfirm = false;

  ngOnDestroy(): void {
    this.alive = false;
    clearTimeout(this.savedChipTimer);
    this.navSub?.unsubscribe();
  }

  /** Suscripción a NavigationEnd para recargar al volver a la pantalla. */
  private navSub?: Subscription;
  /** Ya se hizo la carga inicial: el primer NavigationEnd no debe duplicarla. */
  private primeraCargaHecha = false;
  /** Hay un loadWeek pidiendo datos: evita recargas solapadas al navegar. */
  private cargaEnVuelo = false;

  ngOnInit(): void {
    // Volver a /schedule desde otra pantalla (p.ej. editar una ficha en
    // /employees) NO reconstruye el componente: Angular lo reutiliza y ngOnInit
    // no se repite. Sin esto la semana se quedaba con los datos de la primera
    // visita — no se detectaba que las fichas habían cambiado y el aviso "has
    // cambiado la ficha de X" solo salía forzando Ctrl+F5.
    this.navSub = this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe(() => {
        if (!this.alive || !this.router.url.startsWith('/schedule')) return;
        // El NavigationEnd de la propia entrada llega antes de que ngOnInit
        // termine de cargar: se ignora para no pedir la semana dos veces.
        if (!this.primeraCargaHecha) return;
        // Con una generación en curso NO se recarga: la respuesta llegaría
        // después y pisaría el plan recién generado.
        if (this.isCurrentScopeGenerating() || this.generatingAll()) return;
        // Ni con una carga ya en vuelo: dos loadWeek simultáneos se pisan y el
        // aviso de ficha desactualizada del primero se perdía. No se usa
        // `loading()` porque en la rama normal se apaga desde el pipe de
        // validación, no al recibir el plan: seguiría en true aquí y bloquearía
        // la recarga legítima.
        if (this.cargaEnVuelo) return;
        this.loadWeek(this.startDate());
      });

    // Set up debounced validation pipeline
    this.validateSubject.pipe(
      // 80ms: reacciona casi al instante tras soltar un trabajador, pero sigue
      // agrupando arrastres rápidos seguidos en una sola validación.
      debounceTime(80),
      switchMap(() => {
        this.validating.set(true);
        return this.planningService.validatePlan(this.plan(), this.selectedScopeId() || undefined).pipe(
          catchError(() => {
            this.validating.set(false);
            this.validatingCell.set(null);
            // Si la validación falla, liberamos las celdas pendientes para no
            // dejarlas sin badges permanentemente; vuelven a mostrar el último
            // estado conocido (matching normal).
            if (this.pendingCells().size) this.pendingCells.set(new Set());
            if (this.pendingInitialValidation()) {
              this.pendingInitialValidation.set(false);
              this.loading.set(false);
            }
            return of(null);
          }),
        );
      }),
    ).subscribe(result => {
      if (!result) return;
      // Actualización incremental: solo reemplazamos el objeto `day` cuyas
      // violations REALMENTE cambian. Conservar la referencia de los días sin
      // cambios evita que Angular repinte esas celdas (menos trabajo y, sobre
      // todo, sin parpadeo del resto de la tabla al mover un trabajador).
      // Violations SEMANALES (per_week_*): el backend las devuelve con
      // dayDate=null (no cuelgan de un día concreto). Si solo filtramos por
      // día se pierden del conteo y el banner de avisos NO aparece aunque el
      // plan se generó con avisos. Se adjuntan al PRIMER día del plan para que
      // entren en getWeekWarningCount()/getWeekErrorCount() (una sola vez).
      const weeklyV = (result.violations as any[]).filter(v => !v.dayDate);
      let changed = false;
      const updated = this.plan().map((day, idx) => {
        let dayV = result.violations.filter((v: any) => v.dayDate === day.date);
        if (idx === 0 && weeklyV.length) dayV = [...dayV, ...weeklyV];
        if (this.sameViolations(day.violations ?? [], dayV)) return day;
        changed = true;
        return { ...day, violations: dayV };
      });
      if (changed) this.plan.set(updated);
      this.validating.set(false);
      this.validatingCell.set(null);
      // Llegó validación fresca: ya no hay celdas pendientes → se vuelve a
      // permitir el matching completo de violations (incluido por nombre).
      if (this.pendingCells().size) this.pendingCells.set(new Set());
      if (this.pendingInitialValidation()) {
        this.pendingInitialValidation.set(false);
        this.loading.set(false);
      }
      // Ya hay recuento de errores fresco: si esta regeneración venía de una
      // ficha desactualizada, se guarda sola (ver `autoSaveAfterValidation`).
      //
      // Se comprueba que la validación sea de la MISMA semana/tienda que pidió
      // el auto-guardado: `validatePlan()` se llama desde muchos sitios y una
      // validación que ya venía en vuelo (la de loadWeek, p.ej.) consumía la
      // bandera y guardaba el plan viejo antes de que la regeneración acabara
      // — dejando la pantalla en modo edición.
      const pend = this.autoSaveAfterValidation;
      if (pend && pend.startDate === this.startDate() && pend.scopeId === this.selectedScopeId()
          && !this.generating()) {
        this.autoSaveAfterValidation = null;
        this.saveAfterAutoRegeneration();
      }
    });

    const requestedWeek = this.route.snapshot.queryParamMap.get('week');
    const monday = requestedWeek || this.getCurrentMonday();
    this.startDate.set(monday);
    // Reglas de elegibilidad por ámbito (para el desplegable de empleados). Va
    // aparte del forkJoin: si falla, el resto de la pantalla debe cargar igual.
    this.restrictionService.getAll().pipe(catchError(() => of([]))).subscribe(rs => {
      const rule = (rs as any[]).find(
        r => r.active !== false && (r.config as any)?.scopeMatch);
      const sm = (rule?.config as any)?.scopeMatch;
      const raw = sm?.rules ?? (sm?.workerField && sm?.scopeField ? [sm] : []);
      this.scopeMatchRules.set(raw as ScopeMatchRule[]);

      // Prohibiciones de turno por ERROR (p.ej. "Régimen antiguo no trabaja
      // sábado tarde"): condition / per_week_worker_shift / lte 0 / targetShift.
      // Sin esto, el picker ofrecía a alguien para un turno que le está
      // prohibido y luego el plan salía con error.
      const blocks: { shift: string; field: string; value: unknown }[] = [];
      for (const r of rs as any[]) {
        const cfg = (r?.config ?? {}) as any;
        if (r?.active === false || r?.severity !== 'error') continue;
        if (cfg.scope !== 'per_week_worker_shift' || cfg.operator !== 'lte') continue;
        if (Number(cfg.threshold) !== 0 || !cfg.targetShift) continue;
        const f = cfg.filter;
        if (f?.op === 'eq' && f?.field) {
          blocks.push({ shift: String(cfg.targetShift), field: f.field, value: f.value });
        }
      }
      this.shiftBlocks.set(blocks);

      // TOPES por sección (count / shift_area / lte). Misma lógica que
      // `_area_cap` del generador: si hay varias reglas para la misma sección
      // gana la más restrictiva, y una regla sin `filterAreaNames` es el tope
      // por defecto de cualquier sección.
      const porNombre = new Map<string, number>();
      let porDefecto: number | null = null;
      for (const r of rs as any[]) {
        const cfg = (r?.config ?? {}) as any;
        if (r?.active === false) continue;
        if (r?.engine !== 'count' || cfg.groupBy !== 'shift_area') continue;
        if (cfg.subject !== 'workers' || cfg.operator !== 'lte') continue;
        const th = Number(cfg.threshold);
        if (!Number.isFinite(th)) continue;
        const names = cfg.filterAreaNames;
        if (names) {
          for (const n of (Array.isArray(names) ? names : [names])) {
            const k = this.normalizeSection(String(n));
            porNombre.set(k, Math.min(porNombre.get(k) ?? th, th));
          }
        } else {
          porDefecto = porDefecto === null ? th : Math.min(porDefecto, th);
        }
      }
      this.areaCaps.set({ porNombre, porDefecto });
    });
    forkJoin({
      slots: this.shiftService.getAll(),
      workers: this.workerService.getAll(),
      entityTypes: this.entityTypeService.getAll(),
    }).subscribe(({ slots, workers, entityTypes }) => {
      // Guarda todos los turnos crudos y aplica el filtro de vigencia para la
      // semana actual. Se refiltra al navegar de semana (ver loadWeek).
      this.allShiftSlotsRaw.set(slots as any[]);
      this.applyShiftValidityFilter(monday);
      this.workers.set(workers);
      this.allWorkers.set(workers);
      // ── Scope entity (ámbito de planificación) ────────────────────────────
      const scopeEt = entityTypes.find((e: any) => e.is_planning_scope);
      if (scopeEt) {
        this.scopeEntityName.set(scopeEt.name);
      }
      const scopeSlug = scopeEt?.slug ?? '';
      // Etiquetas legibles de la zona, para el texto de "Generar esta zona".
      this.loadZoneLabels(scopeSlug);
      const scope$ = scopeSlug ? this.entityRecordService.getAll(scopeSlug) : of([]);

      // ── Pills entity (chips asignables dentro de cada turno) ─────────────
      const pillsEt = entityTypes.find((e: any) => e.show_in_schedule);
      const pillsSlug = pillsEt?.slug ?? '';
      const pillsDisplay = pillsEt?.display_field || 'nombre';
      const pills$ = pillsSlug ? this.entityRecordService.getAll(pillsSlug) : of([]);
      // Find the worker field that links to the pills entity (e.g. 'rol' → 'roles')
      if (pillsSlug && workers.length) {
        const schema = workers[0].field_schema ?? [];
        const pf = schema.find(f => f.target_entity === pillsSlug);
        if (pf) this.pillsFieldKey.set(pf.key);
      }
      // Campo worker→turno base (primer entity_select que apunta a 'shift'),
      // misma auto-detección que el generador. Se usa para saber si una celda
      // vacía tiene personal capaz de cubrirla.
      if (workers.length) {
        const sf = (workers[0].field_schema ?? []).find(
          f => f.target_entity === 'shift' && f.field_type === 'entity_select');
        if (sf) this.shiftFieldKey.set(sf.key);
      }
      // Campo worker→ámbito (p.ej. 'tienda'), para filtrar el desplegable de
      // empleados por la tienda que se está planificando.
      if (scopeSlug && workers.length) {
        const cf = (workers[0].field_schema ?? []).find(
          f => f.target_entity === scopeSlug && f.field_type === 'entity_select');
        if (cf) this.scopeFieldKey.set(cf.key);
      }

      // Launch scope + pills + week plan + rest days + absences ALL in parallel
      const weekPlan$ = this.planningService.getWeeklyPlan(monday, 0);
      const rests$ = this.restDayService.getWeekly(monday);
      const absences$ = this.absenceService.getRequests({ status: 'approved' });
      const closed$ = this.closedDayService.getAll();

      forkJoin({
        scopeRecords: scope$,
        pillsRecords: pills$,
        wp: weekPlan$,
        rests: rests$,
        absences: absences$,
        closed: closed$,
      }).subscribe(({ scopeRecords, pillsRecords, wp, rests, absences, closed }) => {
        this.approvedAbsences.set(absences);
        this.closedDays.set(closed || []);

        // Scope records → scope selector dropdown
        const mappedScope = (scopeRecords as any[]).filter((a: any) => a.data?.active !== false).map((a: any) => ({
          id: a.id,
          name: a.data?.[(scopeEt?.display_field || 'nombre')] ?? a.data?.nombre ?? a.data?.name ?? '',
          active: true,
        }));
        this.scopeRecords.set(mappedScope);
        this.scopeDataById.set(Object.fromEntries(
          (scopeRecords as any[]).map((a: any) => [a.id, a.data ?? {}])));
        if (mappedScope.length) {
          // Check if a scope was requested via query param (e.g. from notification action)
          const requestedScope = Number(this.route.snapshot.queryParamMap.get('scope'));
          const targetScope = requestedScope && mappedScope.some(s => s.id === requestedScope)
            ? requestedScope
            : mappedScope[0].id;
          this.selectedScopeId.set(targetScope);
        }

        // Pills records → area chips in each assignment
        const mappedPills = (pillsRecords as any[]).filter((a: any) => a.data?.active !== false).map((a: any) => ({
          id: a.id,
          name: a.data?.[pillsDisplay] ?? a.data?.nombre ?? a.data?.name ?? '',
          active: true,
        }));
        this.areas.set(mappedPills);

        this.weeklyRestDays.set(rests);
        // ── Build EAV-driven worker filters ──────────────────────────
        this.buildWorkerFilters(workers, entityTypes);

        // El `wp` del forkJoin se pidió con scope=0 (aún no sabíamos qué tienda
        // se selecciona). Ahora que ya tenemos el scope real, cargamos el plan
        // de ESA tienda con loadWeek. Sin esto, la PRIMERA carga salía vacía
        // (plan de scope 0 inexistente) y solo aparecía al navegar de semana.
        const draft = this.planningService.getDraft(monday, this.selectedScopeId());
        if (draft) {
          this.plan.set(draft);
          this.hasUnsavedChanges.set(true);
          this.pendingInitialValidation.set(true);
          this.validatePlan();
          // `stale` sale del plan GUARDADO de ESTA tienda, y el `wp` de arriba
          // se pidió con scope=0 (aún no se sabía la tienda): su `stale` es de
          // otro plan y no sirve. Se pide aparte para el scope real.
          const scopeReal = this.selectedScopeId();
          this.planningService.getWeeklyPlan(monday, scopeReal)
            .pipe(catchError(() => of(null as any)))
            .subscribe(wpScope => {
              if (!this.alive || this.selectedScopeId() !== scopeReal) return;
              this.planStale.set(!!wpScope?.stale);
              this.staleWorkers.set(wpScope?.stale_workers ?? []);
              this.applyStaleIfNeeded();
            });
        } else if (this.selectedScopeId()) {
          // Scope real seleccionado → recarga el plan de esa tienda.
          this.loadWeek(monday);
        } else {
          // Sin tiendas (scope 0): usa el plan del forkJoin tal cual.
          const plan = wp.plan ?? [];
          this.mergeOfficialRests(plan);
          this.plan.set(plan);
          this.pendingInitialValidation.set(true);
          this.validatePlan();
        }
        // Desde aquí, cada NavigationEnd de vuelta a /schedule recarga la
        // semana (ver la suscripción al inicio de ngOnInit).
        this.primeraCargaHecha = true;
      });
    });
  }

  /** Discover filterable fields from worker schema and load their options. */
  private buildWorkerFilters(workers: Worker[], entityTypes: any[]): void {
    if (!workers.length) return;
    const schema = workers[0].field_schema ?? [];
    const filterableTypes = ['entity_select', 'multi_entity_select', 'catalog_select', 'multi_catalog_select'];
    const candidates = schema.filter(f => filterableTypes.includes(f.field_type));
    if (!candidates.length) return;

    const loadObs: Record<string, Observable<any>> = {};
    for (const f of candidates) {
      if ((f.field_type === 'entity_select' || f.field_type === 'multi_entity_select') && f.target_entity) {
        loadObs[f.key] = this.entityRecordService.getAll(f.target_entity);
      } else if ((f.field_type === 'catalog_select' || f.field_type === 'multi_catalog_select') && f.kind_code) {
        loadObs[f.key] = this.catalogService.getValues(f.kind_code);
      }
    }

    forkJoin(loadObs).subscribe(results => {
      const filters: FilterDef[] = [];
      for (const f of candidates) {
        const raw = results[f.key] as any[];
        if (!raw?.length) continue;
        // Find display field for entity_select targets
        const targetEt = entityTypes.find((et: any) => et.slug === f.target_entity);
        const displayKey = f.display_key || targetEt?.display_field || 'nombre';

        let options: { value: string | number; label: string }[];
        if (f.field_type === 'entity_select' || f.field_type === 'multi_entity_select') {
          options = raw
            .filter((r: any) => r.data?.active !== false)
            .map((r: any) => ({
              value: r.id,
              label: r.data?.[displayKey] ?? r.data?.nombre ?? r.data?.name ?? r.name ?? `#${r.id}`,
            }));
        } else {
          // catalog values
          options = raw.map((v: any) => ({ value: v.code, label: v.label }));
        }
        filters.push({ key: f.key, label: f.label, field_type: f.field_type, options });
      }
      this.workerFilters.set(filters);
    });
  }

  // ── Worker filters ─────────────────────────────────────────────────────

  onFilterChange(key: string, value: string | number): void {
    this.activeFilters.update(f => {
      const copy = { ...f };
      if (!value && value !== 0) { delete copy[key]; } else { copy[key] = value; }
      return copy;
    });
  }

  clearFilters(): void {
    this.activeFilters.set({});
  }

  activeFilterCount(): number {
    return Object.keys(this.activeFilters()).length;
  }

  /** Check if a worker matches ALL active filters. */
  private workerMatchesFilters(w: Worker): boolean {
    const filters = this.activeFilters();
    for (const [key, target] of Object.entries(filters)) {
      const val = w.custom_data?.[key];
      if (val === undefined || val === null) return false;
      const t = String(target);
      if (Array.isArray(val)) {
        // multi_entity_select (priorities) or multi_catalog_select
        const match = val.some((item: any) => {
          if (typeof item === 'object' && item !== null) {
            return String(item.value ?? item.id ?? item.entity_id ?? '') === t;
          }
          return String(item) === t;
        });
        if (!match) return false;
      } else {
        if (String(val) !== t) return false;
      }
    }
    return true;
  }

  /** ¿El trabajador puede trabajar en la tienda que se está planificando?
   *
   *  Replica `worker_passes_scope_match()` del back (apps/restrictions/engine.py),
   *  que es la fuente de verdad de la elegibilidad por ámbito y ya la comparten
   *  el validador de restricciones y el pre-filtro del generador. El desplegable
   *  usa el MISMO criterio para no ofrecer a gente que el validador rechazaría
   *  luego con "no puede trabajar en esta tienda (fuera de su ámbito)".
   *
   *  Las reglas salen de la restricción `scopeMatch` activa (p.ej. en Cabrero:
   *  coincide la tienda por id, O coincide la zona siendo COMÚN, O coincide la
   *  zona siendo ETT). Pasa si CUALQUIER regla se cumple.
   *
   *  Un campo vacío NO es un comodín: igual que en el back, si el trabajador no
   *  tiene valor en el campo, esa regla no se cumple. Sin esto salían en todas
   *  las tiendas los registros incompletos (sin tienda, zona ni contrato).
   */
  private workerBelongsToScope(w: Worker): boolean {
    const scope = this.selectedScopeId();
    if (!scope) return true;                  // sin ámbito seleccionado: no se filtra
    const rules = this.scopeMatchRules();
    if (!rules.length) {
      // Sin restricción de ámbito configurada, se cae al filtro simple por el
      // campo de ámbito auto-detectado (y sin ese campo, no se filtra nada).
      const key = this.scopeFieldKey();
      if (!key) return true;
      return this._fieldValues(w, key).some(v => String(v) === String(scope));
    }
    const scopeData = this.scopeDataById()[scope] ?? {};
    return rules.some(rule => {
      const wf = rule.workerField;
      if (!wf) return false;
      const wValues = this._fieldValues(w, wf);
      if (!wValues.length) return false;      // campo vacío ⇒ la regla no se cumple
      const matchType = rule.matchType || 'field';
      let ok: boolean;
      if (matchType === 'id') {
        ok = wValues.some(v => String(v) === String(scope));
      } else if (matchType === 'attr') {
        ok = true;
      } else {
        const sv = scopeData[rule.scopeField ?? ''];
        ok = sv !== null && sv !== undefined
          && wValues.some(v => String(v) === String(sv));
      }
      if (!ok) return false;
      if (rule.requireField) {
        const actual = this._fieldValues(w, rule.requireField);
        const want = String(rule.requireValue ?? '').toLowerCase();
        if (!actual.some(v => String(v).toLowerCase() === want)) return false;
      }
      return true;
    });
  }

  /** Valores de un campo EAV del trabajador, siempre como lista y sin vacíos
   *  (equivalente a `_extract_field_values()` del back). */
  private _fieldValues(w: Worker, key: string): any[] {
    const raw = (w.custom_data as any)?.[key];
    if (raw === null || raw === undefined || raw === '') return [];
    const arr = Array.isArray(raw) ? raw : [raw];
    return arr
      .map((item: any) => (typeof item === 'object' && item !== null
        ? (item.value ?? item.id ?? item.entity_id ?? '')
        : item))
      .filter((v: any) => v !== null && v !== undefined && v !== '');
  }

  // ── Scope selector ─────────────────────────────────────────────────────

  /** Whether the currently selected scope is being generated */
  isCurrentScopeGenerating(): boolean {
    return this.generatingScopes().has(this.selectedScopeId());
  }

  /**
   * ¿Hay una generación en curso (esta tienda o "generar todas")?
   *
   * Mientras se genera, los chips de errores y avisos se ocultan: cuentan sobre
   * el plan ANTERIOR, así que mostrarían datos obsoletos que cambian solos en
   * cuanto llega el nuevo plan.
   */
  anyGenerating(): boolean {
    return this.isCurrentScopeGenerating() || this.generatingAll();
  }

  /** Whether the current scope has an unsaved draft */
  hasDraft(): boolean {
    return this.planningService.hasDraft(this.startDate(), this.selectedScopeId());
  }

  /** ¿Hay una planificación GUARDADA con contenido para esta semana/tienda?
   *  Solo entonces tiene sentido el botón "Descargar PDF" (Figma Vista por
   *  Día): no en empty state ni en un borrador aún sin guardar. */
  hasSavedPlan(): boolean {
    return !this.hasUnsavedChanges()
      && !this.hasDraft()
      && this.getTotalAssignments() > 0;
  }

  /** Nombre de la tienda seleccionada (para la cabecera de tienda de la
   *  tabla, Figma th-tienda 2464:40607). Vacío si aún no hay ninguna. */
  selectedScopeName(): string {
    return this.scopeRecords().find(s => s.id === this.selectedScopeId())?.name ?? '';
  }

  /**
   * Contexto de la tienda abierta: "ALTOARAGON-1 · Huesca".
   *
   * El chip y la cabecera solo muestran el código ("T01"), que no dice de qué
   * tienda ni de qué zona se trata: al entrar al planificador no había forma de
   * saber dónde estabas sin ir al maestro de tiendas. Se toma del `data` que ya
   * está cargado, así que no cuesta ninguna petición.
   */
  selectedScopeContext(): string {
    const data = this.scopeDataById()[this.selectedScopeId()] ?? {};
    const codigo = this.selectedScopeName();
    const nombre = String(data['nombre'] ?? '').trim();
    const zona = this.zoneLabel();
    const partes: string[] = [];
    // El nombre solo si aporta algo distinto del código que ya se ve.
    if (nombre && nombre !== codigo) partes.push(nombre);
    if (zona) partes.push(zona);
    return partes.join(' · ');
  }

  /** Nº total de columnas de la tabla (Día + Turnos + secciones + Ausencias),
   *  para el colspan de la fila de cabecera de tienda. */
  totalColumns(): number {
    return this.planSections().length + 3; // Día, Turnos, Ausencias
  }

  /** ¿Esta tienda se está generando ahora? (spinner en su chip) */
  isScopeGenerating(scopeId: number): boolean {
    return this.generatingScopes().has(scopeId);
  }

  /** Indicator text for scope dropdown (shows draft/generating status) */
  getScopeIndicator(scopeId: number): string {
    if (this.generatingScopes().has(scopeId)) return ' ⏳';
    if (this.planningService.hasDraft(this.startDate(), scopeId)) return ' ✎';
    return '';
  }

  onScopeChange(id: number): void {
    // Save current plan as draft if there are unsaved changes
    if (this.hasUnsavedChanges()) {
      this.planningService.setDraft(this.startDate(), this.selectedScopeId(), this.plan());
    }
    this.selectedScopeId.set(id);
    // Otro ámbito = otras secciones y otra plantilla: la caché de cobertura
    // deja de ser válida.
    this._staffForCache.clear();
    this.loadWeek(this.startDate());
  }

  /** Navigate to a specific scope+week, handling both in-component and cross-route scenarios */
  private navigateToScope(scopeId: number, week: string): void {
    if (this.alive) {
      // Component is still mounted — switch scope/week directly
      this.saveDraftIfNeeded();
      this.selectedScopeId.set(scopeId);
      // Igual que en onScopeChange(): otro ámbito = otra plantilla, la caché de
      // cobertura por sección deja de valer.
      this._staffForCache.clear();
      this.loadWeek(week);
    } else {
      // Component was destroyed — use router navigation
      this.router.navigate(['/schedule'], { queryParams: { scope: scopeId, week } });
    }
  }

  // ── Navigation ─────────────────────────────────────────────────────────

  /** Navega a la semana que contiene el día de hoy (chip "Hoy"). */
  goToday(): void {
    this.saveDraftIfNeeded();
    this.loadWeek(this.getCurrentMonday());
  }

  // ── Date picker desplegable del header ─────────────────────────────────
  showDatePicker = signal(false);

  toggleDatePicker(): void {
    this.showDatePicker.update(v => !v);
  }

  /** El fin de la semana mostrada (domingo), para pintar el rango en el panel. */
  weekEndDate(): string {
    const d = new Date(this.startDate() + 'T00:00:00');
    d.setDate(d.getDate() + 6);
    return this.fmt(d);
  }

  /** Al aplicar una fecha en el calendario → cargar la semana de esa fecha. */
  onDatePickerApply(range: DateRange): void {
    this.showDatePicker.set(false);
    if (!range?.startDate) return;
    // Normalizar al lunes de la semana que contiene la fecha elegida
    const d = new Date(range.startDate + 'T00:00:00');
    const dow = d.getDay();
    d.setDate(d.getDate() - (dow === 0 ? 6 : dow - 1));
    this.saveDraftIfNeeded();
    this.loadWeek(this.fmt(d));
  }

  prevWeek(): void {
    this.saveDraftIfNeeded();
    const d = new Date(this.startDate() + 'T00:00:00');
    d.setDate(d.getDate() - 7);
    this.loadWeek(this.fmt(d));
  }

  nextWeek(): void {
    this.saveDraftIfNeeded();
    const d = new Date(this.startDate() + 'T00:00:00');
    d.setDate(d.getDate() + 7);
    this.loadWeek(this.fmt(d));
  }

  private saveDraftIfNeeded(): void {
    if (this.hasUnsavedChanges()) {
      this.planningService.setDraft(this.startDate(), this.selectedScopeId(), this.plan());
    }
  }

  /** Recalcula qué turnos se muestran según la semana (vigencia, AC-2/AC-4/AC-5).
   *  Un turno se muestra si:
   *   1) NO está caducado respecto a HOY (valid_to < hoy → nunca en el
   *      planificador, ni en semanas pasadas; solo en /entities/shift), y
   *   2) su rango [valid_from, valid_to] solapa con la semana [lunes, domingo].
   *  Los turnos normales (sin fechas) pasan siempre. */
  private applyShiftValidityFilter(monday: string): void {
    const d = new Date(monday + 'T00:00:00');
    d.setDate(d.getDate() + 6);
    const sunday = this.fmt(d);
    const hoy = new Date().toISOString().slice(0, 10);

    const caducado = (s: any) => !!s.valid_to && s.valid_to < hoy;
    const solapaSemana = (s: any) =>
      (!s.valid_to || s.valid_to >= monday) && (!s.valid_from || s.valid_from <= sunday);
    const visible = (s: any) => !caducado(s) && solapaSemana(s);

    this.shiftSlots.set(
      this.allShiftSlotsRaw().filter(visible).map((s: any) => ({
        code: String(s.id),
        label: s.name ?? `Turno ${s.id}`,
        color: s.custom_data?.color ?? '#628db4',
        icon: s.custom_data?.icon ?? '',
        parentId: s.parent ?? null,
        // Conservamos la vigencia para filtrar DÍA A DÍA en slotsForDay
        // (no basta con que solape la semana; cada día debe estar en rango).
        validFrom: s.valid_from ?? null,
        validTo: s.valid_to ?? null,
        attributes: {
          start_time: s.start_time ?? '00:00',
          end_time: s.end_time ?? '00:00',
        },
      }))
    );
  }

  loadWeek(date: string): void {
    this.startDate.set(date);
    // Re-fetch de turnos: la lista puede haber cambiado (turnos creados/borrados
    // en /entities/shift) desde que se cargó la vista. Sin esto, al volver a
    // /schedule se seguían pintando turnos ya borrados y no aparecían los nuevos.
    this.shiftService.getAll().subscribe(slots => {
      this.allShiftSlotsRaw.set(slots as any[]);
      this.applyShiftValidityFilter(date); // refiltra por vigencia de esta semana
    });
    this.applyShiftValidityFilter(date); // filtro inmediato con lo que ya hay
    this.loading.set(true);
    this.cargaEnVuelo = true;
    const scope = this.selectedScopeId();

    // If there's a draft for this scope+week, restore it instead of fetching
    const draft = this.planningService.getDraft(date, scope);
    if (draft) {
      this.absenceService.invalidate();
      forkJoin({
        rests: this.restDayService.getWeekly(date),
        absences: this.absenceService.getRequests({ status: 'approved' }),
        closed: this.closedDayService.getAll(),
        // El borrador se pinta tal cual, pero SI se pide el plan guardado para
        // saber si las fichas cambiaron (`stale`). Sin esto esta rama no leia
        // `planStale` nunca: se quedaba con el valor de la carga anterior (o
        // false), asi que con un borrador abierto el aviso de "has cambiado la
        // ficha de X" no aparecia — es el motivo principal de que el toast
        // saliera unas veces y otras no.
        wp: this.planningService.getWeeklyPlan(date, scope).pipe(catchError(() => of(null as any))),
      }).subscribe(({ rests, absences, closed, wp }) => {
        this.approvedAbsences.set(absences || []);
        this.closedDays.set(closed || []);
        this.weeklyRestDays.set(rests);
        this.planStale.set(!!wp?.stale);
        this.staleWorkers.set(wp?.stale_workers ?? []);
        this.plan.set(draft);
        this.hasUnsavedChanges.set(true);
        this.loading.set(false);
        this.pendingInitialValidation.set(true);
        this.validatePlan();
        this.cargaEnVuelo = false;
        // Avisa (sin regenerar: hay borrador que se perderia). La guarda de
        // hasDraft()/hasUnsavedChanges() dentro se encarga del mensaje.
        this.applyStaleIfNeeded();
      });
      return;
    }

    this.hasUnsavedChanges.set(false);
    // Refrescar ausencias aprobadas y días de cierre en CADA carga de semana:
    // si se aprueba una baja en /absences y se vuelve a /schedule sin recargar
    // la página, antes seguían con la lista vieja (solo se cargaban en ngOnInit)
    // → no aparecían en la columna Ausencias ni en el PDF. invalidate() evita el
    // caché shareReplay del servicio.
    this.absenceService.invalidate();
    forkJoin({
      wp: this.planningService.getWeeklyPlan(date, scope),
      rests: this.restDayService.getWeekly(date),
      absences: this.absenceService.getRequests({ status: 'approved' }),
      closed: this.closedDayService.getAll(),
    }).subscribe({
      next: ({ wp, rests, absences, closed }) => {
        this.approvedAbsences.set(absences || []);
        this.closedDays.set(closed || []);
        this.weeklyRestDays.set(rests);
        this.planStale.set(!!wp.stale);
        this.staleWorkers.set(wp.stale_workers ?? []);
        const busy: Record<string, Set<number>> = {};
        for (const [f, ids] of Object.entries(wp.busy_elsewhere ?? {})) {
          busy[f] = new Set(ids);
        }
        this.busyElsewhere.set(busy);
        const plan = wp.plan ?? [];
        this.mergeOfficialRests(plan);
        this.plan.set(plan);
        this.pendingInitialValidation.set(true);
        this.validatePlan();
        // Severidad del resto de tiendas, para que sus chips lleven ▲/● sin
        // tener que abrirlas una por una.
        this.loadScopeSeverities(date);
        this.cargaEnVuelo = false;
        // Fichas editadas después de guardar el plan → se recalcula sola, sin
        // pedir nada. Va después de pintar el plan viejo para que la pantalla no
        // se quede en blanco mientras se regenera.
        this.applyStaleIfNeeded();
      },
      error: () => {
        this.cargaEnVuelo = false;
        this.loading.set(false);
        this.snackBar.open('Error al cargar la planificación', 'Cerrar', { duration: 5000 });
      },
    });
  }

  getWeekRangeLabel(): string {
    const d = new Date(this.startDate() + 'T00:00:00');
    const end = new Date(d);
    end.setDate(d.getDate() + 6);
    const months = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
    if (d.getMonth() === end.getMonth()) {
      return `${d.getDate()} – ${end.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
    }
    return `${d.getDate()} ${months[d.getMonth()]} – ${end.getDate()} ${months[end.getMonth()]} ${d.getFullYear()}`;
  }

  // ── Save / Generate / Copy ─────────────────────────────────────────────

  save(): void {
    // No se permite guardar con ERRORES (rojo). Los avisos (ámbar/warning) sí
    // dejan guardar. Mientras se valida, esperamos a que termine para no
    // bloquear/permitir con un recuento a medias.
    if (this.validating()) {
      this.snackBar.open('Validando… espera un momento antes de guardar', 'OK', { duration: 2500 });
      return;
    }
    if (this.getWeekErrorCount() > 0) {
      const n = this.getWeekErrorCount();
      this.snackBar.open(
        `No se puede guardar: hay ${n} ${n === 1 ? 'error' : 'errores'} que resolver. Los avisos sí permiten guardar.`,
        'Cerrar', { duration: 5000 });
      return;
    }
    this.saving.set(true);
    this.planningService.saveWeeklyPlan(this.startDate(), this.plan(), this.selectedScopeId()).subscribe({
      next: () => {
        this.saving.set(false);
        this.hasUnsavedChanges.set(false);
        this.editMode.set(false);
        // Clear draft since it's now saved
        this.planningService.clearDraft(this.startDate(), this.selectedScopeId());
        this.lastSavedAt.set(new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' }));
        // El chip "Guardado HH:MM" se auto-oculta a los 3s (evita que quede
        // colgado indefinidamente). Se cancela un timer previo por si se guarda
        // varias veces seguidas.
        clearTimeout(this.savedChipTimer);
        this.savedChipTimer = setTimeout(() => this.lastSavedAt.set(''), 3000);
        this.snackBar.open('Planificación guardada correctamente', 'OK', { duration: 3000 });
      },
      error: () => {
        this.saving.set(false);
        this.snackBar.open('Error al guardar la planificación', 'Cerrar', { duration: 5000 });
      },
    });
  }

  /**
   * Guarda la semana que se acaba de regenerar SOLA por una ficha
   * desactualizada, para que el cambio quede aplicado sin pasar por el modo
   * edición (que además reaparecía en cada visita: ver
   * `autoSaveAfterValidation`).
   *
   * Si la regeneración dejó ERRORES no se guarda: se deja el borrador en
   * edición, igual que una generación manual, porque hay que resolverlos a
   * mano y `save()` los rechazaría de todas formas. El toast lo dice para que
   * no parezca que el cambio se aplicó.
   */
  private saveAfterAutoRegeneration(): void {
    if (this.getWeekErrorCount() > 0) {
      const n = this.getWeekErrorCount();
      this.snackBar.open(
        `La planificación se ha recalculado, pero hay ${n} ${n === 1 ? 'error' : 'errores'} que resolver antes de guardarla.`,
        'Cerrar', { duration: 6000 });
      return;
    }

    const startDate = this.startDate();
    const scopeId = this.selectedScopeId();
    this.saving.set(true);
    this.planningService.saveWeeklyPlan(startDate, this.plan(), scopeId).subscribe({
      next: () => {
        this.saving.set(false);
        // Si el usuario cambió de tienda/semana mientras se guardaba, no se
        // toca el estado de la vista que está mirando ahora: el guardado ya
        // surtió efecto en la BD y es lo que importa.
        if (!this.alive || this.startDate() !== startDate || this.selectedScopeId() !== scopeId) return;
        this.hasUnsavedChanges.set(false);
        this.editMode.set(false);
        this.planningService.clearDraft(startDate, scopeId);
        this.lastSavedAt.set(new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' }));
        clearTimeout(this.savedChipTimer);
        this.savedChipTimer = setTimeout(() => this.lastSavedAt.set(''), 3000);
        this.snackBar.open('Planificación actualizada y guardada', 'OK', { duration: 4000 });
      },
      error: () => {
        this.saving.set(false);
        // Se queda en modo edición con el borrador: el cambio no se ha perdido
        // y el usuario puede reintentar con Guardar.
        this.snackBar.open(
          'La planificación se ha recalculado, pero no se pudo guardar. Revísala y pulsa Guardar.',
          'Cerrar', { duration: 6000 });
      },
    });
  }

  /** Cancelar edición (como Figma): descarta el borrador y recarga el
   *  plan guardado. Si no había cambios, simplemente sale de edición. */
  cancelEdit(): void {
    // Si hay cambios sin guardar, pedir confirmación antes de descartarlos
    // (Figma: overlay "tienes cambios sin guardar, si cancelas los perderás").
    if (this.hasUnsavedChanges()) {
      this.showCancelConfirm = true;
      return;
    }
    this.editMode.set(false);
  }

  /** Descarta los cambios del borrador y sale del modo edición (confirmado). */
  doCancelEdit(): void {
    this.showCancelConfirm = false;
    // Si se estaba saliendo de la pantalla, se deja continuar la navegación.
    if (this.resolverSalida) {
      const seguir = this.resolverSalida;
      this.resolverSalida = null;
      this.planningService.clearDraft(this.startDate(), this.selectedScopeId());
      this.hasUnsavedChanges.set(false);
      seguir(true);
      return;
    }
    this.editMode.set(false);
    this.planningService.clearDraft(this.startDate(), this.selectedScopeId());
    this.hasUnsavedChanges.set(false);
    this.loadWeek(this.startDate());
  }

  /**
   * Promesa pendiente cuando el usuario intenta SALIR de la pantalla con
   * cambios sin guardar: se resuelve al pulsar "Descartar" (true) o "Seguir
   * editando" (false). Null el resto del tiempo.
   */
  private resolverSalida: ((salir: boolean) => void) | null = null;

  /**
   * Llamado por `unsavedChangesGuard` al navegar fuera (menú lateral, botón
   * atrás…). Reutiliza el MISMO overlay que "Cancelar": antes el botón avisaba
   * y el menú no, y el borrador se perdía en silencio.
   */
  confirmLeave(destino?: string): boolean | Promise<boolean> {
    if (!this.hasUnsavedChanges() && !this.hasDraft()) return true;

    // Ir a CONSULTAR o AJUSTAR datos que afectan a la planificación no es
    // "abandonar el trabajo": es parte de planificar. Si estás cuadrando una
    // semana y necesitas cambiar una restricción o la ficha de alguien, tienes
    // que poder ir y volver. Se guarda el borrador y se sale sin preguntar.
    if (destino && this.RUTAS_SIN_AVISO.some(r => destino.startsWith(r))) {
      this.saveDraftIfNeeded();
      return true;
    }

    this.showCancelConfirm = true;
    return new Promise<boolean>(resolve => { this.resolverSalida = resolve; });
  }

  /**
   * Pantallas a las que se sale SIN avisar, conservando el borrador: son las
   * que se consultan mientras se planifica (restricciones, fichas, turnos,
   * ausencias…). El borrador vive en PlanningService, que es singleton, así que
   * sobrevive a la navegación y sigue ahí al volver.
   */
  private readonly RUTAS_SIN_AVISO = [
    '/restrictions',   // ajustar topes, mínimos, elegibilidad
    '/employees',      // corregir la ficha de alguien
    '/entities',       // turnos, secciones, tiendas (entidades EAV)
    '/absences',       // consultar o registrar una ausencia
    '/closed-days',    // festivos y cierres
    '/dashboard',      // panel de estado
    '/catalog',        // catálogos auxiliares
  ];

  /**
   * "Seguir editando" (o cerrar el overlay) cuando se estaba saliendo: se
   * cancela la navegación y el borrador se queda como estaba.
   */
  onCancelDialogClosed(): void {
    if (!this.resolverSalida) return;
    const seguir = this.resolverSalida;
    this.resolverSalida = null;
    seguir(false);      // se queda en la pantalla, el borrador intacto
  }

  generate(): void {
    this.generateWarnDrafts = this.pendingDraftNames();
    this.showGenerateConfirm = true;
  }

  /**
   * Nombres de OTRAS tiendas con borrador sin guardar en esta semana.
   *
   * El generador solo respeta los planes GUARDADOS al repartir: un borrador de
   * otra tienda no reserva a nadie, así que generar aquí puede volver a asignar
   * a alguien que en ese borrador ya tiene turno ese día (misma persona en dos
   * tiendas). El aviso deja al usuario guardar primero.
   */
  private pendingDraftNames(): string[] {
    const actual = this.selectedScopeId();
    const conBorrador = new Set(
      this.planningService.draftScopeIds(this.startDate()));
    return this.scopeRecords()
      .filter(s => s.id !== actual && conBorrador.has(s.id))
      .map(s => s.name);
  }

  /** Tiendas a nombrar en el aviso del diálogo de generar (vacío = sin aviso). */
  generateWarnDrafts: string[] = [];

  /**
   * Aviso de borradores para los diálogos de generación masiva.
   *
   * Aquí solo cuentan los borradores de tiendas que NO entran en el lote: las
   * del lote se recalculan de cero, así que su borrador se sustituye y no hay
   * riesgo de doble asignación.
   */
  private bulkDraftWarning(scopes: { id: number; name: string }[]): string {
    const enLote = new Set(scopes.map(s => s.id));
    const conBorrador = new Set(
      this.planningService.draftScopeIds(this.startDate()));
    const fuera = this.scopeRecords()
      .filter(s => !enLote.has(s.id) && conBorrador.has(s.id))
      .map(s => s.name);
    if (!fuera.length) return '';
    const lista = fuera.length <= 4
      ? fuera.join(', ')
      : `${fuera.slice(0, 4).join(', ')} y ${fuera.length - 4} más`;
    return `<br><br><strong>Ojo: tienes cambios sin guardar en ${lista}.</strong>`
      + `<br>No se tendrán en cuenta al repartir (solo cuenta lo guardado), así `
      + `que alguien podría quedar asignado en dos sitios el mismo día.`;
  }

  /** Mensaje del diálogo de generar, con el aviso de borradores si procede. */
  generateConfirmMessage(): string {
    const base = 'Se reemplazarán todas las asignaciones actuales de esta semana.'
      + '<br><strong>Los descansos oficiales se conservarán.</strong>';
    const pendientes = this.generateWarnDrafts;
    if (!pendientes.length) return base;
    const lista = pendientes.length <= 4
      ? pendientes.join(', ')
      : `${pendientes.slice(0, 4).join(', ')} y ${pendientes.length - 4} más`;
    return base
      + `<br><br><strong>Tienes cambios sin guardar en ${lista}.</strong>`
      + `<br>Al generar solo se tiene en cuenta lo GUARDADO, así que alguien de `
      + `ese borrador podría quedar asignado también aquí el mismo día. `
      + `Guarda esas ${this.scopeEntityName().toLowerCase()}s antes para evitarlo.`;
  }

  /** Descargar la planificación en PDF (Figma 2445:23224).
   *
   *  Abre la vista de impresión del navegador (window.print) sobre la vista
   *  imprimible maquetada (.pdf-print), respetando los estilos --figma-pdf-* de
   *  Figma vía @media print. Desde el diálogo del navegador se puede imprimir o
   *  guardar como PDF. */
  downloadPdf(): void {
    window.print();
  }

  /** Nombres de columna de los 6 días (Lunes..Sábado) para la cabecera del
   *  PDF: nombre del día + número. */
  pdfDays(): { name: string; num: string; date: string }[] {
    return this.plan().map(d => ({
      name: d.dayName,
      num: d.date.slice(8),
      date: d.date,
    }));
  }

  /** Columnas de la tabla de Ausencias del PDF: los días de la semana EXCLUYENDO
   *  los de cierre (domingo/festivo). En Figma (2464:42412) la tabla de ausencias
   *  muestra solo LUNES..SÁBADO (sin domingo), porque en cierre no hay ausencias. */
  pdfAusenciasDays(): { name: string; num: string; date: string }[] {
    return this.pdfDays().filter(d => !this.isClosedDay(d.date));
  }

  /** Datos del PDF agrupados por SECCIÓN (ROL) → EMPLEADO → horario por día.
   *  Para cada sección, lista de empleados asignados esa semana; por cada
   *  empleado, su horario en cada día (vacío si no trabaja ese día). */
  pdfRows(): { section: string; workers: { name: string; days: string[][] }[] }[] {
    const days = this.plan();
    return this.planSections().map(section => {
      // Empleados únicos asignados a esta sección en toda la semana. Cada día
      // guarda una LISTA de tramos horarios (Figma 2464:43888: 2 turnos el
      // mismo día → 2 líneas, no separados por " / " en una sola línea).
      const byWorker = new Map<number, { name: string; days: string[][] }>();
      days.forEach((day, di) => {
        for (const slot of this.slotsForDay(day)) {
          for (const a of this.cellEditAssignments(day, slot.code, section.name)) {
            if (!a.workerId || a.workerId <= 0) continue;
            if (!byWorker.has(a.workerId)) {
              byWorker.set(a.workerId, {
                name: this.formatWorkerName(a.workerName),
                days: Array.from({ length: days.length }, () => [] as string[]),
              });
            }
            const trim = (t: string) => (t || '').split(':').slice(0, 2).join(':');
            const horario = a.start && a.end ? `${trim(a.start)} - ${trim(a.end)}h` : '';
            if (!horario) continue;
            const rec = byWorker.get(a.workerId)!;
            if (!rec.days[di].includes(horario)) rec.days[di].push(horario);
          }
        }
      });
      return {
        section: section.name,
        workers: Array.from(byWorker.values()).sort((a, b) => a.name.localeCompare(b.name)),
      };
    }).filter(g => g.workers.length > 0);
  }

  /** Nombres de la columna Ausencias del PDF: SOLO ausencias reales (bajas),
   *  no los descansos (coherente con la columna Ausencias de la pantalla). */
  private pdfAusenciasByDay(date: string): string[] {
    // Días de cierre (domingo/festivo): negocio cerrado → sin ausencias.
    if (this.isClosedDay(date)) return [];
    // Igual que cellRest: se calcula de las ausencias aprobadas que cubren el
    // día (no de day.rest), para que las bajas aprobadas tras guardar el plan
    // también salgan en el PDF. Deduplicado por trabajador.
    const ids = new Set<number>();
    for (const a of this.approvedAbsences()) {
      if (a.worker <= 0 || !this.isAbsentOn(a.worker, date)) continue;
      // Solo los de ESTA tienda: antes se listaban las ausencias de toda la
      // plantilla, así que en cada tienda salían también las bajas de las otras.
      const w = this.allWorkers().find(x => x.id === a.worker);
      if (w && !this.workerBelongsToScope(w)) continue;
      ids.add(a.worker);
    }
    return Array.from(ids).map(id => this.formatWorkerName(this.getWorkerName(id)));
  }

  /** Nº de filas de la tabla de ausencias = máximo de ausentes en un día
   *  (solo días abiertos; los de cierre no cuentan). */
  pdfAusenciasRows(): number[] {
    const max = Math.max(0, ...this.pdfAusenciasDays().map(d => this.pdfAusenciasByDay(d.date).length));
    return Array.from({ length: max }, (_, i) => i);
  }

  /** ¿Hay alguna ausencia que mostrar en el PDF esta semana? */
  hasPdfAusencias(): boolean {
    return this.pdfAusenciasRows().length > 0;
  }

  /** Nombre en la celda [día, fila] de la tabla de ausencias del PDF. */
  pdfAusenciaAt(date: string, rowIdx: number): string {
    return this.pdfAusenciasByDay(date)[rowIdx] ?? '';
  }

  /**
   * @param silent Regeneración automática (fichas cambiadas): no abre el modal de
   *   avisos ni el toast de "generada correctamente". El usuario no la ha pedido,
   *   así que interrumpirle con un diálogo sería intrusivo — los avisos siguen
   *   estando en el chip ámbar de la barra.
   */
  doGenerate(silent = false): void {
    this.showGenerateConfirm = false;
    const scopeId = this.selectedScopeId();
      const startDate = this.startDate();
      const scopeName = this.scopeRecords().find(s => s.id === scopeId)?.name || '';

      // Mark this scope as generating
      this.generatingScopes.update(s => new Set(s).add(scopeId));
      this.generating.set(true);

      this.planningService.generateSchedule(startDate, scopeId).subscribe({
        next: result => {
          const plan = result.plan ?? result as any;
          const warnings: string[] = result.warnings ?? [];
          this.lastGenerationResult.set({
            generatedAt: new Date().toISOString(),
            startDate,
            scopeId,
            warnings,
            plan,
          });
          this.mergeOfficialRests(plan);
          // Ya se ha recalculado con las fichas actuales: el aviso de
          // "desactualizado" deja de aplicar (el back lo volverá a calcular al
          // guardar, comparando contra la nueva fecha del plan).
          this.planStale.set(false);
          this.staleWorkers.set([]);

          // Store as draft in the service (survives component destruction)
          this.planningService.setDraft(startDate, scopeId, plan);

          // Unmark generating for this scope
          this.generatingScopes.update(s => { const n = new Set(s); n.delete(scopeId); return n; });

          // Build warning summary for notifications
          const hasErrors = warnings.some(w => /\berror(es)?\b/i.test(w));
          const hasOnlySuccess = warnings.length === 1 && warnings[0]?.includes('sin problemas');
          const warningDetail = warnings
            .filter(w => !w.includes('sin problemas'))
            .join('\n');
          const navAction = {
            label: 'Ver planificación',
            callback: () => this.navigateToScope(scopeId, startDate),
          };

          // If user is still viewing this scope, update the view
          if (this.alive && this.selectedScopeId() === scopeId && this.startDate() === startDate) {
            this.plan.set(plan);
            this.generating.set(false);
            this.hasUnsavedChanges.set(true);
            // Como Figma (2443:23450): tras generar quedas en el borrador
            // editable con Guardar/Cancelar disponibles.
            this.editMode.set(true);
            if (silent) {
              // Regeneración automática: sin modal ni toast de éxito. Los avisos
              // siguen en el chip ámbar; validatePlan() se llama abajo igual.
            } else if (warnings.length) {
              if (hasOnlySuccess) {
                this.snackBar.open('Planificación generada sin problemas', 'OK', { duration: 4000 });
              } else {
                this.generationWarningsTitle = hasErrors
                  ? 'Planificación generada con problemas'
                  : 'Planificación generada con avisos';
                this.generationWarningsMessage = warnings
                  .filter(w => !w.includes('sin problemas'))
                  .map(w => `• ${w.replace(/\n/g, '<br>&nbsp;&nbsp;')}`)
                  .join('<br><br>');
                this.generationWarningsMode = hasErrors ? 'danger' : 'warning';
                this.showGenerationWarnings = true;
              }
            } else {
              this.snackBar.open('Planificación generada correctamente', 'OK', { duration: 4000 });
            }
            this.validatePlan();
          } else {
            // User switched away — show rich toast with details + navigation
            this.generating.set(false);
            // Aquí no se valida (la vista es otra), así que el auto-guardado
            // nunca llegaría a dispararse: se apaga la bandera para que no la
            // herede la próxima validación de la tienda que se esté mirando.
            // El plan queda como borrador y se avisa por notificación.
            this.autoSaveAfterValidation = null;
            const notifyType = hasErrors ? 'error' : hasOnlySuccess || !warnings.length ? 'success' : 'warning';
            const notifyMsg = `${scopeName}: planificación generada`;
            const notifyMethod = notifyType === 'error' ? 'error' : notifyType === 'warning' ? 'warning' : 'success';
            this.notificationService[notifyMethod](notifyMsg, 10000, {
              detail: warningDetail || undefined,
              action: navAction,
            });
          }
        },
        error: () => {
          this.generatingScopes.update(s => { const n = new Set(s); n.delete(scopeId); return n; });
          this.generating.set(false);
          // Sin plan nuevo no hay nada que auto-guardar; si la bandera quedara
          // encendida, la siguiente validación (de una edición manual) guardaría
          // sola sin que nadie lo haya pedido.
          this.autoSaveAfterValidation = null;
          const navAction = {
            label: 'Ver planificación',
            callback: () => this.navigateToScope(scopeId, startDate),
          };
          this.notificationService.error(`${scopeName}: error al generar`, 10000, { action: navAction });
        },
      });
  }

  /**
   * Resumen de "Generar todas" en un modal (zb-dialog de avisos, mismos estilos
   * que el resto de la app). Sustituye a la pila de toasts: con 15 tiendas eran
   * ilegibles y desaparecían solos.
   */
  private showBulkSummary(
    results: BulkGenerationResult[],
    scopeNames: Map<number, string>,
  ): void {
    const label = this.scopeEntityName().toLowerCase();
    const ok = results.filter(r => r.status === 'success');
    const failed = results.filter(r => r.status !== 'success');
    // "sin problemas" es el texto que devuelve el back cuando no hay nada que
    // avisar; no cuenta como aviso real.
    const realWarnings = (r: BulkGenerationResult) =>
      (r.warnings || []).filter(w => !w.includes('sin problemas'));
    const withWarnings = ok.filter(r => realWarnings(r).length > 0);
    const clean = ok.length - withWarnings.length;

    const rows: string[] = [
      `<strong>${ok.length}</strong> de <strong>${results.length}</strong> ${label}s generadas.`,
    ];
    if (clean > 0)   rows.push(`✔ ${clean} sin problemas.`);
    if (withWarnings.length) rows.push(`▲ ${withWarnings.length} con avisos.`);
    if (failed.length)       rows.push(`✖ ${failed.length} con error.`);
    rows.push('');

    if (failed.length) {
      rows.push('<strong>No se pudieron generar:</strong>');
      for (const r of failed) {
        rows.push(`• ${scopeNames.get(r.scope) || '#' + r.scope}: ${r.error || 'error'}`);
      }
      rows.push('');
    }
    if (withWarnings.length) {
      rows.push('<strong>Con avisos (entra en cada una para el detalle):</strong>');
      for (const r of withWarnings) {
        const n = realWarnings(r).length;
        rows.push(`• ${scopeNames.get(r.scope) || '#' + r.scope} — ${n} aviso(s)`);
      }
      rows.push('');
    }
    rows.push('<em>Quedan como borrador: revisa y guarda cada una.</em>');

    this.generationWarningsTitle = failed.length
      ? 'Generación terminada con errores'
      : `Generación terminada — ${ok.length} ${label}s`;
    this.generationWarningsMessage = rows.join('<br>');
    this.generationWarningsMode = failed.length ? 'danger' : 'warning';
    this.showGenerationWarnings = true;
  }

  /** Abre/cierra el desplegable del botón "Generar". */
  toggleGenerateMenu(ev: MouseEvent): void {
    ev.stopPropagation();   // si no, el listener de document lo cierra al instante
    this.generateMenuOpen.update(v => !v);
  }

  /** "Generar todas" desde el desplegable: cierra el menú y pide confirmación. */
  generateAllFromMenu(): void {
    this.generateMenuOpen.set(false);
    this.generateAll();
  }

  // ── Generación por ZONA ────────────────────────────────────────────────
  //
  // Tercer ámbito del botón Generar: esta tienda · esta zona · todas. Usa el
  // MISMO flujo que "todas" (mismo endpoint, mismas reglas, mismo resumen); lo
  // único que cambia es el conjunto de tiendas.

  /** Código de zona de la tienda seleccionada ('huesca'), o '' si no tiene. */
  private currentZoneCode(): string {
    const data = this.scopeDataById()[this.selectedScopeId()] ?? {};
    return String(data['zona'] ?? '').trim();
  }

  /**
   * Tiendas de la zona de la tienda seleccionada, ella incluida.
   *
   * La zona sale de `scopeDataById`, que ya trae el `data` completo de cada
   * registro, así que el contador no necesita ninguna llamada extra. Se
   * recalcula al cambiar de tienda porque depende de `selectedScopeId`.
   */
  zoneScopes = computed<{ id: number; name: string }[]>(() => {
    const zona = this.currentZoneCode();
    if (!zona) return [];
    const data = this.scopeDataById();
    return this.scopeRecords().filter(
      s => String((data[s.id] ?? {})['zona'] ?? '').trim() === zona);
  });

  /**
   * Nombre legible de la zona ('Jaca + Sabiñánigo'), no su código
   * ('jaca_sabinanigo'). Si el catálogo aún no ha cargado se cae al código para
   * no dejar el texto a medias.
   */
  zoneLabel = computed(() => {
    const zona = this.currentZoneCode();
    if (!zona) return '';
    return this.zoneLabels()[zona] ?? zona;
  });

  /** `{codigo: etiqueta}` del catálogo de zonas. */
  private zoneLabels = signal<Record<string, string>>({});

  /**
   * Carga las etiquetas de zona a partir del campo que las declara.
   *
   * El slug del ámbito es configurable (no siempre 'tienda'), así que se recibe
   * del flujo de carga en vez de escribirlo a mano.
   */
  private loadZoneLabels(scopeSlug: string): void {
    if (!scopeSlug) return;
    this.entityFieldService.getAll(scopeSlug)
      .pipe(catchError(() => of([] as any[])))
      .subscribe(fields => {
        const campo = (fields as any[]).find(
          f => f.key === 'zona' && f.kind_code);
        if (!campo) return;
        this.catalogService.getValues(campo.kind_code)
          .pipe(catchError(() => of([] as any[])))
          .subscribe(values => this.zoneLabels.set(
            Object.fromEntries((values as any[]).map(v => [String(v.code), v.label]))));
      });
  }

  generateZoneFromMenu(): void {
    this.generateMenuOpen.set(false);
    const scopes = this.zoneScopes();
    if (scopes.length < 2) return;
    const nombres = scopes.map(s => s.name).join(', ');
    this.generateAllMessage =
      `Se generarán planificaciones para <strong>${scopes.length}</strong> `
      + `${this.scopeEntityName().toLowerCase()}s de la zona `
      + `<strong>${this.zoneLabel()}</strong> en paralelo:<br><br>${nombres}`
      + this.bulkDraftWarning(scopes);
    this.bulkScopes = scopes;
    this.showGenerateAllConfirm = true;
  }

  /**
   * Tiendas del lote en curso. Lo fija quien abre la confirmación ("todas" o
   * "esta zona") y lo consume `doGenerateAll`, para no duplicar el flujo de
   * generación por cada ámbito.
   */
  private bulkScopes: { id: number; name: string }[] = [];

  generateAll(): void {
    const scopes = this.scopeRecords();
    if (scopes.length < 2) return;
    this.bulkScopes = scopes;

    const scopeNames = scopes.map(s => s.name).join(', ');
    this.generateAllMessage = `Se generarán planificaciones para <strong>${scopes.length}</strong> ${this.scopeEntityName().toLowerCase()}s en paralelo:<br><br>${scopeNames}`
      + this.bulkDraftWarning(scopes);
    this.showGenerateAllConfirm = true;
  }

  doGenerateAll(): void {
    this.showGenerateAllConfirm = false;
    // El lote lo fijó quien abrió la confirmación: todas las tiendas o solo las
    // de la zona. De ahí en adelante el flujo es idéntico.
    const scopes = this.bulkScopes.length ? this.bulkScopes : this.scopeRecords();
    this.generatingAll.set(true);

    const startDate = this.startDate();
    const scopeIds = scopes.map(s => s.id);
    // Marcar TODAS las tiendas como "generando": así la que estés mirando pinta
    // el mismo skeleton que al generar una sola, y los chips del resto llevan su
    // propio spinner. Sustituye al toast, que no decía por dónde iba.
    this.generatingScopes.update(s => {
      const n = new Set(s);
      scopeIds.forEach(id => n.add(id));
      return n;
    });

    this.planningService.generateBulk(startDate, scopeIds).subscribe({
      next: response => {
        this.generatingAll.set(false);
        // Liberar todas: el backend responde cuando ya ha terminado la tanda
        // completa (es secuencial), así que no hay estados intermedios que leer.
        this.generatingScopes.update(s => {
          const n = new Set(s);
          scopeIds.forEach(id => n.delete(id));
          return n;
        });
        const results = response.results || [];
        const scopeMap = new Map(scopes.map(s => [s.id, s.name]));

        // Resumen en un MODAL, no en toasts: con 15 tiendas la pila de avisos
        // tapaba la pantalla y se iba sola antes de poder leerla. Reutiliza el
        // zb-dialog de avisos de generación (mismos estilos que el resto).
        for (const r of results) {
          if (r.status === 'success' && r.plan) {
            this.planningService.setDraft(startDate, r.scope, r.plan);
          }
        }
        this.showBulkSummary(results, scopeMap);

        if (scopeIds.includes(this.selectedScopeId())) this.loadWeek(this.startDate());
      },
      error: () => {
        this.generatingAll.set(false);
        // Sin esto los chips se quedarían girando para siempre tras un fallo.
        this.generatingScopes.update(s => {
          const n = new Set(s);
          scopeIds.forEach(id => n.delete(id));
          return n;
        });
        this.notificationService.error('Error al generar planificaciones');
      },
    });
  }

  copyFromPreviousWeek(): void {
    this.showCopyConfirm = true;
  }

  doCopy(): void {
    this.showCopyConfirm = false;
    this.loading.set(true);
    this.planningService.copyFromPreviousWeek(this.startDate(), this.selectedScopeId()).subscribe({
      next: wp => {
        const plan = wp.plan ?? [];
        this.mergeOfficialRests(plan);
        this.plan.set(plan);
        this.loading.set(false);
        this.hasUnsavedChanges.set(true);
        this.snackBar.open('Semana anterior copiada — revisa y guarda los cambios', 'OK', { duration: 4000 });
        this.validatePlan();
      },
      error: () => {
        this.loading.set(false);
        this.showCopyError = true;
      },
    });
  }

  clearWeek(): void {
    this.showClearConfirm = true;
  }

  doClear(): void {
    this.showClearConfirm = false;
    const empty = this.plan().map(day => {
      const d: DayPlan = { date: day.date, dayName: day.dayName, rest: [] };
      this.shiftSlots().forEach(s => (d[s.code] = []));
      const official = this.weeklyRestDays().filter(r => r.date === day.date).map(r => r.workerId);
      d.rest = [...new Set(official)];
      return d;
    });
    this.plan.set(empty);
    this.hasUnsavedChanges.set(true);
    this.snackBar.open('Planificación limpiada', 'OK', { duration: 2000 });
  }

  validatePlan(): void {
    this.validateSubject.next();
  }

  // ── Merge official rest days ───────────────────────────────────────────

  private mergeOfficialRests(plan: DayPlan[]): void {
    const rests = this.weeklyRestDays();
    for (const day of plan) {
      const official = rests.filter(r => r.date === day.date).map(r => r.workerId);
      if (!day.rest) day.rest = [];
      for (const wid of official) {
        if (!day.rest.includes(wid)) day.rest.push(wid);
      }
    }
  }

  isOfficialRest(workerId: number, dayDate: string): boolean {
    return this.weeklyRestDays().some(r => r.workerId === workerId && r.date === dayDate);
  }

  getRestReason(workerId: number, dayDate: string): string {
    return this.weeklyRestDays().find(r => r.workerId === workerId && r.date === dayDate)?.reason || '';
  }

  // ── Assignment helpers ─────────────────────────────────────────────────

  getAssignments(day: DayPlan, slotCode: string): ShiftAssignment[] {
    return (day[slotCode] as ShiftAssignment[]) || [];
  }

  addAssignment(day: DayPlan, slotCode: string): void {
    const slot = this.shiftSlots().find(s => s.code === slotCode);
    const attrs = slot?.attributes as any || {};
    const newEntry: ShiftAssignment = {
      workerId: 0, workerName: '',
      start: attrs.start_time || '00:00',
      end: attrs.end_time || '00:00',
      areas: [],
    };
    this.patchDay(day, slotCode, [...this.getAssignments(day, slotCode), newEntry]);
    this.markDirty(day.date);
  }

  removeAssignment(day: DayPlan, slotCode: string, index: number): void {
    const current = [...this.getAssignments(day, slotCode)];
    current.splice(index, 1);
    this.patchDay(day, slotCode, current);
    this.markDirty(day.date, slotCode);
    this.validatePlan();
  }

  onWorkerChange(day: DayPlan, slotCode: string, index: number, workerId: number): void {
    const w = this.workers().find(x => x.id === +workerId);
    const pill = w ? this.workerPrimaryPill(w) : '';
    const current = this.getAssignments(day, slotCode).map((a, i) =>
      i === index ? { ...a, workerId: +workerId, workerName: w?.name ?? '', areas: pill ? [pill] : [] } : a
    );
    this.patchDay(day, slotCode, current);
    this.markDirty(day.date, slotCode);
    this.validatePlan();
  }

  /** Resolve the worker's highest-priority pill name (e.g. primary role). */
  workerPrimaryPill(w: Worker): string {
    const key = this.pillsFieldKey();
    if (!key) return '';
    const val = w.custom_data?.[key];
    if (!val) return '';
    const items: any[] = Array.isArray(val) ? val : [val];
    // Sort by priority if objects, otherwise array index is the priority
    const sorted = items
      .map((item: any, idx: number) => ({
        id: typeof item === 'object' && item !== null ? (item.value ?? item.id) : item,
        prio: typeof item === 'object' && item !== null ? (item.priority ?? idx + 1) : idx + 1,
      }))
      .sort((a, b) => a.prio - b.prio);
    // Find the first one that exists in our areas (pills)
    for (const entry of sorted) {
      const area = this.areas().find(a => a.id === +entry.id);
      if (area) return area.name;
    }
    return '';
  }

  toggleArea(day: DayPlan, slotCode: string, index: number, areaName: string): void {
    const current = this.getAssignments(day, slotCode).map((a, i) => {
      if (i !== index) return a;
      const areas = a.areas.includes(areaName)
        ? a.areas.filter(x => x !== areaName)
        : [...a.areas, areaName];
      return { ...a, areas };
    });
    this.patchDay(day, slotCode, current);
    this.markDirty(day.date, slotCode);
    this.validatePlan();
  }

  isAreaAssigned(assignment: ShiftAssignment, areaName: string): boolean {
    return assignment.areas.includes(areaName);
  }

  isAreaBlocked(assignment: ShiftAssignment, area: SimpleArea): boolean {
    return false;
  }

  getAreaBlockReason(assignment: ShiftAssignment, area: SimpleArea): string {
    return '';
  }

  private patchDay(day: DayPlan, key: string, value: any): void {
    this.plan.set(this.plan().map(d => d.date === day.date ? { ...d, [key]: value } : d));
  }

  /** ¿Dos listas de violations son equivalentes? (mismo conjunto, sin importar
   *  orden). Se usa para decidir si un día cambió de verdad tras validar y
   *  evitar repintar celdas sin cambios. */
  private sameViolations(a: RestrictionViolation[], b: RestrictionViolation[]): boolean {
    if (a.length !== b.length) return false;
    const key = (v: RestrictionViolation) =>
      `${v.restrictionId ?? ''}|${v.shift ?? ''}|${v.severity}|${v.message}`;
    const sa = a.map(key).sort();
    const sb = b.map(key).sort();
    return sa.every((k, i) => k === sb[i]);
  }

  private markDirty(dayDate?: string, slotCode?: string): void {
    this.hasUnsavedChanges.set(true);
    // NO vaciamos day.violations aquí. Antes se hacía `violations: []` para
    // "invalidar" el estado viejo mientras el backend recalcula, pero eso
    // borraba TODOS los badges (warning/error) del día en cuanto se movía un
    // trabajador y solo reaparecían al volver la validación (200ms + red):
    // el "reseteo/parpadeo global" de estados. Conservamos las violations
    // actuales; la validación entrante las reemplazará limpiamente por las
    // nuevas, sin parpadeo.
    if (dayDate && slotCode) {
      this.validatingCell.set({ day: dayDate, slot: slotCode });
      // Marca SOLO la celda tocada como pendiente. No marcamos el día entero:
      // hacerlo ocultaba el estado (correcto) de OTROS trabajadores del día
      // mientras llegaba la validación → parpadeaban (p.ej. Borja perdía su
      // rojo al mover a otro y lo recuperaba). Los demás conservan su estado
      // actual; la validación entrante lo reemplaza limpiamente.
      this.pendingCells.update(s => new Set(s).add(`${dayDate}|${slotCode}`));
    }
  }

  // ── Rest ───────────────────────────────────────────────────────────────

  addRest(day: DayPlan): void {
    this.patchDay(day, 'rest', [...(day.rest || []), 0]);
    this.markDirty(day.date);
  }

  removeRest(day: DayPlan, index: number): void {
    const wid = (day.rest || [])[index];
    if (this.isOfficialRest(wid, day.date)) {
      this.snackBar.open('No se puede quitar un descanso oficial', 'OK', { duration: 3000 });
      return;
    }
    const rest = [...(day.rest || [])];
    rest.splice(index, 1);
    this.patchDay(day, 'rest', rest);
    this.markDirty(day.date, 'rest');
    this.validatePlan();
  }

  onRestWorkerChange(day: DayPlan, index: number, workerId: number): void {
    const rest = (day.rest || []).map((id, i) => (i === index ? +workerId : id));
    this.patchDay(day, 'rest', rest);
    this.markDirty(day.date, 'rest');
    this.validatePlan();
  }

  getWorkerName(id: number): string {
    const w = this.workers().find(w => w.id === id);
    if (w?.name) return w.name;
    // Respaldo: nombre desde la ausencia aprobada (por si el trabajador está
    // inactivo o filtrado fuera de la lista visible pero tiene una baja que sí
    // debe mostrarse en la columna Ausencias).
    const ab = this.approvedAbsences().find(a => a.worker === id && !!a.worker_name);
    return ab?.worker_name ?? 'ID: ' + id;
  }

  // ── Smart worker selection with restriction hints ─────────────────────

  getWorkerOptions(day: DayPlan, slotCode: string, currentWorkerId = 0): WorkerOption[] {
    const allWorkers = this.workers().filter(
      w => w.active && this.workerMatchesFilters(w) && this.workerBelongsToScope(w));
    const restIds = new Set<number>([
      ...(day.rest || []),
      ...this.weeklyRestDays().filter(r => r.date === day.date).map(r => r.workerId),
    ]);
    const assignedInDay = new Map<number, number>();
    this.shiftSlots().forEach(s => {
      this.getAssignments(day, s.code).forEach(a => {
        if (a.workerId && a.workerId !== currentWorkerId) {
          assignedInDay.set(a.workerId, (assignedInDay.get(a.workerId) || 0) + 1);
        }
      });
    });
    const prevDay = this.getPreviousDay(day.date);
    const nightWorkers = prevDay ? new Set(
      this.getAssignments(prevDay, 'night').map(a => a.workerId).filter(id => id > 0)
    ) : new Set<number>();

    return allWorkers.map(w => {
      const warnings: string[] = [];
      let blocked = false;
      let blockReason = '';

      // Turno PROHIBIDO por una restricción de error (p.ej. "Régimen antiguo no
      // trabaja sábado tarde"): no se puede ofrecer, o el plan saldría con
      // error justo después de asignarlo.
      if (this.isShiftBlockedFor(w, slotCode)) {
        blocked = true;
        blockReason = 'Este turno le está restringido';
        return { worker: w, warnings, blocked, blockReason };
      }

      // Ausencia aprobada que cubre este día (incl. indefinida sin fecha fin):
      // el empleado no está disponible para asignar (AC-4).
      if (this.isAbsentOn(w.id, day.date)) {
        blocked = true;
        blockReason = 'Ausencia';
        return { worker: w, warnings, blocked, blockReason };
      }

      if (restIds.has(w.id)) {
        blocked = true;
        const reason = this.getRestReason(w.id, day.date);
        blockReason = reason ? `En descanso (${reason})` : 'En descanso';
        return { worker: w, warnings, blocked, blockReason };
      }

      const count = assignedInDay.get(w.id) || 0;
      if (count >= 1) {
        blocked = true;
        blockReason = 'Ya tiene turno asignado hoy';
        return { worker: w, warnings, blocked, blockReason };
      }

      const inThisSlot = this.getAssignments(day, slotCode)
        .some(a => a.workerId === w.id && a.workerId !== currentWorkerId);
      if (inThisSlot) {
        blocked = true;
        blockReason = 'Ya asignado en este turno';
        return { worker: w, warnings, blocked, blockReason };
      }

      if (slotCode === 'morning' && nightWorkers.has(w.id)) {
        warnings.push('Turno de noche ayer');
      }

      if (w.preferredShifts && w.preferredShifts.length > 0) {
        const preferred = w.preferredShifts.map(p => p.shift_type);
        if (!preferred.includes(slotCode)) {
          warnings.push('Turno no preferido');
        }
      }

      return { worker: w, warnings, blocked, blockReason };
    });
  }

  getAvailableOptions(day: DayPlan, slotCode: string, currentWorkerId = 0): WorkerOption[] {
    return this.getWorkerOptions(day, slotCode, currentWorkerId).filter(o => !o.blocked);
  }

  getBlockedOptions(day: DayPlan, slotCode: string, currentWorkerId = 0): WorkerOption[] {
    return this.getWorkerOptions(day, slotCode, currentWorkerId).filter(o => o.blocked);
  }

  availableRestWorkers(day: DayPlan, currentId = 0): Worker[] {
    const usedIds = new Set<number>();
    this.shiftSlots().forEach(s => {
      this.getAssignments(day, s.code).forEach(a => { if (a.workerId) usedIds.add(a.workerId); });
    });
    (day.rest || []).forEach(id => { if (id !== currentId) usedIds.add(id); });
    return this.workers()
      .filter(w => w.active && !usedIds.has(w.id) && this.workerMatchesFilters(w)
        && this.workerBelongsToScope(w))
      .sort((a, b) => a.name.localeCompare(b.name, 'es', { sensitivity: 'base' }));
  }

  // ── Violations ─────────────────────────────────────────────────────────

  downloadGenerationJson(): void {
    const data = this.lastGenerationResult();
    if (!data) return;
    const full = { ...data, planWithViolations: this.plan() };
    const blob = new Blob([JSON.stringify(full, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `planificacion-${data.startDate}-scope${data.scopeId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  getDayViolations(day: DayPlan): RestrictionViolation[] {
    return day.violations ?? [];
  }

  getSlotViolations(day: DayPlan, slotCode: string): RestrictionViolation[] {
    return (day.violations ?? []).filter(v => v.shift === slotCode);
  }

  getSlotViolationTooltip(day: DayPlan, slotCode: string): string {
    return this.getSlotViolations(day, slotCode).map(v => `• ${v.message}`).join('\n');
  }

  getSlotErrorCount(day: DayPlan, slotCode: string): number {
    return (day.violations ?? []).filter(v => v.shift === slotCode && v.severity === 'error').length;
  }

  getSlotWarningCount(day: DayPlan, slotCode: string): number {
    return (day.violations ?? []).filter(v => v.shift === slotCode && v.severity === 'warning').length;
  }

  /** Severidad global de una TIENDA (pill) según sus violaciones, para el
   *  indicador ●/▲ del selector (Figma manual-cabrero punto 6):
   *  'error' (●) > 'warning' (▲) > null. Solo se conoce la severidad de la
   *  tienda actualmente cargada; para las demás devuelve null hasta que se
   *  seleccionen (la validación es por tienda cargada). */
  scopeSeverity(scopeId: number): 'error' | 'warning' | null {
    // La tienda ABIERTA se calcula en vivo: su plan está cargado y puede tener
    // cambios sin guardar, así que el dato del servidor estaría desfasado.
    if (scopeId === this.selectedScopeId()) {
      if (this.getWeekErrorCount() > 0) return 'error';
      if (this.getWeekWarningCount() > 0 || this.getIssueCount() > 0) return 'warning';
      return null;
    }
    // Las DEMÁS salen del servidor (week-status), que evalúa el plan guardado de
    // cada una. Antes devolvían null —el front solo tiene cargado un plan— y su
    // chip no avisaba de nada: había que entrar tienda por tienda para saberlo.
    return this.otherScopeSeverities()[String(scopeId)] ?? null;
  }

  /** `{scope_id: severidad}` de las demás tiendas, según el plan guardado. */
  private otherScopeSeverities = signal<Record<string, 'error' | 'warning'>>({});

  /** Refresca la severidad de todas las tiendas de la semana visible. */
  private loadScopeSeverities(week: string): void {
    this.planningService.getWeekStatus([week])
      .pipe(catchError(() => of({ weeks: [] as any[] })))
      .subscribe(r => {
        const w = (r.weeks ?? []).find((x: any) => x.start === week);
        this.otherScopeSeverities.set(w?.scope_severities ?? {});
      });
  }

  /**
   * Cuántos avisos/errores lleva el chip de una tienda, para pintarlo al lado
   * del icono igual que en la celda de un trabajador ("▲ 1").
   *
   * En ámbar cuenta los MISMOS avisos que lista el modal (getIssueCount), no
   * las violaciones sueltas del motor: así el número del chip y el del modal
   * dicen lo mismo.
   */
  scopeSeverityCount(scopeId: number): number {
    const sev = this.scopeSeverity(scopeId);
    if (sev === 'error') return this.getWeekErrorCount();
    if (sev === 'warning') return this.getIssueCount() || this.getWeekWarningCount();
    return 0;
  }

  /** Violaciones que aplican a una celda [día × turno × sección]. Como el
   *  backend NO trae workerId/sección estructurados, se cruza de 3 formas:
   *   1) el `shift` de la violación coincide con el turno de la celda, o
   *   2) el `message` menciona la SECCIÓN de la columna, o
   *   3) el `message` menciona el NOMBRE de algún trabajador de la celda
   *      (violaciones "por día" tipo "máximo 1 turno por día: NOMBRE…").
   *  Así el resaltado marca la celda entera (decisión acordada). */
  cellViolations(day: DayPlan, slotCode: string, sectionName: string): RestrictionViolation[] {
    // Cache: el template llama esto miles de veces por render. Solo se recalcula
    // cuando cambian plan/pendingCells/shiftSlots (ensureViolationsCache).
    this.ensureViolationsCache();
    const key = `${day.date}|${slotCode}|${this.normalizeSection(sectionName)}`;
    const cached = this._cvCache.get(key);
    if (cached) return cached;
    const r = this.computeCellViolations(day, slotCode, sectionName);
    this._cvCache.set(key, r);
    return r;
  }

  private computeCellViolations(day: DayPlan, slotCode: string, sectionName: string): RestrictionViolation[] {
    const all = day.violations ?? [];
    if (!all.length) return [];
    // ¿Esta celda concreta cambió y aún no se ha revalidado? Solo ocultamos su
    // estado (no el de todo el día, que haría parpadear a los demás).
    if (this.pendingCells().has(`${day.date}|${slotCode}`)) return [];

    // Las violaciones traen `shift` (turno) + `dayDate` (día) + `message` con
    // la SECCIÓN al principio, p.ej. "Carne: 10 (max 3)" o un ROL transversal
    // "Encargado: 2 (máx 1) en Mañana". El nombre de la columna puede diferir
    // del prefijo ("Carne" vs "Carnicería"), así que casamos de forma flexible.
    const secN = this.normalizeSection(sectionName);
    // IMPORTANTE: v.shift es el NOMBRE del turno ("Mañana"), pero slotCode es
    // el ID del slot ("153"). Resolvemos el nombre del slot para comparar.
    const slotName = this.normalizeSection(
      this.shiftSlots().find(s => s.code === slotCode)?.label || '');
    // Prefijo del mensaje antes de ":" (la sección/rol al que se refiere).
    const msgSectionN = (msg: string) => this.normalizeSection((msg.split(':')[0] || '').trim());
    // ¿Dos secciones "coinciden"? Una contiene a la otra (Carne⊂Carnicería…).
    const sameSec = (a: string, b: string) =>
      !!a && !!b && (a === b || a.includes(b) || b.includes(a));
    // Columnas reales del plan (para saber si el prefijo del mensaje es una
    // sección concreta o un rol transversal como "Encargado").
    const columnSecs = this.planSections().map(s => this.normalizeSection(s.name));

    return all.filter(v => {
      // 1) El turno DEBE coincidir con el de esta celda (evita que un error de
      //    "Mañana" tiña la celda de "Tarde" del mismo día). Comparamos el
      //    NOMBRE del turno (v.shift) con el nombre del slot de esta celda.
      //    El día ya está garantizado (day.violations viene filtrado por fecha).
      //    EXCEPCIÓN 'multiple': lo devuelve el motor cuando la violación abarca
      //    VARIOS turnos a la vez (p.ej. "máximo 1 turno por día": la persona
      //    está en mañana Y tarde). No es el nombre de ningún turno, así que
      //    este filtro la descartaba y la celda no se pintaba en rojo.
      const abarcaVariosTurnos = this.normalizeSection(v.shift || '') === 'multiple';
      if (!abarcaVariosTurnos
          && v.shift && slotName
          && this.normalizeSection(v.shift) !== slotName) return false;

      const secFromMsg = msgSectionN(v.message || '');
      // ¿El prefijo del mensaje es una columna concreta del plan?
      const matchesAnyColumn = columnSecs.some(c => sameSec(secFromMsg, c));

      if (matchesAnyColumn) {
        // 2) Violación DE SECCIÓN: solo tiñe la celda de esa columna.
        return sameSec(secFromMsg, secN);
      }

      // 3) Violación TRANSVERSAL del turno (rol tipo "Encargado", o sin sección
      //    reconocible): tiñe TODAS las celdas de ese turno/día. El turno ya
      //    casó en el paso 1, así que se muestra.
      return true;
    });
  }

  /** Violaciones que aplican a UN trabajador concreto dentro de una celda.
   *  De las violaciones de la celda, devuelve:
   *   - las que mencionan por nombre a ESTE trabajador, y
   *   - las que NO mencionan a ningún trabajador concreto (son de celda/sección
   *     y aplican a todos: p.ej. "Carne: 10 (max 3)").
   *  Así el estado/tooltip de un chip NO muestra los errores de OTRO trabajador
   *  de la misma celda. */
  workerViolations(assignment: ShiftAssignment, day: DayPlan, slotCode: string, sectionName: string): RestrictionViolation[] {
    const cellV = this.cellViolations(day, slotCode, sectionName);
    if (!cellV.length) return [];
    const allNames = this.allWorkers().map(w => w.name || '').filter(Boolean);
    const me = assignment.workerName || '';

    return cellV.filter(v => {
      const msg = v.message || '';
      // ¿El mensaje menciona a algún trabajador concreto (nombre COMPLETO,
      // con límites de palabra)? El nombre corto "Ana" ya no casa dentro de
      // "Asunción"/"Mariana" — evita que un chip muestre errores de otro.
      const mentioned = allNames.filter(n => this.msgMentionsName(msg, n));
      if (mentioned.length) {
        return !!me && this.msgMentionsName(msg, me);
      }
      // Sin nombre → es de celda/sección: aplica a todos los de la celda.
      return true;
    });
  }

  /** ¿El mensaje `msg` menciona el nombre COMPLETO `name`? Coincidencia
   *  insensible a mayúsculas/acentos y con límites de palabra, para que un
   *  nombre corto no case como subcadena de otro (Ana ≠ Asunción). */
  private msgMentionsName(msg: string, name: string): boolean {
    const norm = (s: string) => (s || '')
      .toLocaleLowerCase('es-ES')
      .normalize('NFD').replace(/[̀-ͯ]/g, '') // quita acentos
      .replace(/\s+/g, ' ').trim();
    const m = norm(msg);
    const n = norm(name);
    if (!m || !n) return false;
    // Escapar regex y exigir límite no alfanumérico a ambos lados.
    const esc = n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return new RegExp(`(^|[^a-z0-9])${esc}([^a-z0-9]|$)`).test(m);
  }

  /** Cache de la última severidad conocida por trabajador+celda. Mantiene el
   *  estado ESTABLE mientras hay una validación en curso: si Borja está rojo y
   *  mueves a otro, Borja sigue rojo (no se resetea); solo cambia DESPUÉS,
   *  cuando llega el resultado fresco. */
  private severityCache = new Map<string, 'error' | 'warning' | null>();

  private severityKey(a: ShiftAssignment, day: DayPlan, slotCode: string, section: string): string {
    return `${a.workerId}|${day.date}|${slotCode}|${this.normalizeSection(section)}`;
  }

  /** Severidad de un trabajador concreto (error > warning > null). */
  workerSeverity(assignment: ShiftAssignment, day: DayPlan, slotCode: string, sectionName: string): 'error' | 'warning' | null {
    const key = this.severityKey(assignment, day, slotCode, sectionName);
    // Mientras se está validando, devolvemos el último estado conocido para no
    // resetear el badge de un trabajador por mover a otro (estabilidad).
    if (this.validating() && this.severityCache.has(key)) {
      return this.severityCache.get(key)!;
    }
    // Cache por versión (rendimiento): O(1) si no cambió plan/pendingCells.
    this.ensureViolationsCache();
    const cached = this._sevCache2.get(key);
    if (cached !== undefined) { this.severityCache.set(key, cached); return cached; }

    const vs = this.workerViolations(assignment, day, slotCode, sectionName);
    const sev: 'error' | 'warning' | null =
      vs.some(v => v.severity === 'error') ? 'error'
      : vs.some(v => v.severity === 'warning') ? 'warning'
      : null;
    this._sevCache2.set(key, sev);
    this.severityCache.set(key, sev);
    return sev;
  }

  /** Tooltip de un trabajador concreto (solo sus violaciones). */
  workerViolationTooltip(assignment: ShiftAssignment, day: DayPlan, slotCode: string, sectionName: string): string {
    return this.workerViolations(assignment, day, slotCode, sectionName)
      .map(v => `• ${v.message}`)
      .join('\n');
  }

  /**
   * Tooltip de la cajita de un trabajador: SIEMPRE el nombre completo, más el
   * horario y —si las hay— las violaciones.
   *
   * En la parrilla el nombre se trunca ("Cebrian…"), sobre todo cuando un turno
   * se parte en dos columnas. Antes el tooltip solo mostraba el horario, así que
   * no había forma de leer el nombre entero sin abrir otra pantalla.
   *
   * El nombre va primero porque es el dato que se viene a buscar al pasar el
   * ratón; se muestra igual esté truncado o no, para que el comportamiento sea
   * uniforme en toda la parrilla.
   */
  workerCellTooltip(
    assignment: ShiftAssignment, day: DayPlan, slotCode: string, sectionName: string,
  ): string {
    const partes = [this.formatWorkerName(assignment.workerName)];
    if (assignment.start && assignment.end) {
      partes.push(`${assignment.start} - ${assignment.end}`);
    }
    const violaciones = this.workerViolationTooltip(assignment, day, slotCode, sectionName);
    if (violaciones) partes.push(violaciones);
    return partes.join('\n');
  }

  /** Severidad de una celda [día×turno×sección] para pintarla en el cuadrante
   *  (Figma manual-cabrero punto 6): 'error' (rojo) > 'warning' (ámbar) > null. */
  cellSeverity(day: DayPlan, slotCode: string, sectionName: string): 'error' | 'warning' | null {
    const vs = this.cellViolations(day, slotCode, sectionName);
    if (vs.some(v => v.severity === 'error')) return 'error';
    if (vs.some(v => v.severity === 'warning')) return 'warning';
    return null;
  }

  /** Tooltip con los mensajes de violación de una celda [día×turno×sección]. */
  cellViolationTooltip(day: DayPlan, slotCode: string, sectionName: string): string {
    return this.cellViolations(day, slotCode, sectionName)
      .map(v => `• ${v.message}`)
      .join('\n');
  }

  isCellValidating(day: DayPlan, slotCode: string): boolean {
    const c = this.validatingCell();
    return this.validating() && !!c && c.day === day.date && c.slot === slotCode;
  }

  getDayErrorCount(day: DayPlan): number {
    return (day.violations ?? []).filter(v => v.severity === 'error').length;
  }

  getDayWarningCount(day: DayPlan): number {
    return (day.violations ?? []).filter(v => v.severity === 'warning').length;
  }

  getDayViolationTooltip(day: DayPlan): string {
    return (day.violations ?? []).map(v => `• ${v.message}`).join('\n');
  }

  getDayErrorTooltip(day: DayPlan): string {
    return (day.violations ?? []).filter(v => v.severity === 'error').map(v => `• ${v.message}`).join('\n');
  }

  getDayWarningTooltip(day: DayPlan): string {
    return (day.violations ?? []).filter(v => v.severity === 'warning').map(v => `• ${v.message}`).join('\n');
  }

  getWeekErrorCount(): number {
    return this.plan().reduce((sum, d) => sum + this.getDayErrorCount(d), 0);
  }

  getWeekWarningCount(): number {
    return this.plan().reduce((sum, d) => sum + this.getDayWarningCount(d), 0);
  }

  /** Reabre el detalle de errores/avisos del plan actual (chips del
   *  cuadrante clicables — el detalle no se pierde al cerrar el diálogo). */
  /** Violaciones de una severidad, agrupadas por restricción y ya formateadas.
   *  Lo comparten el diálogo de errores y el de "problemas a solucionar". */
  private violationLines(severity: 'error' | 'warning'): string[] {
    const all = this.plan().flatMap(d => (d.violations ?? []).filter(v => v.severity === severity));
    if (!all.length) return [];
    const groups = new Map<string, RestrictionViolation[]>();
    for (const v of all) {
      const k = v.restrictionName || 'Otras restricciones';
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k)!.push(v);
    }
    return Array.from(groups.entries()).map(([name, vs]) =>
      vs.length === 1
        ? `<strong>${name}</strong>: ${vs[0].message}`
        : `<strong>${name}</strong> (${vs.length} veces). Ej: ${vs[0].message}`
    );
  }

  showViolationsDetail(severity: 'error' | 'warning'): void {
    const all = this.plan().flatMap(d => (d.violations ?? []).filter(v => v.severity === severity));
    if (!all.length) return;
    const lines = this.violationLines(severity).map(l => `• ${l}`);
    this.generationWarningsTitle = severity === 'error'
      ? `${all.length} ${all.length === 1 ? 'error' : 'errores'} en el plan`
      : `${all.length} ${all.length === 1 ? 'aviso' : 'avisos'} en el plan`;
    this.generationWarningsMessage = lines.join('<br><br>');
    this.generationWarningsMode = severity === 'error' ? 'danger' : 'warning';
    this.showGenerationWarnings = true;
  }

  getTotalAssignments(): number {
    return this.plan().reduce((sum, day) => {
      return sum + this.shiftSlots().reduce((s, slot) =>
        s + this.getAssignments(day, slot.code).filter(a => a.workerId > 0).length, 0);
    }, 0);
  }

  // ── Helpers ────────────────────────────────────────────────────────────

  isWeekend(day: DayPlan): boolean {
    const d = new Date(day.date + 'T00:00:00');
    return d.getDay() === 0 || d.getDay() === 6;
  }

  isToday(day: DayPlan): boolean {
    return day.date === this.fmt(new Date());
  }

  isIncomplete(a: ShiftAssignment): boolean {
    return !a.workerId || a.workerId === 0;
  }

  // ── Figma plan table (rows = day×shift, cols = section) ────────────────
  // Presentación pura: reorganiza los datos YA cargados (plan/shiftSlots/
  // areas/rest) en la matriz de la tabla de Figma. No llama a backend.

  /** Secciones = columnas de la tabla (entidad show_in_schedule → areas()). */
  planSections(): SimpleArea[] {
    return this.areas();
  }

  /** ¿Es el día un fin de semana (sábado/domingo)? */
  private isSaturdayOrSunday(dayDate: string): boolean {
    const dow = new Date(dayDate + 'T00:00:00').getDay(); // 0=domingo, 6=sábado
    return dow === 0 || dow === 6;
  }

  /** Turnos aplicables a un día (heurística por nombre, ya que el modelo
   *  Shift no tiene campo de días): los turnos "Sábado …" solo en fin de
   *  semana; el resto solo de lunes a viernes. */
  slotsForDay(day: DayPlan): any[] {
    // Día de cierre (domingo/festivo): no se trabaja → NINGÚN turno aplica.
    // Sin esto el domingo heredaba los turnos "Sábado …" (isSaturdayOrSunday
    // incluye el domingo) y la columna TURNOS pintaba "Sábado Mañana/Tarde"
    // en una fila donde no hay horarios.
    if (this.isClosedDay(day.date)) return [];
    const isWeekend = this.isSaturdayOrSunday(day.date);
    return this.shiftSlots().filter(slot => {
      // 1) Sábado/domingo → solo turnos "sábado"; resto → solo no-sábado.
      const isSaturdaySlot = /s[áa]bado/i.test(slot.label || '');
      if (isWeekend ? !isSaturdaySlot : isSaturdaySlot) return false;
      // 2) Vigencia DÍA A DÍA: el turno solo aplica si ESTE día está dentro de
      //    su rango [validFrom, validTo]. Los turnos normales (sin fechas)
      //    aplican siempre. (Antes solo se filtraba por semana, así que una
      //    vigencia L-X se pintaba también J-D.)
      if (slot.validFrom && day.date < slot.validFrom) return false;
      if (slot.validTo && day.date > slot.validTo) return false;
      return true;
    });
  }

  /** Filas de la tabla: por cada día, una sub-fila por cada turno aplicable. */
  planTableRows(): { day: DayPlan; slot: any; isFirstOfDay: boolean; dayRowSpan: number }[] {
    const rows: { day: DayPlan; slot: any; isFirstOfDay: boolean; dayRowSpan: number }[] = [];
    for (const day of this.plan()) {
      const slots = this.slotsForDay(day);
      if (!slots.length) {
        // Día sin turnos aplicables (cierre/festivo): igual necesita SU fila,
        // o el día desaparecería de la semana. Slot sintético vacío para que
        // los bindings del template (slot.code/label) sigan funcionando: la
        // columna TURNOS queda en blanco y la fila se pinta en gris.
        rows.push({ day, slot: { code: '', label: '' }, isFirstOfDay: true, dayRowSpan: 1 });
        continue;
      }
      slots.forEach((slot, i) => {
        rows.push({ day, slot, isFirstOfDay: i === 0, dayRowSpan: slots.length });
      });
    }
    return rows;
  }

  // ── Estados visuales de la parrilla: festivo/cierre y ausencias ──────────
  /** Público para el template: ¿la fecha es día de cierre (domingo/festivo)?
   *  En cierre no se trabaja → la fila se pinta neutra y sin horarios. */
  isDayClosed(dateStr: string): boolean {
    return this.isClosedDay(dateStr);
  }

  /** Nombres de los empleados con ausencia aprobada ese día (vacío en cierre).
   *  Reutiliza la misma lógica que el PDF de ausencias. */
  absentWorkersOn(dateStr: string): string[] {
    return this.pdfAusenciasByDay(dateStr);
  }

  /** ¿Hay al menos una ausencia ese día? (para pintar la columna Ausencias). */
  dayHasAbsences(dateStr: string): boolean {
    return this.absentWorkersOn(dateStr).length > 0;
  }

  /** ¿Es una sección "ancha" (2 sub-columnas)? Solo cuando REALMENTE hace
   *  falta: alguna celda de la semana tiene 2+ horarios que se repartirían
   *  en dos sub-columnas. Antes se fijaba por nombre (Caja/Pescadería
   *  siempre anchas), lo que dejaba columnas de 220px medio vacías y forzaba
   *  scroll horizontal. Ahora el ancho se adapta al contenido real. */
  isWideSection(name: string): boolean {
    // Caja y Pescadería van SIEMPRE anchas y a dos sub-columnas, como en el
    // diseño de Figma (nodo 2464:36717): son las dos secciones con más gente y
    // el mockup las dibuja con col-1 / col-2 fijas.
    //
    // Antes se decidía según los HORARIOS distintos de cada celda, y eso las
    // hacía cambiar de forma según la semana: en una, Pescadería salía a dos
    // columnas y Caja a una, así que parecían tener anchos distintos aunque
    // comparten el mismo token. Ahora el ancho es estable y las dos idénticas.
    const n = this.normalizeSection(name);
    return n.includes('caja') || n.includes('pescad');
  }

  // ── Picker de empleados por celda (Figma: Dropdown_menu 2480:28495) ────
  openPicker = signal<{ dayDate: string; slotCode: string; section: string } | null>(null);
  pickerSearch = signal('');

  // ── Menú de worker asignado (clic en slot lleno → sustituir/borrar,
  //    Figma 2435:18950). Identifica el worker concreto por índice. ────────
  openWorkerMenu = signal<{ dayDate: string; slotCode: string; section: string; idx: number } | null>(null);

  /** Cierra los dropdowns (picker y menú de worker) al clicar fuera. */
  @HostListener('document:click', ['$event'])
  onDocumentClick(ev: MouseEvent): void {
    const target = ev.target as HTMLElement;
    // El picker se abre desde 2 sitios: el botón "+" (.cell-add-wrap) y la
    // cajita punteada del slot vacío (.figma-plantable__worker--slot, que vive
    // en el drop-list). También hay que respetar clics dentro del propio panel
    // (.emp-picker). Solo se cierra si el clic cae FUERA de todos ellos.
    if (this.openPicker()
        && !target.closest('.cell-add-wrap')
        && !target.closest('.figma-plantable__worker--slot')
        && !target.closest('.emp-picker')) {
      this.openPicker.set(null);
    }
    if (this.openWorkerMenu() && !target.closest('.worker-menu-wrap')) {
      this.openWorkerMenu.set(null);
    }
    if (this.generateMenuOpen() && !target.closest('.gen-split')) {
      this.generateMenuOpen.set(false);
    }
  }

  /** Cierra cualquier dropdown de empleados abierto (picker o menú de worker)
   *  y limpia el buscador. Lo usa la "x" del buscador. */
  closePickers(): void {
    this.openPicker.set(null);
    this.openWorkerMenu.set(null);
    this.pickerSearch.set('');
  }

  /** Abre/cierra el menú de un worker asignado (sustituir/borrar). */
  toggleWorkerMenu(day: DayPlan, slotCode: string, section: string, idx: number): void {
    const cur = this.openWorkerMenu();
    if (cur && cur.dayDate === day.date && cur.slotCode === slotCode && cur.section === section && cur.idx === idx) {
      this.openWorkerMenu.set(null);
    } else {
      this.pickerSearch.set('');
      this.openWorkerMenu.set({ dayDate: day.date, slotCode, section, idx });
    }
  }

  isWorkerMenuOpen(day: DayPlan, slotCode: string, section: string, idx: number): boolean {
    const cur = this.openWorkerMenu();
    return !!cur && cur.dayDate === day.date && cur.slotCode === slotCode && cur.section === section && cur.idx === idx;
  }

  togglePicker(day: DayPlan, slotCode: string, section: string): void {
    // En día de cierre no se trabaja: no se abre el selector de empleados.
    if (this.isClosedDay(day.date)) return;
    const cur = this.openPicker();
    if (cur && cur.dayDate === day.date && cur.slotCode === slotCode && cur.section === section) {
      this.openPicker.set(null);
    } else {
      this.pickerSearch.set('');
      this.openPicker.set({ dayDate: day.date, slotCode, section });
    }
  }

  isPickerOpen(day: DayPlan, slotCode: string, section: string): boolean {
    const cur = this.openPicker();
    return !!cur && cur.dayDate === day.date && cur.slotCode === slotCode && cur.section === section;
  }

  /** Trabajadores disponibles para la celda, filtrados por el buscador. */
  pickerWorkers(day: DayPlan, slotCode: string): WorkerOption[] {
    const q = this._searchKey(this.pickerSearch().trim());
    const all = this.getWorkerOptions(day, slotCode);
    // Se muestran los disponibles y, además, los ausentes (bloqueados por
    // ausencia) para que quede reflejado que están de baja al buscarlos.
    // El resto de bloqueos (ya tiene turno, descanso…) se siguen ocultando.
    return all
      .filter(o => !o.blocked || o.blockReason === 'Ausencia')
      // Se busca sobre el nombre normalizado (sin acentos) porque los datos
      // llegan casi todos en MAYUSCULAS y se pintan capitalizados: asi
      // "bego" encuentra a "BEGOÑA" y "banos" a "Baños".
      .filter(o => !q || this._searchKey(o.worker.name).includes(q))
      // La API no devuelve los trabajadores ordenados, asi que el desplegable
      // salia en orden arbitrario (y los ausentes aparecian arriba por puro
      // azar). Se ordena alfabeticamente con localeCompare para que Ñ y los
      // acentos caigan donde toca en español.
      .sort((a, b) => a.worker.name.localeCompare(b.worker.name, 'es', { sensitivity: 'base' }));
  }

  /** Clave de búsqueda: minúsculas y sin acentos, para comparar nombres que
   *  llegan en MAYUSCULAS con lo que el usuario teclea. */
  private _searchKey(s: string): string {
    return (s ?? '')
      .toLocaleLowerCase('es-ES')
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '');
  }

  /** Etiqueta corta para el empleado ausente en el buscador. Se mantiene
   *  breve ("Ausencia") para no pisar el nombre; el detalle del tipo va como
   *  tooltip (title) en el propio elemento. */
  absenceLabel(wid: number, dateStr: string): string {
    return this.isAbsentOn(wid, dateStr) ? 'Ausencia' : '';
  }

  /** Detalle de la ausencia para el tooltip (tipo + rango o indefinida). */
  absenceTitle(wid: number, dateStr: string): string {
    const a = this.approvedAbsences().find(x =>
      x.worker === wid && x.start_date <= dateStr && (!x.end_date || dateStr <= x.end_date)
    );
    if (!a) return '';
    return a.end_date
      ? `${a.type_name}: ${a.start_date} → ${a.end_date}`
      : `${a.type_name}: desde ${a.start_date} (indefinida)`;
  }

  /** Normaliza el nombre de un trabajador a Título consistente: los datos
   *  vienen mezclados ("ALASTUEY SOLANILLA, MARI MAR" vs "Ana Garcia"). Se
   *  capitaliza cada palabra (primera letra mayúscula, resto minúscula),
   *  respetando comas y espacios, para que TODOS se vean igual. */
  formatWorkerName(name: string): string {
    if (!name) return '';
    return name
      .toLocaleLowerCase('es-ES')
      .replace(/(^|[\s,\-./])([\p{L}])/gu, (_m, sep, ch) => sep + ch.toLocaleUpperCase('es-ES'));
  }

  /** ¿El trabajador es de una ETT (empresa de trabajo temporal)? Para el
   *  badge "ETT" del dropdown de empleados (Figma 2480:28495). En el modelo
   *  Cabrero el dato vive en custom_data: `tipo_contrato` == "ett" o el campo
   *  `proveedor_ett` con valor (nombre de la ETT). */
  isEttWorker(w: Worker): boolean {
    const cd = (w?.custom_data as any) || {};
    const tipo = (cd.tipo_contrato ?? '').toString().toLowerCase();
    const proveedor = (cd.proveedor_ett ?? '').toString().trim();
    return /ett/.test(tipo) || proveedor.length > 0;
  }

  /** Añade un trabajador a la celda [sección × día×turno] desde el picker. */
  addWorkerToCell(day: DayPlan, slotCode: string, sectionName: string, w: Worker): void {
    // Blindaje: en día de cierre no se asigna a nadie (el template ya no ofrece
    // la celda, pero esto cubre cualquier otra vía de entrada).
    if (this.isClosedDay(day.date)) return;
    // Sección que ese día no abre: no se añade a nadie (misma regla que el
    // arrastre). El picker no debería llegar aquí —su botón está oculto—, pero
    // la comprobación va en el sitio que modifica el plan.
    if (this.isSectionClosedToday(sectionName, day.date)) return;
    const slot = this.shiftSlots().find(s => s.code === slotCode);
    const attrs = (slot?.attributes as any) || {};
    const entry: ShiftAssignment = {
      workerId: w.id,
      workerName: w.name,
      start: attrs.start_time || '00:00',
      end: attrs.end_time || '00:00',
      areas: [sectionName],
    };
    this.patchDay(day, slotCode, [...this.getAssignments(day, slotCode), entry]);
    this.markDirty(day.date, slotCode);
    this.validatePlan();
    this.openPicker.set(null);
  }

  /** ¿La celda [sección × día×turno] tiene empleados asignados? Determina si
   *  el dropdown muestra la opción "Borrar" (slot lleno, Figma 2483:30551). */
  cellHasWorkers(day: DayPlan, slotCode: string, sectionName: string): boolean {
    return this.cellAssignments(day, slotCode, sectionName).length > 0;
  }

  // ── Drag & drop de workers entre slots (Figma 2435:18952) ──────────────
  /** Info que viaja con el worker arrastrado (incluye la sección de origen). */
  private dragData: { day: DayPlan; slotCode: string; section: string; assignment: ShiftAssignment } | null = null;

  /** Celda [día×turno×sección] sobre la que se está arrastrando (para el
   *  resalte del slot destino: fondo #fff9e9 + borde punteado #fccf3f). */
  dropHover = signal<string | null>(null);

  /** ¿Hay un arrastre de worker en curso? Mientras dura, se ocultan los
   *  slots vacíos punteados de las celdas para que no se sumen al placeholder
   *  (evita el "doble borde" al mover un trabajador). */
  isDragging = signal(false);

  /** Clave única de una celda destino, para el resalte durante el drag. */
  cellKey(day: DayPlan, slotCode: string, sectionName: string): string {
    return `${day.date}|${slotCode}|${sectionName}`;
  }

  onDragStarted(day: DayPlan, slotCode: string, section: string, assignment: ShiftAssignment): void {
    this.dragData = { day, slotCode, section, assignment };
    this.isDragging.set(true);
  }

  onDragEnded(): void {
    this.dragData = null;
    this.dropHover.set(null);
    this.isDragging.set(false);
  }

  /** Soltar un worker en una celda destino: MOVER (quitar de origen, poner
   *  en destino) — como acordado. Si origen y destino coinciden, no hace nada.
   *  El horario se toma del turno destino; la sección pasa a ser la de la
   *  columna destino. Usa los datos del evento CDK (previousContainer.data +
   *  item.data) como fuente principal, con dragData como respaldo. */
  onWorkerDrop(destDay: DayPlan, destSlot: string, destSection: string, e: CdkDragDrop<any>): void {
    this.dropHover.set(null);
    // No se puede soltar a nadie en un día de cierre (no se trabaja).
    if (this.isClosedDay(destDay.date)) return;
    // Ni en una sección que ese día no abre (pescadería los lunes). El
    // cdkDropListDisabled del template ya lo impide; esto cubre la vía de
    // datos, para que ninguna forma de asignar se salte la regla.
    if (this.isSectionClosedToday(destSection, destDay.date)) return;

    // Origen: preferir los datos del contenedor de origen del evento CDK.
    const origin = (e?.previousContainer?.data as any) || null;
    const assignment: ShiftAssignment = (e?.item?.data as ShiftAssignment) || this.dragData?.assignment!;
    const originDay: DayPlan = origin?.day ?? this.dragData?.day!;
    const originSlot: string = origin?.slot ?? this.dragData?.slotCode!;
    const originSection: string = origin?.section ?? this.dragData?.section ?? '';
    this.dragData = null;

    if (!assignment || !originDay || !originSlot) return;

    // Misma celda (mismo día+turno+sección): no hacer nada.
    if (originDay.date === destDay.date && originSlot === destSlot
        && this.normalizeSection(originSection) === this.normalizeSection(destSection)) return;

    const wid = assignment.workerId;
    const originSecN = this.normalizeSection(originSection);
    const destSecN = this.normalizeSection(destSection);

    // IMPORTANTE: diferir la mutación del plan a un microtask. Si mutamos el
    // plan aquí (síncrono), Angular re-renderiza y DESTRUYE el elemento que
    // el CDK todavía está restaurando en su limpieza → crash
    // "Cannot read properties of null (reading 'style')". Esperando al
    // siguiente tick, el CDK termina su cleanup antes.
    Promise.resolve().then(() => {
      // MOVER = una sola posición. El worker sale de la sección de ORIGEN y
      // pasa a existir SOLO en la sección de DESTINO (no se acumulan areas).
      //
      // 1) QUITAR del origen: elimino la asignación del worker que cubre la
      //    sección de origen. Si esa asignación cubría también OTRAS secciones
      //    (areas múltiples), le quito solo la de origen y la conservo para
      //    las demás; si era su única sección, desaparece del slot origen.
      const isSameSlot = originDay.date === destDay.date && originSlot === destSlot;
      let originList = this.getAssignments(originDay, originSlot);
      const originKept: ShiftAssignment[] = [];
      for (const a of originList) {
        if (a.workerId !== wid) { originKept.push(a); continue; }
        const areasN = (a.areas || []).map(x => this.normalizeSection(x));
        const matchesOrigin = areasN.length === 0 || areasN.includes(originSecN);
        if (!matchesOrigin) { originKept.push(a); continue; }
        const restAreas = (a.areas || []).filter(x => this.normalizeSection(x) !== originSecN);
        if (restAreas.length > 0) originKept.push({ ...a, areas: restAreas });
      }

      // 2) PONER en el destino con areas = [destSection] ÚNICAMENTE. Antes,
      //    para evitar que el worker quede en dos filas del mismo slot,
      //    elimino cualquier asignación previa suya que cubra la sección
      //    destino. (Si mismo slot, partimos de originKept.)
      const destSlotDef = this.shiftSlots().find(s => s.code === destSlot);
      const attrs = (destSlotDef?.attributes as any) || {};
      let destBase = isSameSlot ? originKept : this.getAssignments(destDay, destSlot);
      // quitar del destino cualquier resto del mismo worker en la sección destino
      destBase = destBase.filter(a => {
        if (a.workerId !== wid) return true;
        const areasN = (a.areas || []).map(x => this.normalizeSection(x));
        return !(areasN.length === 0 || areasN.includes(destSecN));
      });
      const moved: ShiftAssignment = {
        workerId: assignment.workerId,
        workerName: assignment.workerName,
        start: attrs.start_time || assignment.start,
        end: attrs.end_time || assignment.end,
        areas: [destSection],
      };

      if (isSameSlot) {
        // Mismo día+turno: una sola escritura con el resultado final.
        this.patchDay(destDay, destSlot, [...destBase, moved]);
        this.markDirty(destDay.date, destSlot);
      } else {
        this.patchDay(originDay, originSlot, originKept);
        this.markDirty(originDay.date, originSlot);
        this.patchDay(destDay, destSlot, [...destBase, moved]);
        this.markDirty(destDay.date, destSlot);
      }

      this.validatePlan();
    });
  }

  /** Quita UN trabajador concreto de la celda (opción "Borrar" del dropdown
   *  que aparece al clicar un slot lleno, Figma 2435:18950). A diferencia de
   *  clearCell, solo elimina esa asignación, no toda la celda. */
  removeWorkerFromCell(day: DayPlan, slotCode: string, assignment: ShiftAssignment): void {
    const kept = this.getAssignments(day, slotCode).filter(a => a !== assignment);
    this.patchDay(day, slotCode, kept);
    this.markDirty(day.date, slotCode);
    this.validatePlan();
    this.openWorkerMenu.set(null);
  }

  /** Sustituye UN trabajador por otro en la misma celda/slot (mantiene el
   *  horario del turno). Opción "sustitución" del dropdown de slot lleno. */
  replaceWorkerInCell(day: DayPlan, slotCode: string, sectionName: string,
                      oldAssignment: ShiftAssignment, newWorker: Worker): void {
    const list = this.getAssignments(day, slotCode).map(a =>
      a === oldAssignment
        ? { ...a, workerId: newWorker.id, workerName: newWorker.name }
        : a
    );
    this.patchDay(day, slotCode, list);
    this.markDirty(day.date, slotCode);
    this.validatePlan();
    this.openWorkerMenu.set(null);
  }

  /** Borra todas las asignaciones de la celda [sección × día×turno]
   *  (opción "Borrar" del dropdown, Figma). */
  clearCell(day: DayPlan, slotCode: string, sectionName: string): void {
    const toRemove = new Set(
      this.cellAssignments(day, slotCode, sectionName).map(a => a.workerId)
    );
    const kept = this.getAssignments(day, slotCode).filter(a => !toRemove.has(a.workerId));
    this.patchDay(day, slotCode, kept);
    this.markDirty(day.date, slotCode);
    this.validatePlan();
    this.openPicker.set(null);
  }

  /** Reparte los grupos de horario de una celda en N sub-columnas
   *  (2 para Caja/Pescadería, 1 el resto), como Figma. */
  cellColumns(day: DayPlan, slotCode: string, sectionName: string): {
    start: string; end: string; count: number; label: string;
    tooltip: string; assignments: ShiftAssignment[];
  }[][] {
    const slots = this.cellSlots(day, slotCode, sectionName);
    const nCols = this.isWideSection(sectionName) ? 2 : 1;
    const cols: any[][] = Array.from({ length: nCols }, () => []);
    slots.forEach((s, i) => cols[i % nCols].push(s));
    return cols;
  }

  /** ¿La celda [sección × día×turno] está vacía en modo VISTA (sin ninguna
   *  asignación con trabajador)? Sirve para mostrar, en el empty state, el
   *  horario base del turno como referencia (Figma View mode 2434:19080). */
  cellViewEmpty(day: DayPlan, slotCode: string, sectionName: string): boolean {
    return this.cellSlots(day, slotCode, sectionName).length === 0;
  }

  /** Normaliza un texto para comparar secciones (sin acentos, minúsculas). */
  private normalizeSection(s: string): string {
    return (s || '')
      .toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '')
      .trim();
  }

  /** Asignaciones de un día+turno cuya sección (areas[]) coincide con la
   *  columna. Matching tolerante a acentos/mayúsculas. Si la asignación no
   *  tiene sección, cae en la PRIMERA columna para no perder el dato. */
  cellAssignments(day: DayPlan, slotCode: string, sectionName: string): ShiftAssignment[] {
    const target = this.normalizeSection(sectionName);
    const sections = this.planSections().map(s => this.normalizeSection(s.name));
    const isFirst = sections[0] === target;
    return this.getAssignments(day, slotCode).filter(a => {
      if (!a.workerId || a.workerId <= 0) return false;
      const areas = (a.areas || []).map(x => this.normalizeSection(x));
      if (areas.length === 0) return isFirst; // sin sección → primera columna
      return areas.some(ar => ar === target);
    });
  }

  /** Horarios AGRUPADOS de una celda [sección × día×turno] para la vista
   *  tipo Figma: en vez de un chip por trabajador, agrupa por rango
   *  horario y cuenta ("2x 09:30-13:00"). Ordenados por hora de inicio.
   *  Cada entrada conserva las asignaciones que agrupa (para editar). */
  cellSlots(day: DayPlan, slotCode: string, sectionName: string): {
    start: string; end: string; count: number; label: string;
    tooltip: string; assignments: ShiftAssignment[];
  }[] {
    const list = this.cellAssignments(day, slotCode, sectionName);
    const groups = new Map<string, ShiftAssignment[]>();
    for (const a of list) {
      const key = `${a.start}-${a.end}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(a);
    }
    return Array.from(groups.values())
      .map(g => {
        const first = g[0];
        return {
          start: first.start,
          end: first.end,
          count: g.length,
          label: `${first.start} - ${first.end}`,
          tooltip: g.map(x => x.workerName).join('\n'),
          assignments: g,
        };
      })
      .sort((a, b) => (a.start || '').localeCompare(b.start || ''));
  }

  /** Igual que cellAssignments pero SIN filtrar los slots vacíos
   *  (workerId 0). Modo edición: incluye los slots de tiempo por cubrir. */
  cellEditAssignments(day: DayPlan, slotCode: string, sectionName: string): ShiftAssignment[] {
    const target = this.normalizeSection(sectionName);
    const sections = this.planSections().map(s => this.normalizeSection(s.name));
    const isFirst = sections[0] === target;
    return this.getAssignments(day, slotCode).filter(a => {
      const areas = (a.areas || []).map(x => this.normalizeSection(x));
      if (areas.length === 0) return isFirst; // sin sección → primera columna
      return areas.some(ar => ar === target);
    });
  }

  /** Items INDIVIDUALES de una celda en modo edición, repartidos en N
   *  sub-columnas (2 para Caja/Pescadería, 1 el resto). Cada item indica
   *  si es un empleado (nombre) o un slot de tiempo por cubrir (horario).
   *  Figma 2435:18950. */
  cellEditColumns(day: DayPlan, slotCode: string, sectionName: string): {
    filled: boolean; label: string; assignment: ShiftAssignment;
  }[][] {
    const list = this.cellEditAssignments(day, slotCode, sectionName).map(a => ({
      filled: !this.isIncomplete(a),
      label: this.isIncomplete(a) ? `${a.start} - ${a.end}` : a.workerName,
      assignment: a,
    }));
    const nCols = this.isWideSection(sectionName) ? 2 : 1;
    const cols: typeof list[] = Array.from({ length: nCols }, () => []);
    list.forEach((it, i) => cols[i % nCols].push(it));
    return cols;
  }

  /** Trabajadores en descanso ese día (para la columna Ausencias). */
  /** Trabajadores para la columna AUSENCIAS: SOLO ausencias reales (bajas de
   *  /absences que cubren ese día). Los descansos (día libre) NO van aquí —
   *  antes se mezclaban en day.rest y saturaban la columna. */
  cellRest(day: DayPlan): number[] {
    // Días de cierre (domingo/festivo): negocio cerrado → sin ausencias.
    if (this.isClosedDay(day.date)) return [];
    // La columna Ausencias se calcula DIRECTAMENTE de las ausencias aprobadas
    // que cubren el día, NO de day.rest. Antes dependía de day.rest, así que una
    // baja aprobada DESPUÉS de generar/guardar el plan no aparecía (el worker no
    // estaba en rest). Ahora cualquier ausencia aprobada (incl. indefinidas) se
    // muestra el día que corresponde. Se deduplica por trabajador.
    const ids = new Set<number>();
    for (const a of this.approvedAbsences()) {
      if (a.worker > 0 && this.isAbsentOn(a.worker, day.date)) ids.add(a.worker);
    }
    return Array.from(ids);
  }

  /** Etiqueta corta del turno para la columna TURNOS (p.ej. "Mañana"). */
  slotLabel(slot: any): string {
    return slot?.label ?? '';
  }

  /** Horario por defecto del turno ("07:45 - 14:45") para el slot vacío
   *  del modo edición (Figma empty state: slots por turno). Recorta los
   *  segundos ("07:45:00" → "07:45"). */
  slotTimeLabel(slot: any): string {
    const attrs = (slot?.attributes as any) || {};
    const trim = (t: string) => (t || '').split(':').slice(0, 2).join(':');
    const s = trim(attrs.start_time), e = trim(attrs.end_time);
    return s && e ? `${s} - ${e}` : '';
  }

  /** ¿La celda [sección × día×turno] está vacía en modo edición? */
  cellEditEmpty(day: DayPlan, slotCode: string, sectionName: string): boolean {
    return this.cellEditAssignments(day, slotCode, sectionName).length === 0;
  }

  /** Nº de vacantes por cubrir en la semana visible (chip del modo edición,
   *  Figma 2443:23450 "Hay N vacantes por cubrir").
   *
   *  El modelo NO define un "nº de trabajadores requeridos" por slot (Shift/
   *  Area no lo tienen), así que se cuenta cada slot de horario mostrado SIN
   *  empleado asignado: los items incompletos de cada celda y, cuando una
   *  celda está totalmente vacía, el propio slot de turno que hay que cubrir. */
  /** Avisos "de datos" de la última generación que NO son violaciones de
   *  restricción (p.ej. «Turno "Sábado Tarde" tiene 0 trabajadores»). Estos
   *  avisos solo viven en el resultado del generador (no en day.violations),
   *  así que se muestran aparte en un banner del modo edición para que no se
   *  pierdan al cerrar el diálogo. Se filtran los resúmenes ("N errores/avisos
   *  en el plan", ya cubiertos por sus chips) y el "sin problemas". Solo si el
   *  resultado corresponde a la semana + ámbito que se está viendo ahora. */
  getGenerationNotices(): string[] {
    const data = this.lastGenerationResult();
    if (!data) return [];
    if (data.startDate !== this.startDate() || data.scopeId !== this.selectedScopeId()) return [];
    return (data.warnings ?? []).filter((w: string) =>
      !w.includes('sin problemas') &&
      !/\d+\s+(errores?|avisos?)\s+en el plan/i.test(w)
    );
  }

  /** Reabre el diálogo con el detalle de los avisos de generación. */
  showGenerationNoticesDetail(): void {
    const notices = this.getGenerationNotices();
    if (!notices.length) return;
    this.generationWarningsTitle = notices.length === 1 ? '1 aviso de la generación' : `${notices.length} avisos de la generación`;
    this.generationWarningsMessage = notices
      .map(w => `• ${w.replace(/\n/g, '<br>&nbsp;&nbsp;')}`)
      .join('<br><br>');
    this.generationWarningsMode = 'warning';
    this.showGenerationWarnings = true;
  }

  /** Cosas a revisar que NO bloquean guardar: vacantes de la parrilla,
   *  secciones sin cubrir toda la semana y avisos de la generación. Los avisos
   *  del MOTOR de restricciones no entran: se ven en la celda del trabajador. */
  getIssueCount(): number {
    // Cuenta las MISMAS filas que muestra el modal, para que el número del chip
    // y los contadores de los bloques cuadren. Antes sumaba
    // `structuralGaps().length` (combinaciones sección×turno: 15) mientras el
    // modal las agrupaba por sección (6), así que no coincidían.
    return this.vacancyRows().length
      + this.structuralRows().length
      + this.getGenerationNotices().length;
  }

  /** Etiqueta del chip: un único número. Todo lo que hay que revisar y no
   *  bloquea el guardado cuenta igual; el desglose está dentro del modal. */
  /**
   * Al abrir una tienda cuyas fichas se han editado DESPUÉS de guardar el plan,
   * se regenera la semana sola: el plan es un cálculo hecho con datos viejos y
   * cambiar el turno de alguien no lo recalcula por sí solo.
   *
   * Se abstiene en tres casos, porque regenerar reasigna la semana entera y
   * perdería trabajo del usuario:
   *   - hay un BORRADOR sin guardar (generado y no confirmado)
   *   - hay cambios manuales sin guardar
   *   - ya se está generando (evita dispararlo dos veces)
   *
   * También se abstiene si la semana está vacía: no hay nada que rehacer, y
   * generar sin que nadie lo pida convertiría "abrir una tienda" en "planificar
   * una tienda".
   */
  /**
   * "Casas Capablo, Rosana" / "Casas Capablo, Rosana y 2 más" / "algún
   * empleado" si el back no pudo dar nombres (fichas sin nombre).
   */
  private staleWorkerLabel(): string {
    const quien = this.staleWorkers();
    if (!quien.length) return 'algún empleado';
    return quien.length === 1 ? quien[0] : `${quien[0]} y ${quien.length - 1} más`;
  }

  private applyStaleIfNeeded(): void {
    if (!this.planStale()) return;
    if (this.isCurrentScopeGenerating() || this.generatingAll()) return;

    // Con borrador o cambios a mano NO se regenera (se perderia ese trabajo),
    // pero hay que DECIRLO: antes se salia en silencio y el usuario se quedaba
    // mirando un plan calculado con fichas viejas sin ninguna pista. El chip
    // ambar de "desactualizado" sigue visible para regenerar cuando quiera.
    if (this.hasDraft() || this.hasUnsavedChanges()) {
      this.snackBar.open(
        `Has cambiado la ficha de ${this.staleWorkerLabel()}, pero hay cambios sin guardar: guarda o cancela y se recalculará.`,
        'OK', { duration: 6000 });
      return;
    }

    // Semana vacia: no se regenera sola (abrir una tienda no deberia
    // planificarla), pero tampoco se calla, que era el caso mas confuso: sin
    // asignaciones el chip ambar apenas se ve y no habia ningun aviso.
    if (this.getTotalAssignments() === 0) {
      this.snackBar.open(
        `Has cambiado la ficha de ${this.staleWorkerLabel()}. Esta semana está vacía: pulsa Generar para planificarla.`,
        'OK', { duration: 6000 });
      return;
    }

    this.snackBar.open(
      `Has cambiado la ficha de ${this.staleWorkerLabel()}: recalculando la planificación…`,
      '', { duration: 4000 });
    // El resultado se guarda solo al acabar de validar: este recálculo no lo ha
    // pedido el usuario, así que dejarlo en modo edición le obligaba a pulsar
    // Guardar en cada visita para salir del aviso.
    this.autoSaveAfterValidation = { startDate: this.startDate(), scopeId: this.selectedScopeId() };
    this.doGenerate(true);
  }

  getIssueLabel(): string {
    const n = this.getIssueCount();
    return `${n} ${n === 1 ? 'aviso' : 'avisos'} a solucionar`;
  }

  /**
   * Detalle del chip en LISTA PLANA: una línea por caso, en dos bloques según
   * lo que se puede hacer. El detalle largo (causa y sugerencia) va en el
   * tooltip de la fila, para no convertir el modal en un muro de texto.
   */
  showIssuesDetail(): void {
    const bloques: string[] = [];

    // 1) Lo que SÍ se puede arreglar: vacantes con alguien que pueda cubrirlas.
    //    Las que no tienen a nadie disponible NO van aquí (decían "vacante a
    //    poder cubrir" y debajo "no hay nadie que pueda cubrirlo"): se agrupan
    //    abajo con el resto de falta de plantilla.
    const todas = this.vacancyRows();
    const vac = todas.filter(r => r.cubrible);
    const sinNadie = todas.filter(r => !r.cubrible);
    if (vac.length) {
      bloques.push(
        `<div class="dlg-group">` +
        `<div class="dlg-sub__title">` +
        `${vac.length === 1 ? 'Vacante a poder cubrir' : 'Vacantes a poder cubrir'}</div>` +
        // La solución va VISIBLE, no en el tooltip: es el bloque accionable, así
        // que lo útil es leer qué hacer sin tener que pasar el ratón.
        vac.map(r =>
          `<div class="dlg-item">` +
          `<div class="dlg-row">` +
          `<span class="dlg-row__key">${r.what}</span>` +
          `<span class="dlg-row__val">${r.when}</span></div>` +
          `<div class="dlg-item__body">${r.tip}</div></div>`).join('') +
        `</div>`
      );
    }

    // 2) Lo que NO: falta plantilla o falta darle ese turno a alguien.
    const gaps = this.structuralRows();
    const notices = this.getGenerationNotices();
    if (gaps.length || notices.length || sinNadie.length) {
      bloques.push(
        `<div class="dlg-group">` +
        `<div class="dlg-sub__title">Falta plantilla</div>` +
        `<div class="dlg-sub__note">no hay nadie disponible a quien asignar</div>` +
        // Días concretos sin nadie que pueda cubrirlos (antes salían arriba como
        // "a poder cubrir" contradiciéndose con su propio texto).
        sinNadie.map(r =>
          `<div class="dlg-row" title="${r.tip}">` +
          `<span class="dlg-row__key">${r.what}</span>` +
          `<span class="dlg-row__val">${r.when}</span></div>`).join('') +
        gaps.map(r =>
          `<div class="dlg-row" title="${r.tip}">` +
          `<span class="dlg-row__key">${r.shift}</span>` +
          `<span class="dlg-row__val">${r.sections}</span></div>`).join('') +
        notices.map(n =>
          `<div class="dlg-row"><span class="dlg-row__val">` +
          `${n.replace(/\n/g, ' ')}</span></div>`).join('') +
        `</div>`
      );
    }

    if (!bloques.length) return;
    this.generationWarningsMode = 'warning';
    // Sin título: el chip que abre esta modal ya dice "N avisos a solucionar", y
    // cada bloque lleva el suyo. Repetirlo arriba no aportaba nada.
    this.generationWarningsTitle = '';
    this.generationWarningsMessage = bloques.join('');
    this.showGenerationWarnings = true;
  }

  /** Detalle de las vacantes como HTML, sin abrir nada. Lo usan tanto el
   *  diálogo propio como el unificado de "problemas a solucionar". */
  /**
   * Vacantes como FILAS planas: {qué, cuándo, tooltip}. Una por combinación
   * sección×turno, agrupando los días. El "por qué" y la sugerencia van en el
   * tooltip para que el modal quepa de un vistazo.
   */
  private vacancyRows(): {
    what: string; when: string; tip: string; cubrible: boolean;
  }[] {
    // Sin plan no hay vacantes que contar (`hasStaffFor` no tiene referencia:
    // se basa en quién aparece en el plan de la semana).
    if (this.getTotalAssignments() === 0) return [];
    const porClave = new Map<string, {
      dias: string[]; section: string; slot: string; tip: string; cubrible: boolean;
    }>();
    for (const day of this.plan()) {
      if (this.isDayClosed(day.date)) continue;
      for (const slot of this.slotsForDay(day)) {
        if (!this.slotTimeLabel(slot)) continue;
        for (const section of this.planSections()) {
          const assigns = this.cellEditAssignments(day, slot.code, section.name);
          const huecos = assigns.filter(a => this.isIncomplete(a)).length;
          const vacia = assigns.length === 0;
          // Sección que ese día de la semana NO abre (p.ej. pescadería los
          // lunes): no es un hueco que cubrir, es que no toca. No se cuenta.
          if (vacia && this.sectionClosedOnWeekday(section.name, day.date)) continue;
          if (vacia && !this.hasStaffFor(section.name, slot.code)) continue;
          if (!vacia && !huecos) continue;

          const slotLabel = slot.label ?? slot.code;
          const k = `${section.name}|${slotLabel}`;
          if (!porClave.has(k)) {
            const libres = this.staffAvailableFor(day, slot.code, section.name);
            // Tooltip: quién puede entrar, o la causa si no hay nadie libre.
            const causa = libres.length
              ? `Puedes asignar a: ${libres.slice(0, 5).join(', ')}`
              : this.gapPlainCause(section.name, slot.code, slotLabel, day);
            // ¿Hay alguien que REALMENTE pueda cubrirlo? Es lo que decide en qué
            // bloque va la fila. Sin esto salía "Vacante a poder cubrir" con el
            // texto "no hay nadie que pueda cubrirlo" debajo: los dos criterios
            // no eran el mismo.
            // Cuenta como cubrible también si el único freno es el descanso
            // oficial: eso el usuario lo puede cambiar, así que la fila tiene
            // solución y va al bloque accionable.
            const cubrible = this.candidatesForGap(
                section.name, slot.code, day.date).length > 0
              || this.candidatesBlockedOnlyByRest(
                section.name, slot.code, day.date).length > 0;
            porClave.set(k, {
              dias: [], section: section.name, slot: slotLabel,
              tip: causa, cubrible,
            });
          }
          porClave.get(k)!.dias.push(this.formatDayLabel(day).split(' ')[1] ?? '');
        }
      }
    }
    return Array.from(porClave.values())
      .sort((a, b) => a.section.localeCompare(b.section))
      .map(v => ({
        what: `${v.section} · ${v.slot}`,
        when: v.dias.length <= 3
          ? v.dias.join(', ')
          : `${v.dias.length} días`,
        tip: v.tip,
        cubrible: v.cubrible,
      }));
  }

  /** Causa en texto plano (sin HTML), para el tooltip de una fila. */
  private gapPlainCause(section: string, slotCode: string, slotLabel: string, day: DayPlan): string {
    const html = this.gapCauses([{ section, slotCode, slotLabel, day }])[0] ?? '';
    const plano = html
      .replace(/<br\s*\/?>/g, ' ')
      .replace(/<[^>]+>/g, '')
      .replace(/&nbsp;/g, ' ')
      .replace(/\s+/g, ' ')
      .replace(/"/g, '')
      .trim();
    // Solo la parte accionable: el párrafo completo explica también el porqué,
    // y en una lista plana eso es demasiado. Si no hay sugerencia, se deja el
    // texto tal cual (mejor algo que nada).
    const i = plano.indexOf('Sugerencia:');
    return i >= 0 ? plano.slice(i + 'Sugerencia:'.length).trim() : plano;
  }

  /**
   * Secciones sin cubrir agrupadas POR TURNO: {turno, secciones, tooltip}.
   *
   * Agrupar por sección repetía "Sáb. Tarde" en cada fila (7 veces en T16).
   * Por turno queda "Sáb. Tarde → Caja, Carne, Charcutería…": una línea por
   * turno y se ve de un golpe qué franja es la problemática.
   */
  private structuralRows(): { shift: string; sections: string; tip: string }[] {
    const porTurno = new Map<string, { secciones: string[]; sinPersonal: string[] }>();
    for (const g of this.structuralGaps()) {
      const [sec, turno] = g.split('·').map(s => s.trim());
      if (!turno) continue;
      const clave = turno.replace(/^Sábado /, 'Sáb. ');
      if (!porTurno.has(clave)) porTurno.set(clave, { secciones: [], sinPersonal: [] });
      const e = porTurno.get(clave)!;
      e.secciones.push(sec);
      if (!this.staffOfSection(sec).length) e.sinPersonal.push(sec);
    }
    // Orden de turnos tal como salen en la parrilla, no alfabético.
    const orden = this.shiftSlots().map(s => (s.label ?? s.code).replace(/^Sábado /, 'Sáb. '));
    return Array.from(porTurno.entries())
      .sort(([a], [b]) => {
        const ia = orden.indexOf(a), ib = orden.indexOf(b);
        return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
      })
      .map(([shift, e]) => ({
        shift,
        sections: e.secciones.sort((a, b) => a.localeCompare(b)).join(', '),
        tip: e.sinPersonal.length
          ? `Sin personal en la tienda: ${e.sinPersonal.join(', ')}. `
            + `El resto sí tiene gente, pero ninguna trabaja ese turno.`
          : `Hay personal de esas secciones, pero ninguna trabaja ese turno: `
            + `se arregla en su ficha (turno base o alternativo).`,
      }));
  }


  /**
   * Explica POR QUÉ una sección se queda sin nadie en un turno.
   *
   * La causa más habitual (y la menos evidente) es que TODO el personal de esa
   * sección en la tienda tiene la misma configuración de rotación: rotan juntos,
   * así que en semanas alternas se van todos al mismo turno y el otro queda
   * vacío. El generador no puede arreglarlo — no hay a quién asignar —, pero se
   * resuelve invirtiendo `turno base`/`turno alternativo` en una de las personas.
   */
  private gapCauses(
    huecos: { section: string; slotCode: string; slotLabel: string; day: DayPlan }[],
  ): string[] {
    const out: string[] = [];
    const vistos = new Set<string>();
    const shiftKey = this.shiftFieldKey();
    for (const h of huecos) {
      if (vistos.has(h.section)) continue;   // una explicación por sección
      vistos.add(h.section);

      const dela = this.staffOfSection(h.section);
      if (!dela.length) continue;

      // ¿Rotan todos igual? (mismo turno base y mismo alternativo)
      const firmas = new Set(dela.map(w => {
        const cd = (w.custom_data ?? {}) as Record<string, unknown>;
        const base = shiftKey ? String(cd[shiftKey] ?? '') : '';
        const alt = Object.keys(cd)
          .filter(k => k !== shiftKey && /alternativ/i.test(k))
          .map(k => String(cd[k] ?? '')).find(Boolean) ?? '';
        return `${base}|${alt}`;
      }));
      // Solo los APELLIDOS: el nombre completo viene como "Apellidos, Nombre" y
      // al unir varios con comas se leían como el doble de personas
      // ("Hinarejos Radigales, Maria Angeles, Segura Muñoz, Mercedes" parecían 4).
      // Se separan con " y " para que quede claro cuántas son.
      const apellidos = dela.map(w => this.shortSurname(w.name));
      const nombres = apellidos.length <= 3
        ? apellidos.slice(0, -1).join(', ') + (apellidos.length > 1 ? ' y ' : '') + apellidos.slice(-1)
        : `${apellidos.slice(0, 3).join(', ')} y ${apellidos.length - 3} más`;

      if (firmas.size === 1 && dela.length > 0) {
        // El turno donde SÍ están, para que la explicación sea concreta.
        const otro = this.shiftSlots()
          .filter(s => s.code !== h.slotCode)
          .find(s => this.plan().some(d =>
            this.getAssignments(d, s.code).some(a =>
              dela.some(w => w.id === a.workerId))));
        const otroTurno = otro ? (otro.label ?? otro.code) : 'el otro turno';
        const unaSola = dela.length === 1;
        // Sin repetir la sección: ya está en la cabecera de la ficha.
        out.push(
          `<div class="dlg-item__body">` +
          `${dela.length === 1 ? '1 persona' : `${dela.length} personas`} en plantilla: ` +
          `${nombres}.<br>` +
          (unaSola
            ? `Es la única, así que no puede cubrir los dos turnos.`
            : `Las ${dela.length} rotan igual y cambian de turno el mismo día: esta ` +
              `semana están en ${otroTurno.toLowerCase()}.`) +
          `<br><strong>Sugerencia:</strong> ` +
          (unaSola
            // Antes decía "asignar X a otra persona" sin comprobar que esa otra
            // persona existiera: en una tienda con una sola pescadera mandaba al
            // usuario a hacer algo imposible. Ahora se busca de verdad.
            ? this.coverSuggestion(h)
            // Hay que INTERCAMBIAR base y alternativo de una de ellas, no fijarlos
            // al turno del hueco: su base ya es el turno que falta (por eso la
            // semana que viene sí lo cubren). Lo que hace falta es que una vaya
            // desfasada respecto a la otra.
            : this.swapSuggestion(dela[dela.length - 1])) +
          `</div>`
        );
      } else {
        // Motivo EXACTO por persona en vez de "en otro turno, de descanso o
        // ausentes": el dato lo tenemos, así que se desglosa.
        const desglose = this.unavailableBreakdown(h.day, h.slotCode, h.section)
          .map(x => `<div class="dlg-reason"><span class="dlg-reason__why">${x.motivo}:</span> ` +
                    `${x.quienes.join(', ')}</div>`).join('');
        out.push(
          `<div class="dlg-item__body">${dela.length} en plantilla, ninguna libre:</div>` +
          desglose
        );
      }
    }
    return out;
  }

  /**
   * Por qué NO está disponible cada persona de la sección ese día, con el motivo
   * exacto en vez del genérico "en otro turno, de descanso o ausentes".
   * Devuelve {motivo: [nombres]} con los motivos que de verdad aplican.
   */
  private unavailableBreakdown(
    day: DayPlan, slotCode: string, sectionName: string,
  ): { motivo: string; quienes: string[] }[] {
    const enOtroTurno = new Map<number, string>();   // wid → etiqueta del turno
    for (const s of this.slotsForDay(day)) {
      for (const a of this.getAssignments(day, s.code)) {
        if (a.workerId > 0 && s.code !== slotCode) {
          enOtroTurno.set(a.workerId, s.label ?? s.code);
        }
      }
    }
    const descansan = new Set<number>(day.rest ?? []);
    const porMotivo = new Map<string, string[]>();
    const add = (motivo: string, nombre: string) => {
      if (!porMotivo.has(motivo)) porMotivo.set(motivo, []);
      porMotivo.get(motivo)!.push(nombre);
    };
    for (const w of this.eligibleStaffFor(sectionName, slotCode)) {
      const nombre = this.shortSurname(w.name);
      // Orden de prioridad: la ausencia manda sobre el descanso, y el descanso
      // sobre "asignada en otro turno" (que es consecuencia, no causa).
      if (this.isAbsentOn(w.id, day.date)) add('Ausente', nombre);
      else if (enOtroTurno.has(w.id)) add(`En turno de ${enOtroTurno.get(w.id)!.toLowerCase()}`, nombre);
      else if (descansan.has(w.id)) add('De descanso', nombre);
      else add('Sin turno ese día', nombre);
    }
    return Array.from(porMotivo.entries())
      .map(([motivo, quienes]) => ({ motivo, quienes }))
      .sort((a, b) => b.quienes.length - a.quienes.length);
  }

  /** Nombres de quienes podrían cubrir esa celda: de la sección, con ese turno
   *  base, y que ese día no estén ya asignados, de descanso ni ausentes. */
  private staffAvailableFor(day: DayPlan, slotCode: string, sectionName: string): string[] {
    const ocupados = new Set<number>();
    for (const s of this.slotsForDay(day)) {
      for (const a of this.getAssignments(day, s.code)) {
        if (a.workerId > 0) ocupados.add(a.workerId);
      }
    }
    const descansan = new Set<number>(day.rest ?? []);
    return this.eligibleStaffFor(sectionName, slotCode)
      .filter(w => !ocupados.has(w.id) && !descansan.has(w.id)
        && !this.isAbsentOn(w.id, day.date))
      .map(w => this.formatWorkerName(w.name));
  }

  /** Etiqueta corta del día para los diálogos ("Lunes 27/07"). */
  private formatDayLabel(day: DayPlan): string {
    const d = new Date(day.date + 'T00:00:00');
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    return `${day.dayName || ''} ${dd}/${mm}`.trim();
  }

  /** Secciones que NO tienen a nadie capaz de cubrir un turno concreto.
   *
   *  No son vacantes: por muchos ajustes que se hagan, esas celdas no se
   *  pueden rellenar porque no existe personal de esa sección con ese turno
   *  base. Es información para RRHH (falta plantilla), no para el planificador.
   *  Devuelve una lista tipo ["Repostería · Mañana", "Frutería · Tarde"]. */
  structuralGaps(): string[] {
    // Sin plan generado no se puede diagnosticar nada: `eligibleStaffFor()` toma
    // como referencia quién aparece en el plan de la semana, así que en una
    // tienda todavía sin planificar NADIE sale elegible y TODAS las secciones se
    // reportaban como "sin personal". Era el aviso que se quedaba pegado al
    // cambiar de tienda después de generar solo una.
    if (this.getTotalAssignments() === 0) return [];
    const out: string[] = [];
    const vistos = new Set<string>();
    for (const day of this.plan()) {
      if (this.isDayClosed(day.date)) continue;
      for (const slot of this.slotsForDay(day)) {
        if (!this.slotTimeLabel(slot)) continue;
        for (const section of this.planSections()) {
          const key = `${section.name}|${slot.code}`;
          if (vistos.has(key)) continue;
          vistos.add(key);
          if (this.cellEditAssignments(day, slot.code, section.name).length) continue;
          if (!this.hasStaffFor(section.name, slot.code)) {
            out.push(`${section.name} · ${slot.label ?? slot.code}`);
          }
        }
      }
    }
    return out.sort();
  }

  /** Personal de una sección que aparece en el plan de esta tienda. */
  private staffOfSection(sectionName: string): Worker[] {
    const target = this.normalizeSection(sectionName);
    const enPlan = new Set<number>();
    for (const d of this.plan()) {
      for (const s of this.shiftSlots()) {
        for (const a of this.getAssignments(d, s.code)) {
          if (a.workerId > 0) enPlan.add(a.workerId);
        }
      }
    }
    return this.workers().filter(w =>
      w.active && enPlan.has(w.id)
      && this.normalizeSection(this.workerPrimaryPill(w)) === target);
  }

  /** Solo los apellidos ("Apellidos, Nombre" → "Apellidos"), para listas legibles. */
  private shortSurname(name: string): string {
    const completo = this.formatWorkerName(name);
    return completo.includes(',') ? completo.split(',')[0].trim() : completo;
  }

  /** ¿Hay al menos un trabajador elegible de `sectionName` cuyo turno base sea
   *  `slotCode`? Determina si una celda vacía es una vacante cubrible o un
   *  hueco estructural de plantilla. Cacheado: se llama por cada celda. */
  private _staffForCache = new Map<string, boolean>();
  private hasStaffFor(sectionName: string, slotCode: string): boolean {
    const key = `${sectionName}|${slotCode}`;
    const hit = this._staffForCache.get(key);
    if (hit !== undefined) return hit;
    const ok = this.eligibleStaffFor(sectionName, slotCode).length > 0;
    this._staffForCache.set(key, ok);
    return ok;
  }

  /** Trabajadores que PUEDEN cubrir `sección × turno` en el ámbito actual.
   *
   *  La regla de elegibilidad por tienda vive en el backend (personal fijo de
   *  la tienda + común/ETT de su zona), y el front no la replica. Se usa como
   *  referencia quién aparece en el plan de ESTA semana: si alguien está
   *  asignado aquí, es elegible. Así no se ofrece a plantilla de otra tienda
   *  que el generador nunca podría colocar. */
  private eligibleStaffFor(sectionName: string, slotCode: string): Worker[] {
    const target = this.normalizeSection(sectionName);
    const shiftKey = this.shiftFieldKey();
    const enPlan = new Set<number>();
    for (const d of this.plan()) {
      for (const s of this.shiftSlots()) {
        for (const a of this.getAssignments(d, s.code)) {
          if (a.workerId > 0) enPlan.add(a.workerId);
        }
      }
    }
    // Turnos que esa persona puede hacer: su turno base y cualquier turno de
    // override (p.ej. 'turno_sabado'), porque las reglas de asignación la
    // reubican según el día. Sin eso, el sábado se contaba como descubierto
    // aunque en la parrilla estuviera cubierto.
    //
    // Ojo con el patrón: `turnos_max_semana` NO es un turno (es un número), y
    // con un /turno/i suelto se colaba como si lo fuera.
    const shiftValues = (w: Worker): string[] => {
      const cd = w.custom_data ?? {};
      const vals = Object.keys(cd)
        .filter(k => k === shiftKey || /^turno(_|$)/i.test(k))
        .map(k => String(cd[k] ?? ''))
        .filter(Boolean);
      return vals.length ? vals : [''];
    };

    return this.workers().filter(w =>
      w.active
      && enPlan.has(w.id)
      && this.normalizeSection(this.workerPrimaryPill(w)) === target
      // Sin campo de turno configurado no se puede afinar: se asume cubrible.
      && (!shiftKey || shiftValues(w).includes(String(slotCode)))
      && !this.isShiftBlockedFor(w, slotCode));
  }

  /**
   * Sugerencia de intercambio de turnos, dicha con los valores REALES de la
   * ficha en vez de "intercambiar el turno base y el alternativo".
   *
   * "Intercambiar" obliga al usuario a abrir la ficha para saber qué hay dentro.
   * Con los nombres de turno el cambio se entiende sin salir del aviso:
   *   en la ficha de Martinez Muñoz: turno base Mañana → Tarde
   *   y turno alternativo Tarde → Mañana.
   */
  private swapSuggestion(w: Worker): string {
    const quien = this.shortSurname(w.name);
    const cd = (w.custom_data ?? {}) as Record<string, unknown>;
    const shiftKey = this.shiftFieldKey();

    // Nombre del turno a partir del valor guardado en la ficha (un ID).
    const nombreTurno = (val: unknown): string => {
      const s = this.shiftSlots().find(x => String(x.code) === String(val ?? ''));
      return s ? String(s.label ?? s.code) : '';
    };

    const baseVal = shiftKey ? cd[shiftKey] : null;
    const altKey = Object.keys(cd).find(k => k !== shiftKey && /alternativ/i.test(k));
    const altVal = altKey ? cd[altKey] : null;
    const base = nombreTurno(baseVal);
    const alt = nombreTurno(altVal);

    // Sin poder resolver los nombres, se cae al texto genérico (mejor eso que
    // escribir "turno base  →  ").
    if (!base || !alt) {
      return `en la ficha de <strong>${quien}</strong>, intercambiar el turno ` +
        `base y el alternativo.`;
    }
    return `en la ficha de <strong>${quien}</strong>, poner turno base ` +
      `<strong>${alt}</strong> (ahora ${base}) y turno alternativo ` +
      `<strong>${base}</strong> (ahora ${alt}). Así deja de coincidir con el ` +
      `resto y una de las dos cubre siempre este turno.`;
  }

  /**
   * Sugerencia para un hueco de una sección con UNA sola persona: nombra a quien
   * puede cubrirlo de verdad, o dice claramente que no hay nadie.
   *
   * Nunca afirma que exista un sustituto sin haberlo comprobado.
   */
  private coverSuggestion(
    h: { section: string; slotCode: string; slotLabel: string; day: DayPlan },
  ): string {
    const cand = this.candidatesForGap(h.section, h.slotCode, h.day.date);
    if (!cand.length) {
      // ¿El ÚNICO impedimento es el descanso oficial? Entonces sí hay salida:
      // quitarle el descanso ese día (y dárselo en otro). Es decisión del
      // usuario, así que se ofrece como opción en vez de callarla.
      const porDescanso = this.candidatesBlockedOnlyByRest(
        h.section, h.slotCode, h.day.date);
      if (porDescanso.length) {
        const nombres = porDescanso.slice(0, 3).map(w => this.shortSurname(w.name));
        const lista = nombres.length <= 1 ? nombres[0]
          : nombres.slice(0, -1).join(', ') + ' o ' + nombres.slice(-1);
        const dia = this.formatDayLabel(h.day);
        return `<strong>${lista}</strong> podría cubrirlo, pero tiene el ` +
          `${dia} como día de descanso. Si le cambias el descanso a otro día, ` +
          `queda libre para este turno.`;
      }
      return `no hay nadie más en la tienda que pueda cubrir ` +
        `${h.section.toLowerCase()} en este turno: hace falta polivalencia o ` +
        `una persona más.`;
    }
    const nombres = cand.slice(0, 3).map(w => this.shortSurname(w.name));
    const lista = cand.length <= 3
      ? nombres.slice(0, -1).join(', ') + (nombres.length > 1 ? ' y ' : '') + nombres.slice(-1)
      : `${nombres.join(', ')} y ${cand.length - 3} más`;
    // El día es el PRIMERO del grupo (una fila puede abarcar varios): se dice
    // cuál es, porque quien está libre el lunes puede no estarlo el martes.
    const dia = this.formatDayLabel(h.day);
    // ¿Es la ÚNICA persona de esa sección en la tienda? Entonces conviene
    // decirlo: se cubre este hueco, pero la sección sigue dependiendo de una
    // sola persona (si falta, no hay recambio).
    const total = this.workers().filter(w =>
      w.active
      && this.workerBelongsToScope(w)
      && this.normalizeSection(this.workerPrimaryPill(w))
         === this.normalizeSection(h.section)).length;
    const aviso = (total === 1 && cand.length === 1)
      ? ` Es la única persona de ${h.section.toLowerCase()} en la tienda: ` +
        `cubre este día, pero la sección depende solo de ella.`
      : '';
    return `puedes asignar ${h.section.toLowerCase()} a ` +
      `<strong>${lista}</strong> (libre${cand.length > 1 ? 's' : ''} el ${dia} ` +
      `y con ese turno).${aviso}`;
  }

  /**
   * Quién podría cubrir el hueco si NO tuviera descanso oficial ese día.
   *
   * Cumple todo lo demás (tienda, sección, turno, no ausente, no libra por
   * ficha, no ocupado en otra tienda) y lo único que lo frena es el `rest` del
   * plan. A diferencia del resto de bloqueos, este lo puede cambiar el usuario:
   * mover el descanso a otro día. Por eso se ofrece como sugerencia.
   */
  private candidatesBlockedOnlyByRest(
    sectionName: string, slotCode: string, dateStr: string,
  ): Worker[] {
    const dia = this.plan().find(d => d.date === dateStr);
    const descansan = new Set<number>(
      (dia?.rest ?? []).map(x => Number(x)).filter(n => !isNaN(n)));
    if (!descansan.size) return [];
    // Se reutiliza el mismo filtro, pero SIN la condición de descanso: lo que
    // aparezca aquí y no en candidatesForGap está bloqueado solo por el rest.
    return this.candidatesForGap(sectionName, slotCode, dateStr, true)
      .filter(w => descansan.has(w.id));
  }

  /**
   * ¿Hay alguien que REALMENTE pueda cubrir la sección S en el turno T ese día?
   *
   * `staffOfSection` no sirve para esto: solo mira quien ya salió en el plan y
   * solo su sección PRINCIPAL, así que se sugería "asignar pescadería a otra
   * persona" en tiendas donde no había ninguna otra. Aquí se busca sobre TODA la
   * plantilla de la tienda y se descarta a quien no puede:
   *   - no es de esta tienda / inactiva
   *   - no tiene la sección (ni principal ni en polivalencia)
   *   - su ficha no contempla ese turno
   *   - una restricción de error le prohíbe ese turno
   *   - está ausente ese día
   *   - ya está asignada ese mismo día (no puede estar en dos sitios)
   *
   * Devuelve los candidatos reales (puede ser lista vacía). No comprueba el tope
   * de horas semanales ni las 17 restricciones del motor: por eso el texto habla
   * de "puedes probar con", no de una garantía.
   */
  private candidatesForGap(
    sectionName: string, slotCode: string, dateStr: string,
    ignorarDescanso = false,
  ): Worker[] {
    const target = this.normalizeSection(sectionName);
    const shiftKey = this.shiftFieldKey();

    // Ocupados ese día: en ESTA tienda (nadie dobla turno) y en CUALQUIER OTRA
    // (nadie está en dos tiendas a la vez). Lo segundo es lo que faltaba: los
    // volantes sin tienda propia se los queda la primera tienda que genera, y
    // aquí salían como libres.
    const ocupados = new Set<number>(this.busyElsewhere()[dateStr] ?? []);
    const dia = this.plan().find(d => d.date === dateStr);
    if (dia) {
      for (const s of this.shiftSlots()) {
        for (const a of this.getAssignments(dia, s.code)) {
          if (a.workerId > 0) ocupados.add(a.workerId);
        }
      }
    }

    // ¿Es SU sección? Solo la principal (prioridad 1).
    //
    // La polivalencia (secciones de prioridad 2+) NO cuenta: medido sobre los
    // planes guardados, el generador asigna 2.986 veces en la sección principal
    // y solo 19 en una secundaria. Aceptarlas producía sugerencias que el motor
    // nunca iba a aplicar — p.ej. Alonso Mata (Carne 1ª, Pescadería 2ª) salía
    // como candidata de pescadería en las 15 tiendas, y el motor la pone
    // siempre en Carne.
    const tieneSeccion = (w: Worker): boolean =>
      this.normalizeSection(this.workerPrimaryPill(w)) === target;

    // ¿Su ficha contempla este turno? Solo los campos que son REALMENTE turnos
    // (base, sábado, alternativo). `turnos_max_semana` casaría un /turno/ suelto
    // y su valor (un número o '') se colaría como si fuera un turno.
    const haceEsteTurno = (w: Worker): boolean => {
      if (!shiftKey) return true;   // sin campo configurado, no se puede afinar
      const cd = w.custom_data ?? {};
      const vals = Object.keys(cd)
        .filter(k => k === shiftKey || /^turno(_|$)/i.test(k))
        .map(k => String(cd[k] ?? ''))
        .filter(Boolean);
      return !vals.length || vals.includes(String(slotCode));
    };

    // DESCANSO OFICIAL de ese día (array `rest` del plan). El motor lo respeta
    // con una restricción de error ("No asignar trabajadores en día de descanso
    // oficial"), así que proponer a alguien que descansa era proponer algo que
    // el generador rechazaría.
    const descansan = new Set<number>(
      (dia?.rest ?? []).map(x => Number(x)).filter(n => !isNaN(n)));

    return this.workers().filter(w =>
      w.active
      && this.workerBelongsToScope(w)
      && tieneSeccion(w)
      && haceEsteTurno(w)
      && !this.isShiftBlockedFor(w, slotCode)
      && !this.isAbsentOn(w.id, dateStr)
      && !this.hasDayOffOn(w, dateStr)
      && (ignorarDescanso || !descansan.has(w.id))
      && !ocupados.has(w.id));
  }

  /**
   * ¿Esta sección NO abre este día de la semana?
   *
   * Caso real: pescadería no trabaja los lunes. No está configurado como cierre
   * ni como restricción — se deduce de las fichas: 29 de las 32 personas de
   * pescadería tienen `dias_libres: lunes`, y el generador las respeta.
   *
   * Se considera cerrada cuando NADIE de esa sección puede trabajar ese día:
   * todo su personal libra. Así no se inventa nada (no hay umbral arbitrario) y
   * se distingue de un hueco real, donde sí hay gente disponible.
   */
  /**
   * Tope de plazas de una sección (o null si no tiene). Público: el template lo
   * usa para el tooltip que explica por qué no se puede añadir a nadie más.
   */
  sectionCap(sectionName: string): number | null {
    const caps = this.areaCaps();
    const propio = caps.porNombre.get(this.normalizeSection(sectionName));
    return propio !== undefined ? propio : caps.porDefecto;
  }

  /**
   * ¿Esta celda ya alcanzó el tope de su sección?
   *
   * Cuenta las personas REALMENTE asignadas (no las filas vacías del editor).
   * Con esto la parrilla deja de ofrecer el "+" en una sección llena.
   */
  isCellAtCap(day: DayPlan, slotCode: string, sectionName: string): boolean {
    const cap = this.sectionCap(sectionName);
    if (cap === null) return false;
    const asignados = this.cellEditAssignments(day, slotCode, sectionName)
      .filter(a => a.workerId > 0).length;
    return asignados >= cap;
  }

  /**
   * Igual que `sectionClosedOnWeekday`, para el template: si la sección no abre
   * ese día no se pinta ni la cajita del horario ni el botón de añadir — la
   * celda queda vacía, porque no hay turno que cubrir.
   *
   * Cacheado: el template lo llama por cada celda de la parrilla.
   */
  isSectionClosedToday(sectionName: string, dateStr: string): boolean {
    this.ensureViolationsCache();   // invalida el caché si cambió plan/tienda
    const k = `${sectionName}|${dateStr}`;
    const hit = this._secClosedCache.get(k);
    if (hit !== undefined) return hit;
    const r = this.sectionClosedOnWeekday(sectionName, dateStr);
    this._secClosedCache.set(k, r);
    return r;
  }
  private _secClosedCache = new Map<string, boolean>();

  private sectionClosedOnWeekday(sectionName: string, dateStr: string): boolean {
    const target = this.normalizeSection(sectionName);
    const dela = this.workers().filter(w =>
      w.active
      && this.workerBelongsToScope(w)
      && this.normalizeSection(this.workerPrimaryPill(w)) === target);
    if (!dela.length) return false;      // sin personal: es "falta plantilla", no cierre
    return dela.every(w => this.hasDayOffOn(w, dateStr));
  }

  /**
   * ¿Este día es uno de sus DÍAS LIBRES fijos de la ficha (`dias_libres`)?
   *
   * Caso real: 29 de las 32 personas de pescadería libran el lunes, y el motor
   * lo respeta con la regla "Días libres personales" (overrideType: day_off).
   * Sin esta comprobación el aviso proponía cubrir el lunes con gente que libra
   * ese día — mandaba a hacer algo que el generador iba a deshacer.
   *
   * El campo guarda códigos sin acentos ('lunes', 'miercoles'), igual que
   * `_WEEKDAY_CODES` en el generador; se acepta también el índice numérico.
   */
  private hasDayOffOn(w: Worker, dateStr: string): boolean {
    const cd = (w.custom_data ?? {}) as Record<string, unknown>;
    const raw = cd['dias_libres'];
    if (!raw) return false;
    const vals = Array.isArray(raw) ? raw : [raw];
    const dia = new Date(dateStr + 'T00:00:00').getDay();   // 0=domingo
    const idx = dia === 0 ? 6 : dia - 1;                    // 0=lunes … 6=domingo
    const codigos = ['lunes', 'martes', 'miercoles', 'jueves',
                     'viernes', 'sabado', 'domingo'];
    return vals.some(v => {
      const s = (typeof v === 'object' && v !== null
        ? String((v as any).label ?? (v as any).value ?? '')
        : String(v ?? ''))
        .toLowerCase().trim()
        .normalize('NFD').replace(/[̀-ͯ]/g, '');   // quita acentos
      if (!s) return false;
      if (/^\d+$/.test(s)) return Number(s) === idx;
      return s === codigos[idx];
    });
  }

  /**
   * ¿Este turno le está PROHIBIDO por una restricción de error?
   *
   * Caso real: "Régimen antiguo no trabaja sábado tarde". Sin esta comprobación
   * el picker sugería a esa persona para cubrir el hueco y, al asignarla, el
   * plan salía con error — el sistema se contradecía a sí mismo.
   */
  private isShiftBlockedFor(w: Worker, slotCode: string): boolean {
    const cd = (w.custom_data ?? {}) as Record<string, unknown>;
    return this.shiftBlocks().some(b =>
      String(b.shift) === String(slotCode)
      && String(cd[b.field] ?? '').toLowerCase() === String(b.value ?? '').toLowerCase());
  }

  /**
   * Clase de ancho de columna por sección.
   *
   * Caja y Pescadería siguen llevando el ancho mayor (--section-wide) cuando
   * tienen mucha gente, pero ahora los trabajadores se apilan en vertical: ese
   * ancho va ÍNTEGRO al nombre en vez de partirse en dos sub-columnas, que era
   * lo que dejaba los nombres en "C…", "D…".
   */
  sectionColClass(name: string): string {
    const n = this.normalizeSection(name);
    if (this.isWideSection(name)) return 'figma-plantable__col--section-wide';
    if (n.includes('frut') || n.includes('charc')) return 'figma-plantable__col--section-narrow';
    return 'figma-plantable__col--section';
  }

  /** Icono SVG de la cabecera de cada sección (Figma tabla 2464:40401).
   *  Los SVG viven en public/icons/sections/. El match es por nombre
   *  (tolerante a acentos/mayúsculas); si no hay coincidencia → sin icono. */
  sectionIcon(name: string): string | null {
    const n = this.normalizeSection(name);
    const map: { test: (s: string) => boolean; file: string }[] = [
      { test: s => s.includes('encarg'),  file: 'encargada' },
      { test: s => s.includes('caja'),    file: 'caja' },
      { test: s => s.includes('panad'),   file: 'panaderia' },
      { test: s => s.includes('pescad'),  file: 'pescaderia' },
      { test: s => s.includes('frut'),    file: 'fruteria' },
      { test: s => s.includes('carn'),    file: 'carniceria' },   // carne / carnicería
      { test: s => s.includes('charc'),   file: 'charcuteria' },
    ];
    const hit = map.find(m => m.test(n));
    return hit ? `icons/sections/${hit.file}.svg` : null;
  }

  // ── Table view ────────────────────────────────────────────────────────

  /** Build worker groups for the table view (rows=workers grouped by role, cols=days). */
  tableGroups(): { name: string; color: string; rows: TableWorkerRow[] }[] {
    const plan = this.plan();
    if (!plan.length) return [];

    const allWorkers = this.workers().filter(w => w.active && this.workerMatchesFilters(w));
    const PALETTE = ['#4A90D9','#E87722','#6B4C9A','#2A9D8F','#E63946','#8B5E3C','#264653','#6C757D','#A0522D','#2E8B57'];

    // Build rows
    const rows: TableWorkerRow[] = allWorkers.map(w => ({
      worker: w,
      primaryPill: this.workerPrimaryPill(w) || 'Sin rol',
      groupColor: '',
      days: plan.map(day => this.buildTableCell(w, day)),
    }));

    // Group by primary pill/role
    const groupMap = new Map<string, TableWorkerRow[]>();
    for (const row of rows) {
      if (!groupMap.has(row.primaryPill)) groupMap.set(row.primaryPill, []);
      groupMap.get(row.primaryPill)!.push(row);
    }

    let ci = 0;
    return Array.from(groupMap.entries())
      .sort(([a], [b]) => a.localeCompare(b, 'es'))
      .map(([name, groupRows]) => {
        const color = PALETTE[ci++ % PALETTE.length];
        groupRows.forEach(r => { r.groupColor = color; });
        groupRows.sort((a, b) => a.worker.name.localeCompare(b.worker.name, 'es'));
        return { name, color, rows: groupRows };
      });
  }

  private buildTableCell(worker: Worker, day: DayPlan): TableCell {
    const restIds = new Set((day.rest || []).filter((id: number) => id > 0));
    if (restIds.has(worker.id)) {
      return {
        date: day.date, isRest: true,
        isOfficialRest: this.isOfficialRest(worker.id, day.date),
        shiftName: '', start: '', end: '', slotCode: '', color: '',
      };
    }
    for (const slot of this.shiftSlots()) {
      const found = (this.getAssignments(day, slot.code) || []).find(a => a.workerId === worker.id);
      if (found) {
        return {
          date: day.date, isRest: false, isOfficialRest: false,
          shiftName: slot.label,
          start: found.start || slot.attributes?.start_time || '',
          end: found.end || slot.attributes?.end_time || '',
          slotCode: slot.code,
          color: (slot as any).color || '#628db4',
        };
      }
    }
    // No assignment and not in rest list — unscheduled
    return { date: day.date, isRest: false, isOfficialRest: false, shiftName: '', start: '', end: '', slotCode: '', color: '' };
  }

  /** Shorten a long shift name to fit in a table cell */
  shiftAbbr(name: string): string {
    if (!name) return '—';
    // Keep max 22 chars, truncate at word boundary
    if (name.length <= 22) return name;
    return name.slice(0, 20).trimEnd() + '…';
  }

  private getPreviousDay(dateStr: string): DayPlan | null {
    const d = new Date(dateStr + 'T00:00:00');
    d.setDate(d.getDate() - 1);
    return this.plan().find(p => p.date === this.fmt(d)) || null;
  }

  private getCurrentMonday(): string {
    const d = new Date();
    const dow = d.getDay();
    d.setDate(d.getDate() - (dow === 0 ? 6 : dow - 1));
    return this.fmt(d);
  }

  /** ¿La semana mostrada es la que contiene HOY? Controla el estado
   *  "seleccionado" del chip "Hoy" (solo marcado cuando estás en la semana
   *  actual; al navegar a otra semana deja de estarlo). */
  isCurrentWeek(): boolean {
    return this.startDate() === this.getCurrentMonday();
  }

  private fmt(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  // ── Timeline / Calendar helpers ────────────────────────────────────────

  private readonly TIMELINE_START = 7;  // 07:00
  private readonly TIMELINE_END = 22;   // 22:00 (exclusive)

  /** Hours to display as markers on the timeline */
  timelineHours(): number[] {
    const hours: number[] = [];
    for (let h = this.TIMELINE_START; h <= this.TIMELINE_END; h++) {
      hours.push(h);
    }
    return hours;
  }

  /** Get position percentage for an hour on the timeline */
  getHourPosition(hour: number): number {
    const range = this.TIMELINE_END - this.TIMELINE_START;
    return ((hour - this.TIMELINE_START) / range) * 100;
  }

  /** Convert a time string (HH:MM) to a percentage position */
  getTimePosition(timeStr: string): number {
    const [h, m] = (timeStr || '07:00').split(':').map(Number);
    const totalMinutes = h * 60 + m;
    const startMinutes = this.TIMELINE_START * 60;
    const endMinutes = this.TIMELINE_END * 60;
    const range = endMinutes - startMinutes;
    return Math.max(0, Math.min(100, ((totalMinutes - startMinutes) / range) * 100));
  }

  /** Calculate width percentage for a block between start and end times */
  getBlockWidth(start: string, end: string): number {
    const startPos = this.getTimePosition(start);
    const endPos = this.getTimePosition(end);
    return Math.max(2, endPos - startPos); // min 2% so blocks are visible
  }

  /** Get active shift lanes for a day (one lane per shift, workers listed inside). */
  getDayShiftLanes(day: DayPlan): ShiftLaneBlock[] {
    const lanes: ShiftLaneBlock[] = [];
    for (const slot of this.shiftSlots()) {
      const assignments = this.getAssignments(day, slot.code);
      if (!assignments.length) continue;
      const first = assignments[0];
      lanes.push({
        id: `${day.date}-${slot.code}`,
        slotCode: slot.code,
        shiftName: slot.label,
        start: first.start || (slot.attributes as any)?.start_time || '07:00',
        end: first.end || (slot.attributes as any)?.end_time || '15:00',
        color: (slot as any).color || '#628db4',
        row: 0,
        workers: assignments.map((a, i) => ({
          workerId: a.workerId,
          workerName: a.workerName || '',
          index: i,
        })),
      });
    }
    // Assign rows (greedy, same algorithm as before but per-shift not per-worker)
    lanes.sort((a, b) => this.timeToMinutes(a.start) - this.timeToMinutes(b.start));
    const rowEnds: number[] = [];
    for (const lane of lanes) {
      const startMin = this.timeToMinutes(lane.start);
      let placed = false;
      for (let r = 0; r < rowEnds.length; r++) {
        if (rowEnds[r] <= startMin) {
          lane.row = r; rowEnds[r] = this.timeToMinutes(lane.end); placed = true; break;
        }
      }
      if (!placed) { lane.row = rowEnds.length; rowEnds.push(this.timeToMinutes(lane.end)); }
    }
    return lanes;
  }

  /** Minimum pixel height needed for a day's timeline (based on lane count). */
  getDayTimelineHeight(day: DayPlan): number {
    const lanes = this.getDayShiftLanes(day);
    if (!lanes.length) return 44;
    const maxRow = Math.max(...lanes.map(l => l.row));
    return (maxRow + 1) * 56 + 8;
  }

  /** @deprecated kept for callers that may reference it */
  getDayBlocks(day: DayPlan): CalendarBlock[] { return []; }

  private timeToMinutes(timeStr: string): number {
    const [h, m] = (timeStr || '07:00').split(':').map(Number);
    return h * 60 + m;
  }

  /** Open a dialog/dropdown to add a new assignment — for now picks the first available shift */
  openAddAssignment(day: DayPlan): void {
    // Find the first active slot for this day
    const weekday = new Date(day.date + 'T00:00:00').getDay();
    const adjustedWeekday = weekday === 0 ? 6 : weekday - 1; // JS Sunday=0 → Python Monday=0

    // Find variant slots that operate on this day
    const activeSlots = this.shiftSlots().filter(s => {
      // Root shifts (parent=null) always show; variants check ShiftDay
      return true; // All slots are valid — let user pick
    });

    if (activeSlots.length === 0) return;

    // For simplicity, use the first root shift
    const rootSlots = this.shiftSlots().filter(s => !s.parentId);
    const targetSlot = rootSlots[0] || activeSlots[0];
    this.addAssignment(day, targetSlot.code);
  }
}
