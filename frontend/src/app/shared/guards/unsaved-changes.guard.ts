import { CanDeactivateFn } from '@angular/router';

/**
 * Componente que puede bloquear la salida cuando tiene trabajo sin guardar.
 *
 * `confirmLeave()` devuelve `true` si se puede salir, o una promesa que se
 * resuelve cuando el usuario decide (para poder enseñarle un diálogo).
 */
export interface PuedeSalir {
  confirmLeave(destino?: string): boolean | Promise<boolean>;
}

/**
 * Impide salir de una pantalla con cambios sin guardar sin avisar.
 *
 * Antes, al pulsar cualquier enlace del menú mientras editabas la
 * planificación, se navegaba sin más y el borrador se perdía en silencio. El
 * botón "Cancelar" sí avisaba, pero el menú no: el mismo riesgo con dos
 * comportamientos distintos.
 *
 * La guarda solo pregunta al componente; el diálogo (y su texto) es cosa suya,
 * así que se reutiliza el mismo overlay que ya usa "Cancelar".
 */
export const unsavedChangesGuard: CanDeactivateFn<PuedeSalir> = (
  component, _ruta, _estado, siguiente,
) => {
  if (!component?.confirmLeave) return true;
  return component.confirmLeave(siguiente.url);
};
