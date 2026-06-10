import { OnInit, Input } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    @Input() model: any = null;

    constructor(public service: Service) {
        if (!this.model) this.model = service.modal;
    }

    public async ngOnInit() {
    }

    public btnColorClass() {
        const base = 'inline-flex h-9 min-w-[86px] items-center justify-center rounded-md px-3 text-sm font-semibold text-white transition disabled:opacity-60';
        if (this.model.opts.status == 'warning')
            return `${base} bg-amber-600 hover:bg-amber-500`;
        if (this.model.opts.status == 'success')
            return `${base} bg-zinc-950 hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-950 dark:hover:bg-zinc-200`;
        return `${base} bg-rose-600 hover:bg-rose-500`;
    }

    public statusIconWrapClass() {
        if (this.model.opts.status == 'warning')
            return 'bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300';
        if (this.model.opts.status == 'success')
            return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300';
        return 'bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300';
    }

    public statusIconClass() {
        if (this.model.opts.status == 'warning') return 'fa-triangle-exclamation';
        if (this.model.opts.status == 'success') return 'fa-circle-check';
        return 'fa-circle-exclamation';
    }

    public cancelText() {
        if (typeof this.model?.opts?.cancelLabel === 'string' && this.model.opts.cancelLabel.trim() !== '')
            return this.model.opts.cancelLabel;
        if (typeof this.model?.opts?.cancel === 'string' && this.model.opts.cancel.trim() !== '')
            return this.model.opts.cancel;
        return '취소';
    }
}
