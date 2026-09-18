import {
  Directive, ElementRef, AfterViewInit, OnDestroy, inject, NgZone,
} from '@angular/core';

/**
 * appDropdownFlip — posiciona un dropdown con `position: fixed` respecto al
 * viewport, anclándolo a su elemento contenedor (la celda/`cell-add-wrap`).
 *
 * Se usa `fixed` (no `absolute`) a propósito: así el panel NO participa en el
 * overflow del contenedor de scroll de la tabla (.schedule-scroll con
 * overflow-x:auto). Con `absolute`, un panel que sobresalía disparaba el
 * scrollbar del contenedor y la tabla "saltaba"/temblaba al abrirlo.
 *
 * Decide hacia dónde se despliega para no cortarse contra el borde de la
 * pantalla: hacia arriba si no cabe abajo, y hacia la izquierda si no cabe a la
 * derecha. La altura la fija el CSS (max-height); aquí solo se coloca.
 *
 * Uso: <div class="emp-picker" appDropdownFlip> … </div>
 */
@Directive({
  selector: '[appDropdownFlip]',
  standalone: true,
})
export class DropdownFlipDirective implements AfterViewInit, OnDestroy {
  private el = inject(ElementRef<HTMLElement>);
  private zone = inject(NgZone);

  /** Margen mínimo con el borde de la ventana. */
  private readonly MARGIN = 8;
  /** Separación entre el ancla y el panel. */
  private readonly GAP = 2;
  private onReposition = () => this.reposition();

  ngAfterViewInit(): void {
    const node = this.el.nativeElement;
    // Fijar el posicionamiento respecto al viewport (sale del overflow de la
    // tabla). Oculto hasta colocarlo para no mostrar el frame sin posicionar.
    node.style.position = 'fixed';
    node.style.margin = '0';
    node.style.visibility = 'hidden';
    this.zone.runOutsideAngular(() => {
      requestAnimationFrame(() => {
        this.reposition();
        node.style.visibility = '';
      });
      // Al ser `fixed`, sí hay que recolocar si la página hace scroll o resize
      // (el ancla se mueve con el documento pero el panel es fijo al viewport).
      window.addEventListener('scroll', this.onReposition, true);
      window.addEventListener('resize', this.onReposition);
    });
  }

  ngOnDestroy(): void {
    window.removeEventListener('scroll', this.onReposition, true);
    window.removeEventListener('resize', this.onReposition);
  }

  private reposition(): void {
    const node = this.el.nativeElement;
    // El ancla es el contenedor del dropdown (la celda / cell-add-wrap).
    const anchor = node.parentElement;
    if (!anchor) return;
    const a = anchor.getBoundingClientRect();

    // Medir el tamaño real del panel (sin restringir posición).
    const w = node.offsetWidth;
    const h = node.offsetHeight;
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    // ── Horizontal: por defecto alineado al borde izq del ancla; si se sale
    //    por la derecha, alinea el borde derecho del panel con el del ancla.
    let left = a.left;
    if (left + w > vw - this.MARGIN) {
      left = Math.max(this.MARGIN, a.right - w);
    }

    // ── Vertical: por defecto justo debajo del ancla; si no cabe abajo y
    //    arriba hay más hueco, lo coloca encima.
    const spaceBelow = vh - a.bottom - this.MARGIN;
    const spaceAbove = a.top - this.MARGIN;
    let top = a.bottom + this.GAP;
    if (h > spaceBelow && spaceAbove > spaceBelow) {
      top = a.top - this.GAP - h;
    }
    // No dejar que se salga por arriba.
    if (top < this.MARGIN) top = this.MARGIN;

    node.style.left = `${Math.round(left)}px`;
    node.style.top = `${Math.round(top)}px`;
    node.style.right = 'auto';
    node.style.bottom = 'auto';
  }
}
