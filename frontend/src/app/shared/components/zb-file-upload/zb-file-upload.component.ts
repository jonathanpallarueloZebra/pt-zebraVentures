import {
  Component, Input, Output, EventEmitter, signal,
  ChangeDetectionStrategy, effect, model, HostListener,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';
import { ZbButtonComponent } from '../zb-button/zb-button.component';

export interface ZbUploadFile {
  id: string;
  file: File;
  name: string;
  sizeFmt: string;
  progress: number;
  done: boolean;
}

@Component({
  selector: 'zb-file-upload',
  standalone: true,
  imports: [CommonModule, MatIconModule, ZbButtonComponent],
  templateUrl: './zb-file-upload.component.html',
  styleUrl: './zb-file-upload.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ZbFileUploadComponent {
  open = model<boolean>(false);

  @Input() title         = 'Subir documentos';
  @Input() hint          = 'PNG, JPG o PDF (máx. 1mb)';
  @Input() accept        = '.png,.jpg,.jpeg,.pdf';
  @Input() multiple      = true;
  @Input() confirmLabel  = 'Adjuntar archivos';
  @Input() cancelLabel   = 'Cancelar';

  /**
   * Ancho maximo de la tarjeta. Por defecto 480px (lo que tenia); se sube
   * cuando el footer lleva una accion extra proyectada y los tres botones no
   * caben en una linea.
   */
  @Input() maxWidth = '480px';

  /**
   * Ocultar el boton de confirmar mientras no haya ficheros, en vez de
   * mostrarlo desactivado. Util cuando el footer ya tiene otras acciones: un
   * boton gris que no se puede pulsar solo ocupa sitio.
   */
  @Input() hideConfirmUntilFiles = false;

  @Output() confirm = new EventEmitter<File[]>();
  /**
   * Se emite en cuanto se sueltan/eligen ficheros, ANTES de confirmar. Permite
   * revisarlos y avisar de lo que va a pasar (p.ej. cuantas filas del Excel
   * tienen fallos) sin que el usuario tenga que importar para descubrirlo.
   */
  @Output() filesAdded = new EventEmitter<File[]>();
  @Output() cancel  = new EventEmitter<void>();
  @Output() closed  = new EventEmitter<void>();

  files      = signal<ZbUploadFile[]>([]);
  isDragging = signal(false);

  constructor() {
    effect((onCleanup) => {
      const isOpen = this.open();
      if (typeof document === 'undefined') return;
      document.body.style.overflow = isOpen ? 'hidden' : '';
      onCleanup(() => { document.body.style.overflow = ''; });
    });
  }

  @HostListener('document:keydown.escape')
  onEscape(): void { if (this.open()) this.close(); }

  get hasFiles(): boolean { return this.files().length > 0; }

  formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  private addFiles(list: FileList): void {
    const entries: ZbUploadFile[] = Array.from(list).map((file, i) => ({
      id: `${Date.now()}-${i}-${file.name}`,
      file,
      name: file.name,
      sizeFmt: this.formatSize(file.size),
      progress: 0,
      done: false,
    }));
    this.files.update(cur => [...cur, ...entries]);
    this.filesAdded.emit(entries.map(e => e.file));

    entries.forEach(entry => {
      // Trigger CSS transition on next tick
      setTimeout(() => {
        this.files.update(all => all.map(f => f.id === entry.id ? { ...f, progress: 100 } : f));
        // Mark done after transition completes
        setTimeout(() => {
          this.files.update(all => all.map(f => f.id === entry.id ? { ...f, done: true } : f));
        }, 550);
      }, 50);
    });
  }

  onFileInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files?.length) this.addFiles(input.files);
    input.value = '';
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragging.set(true);
  }

  onDragLeave(event: DragEvent): void {
    const related = event.relatedTarget as Node | null;
    if (!(event.currentTarget as HTMLElement).contains(related)) {
      this.isDragging.set(false);
    }
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragging.set(false);
    if (event.dataTransfer?.files?.length) this.addFiles(event.dataTransfer.files);
  }

  removeFile(id: string): void {
    this.files.update(list => list.filter(f => f.id !== id));
  }

  onConfirm(): void {
    this.confirm.emit(this.files().map(f => f.file));
    this.close();
  }

  onCancel(): void {
    this.cancel.emit();
    this.close();
  }

  close(): void {
    if (!this.open()) return;
    this.files.set([]);
    this.isDragging.set(false);
    this.open.set(false);
    this.closed.emit();
  }
}
