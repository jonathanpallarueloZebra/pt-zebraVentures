import { Component, HostBinding, Input, computed, signal } from '@angular/core';

/** Nombre de icono disponible en el set de Figma. */
export type ZbIconName =
  | 'expand_more'
  | 'settings'
  | 'add'
  | 'file_download'
  | 'download'          // alias de file_download (nombre usado en la app)
  | 'upload_file'
  | 'arrow_back'
  | 'arrow_forward'
  | 'arrow_downward'
  | 'arrow_upward'
  | 'filter_list'
  | 'highlight_off'
  | 'search'
  | 'close'
  | 'edit'
  | 'content_copy'
  | 'delete';

interface IconDef {
  /** viewBox de la CAJA COMPLETA del icono, no del glifo recortado.
   *
   *  En Figma cada icono vive en una caja (normalmente 24×24) y el glifo ocupa
   *  solo una parte, con un inset alrededor: settings inset 8.33%/9.49%, add
   *  20.83%, expand_more 36.28%/26.72%… El SVG del asset server viene RECORTADO
   *  al glifo, así que pintarlo tal cual llena toda la caja y el icono se ve
   *  mucho más grande y ancho que en el diseño. Por eso el viewBox lleva aquí
   *  el origen desplazado y el tamaño de la caja completa: así el glifo
   *  conserva su aire original. */
  viewBox: string;
  path: string;
  /** Iconos de trazo (no relleno), como la X del buscador. */
  stroke?: boolean;
  strokeWidth?: string;
  /** Reutiliza el path de otro icono espejado horizontalmente. */
  flipOf?: ZbIconName;
  /** Reutiliza el path de otro icono espejado verticalmente. */
  flipVerticalOf?: ZbIconName;
}

/**
 * Iconos SVG exactos exportados de Figma (Material Symbols "Outlined").
 *
 * El proyecto solo tiene la fuente `material-icons`, que es de TRAZO GRUESO y
 * no coincide con el diseño. Estos paths salen del asset server de Figma
 * (ver figma-cache/2658-13890-iconos-toolbar-botones.md) y se pintan inline con
 * `fill=currentColor`, así que heredan el color del contenedor igual que hacía
 * la fuente.
 */
