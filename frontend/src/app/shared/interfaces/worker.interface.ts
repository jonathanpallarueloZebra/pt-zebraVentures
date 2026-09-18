import { FieldSchema } from './entity-field.interface';

export interface WorkerPreference {
  shift_type: string;
}

export interface Worker {
  id: number;
  name: string;
  active: boolean;
  preferredShifts: WorkerPreference[];
  user?: number | null;
  custom_data: Record<string, any>;
  field_schema: FieldSchema[];
}
