import { Component, Input, ChangeDetectionStrategy } from '@angular/core';
import { NgStyle } from '@angular/common';

@Component({
  selector: 'zb-skeleton',
  standalone: true,
  imports: [NgStyle],
  template: `<div class="sk-bone" [ngStyle]="styles"></div>`,
  styleUrl: './zb-skeleton.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ZbSkeletonComponent {
  @Input() width  = '100%';
  @Input() height = '16px';
  @Input() radius = '6px';
  @Input() circle = false;

  get styles(): Record<string, string> {
    return {
      width:        this.circle ? this.height : this.width,
      height:       this.height,
      borderRadius: this.circle ? '50%' : this.radius,
    };
  }
}