const ICONS: Record<string, IconDef> = {
  // ── Toolbar / dropdowns ────────────────────────────────────────────────
  // caja 24×24 · inset 36.28% vert / 26.72% horiz
  expand_more: {
    viewBox: '-6.41 -8.71 24 24',
    path: 'M10.59 0L6 4.58L1.41 0L0 1.41L6 7.41L12 1.41L10.59 0Z',
  },
  // caja 24×24 · inset 8.33% vert / 9.49% horiz
  settings: {
    viewBox: '-2.28 -2 24 24',
    path: 'M17.1593 10.98C17.1993 10.66 17.2293 10.34 17.2293 10C17.2293 9.66 17.1993 9.34 17.1593 9.02L19.2693 7.37C19.4593 7.22 19.5093 6.95 19.3893 6.73L17.3893 3.27C17.2993 3.11 17.1293 3.02 16.9493 3.02C16.8893 3.02 16.8293 3.03 16.7793 3.05L14.2893 4.05C13.7693 3.65 13.2093 3.32 12.5993 3.07L12.2193 0.42C12.1893 0.18 11.9793 0 11.7293 0H7.72933C7.47933 0 7.26933 0.18 7.23933 0.42L6.85933 3.07C6.24933 3.32 5.68933 3.66 5.16933 4.05L2.67933 3.05C2.61933 3.03 2.55933 3.02 2.49933 3.02C2.32933 3.02 2.15933 3.11 2.06933 3.27L0.0693316 6.73C-0.0606684 6.95 -0.000668304 7.22 0.189332 7.37L2.29933 9.02C2.25933 9.34 2.22933 9.67 2.22933 10C2.22933 10.33 2.25933 10.66 2.29933 10.98L0.189332 12.63C-0.000668304 12.78 -0.0506684 13.05 0.0693316 13.27L2.06933 16.73C2.15933 16.89 2.32933 16.98 2.50933 16.98C2.56933 16.98 2.62933 16.97 2.67933 16.95L5.16933 15.95C5.68933 16.35 6.24933 16.68 6.85933 16.93L7.23933 19.58C7.26933 19.82 7.47933 20 7.72933 20H11.7293C11.9793 20 12.1893 19.82 12.2193 19.58L12.5993 16.93C13.2093 16.68 13.7693 16.34 14.2893 15.95L16.7793 16.95C16.8393 16.97 16.8993 16.98 16.9593 16.98C17.1293 16.98 17.2993 16.89 17.3893 16.73L19.3893 13.27C19.5093 13.05 19.4593 12.78 19.2693 12.63L17.1593 10.98ZM15.1793 9.27C15.2193 9.58 15.2293 9.79 15.2293 10C15.2293 10.21 15.2093 10.43 15.1793 10.73L15.0393 11.86L15.9293 12.56L17.0093 13.4L16.3093 14.61L15.0393 14.1L13.9993 13.68L13.0993 14.36C12.6693 14.68 12.2593 14.92 11.8493 15.09L10.7893 15.52L10.6293 16.65L10.4293 18H9.02933L8.67933 15.52L7.61933 15.09C7.18933 14.91 6.78933 14.68 6.38933 14.38L5.47933 13.68L4.41933 14.11L3.14933 14.62L2.44933 13.41L3.52933 12.57L4.41933 11.87L4.27933 10.74C4.24933 10.43 4.22933 10.2 4.22933 10C4.22933 9.8 4.24933 9.57 4.27933 9.27L4.41933 8.14L3.52933 7.44L2.44933 6.6L3.14933 5.39L4.41933 5.9L5.45933 6.32L6.35933 5.64C6.78933 5.32 7.19933 5.08 7.60933 4.91L8.66933 4.48L8.82933 3.35L9.02933 2H10.4193L10.7693 4.48L11.8293 4.91C12.2593 5.09 12.6593 5.32 13.0593 5.62L13.9693 6.32L15.0293 5.89L16.2993 5.38L16.9993 6.59L15.9293 7.44L15.0393 8.14L15.1793 9.27ZM9.72933 6C7.51933 6 5.72933 7.79 5.72933 10C5.72933 12.21 7.51933 14 9.72933 14C11.9393 14 13.7293 12.21 13.7293 10C13.7293 7.79 11.9393 6 9.72933 6ZM9.72933 12C8.62933 12 7.72933 11.1 7.72933 10C7.72933 8.9 8.62933 8 9.72933 8C10.8293 8 11.7293 8.9 11.7293 10C11.7293 11.1 10.8293 12 9.72933 12Z',
  },

  // ── Botones de acción ──────────────────────────────────────────────────
  // caja 24×24 · inset 20.83%
  add: {
    viewBox: '-5 -5 24 24',
    path: 'M14 8H8V14H6V8H0V6H6V0H8V6H14V8Z',
  },
  // caja 24×24 · inset 16.67%
  file_download: {
    viewBox: '-4 -4 24 24',
    path: 'M14 11V14H2V11H0V14C0 15.1 0.9 16 2 16H14C15.1 16 16 15.1 16 14V11H14ZM13 7L11.59 5.59L9 8.17V0H7V8.17L4.41 5.59L3 7L8 12L13 7Z',
  },
  // La app usa "download" en varios botones; es el mismo glifo de Figma.
  download: {
    viewBox: '-4 -4 24 24',
    path: 'M14 11V14H2V11H0V14C0 15.1 0.9 16 2 16H14C15.1 16 16 15.1 16 14V11H14ZM13 7L11.59 5.59L9 8.17V0H7V8.17L4.41 5.59L3 7L8 12L13 7Z',
  },
  // caja 24×24 · inset 8.33% vert / 16.67% horiz
  upload_file: {
    viewBox: '-4 -2 24 24',
    path: 'M10 0H2C0.9 0 0.0100002 0.9 0.0100002 2L0 18C0 19.1 0.89 20 1.99 20H14C15.1 20 16 19.1 16 18V6L10 0ZM14 18H2V2H9V7H14V18ZM4 13.01L5.41 14.42L7 12.84V17H9V12.84L10.59 14.43L12 13.01L8.01 9L4 13.01Z',
  },

  // ── Paginador / tabla ──────────────────────────────────────────────────
  // caja 20×20 · inset 18.39% vert / 17.54% horiz
  arrow_back: {
    viewBox: '-3.51 -3.68 20 20',
    path: 'M12.1521 5.49375H2.84375L6.91042 1.42708C7.23542 1.10208 7.23542 0.56875 6.91042 0.24375C6.58542 -0.08125 6.06042 -0.08125 5.73542 0.24375L0.24375 5.73542C-0.08125 6.06042 -0.08125 6.58542 0.24375 6.91042L5.73542 12.4021C6.06042 12.7271 6.58542 12.7271 6.91042 12.4021C7.23542 12.0771 7.23542 11.5521 6.91042 11.2271L2.84375 7.16042H12.1521C12.6104 7.16042 12.9854 6.78542 12.9854 6.32708C12.9854 5.86875 12.6104 5.49375 12.1521 5.49375Z',
  },
  // Figma reutiliza arrow_back espejado para la flecha de "Siguiente".
  arrow_forward: {
    viewBox: '0 0 12.9854 12.6458',
    path: '',
    flipOf: 'arrow_back',
  },
  // caja 12×12 · inset 16.67% (cabecera de tabla)
  arrow_downward: {
    viewBox: '-2 -2 12 12',
    path: 'M8 4L7.295 3.295L4.5 6.085V0H3.5V6.085L0.71 3.29L0 4L4 8L8 4Z',
  },
  // Espejo vertical de arrow_downward (Figma reutiliza el glifo).
  arrow_upward: {
    viewBox: '-2 -2 12 12',
    path: '',
    flipVerticalOf: 'arrow_downward',
  },
  // caja 16×16 · inset 25% vert / 12.5% horiz
  filter_list: {
    viewBox: '-2 -4 16 16',
    path: 'M4.66667 8H7.33333V6.66667H4.66667V8ZM0 0V1.33333H12V0H0ZM2 4.66667H10V3.33333H2V4.66667Z',
  },
  highlight_off: {
    viewBox: '0 0 16.6667 16.6667',
    path: 'M9.90833 5.58333L8.33333 7.15833L6.75833 5.58333C6.43333 5.25833 5.90833 5.25833 5.58333 5.58333C5.25833 5.90833 5.25833 6.43333 5.58333 6.75833L7.15833 8.33333L5.58333 9.90833C5.25833 10.2333 5.25833 10.7583 5.58333 11.0833C5.90833 11.4083 6.43333 11.4083 6.75833 11.0833L8.33333 9.50833L9.90833 11.0833C10.2333 11.4083 10.7583 11.4083 11.0833 11.0833C11.4083 10.7583 11.4083 10.2333 11.0833 9.90833L9.50833 8.33333L11.0833 6.75833C11.4083 6.43333 11.4083 5.90833 11.0833 5.58333C10.7583 5.26667 10.225 5.26667 9.90833 5.58333ZM8.33333 0C3.725 0 0 3.725 0 8.33333C0 12.9417 3.725 16.6667 8.33333 16.6667C12.9417 16.6667 16.6667 12.9417 16.6667 8.33333C16.6667 3.725 12.9417 0 8.33333 0ZM8.33333 15C4.65833 15 1.66667 12.0083 1.66667 8.33333C1.66667 4.65833 4.65833 1.66667 8.33333 1.66667C12.0083 1.66667 15 4.65833 15 8.33333C15 12.0083 12.0083 15 8.33333 15Z',
  },

  // ── Buscador ───────────────────────────────────────────────────────────
  // caja 16×16 · inset 14.46% vert / 14.48% horiz
  search: {
    viewBox: '-2.32 -2.31 16 16',
    path: 'M8.33375 7.33375H7.80708L7.62042 7.15375C8.42042 6.22042 8.83375 4.94708 8.60708 3.59375C8.29375 1.74042 6.74708 0.260417 4.88042 0.0337504C2.06042 -0.312916 -0.312916 2.06042 0.0337504 4.88042C0.260417 6.74708 1.74042 8.29375 3.59375 8.60708C4.94708 8.83375 6.22042 8.42042 7.15375 7.62042L7.33375 7.80708V8.33375L10.1671 11.1671C10.4404 11.4404 10.8871 11.4404 11.1604 11.1671C11.4338 10.8938 11.4338 10.4471 11.1604 10.1738L8.33375 7.33375ZM4.33375 7.33375C2.67375 7.33375 1.33375 5.99375 1.33375 4.33375C1.33375 2.67375 2.67375 1.33375 4.33375 1.33375C5.99375 1.33375 7.33375 2.67375 7.33375 4.33375C7.33375 5.99375 5.99375 7.33375 4.33375 7.33375Z',
  },
  // La X del buscador es de TRAZO (dos líneas), no un relleno.
  // caja 20×20 · inset 12.49% (lápiz de la columna ACCIONES, Icon/link #026aa2)
  edit: {
    viewBox: '-2.5 -2.5 20 20',
    path: 'M0 11.8771V15.0021H3.125L12.3417 5.78542L9.21667 2.66042L0 11.8771ZM14.7583 3.36875C15.0833 3.04375 15.0833 2.51875 14.7583 2.19375L12.8083 0.24375C12.4833 -0.08125 11.9583 -0.08125 11.6333 0.24375L10.1083 1.76875L13.2333 4.89375L14.7583 3.36875Z',
  },
  // Duplicar y borrar (columna ACCIONES, junto al lápiz de edit).
  // Material Symbols Outlined. El glifo viene en caja 24×24 ocupándola entera,
  // así que el viewBox se AGRANDA a 30×30 centrado (-3 -3) para darle el mismo
  // aire que edit (glifo 15 en caja 20): sin ese margen el icono se ve más
  // grande que el lápiz de al lado.
  content_copy: {
    viewBox: '-3 -3 30 30',
    path: 'M16 1H4C2.9 1 2 1.9 2 3V17H4V3H16V1ZM19 5H8C6.9 5 6 5.9 6 7V21C6 22.1 6.9 23 8 23H19C20.1 23 21 22.1 21 21V7C21 5.9 20.1 5 19 5ZM19 21H8V7H19V21Z',
  },
  delete: {
    viewBox: '-3 -3 30 30',
    path: 'M6 19C6 20.1 6.9 21 8 21H16C17.1 21 18 20.1 18 19V7H6V19ZM8 9H16V19H8V9ZM15.5 4L14.5 3H9.5L8.5 4H5V6H19V4H15.5Z',
  },
  // caja 16×16 · inset 25% (la X de Figma es de trazo, no relleno)
  close: {
    viewBox: '-4 -4 19.33 19.33',
    path: 'M8.83333 0.833333L0.833333 8.83333M0.833333 0.833333L8.83333 8.83333',
    stroke: true,
    strokeWidth: '1.66667',
  },
};

