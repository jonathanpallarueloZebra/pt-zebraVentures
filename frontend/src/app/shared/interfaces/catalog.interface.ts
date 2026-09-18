// 'float' = decimal (p.ej. 37,5 horas semanales). 'number' es entero.
export type FieldType = 'text' | 'number' | 'float' | 'time' | 'color' | 'boolean' | 'textarea';

export interface KindAttribute {
  id: number;
  kind: number;
  key: string;
  label: string;
  field_type: FieldType;
  field_type_display: string;
  required: boolean;
  default_value: string;
  placeholder: string;
  order: number;
}

export interface KindValueAttribute {
  id: number;
  kind_value: number;
  attribute: number;
  attribute_key: string;
  attribute_label: string;
  attribute_field_type: FieldType;
  value: string;
}

export interface KindValue {
  id: number;
  kind: number;
  kind_code: string;
  code: string;
  label: string;
  description: string;
  icon: string;
  color: string;
  order: number;
  active: boolean;
  attributes: KindValueAttribute[];
}

export interface Kind {
  id: number;
  code: string;
  name: string;
  description: string;
  icon: string;
  editable: boolean;
  active: boolean;
  attributes: KindAttribute[];
  values: KindValue[];
}
