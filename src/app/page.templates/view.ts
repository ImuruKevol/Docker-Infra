import { OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    public loading = signal<boolean>(true);
    public error = signal<string>('');
    public templates = signal<any[]>([]);
    public versions = signal<any[]>([]);
    public setup = signal<any>({});

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.load();
    }

    public async load() {
        this.loading.set(true);
        this.error.set('');
        const { code, data } = await wiz.call("load", {});
        if (code === 200) {
            this.templates.set(data.templates || []);
            this.versions.set(data.versions || []);
            this.setup.set(data.setup || {});
        } else {
            this.error.set(data?.message || '템플릿 정보를 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
    }

    public statusClass(enabled: any) {
        if (enabled === true || enabled === 'active') {
            return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        }
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }

    public formatDate(value: any) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString();
    }
}
