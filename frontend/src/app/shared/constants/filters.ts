/**
 * Valor centinela del filtro "Sin asignar".
 *
 * Los filtros llevan el valor real del campo (un id de tienda, un codigo de
 * catalogo...), y `null` ya significa "todos". Hace falta un tercer valor para
 * decir "los que NO tienen valor", y tiene que ser una cadena porque el
 * zb-select trabaja con strings.
 *
 * Se usan los `__` para que no pueda colisionar nunca con un id o un codigo
 * real que venga del backend.
 */
export const SIN_ASIGNAR = '__sin_asignar__';

/**
 * Un valor de campo esta "sin asignar".
 *
 * Cubre las cuatro formas en que aparece un hueco en custom_data, no solo null:
 * en los datos reales del cliente la tienda vacia esta unas veces como `null` y
 * otras como cadena vacia (segun si la ficha se creo por Excel o a mano), y los
 * multi-select guardan listas, donde el hueco es `[]`.
 *
 * El 0 y el false NO son huecos: "0 turnos" o un boolean en "no" son valores.
 * Mismo criterio que `_missing_required` en el backend.
 */
export function valorSinAsignar(v: any): boolean {
  if (v === null || v === undefined || v === '') return true;
  if (Array.isArray(v)) return v.length === 0;
  if (typeof v === 'object') return Object.keys(v).length === 0;
  return false;
}
