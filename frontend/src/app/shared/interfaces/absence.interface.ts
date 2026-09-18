export interface AbsenceType {
  id: number;
  name: string;
  requires_approval: boolean;
  active: boolean;
}

export interface AbsenceRequest {
  id: number;
  worker: number;
  worker_name: string;
  type: number;
  type_name: string;
  start_date: string;
  end_date: string | null;
  /** Ausencia sin fecha de fin conocida (baja indefinida). */
  indefinite: boolean;
  reason: string;
  status: string;
  reviewed_by: number | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  created_at: string;
}
