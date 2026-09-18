import { FieldSchema } from './entity-field.interface';

export interface Shift {
  id: number;
  name: string;
  start_time: string;
  end_time: string;
  /** Inicio de vigencia (YYYY-MM-DD) o null = sin límite. Turno "extra". */
  valid_from?: string | null;
  /** Fin de vigencia (YYYY-MM-DD) o null = sin límite. Turno "extra". */
  valid_to?: string | null;
  custom_data: Record<string, any>;
  field_schema?: FieldSchema[];
  operating_days?: number[];
}
