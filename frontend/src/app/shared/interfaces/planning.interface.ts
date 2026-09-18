export interface ShiftAssignment {
  workerId: number;
  workerName: string;
  start: string;
  end: string;
  areas: string[];
}

export interface DayPlan {
  date: string;
  dayName: string;
  rest: number[];
  violations?: RestrictionViolation[];
  [shiftSlot: string]: any;
}

export interface WeeklyPlan {
  start: string;
  plan: DayPlan[];
  /**
   * El plan guardado se calculó ANTES de la última edición de fichas de esta
   * tienda: los avisos que muestra pueden estar resueltos (o haber aparecido
   * otros). Hay que regenerar para aplicar los cambios.
   */
  stale?: boolean;
  stale_since?: string | null;
  /** Quién se editó (hasta 5 nombres), para nombrarlo en el aviso. */
  stale_workers?: string[];
  /**
   * `{fecha: [workerId]}` de quien ya trabaja en OTRA tienda esa semana. Nadie
   * puede estar en dos tiendas el mismo día, así que no se le puede ofrecer
   * como candidato para cubrir un hueco aquí.
   */
  busy_elsewhere?: Record<string, number[]>;
}

export interface RestrictionViolation {
  restrictionId: number;
  restrictionName: string;
  message: string;
  severity: 'warning' | 'error';
  dayDate?: string;
  shift?: string;
}

export interface ValidationResult {
  isValid: boolean;
  violations: RestrictionViolation[];
}

export interface RestDay {
  id: number;
  workerId: number;
  worker_name: string;
  date: string;
  reason: string | null;
}
