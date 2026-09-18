import { Component, Input, Output, EventEmitter, HostListener, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ZbIconComponent } from '@app/shared/components/zb-icon/zb-icon.component';

@Component({
  selector: 'zb-table-toolbar',
  standalone: true,
  imports: [CommonModule, ZbIconComponent],
  templateUrl: './zb-table-toolbar.component.html',
  styleUrl: './zb-table-toolbar.component.scss',
})
export class ZbTableToolbarComponent {
  // Left: page-size selector
  @Input() showPageSize = true;
  @Input() pageSize = 100;
  @Input() pageSizeOptions: number[] = [10, 25, 50, 100];
  @Output() pageSizeChange = new EventEmitter<number>();

  // Left: columns toggle button
  @Input() showColumnsToggle = true;
  @Input() columnsLabel = 'Columnas';
  @Output() columnsClick = new EventEmitter<void>();

  showPageSizeMenu = false;

  constructor(private el: ElementRef) {}

  @HostListener('document:click', ['$event'])
  onDocClick(e: MouseEvent): void {
    if (!this.el.nativeElement.contains(e.target)) {
      this.showPageSizeMenu = false;
    }
  }

  togglePageSizeMenu(e: MouseEvent): void {
    e.stopPropagation();
    this.showPageSizeMenu = !this.showPageSizeMenu;
  }

  selectPageSize(opt: number, e: MouseEvent): void {
    e.stopPropagation();
    this.pageSizeChange.emit(opt);
    this.showPageSizeMenu = false;
  }

  onPageSizeChange(event: Event) {
    const value = +(event.target as HTMLSelectElement).value;
    this.pageSizeChange.emit(value);
  }
}
