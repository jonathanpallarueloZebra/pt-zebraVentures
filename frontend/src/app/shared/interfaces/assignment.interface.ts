export interface AssignmentPattern {
  value: string;
  label: string;
  description: string;
}

export interface WorkerFieldOption {
  key: string;
  label: string;
  field_type: string;
  target_entity: string;
}

export interface AssignmentRule {
  id: number;
  name: string;
  description: string;
  config: Record<string, any>;
  active: boolean;
  priority: number;
  scope_records: number[];
}