/** ¿Existe este nombre en el set de SVG de Figma? Permite a otros componentes
 *  (p.ej. zb-button) usar el SVG exacto cuando lo hay y caer a la fuente
 *  material-icons para iconos que el diseño no define. */
export function hasZbIcon(name?: string | null): name is ZbIconName {
  return !!name && name in ICONS;
}

/**
 * Icono SVG del sistema (set exacto de Figma).
 *
 * Uso: `<zb-icon name="expand_more" size="16"></zb-icon>`
 *
 * El contenedor fija la caja (16/20/…px) y el `<svg>` la rellena al 100%
 * conservando su viewBox propio — mismo patrón que `.dash-icon` del dashboard.
 * El color se hereda del padre vía `currentColor`.
 */
@Component({
  selector: 'zb-icon',
  standalone: true,
  template: `
    <svg [attr.viewBox]="def().viewBox"
         [attr.fill]="def().stroke ? 'none' : 'currentColor'"
         aria-hidden="true"
         focusable="false">
      <path [attr.d]="def().path"
            [attr.transform]="flipTransform()"
            [attr.fill]="def().stroke ? 'none' : 'currentColor'"
            [attr.stroke]="def().stroke ? 'currentColor' : null"
            [attr.stroke-width]="def().strokeWidth ?? null"
            [attr.stroke-linecap]="def().stroke ? 'round' : null" />
    </svg>
  `,
  styles: [`
    /* El tamaño se aplica como estilo INLINE en el host (ver hostWidth/
       hostHeight): así nunca depende de que el componente padre defina
       --zb-icon-size, y un contenedor que fije width/height sobre el propio
       <zb-icon> (p.ej. .btn-icon) lo sobreescribe de forma predecible. */
    :host {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      color: inherit;
      /* Red de seguridad: si por lo que sea el host se quedara sin tamaño,
         el svg (width:100%) se estiraría a todo el contenedor flex. */
      width: 16px;
      height: 16px;
    }
    /* El SVG rellena la caja del host conservando su viewBox propio.
       flex-shrink:0 evita que un contenedor flex lo comprima, y los
       width/height explicitos ganan al tamano intrinseco del viewBox. */
    svg {
      display: block;
      width: 100%;
      height: 100%;
      flex-shrink: 0;
    }
  `],
})
export class ZbIconComponent {
  private _name = signal<ZbIconName>('expand_more');

