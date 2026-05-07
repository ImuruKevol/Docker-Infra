import { OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    public loading = signal<boolean>(true);
    public data = signal<any>({});
    public error = signal<string>('');

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.load();
    }

    public async load() {
        this.loading.set(true);
        this.error.set('');
        await this.service.render();

        const { code, data } = await wiz.call("overview", {});
        if (code === 200) {
            this.data.set(data || {});
        } else {
            this.error.set(data?.message || 'Dashboard를 불러올 수 없습니다.');
        }

        this.loading.set(false);
        await this.service.render();
    }

    public counts() {
        return this.data()?.counts || {};
    }

    public stats() {
        const counts = this.counts();
        const jobs = this.data()?.job_statuses || {};
        return [
            { label: 'Servers', value: counts.nodes || 0, icon: 'fa-server', tone: 'emerald' },
            { label: 'Services', value: counts.services || 0, icon: 'fa-layer-group', tone: 'sky' },
            { label: 'Images', value: counts.images || 0, icon: 'fa-cubes', tone: 'violet' },
            { label: 'Running jobs', value: jobs.running || 0, icon: 'fa-bars-progress', tone: 'amber' },
        ];
    }

    public setup() {
        return this.data()?.setup || {};
    }

    public health() {
        return this.data()?.health || {};
    }

    public nodes() {
        return this.data()?.nodes || [];
    }

    public jobs() {
        return this.data()?.recent_jobs || [];
    }

    public integrations() {
        return this.data()?.integrations || [];
    }

    public statusLabel(status: string) {
        const labels: any = {
            ok: 'OK',
            degraded: 'Degraded',
            active: 'Active',
            pending: 'Pending',
            running: 'Running',
            succeeded: 'Succeeded',
            failed: 'Failed',
            canceled: 'Canceled',
            draft: 'Draft',
        };
        return labels[status] || status || '-';
    }

    public statusClass(status: string) {
        if (['ok', 'active', 'succeeded'].includes(status)) {
            return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        }
        if (['running', 'pending', 'degraded'].includes(status)) {
            return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        }
        if (['failed', 'canceled', 'error'].includes(status)) {
            return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        }
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }

    public statIconClass(tone: string) {
        const tones: any = {
            emerald: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300',
            sky: 'bg-sky-50 text-sky-700 dark:bg-sky-950/50 dark:text-sky-300',
            violet: 'bg-violet-50 text-violet-700 dark:bg-violet-950/50 dark:text-violet-300',
            amber: 'bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300',
        };
        return tones[tone] || tones.sky;
    }

    public formatDate(value: any) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString();
    }
}
