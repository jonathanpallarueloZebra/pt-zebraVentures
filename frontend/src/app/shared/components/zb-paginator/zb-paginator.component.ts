import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ZbIconComponent } from '@app/shared/components/zb-icon/zb-icon.component';

export type PaginatorPage = number | '...';

@Component({
  selector: 'zb-paginator',
  standalone: true,
  imports: [CommonModule, ZbIconComponent],
  templateUrl: './zb-paginator.component.html',
  styleUrl: './zb-paginator.component.scss',
})
export class ZbPaginatorComponent {
  @Input() currentPage = 1;
  @Input() totalPages = 10;
  @Output() pageChange = new EventEmitter<number>();

  get isPrevDisabled() { return this.currentPage <= 1; }
  get isNextDisabled() { return this.currentPage >= this.totalPages; }

  get pages(): PaginatorPage[] {
    const total = this.totalPages;
    const cur = this.currentPage;

    if (total <= 7) {
      return Array.from({ length: total }, (_, i) => i + 1);
    }

    // Near the start → show first 3 + ellipsis + last 3
    if (cur <= 4) {
      return [1, 2, 3, '...', total - 2, total - 1, total];
    }

    // Near the end → same mirror
    if (cur >= total - 3) {
      return [1, 2, 3, '...', total - 2, total - 1, total];
    }

    // Middle → flanking ellipses
    return [1, '...', cur - 1, cur, cur + 1, '...', total];
  }

  isNumber(p: PaginatorPage): p is number { return typeof p === 'number'; }

  goTo(page: number) {
    if (page >= 1 && page <= this.totalPages && page !== this.currentPage) {
      this.pageChange.emit(page);
    }
  }

  prevPage() { if (!this.isPrevDisabled) this.goTo(this.currentPage - 1); }
  nextPage() { if (!this.isNextDisabled) this.goTo(this.currentPage + 1); }
}
