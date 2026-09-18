import { FieldSchema } from './entity-field.interface';

export interface Role {
  id: number;
  name: string;
  description: string;
  active: boolean;
  custom_data: Record<string, any>;
  field_schema: FieldSchema[];
}
