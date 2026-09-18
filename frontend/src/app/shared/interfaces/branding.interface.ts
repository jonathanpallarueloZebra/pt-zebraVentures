export interface Branding {
  company_name: string;
  tagline: string;
  logo_url: string | null;
  favicon_url: string | null;
  primary_color: string;
  primary_dark: string;
  /**
   * Modo del selector de fechas del planificador:
   *   'week'  → al pulsar un día se selecciona su semana completa
   *   'range' → el usuario elige fecha de inicio y de fin
   *
   * Opcional porque un backend anterior a esta configuración no lo envía; en
   * ese caso se asume 'range', que es el comportamiento previo.
   */
  date_picker_mode?: DatePickerMode;
  updated_at: string;
}

export type DatePickerMode = 'week' | 'range';
