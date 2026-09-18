export type EngineType = 'count' | 'exclusion' | 'match' | 'condition' | 'closed_day';

export interface EngineFieldOption {
  value: string;
  label: string;
}

export interface EngineField {
  key: string;
  label: string;
  field_type: string;
  options?: EngineFieldOption[];
  min?: number;
  max?: number;
  showWhen?: Record<string, string>;
}

export interface EngineSchema {
  label: string;
  description: string;
  fields: EngineField[];
}

export interface Restriction {
  id: number;
  name: string;
  description: string;
  engine: EngineType;
  config: Record<string, any>;
  severity: 'warning' | 'error';
  active: boolean;
  message: string;
  scope_records: number[];
  /** Fija (false) = el cliente solo la activa/desactiva.
   *  Personalizable (true) = el cliente edita sus valores, la duplica y le asigna tiendas. */
  customizable: boolean;
  /** ID de la restricción de la que se duplicó. Solo traza: la copia es independiente. */
  duplicated_from?: number | null;
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
