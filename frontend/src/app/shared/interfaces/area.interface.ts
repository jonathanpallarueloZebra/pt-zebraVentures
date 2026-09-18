import { FieldSchema } from './entity-field.interface';

export interface Area {
  id: number;
  name: string;
  short_name: string | null;
  description: string;
  order: number;
  active: boolean;
  required_role: number | null;
  required_role_name: string | null;
  custom_data: Record<string, any>;
  field_schema: FieldSchema[];
}
