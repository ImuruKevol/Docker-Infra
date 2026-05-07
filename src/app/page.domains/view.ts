import { OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    public loading = signal<boolean>(true);
    public error = signal<string>('');
    public zones = signal<any[]>([]);
    public domains = signal<any[]>([]);
    public certificates = signal<any[]>([]);
    public integrations = signal<any[]>([]);

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
            this.zones.set(data.zones || []);
            this.domains.set(data.domains || []);
            this.certificates.set(data.certificates || []);
            this.integrations.set(data.integrations || []);
        } else {
            this.error.set(data?.message || '도메인 정보를 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
    }

    public cloudflare() {
        return this.integrations().find((item: any) => item.key === 'cloudflare') || {};
    }

    public statusClass(status: any) {
        if (status === true || ['active', 'ok', 'issued'].includes(status)) {
            return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        }
        if (['pending', 'none'].includes(status)) {
            return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        }
        if (['failed', 'expired', 'error'].includes(status)) {
            return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
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
