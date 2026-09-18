export type EntityType = string; // slug, e.g. 'role', 'shift', 'store', 'zone' …
export type FieldType =
  // 'float' = decimal (p.ej. 37,5 horas semanales). 'number' es entero.
  | 'text' | 'number' | 'float' | 'boolean' | 'color' | 'time' | 'select' | 'textarea'
  | 'catalog_select' | 'multi_catalog_select'
  | 'entity_select' | 'multi_entity_select'
  | 'icon';

export interface EntityTypeDef {
  id: number;
  slug: string;
  name: string;
  icon: string;
  order: number;
  show_in_sidebar: boolean;
  is_system: boolean;
  display_field: string;
  use_as_filter: boolean;
  is_planning_scope: boolean;
  show_in_schedule: boolean;
  record_count: number;
}

export interface EntityRecord {
  id: number;
  entity_type: string; // slug
  entity_type_slug: string;
  data: Record<string, any>;
  field_schema: FieldSchema[];
  created_at: string;
  updated_at: string;
}

export interface EntityField {
  id: number;
  entity_type: EntityType;
  key: string;
  label: string;
  field_type: FieldType;
  required: boolean;
  default_value: string;
  placeholder: string;
  options: string[];
  kind_code?: string;
  target_entity?: string;
  display_key?: string;
  depends_on?: string;
  depends_on_field?: string;
  visible_when_field?: string;
  visible_when_value?: string;
  allow_priority: boolean;
  help_text: string;
  show_in_list: boolean;
  show_as_filter: boolean;
  /** Anade la opcion "Sin asignar" al filtro de este campo. Es por campo. */
  allow_unassigned_filter: boolean;
  order: number;
  active: boolean;
}

/** Schema attached to each entity instance in API responses */
export interface FieldSchema {
  key: string;
  label: string;
  field_type: FieldType;
  required: boolean;
  default_value: string;
  placeholder: string;
  options: string[];
  show_in_list: boolean;
  show_as_filter: boolean;
  /** Anade la opcion "Sin asignar" al filtro de este campo. */
  allow_unassigned_filter?: boolean;
  order: number;
  allow_priority: boolean;
  help_text: string;
  kind_code?: string;
  target_entity?: string;
  display_key?: string;
  depends_on?: string;
  depends_on_field?: string;
  visible_when_field?: string;
  visible_when_value?: string;
}
