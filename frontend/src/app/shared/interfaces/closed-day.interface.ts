export interface ClosedDay {
  id: number;
  date: string; // YYYY-MM-DD
  scope_entity_id: number; // 0 = global (aplica a todos los ámbitos)
  reason: string;
  created_at: string;
}
