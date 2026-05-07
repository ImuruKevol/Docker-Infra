import { OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    public loading = signal<boolean>(true);
    public error = signal<string>('');
    public setup = signal<any>({});
    public health = signal<any>({});
    public advancedSettings = signal<boolean>(false);
    public general: any = {
        browser_title: 'Docker Infra',
        favicon_url: '',
        logo_url: ''
    };
    public integrations: any[] = [];

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.load();
    }

    public async alert(message: string, status: string = 'error') {
        return await this.service.modal.show({
            title: "",
            message,
            cancel: false,
            actionBtn: status,
            action: '확인',
            status
        });
    }

    public async load() {
        this.loading.set(true);
        this.error.set('');
        const { code, data } = await wiz.call("load", {});
        if (code === 200) {
            this.general = data.general || this.general;
            this.integrations = this.prepareIntegrations(data.integrations || []);
            this.setup.set(data.setup || {});
            this.health.set(data.health || {});
        } else {
            this.error.set(data?.message || '시스템 설정을 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
    }

    public prepareIntegrations(items: any[]) {
        return items.map((integration: any) => ({
            ...integration,
            field_entries: Object.keys(integration.fields || {}).map((key) => ({ key, label: key })),
        }));
    }

    public async saveGeneral() {
        const { code, data } = await wiz.call("save_general", this.general);
        if (code === 200) {
            this.general = data.general || this.general;
            await this.alert("저장되었습니다.", "success");
            return;
        }
        await this.alert(data.message || "저장할 수 없습니다.");
    }

    public async saveIntegration(integration: any) {
        const { code, data } = await wiz.call("save_integration", integration);
        if (code === 200) {
            this.general = data.general || this.general;
            this.integrations = this.prepareIntegrations(data.integrations || this.integrations);
            await this.alert("저장되었습니다.", "success");
            return;
        }
        await this.alert(data.message || "저장할 수 없습니다.");
    }

    public toggleAdvancedSettings() {
        this.advancedSettings.set(!this.advancedSettings());
    }

    public statusClass(status: any) {
        if (status === true || ['ok', 'active', 'configured'].includes(status)) {
            return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        }
        if (['degraded', 'pending'].includes(status)) {
            return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        }
        if (['error', 'failed'].includes(status)) {
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