  @Input({ required: true })
  set name(value: ZbIconName) { this._name.set(value); }

  /** Tamaño de la caja en px (el glifo se escala dentro).
   *
   *  Se aplica como width/height INLINE en el host. Es deliberado: si el
   *  tamaño dependiera de una custom property (--zb-icon-size) y el
   *  componente que lo usa no la definiera, el <svg> (width:100%) se
   *  estiraría a todo el ancho disponible del contenedor flex. Con el
   *  inline siempre hay una caja concreta. */
  @HostBinding('style.width') hostWidth = '16px';
  @HostBinding('style.height') hostHeight = '16px';

  @Input()
  set size(value: number | string) {
    const px = typeof value === 'number' ? `${value}px` : value;
    this.hostWidth = px;
    this.hostHeight = px;
  }

  /** Definición del icono; resuelve los que son espejo de otro. */
  def = computed<IconDef>(() => {
    const d = ICONS[this._name()] ?? ICONS['expand_more'];
    const mirror = d.flipOf ?? d.flipVerticalOf;
    if (mirror) {
      const src = ICONS[mirror];
      return { ...d, path: src.path, viewBox: src.viewBox };
    }
    return d;
  });

  /** Espejo horizontal para arrow_forward (reutiliza el path de arrow_back).
   *
   *  El viewBox es "minX minY ancho alto" y minX NO es 0 (lleva el offset de
   *  la caja de Figma), así que el eje de simetría es 2·minX + ancho: refleja
   *  dentro de la caja completa, no sobre el origen. */
  flipTransform = computed<string | null>(() => {
    const d = ICONS[this._name()];
    if (d?.flipOf) {
      const [minX, , width] = ICONS[d.flipOf].viewBox.split(' ').map(parseFloat);
      return `translate(${2 * minX + width}, 0) scale(-1, 1)`;
    }
    if (d?.flipVerticalOf) {
      const [, minY, , height] = ICONS[d.flipVerticalOf].viewBox.split(' ').map(parseFloat);
      return `translate(0, ${2 * minY + height}) scale(1, -1)`;
    }
    return null;
  });
}
