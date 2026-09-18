import { Component, Input, HostBinding } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ZbIconComponent, ZbIconName, hasZbIcon } from '@app/shared/components/zb-icon/zb-icon.component';

// Figma variants:
// primary        → filled brand yellow
// secondary      → transparent + neutral dark border (light bg)
// danger         → filled dark red
// danger-outlined→ transparent + red border
// outline-dark   → transparent + white border (dark bg)
// text           → no bg, no border, link color, hover pill highlight
// icon-only      → circular, single icon, no label
export type ZbButtonVariant =
  | 'primary'
  | 'secondary'
  | 'danger'
  | 'danger-outlined'
  | 'outline-dark'
  | 'text'
  | 'icon-only';

// sm: h=34px, pad 0 16px, fs 12px
// md: h=38px, pad 0 24px, fs 14px
// lg: h=42px, pad 0 24px, fs 16px
export type ZbButtonSize = 'sm' | 'md' | 'lg';

@Component({
  selector: 'zb-button',
  standalone: true,
  imports: [CommonModule, ZbIconComponent],
  templateUrl: './zb-button.component.html',
  styleUrl: './zb-button.component.scss',
})
export class ZbButtonComponent {
  @Input() variant: ZbButtonVariant = 'primary';
  @Input() size: ZbButtonSize = 'md';
  @Input() disabled = false;
  @Input() loading = false;
  @Input() type: 'button' | 'submit' | 'reset' = 'button';
  @Input() iconLeft?: string;
  @Input() iconRight?: string;
  @Input() icon?: string;         // for icon-only variant
  @Input() ariaLabel?: string;    // required for icon-only (accessibility)

  /** ¿El icono existe como SVG de Figma? Si no, se pinta con la fuente
   *  material-icons (iconos que el diseño no define, p.ej. los de adminZebra). */
  isFigmaIcon(name?: string): name is ZbIconName { return hasZbIcon(name); }

  @HostBinding('class') get hostClass() {
    const classes = ['zb-btn', `zb-btn--${this.variant}`, `zb-btn--${this.size}`];
    if (this.disabled || this.loading) classes.push('zb-btn--disabled');
    return classes.join(' ');
  }
}
