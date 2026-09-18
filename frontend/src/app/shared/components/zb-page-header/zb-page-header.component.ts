import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'zb-page-header',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './zb-page-header.component.html',
  styleUrl: './zb-page-header.component.scss',
})
export class ZbPageHeaderComponent {
  @Input({ required: true }) title!: string;
  @Input() subtitle?: string;

  // Sidebar collapse toggle — set true to show the dark tab on the left edge
  @Input() showSidebarToggle = false;
  @Input() sidebarCollapsed = false;
  @Output() sidebarToggle = new EventEmitter<void>();
}
