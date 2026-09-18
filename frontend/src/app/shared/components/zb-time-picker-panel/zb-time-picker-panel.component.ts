import { Component, Input, Output, EventEmitter, OnInit } from '@angular/core';

@Component({
  selector: 'zb-time-picker-panel',
  standalone: true,
  imports: [],
  templateUrl: './zb-time-picker-panel.component.html',
  styleUrl: './zb-time-picker-panel.component.scss',
})
export class ZbTimePickerPanelComponent implements OnInit {
  @Input() value = ''; // HH:MM (24h)

  @Output() apply  = new EventEmitter<string>();
  @Output() cancel = new EventEmitter<void>();

  hours   = 9;
  minutes = 0;
  period: 'AM' | 'PM' = 'AM';

  get hoursDisplay():   string { return String(this.hours).padStart(2, '0'); }
  get minutesDisplay(): string { return String(this.minutes).padStart(2, '0'); }
  get timeDisplay():    string { return `${this.hours}:${this.minutesDisplay}`; }

  ngOnInit() {
    if (this.value) {
      const [hStr, mStr] = this.value.split(':');
      const h = parseInt(hStr, 10);
      const m = parseInt(mStr, 10);
      this.period  = h >= 12 ? 'PM' : 'AM';
      this.hours   = h === 0 ? 12 : h > 12 ? h - 12 : h;
      this.minutes = isNaN(m) ? 0 : m;
    }
  }

  incrHours()   { this.hours   = this.hours   === 12 ? 1  : this.hours   + 1; }
  decrHours()   { this.hours   = this.hours   === 1  ? 12 : this.hours   - 1; }
  incrMinutes() { this.minutes = this.minutes === 59 ? 0  : this.minutes + 1; }
  decrMinutes() { this.minutes = this.minutes === 0  ? 59 : this.minutes - 1; }

  setPeriod(p: 'AM' | 'PM') { this.period = p; }

  onApply() {
    let h = this.hours;
    if (this.period === 'AM') h = h === 12 ? 0 : h;
    else h = h === 12 ? 12 : h + 12;
    this.apply.emit(`${String(h).padStart(2,'0')}:${this.minutesDisplay}`);
  }

  onCancel() { this.cancel.emit(); }
}
