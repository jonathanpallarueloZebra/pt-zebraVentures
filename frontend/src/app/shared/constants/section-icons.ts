/**
 * Iconos SVG de SECCIÓN disponibles (los mismos que pinta el planificador en las
 * cabeceras de columna). Viven en `public/icons/sections/<file>.svg`.
 *
 * Se usan como opciones del campo de tipo `icon` de la entidad "seccion":
 * el valor guardado es la clave (`value`, p.ej. 'fruteria') y el SVG se resuelve
 * con `sectionIconPath()`.
 *
 * AC-6: solo se puede SELECCIONAR de esta lista; no hay subida de iconos nuevos.
 */
export interface SectionIcon {
  /** Valor guardado en el registro (nombre del fichero SVG, sin extensión). */
  value: string;
  /** Etiqueta legible en el dropdown. */
  label: string;
}

export const SECTION_ICONS: SectionIcon[] = [
  { value: 'encargada',   label: 'Encargada' },
  { value: 'caja',        label: 'Caja' },
  { value: 'panaderia',   label: 'Panadería' },
  { value: 'pescaderia',  label: 'Pescadería' },
  { value: 'fruteria',    label: 'Frutería' },
  { value: 'carniceria',  label: 'Carnicería' },
  { value: 'charcuteria', label: 'Charcutería' },
];

/** Ruta del SVG a partir del valor guardado ('fruteria' → 'icons/sections/fruteria.svg').
 *  Devuelve '' si el valor está vacío o no es un icono de sección conocido. */
export function sectionIconPath(value: string | null | undefined): string {
  if (!value) return '';
  const found = SECTION_ICONS.some(i => i.value === value);
  return found ? `icons/sections/${value}.svg` : '';
}
