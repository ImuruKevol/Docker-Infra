import { OnDestroy, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

type OperationStatus = '' | 'pending' | 'running' | 'succeeded' | 'failed' | 'canceled';

export class Component implements OnInit, OnDestroy {
    public loading = signal<boolean>(true);
    public error = signal<string>('');
    public operations = signal<any[]>([]);
    public statusCounts = signal<any>({});
    public selectedOperation = signal<any>(null);
    public detailOpen = signal<boolean>(false);
    public detailBusy = signal<boolean>(false);
    public query = signal<string>('');
    public statusFilter = signal<OperationStatus>('');
    public limit = signal<number>(80);
    private pollTimer: any = null;

    public statusFilters: { value: OperationStatus; label: string }[] = [
        { value: '', label: '전체' },
        { value: 'running', label: '실행 중' },
        { value: 'pending', label: '대기' },
        { value: 'succeeded', label: '성공' },
        { value: 'failed', label: '실패' },
        { value: 'canceled', label: '취소' },
    ];

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.load();
    }

    public ngOnDestroy() {
        this.stopPolling();
    }

    public async load(showLoading: boolean = true) {
        if (showLoading) this.loading.set(true);
        this.error.set('');
        const { code, data } = await wiz.call('load', {
            query: this.query(),
            status: this.statusFilter(),
            limit: this.limit(),
        });
        if (code === 200) {
            this.operations.set(data.operations || []);
            this.statusCounts.set(data.status_counts || {});
        } else {
            this.error.set(data?.message || '작업 로그를 불러올 수 없습니다.');
        }
        if (showLoading) this.loading.set(false);
        await this.service.render();
    }

    public async applyFilters() {
        await this.load(true);
    }

    public async selectStatus(status: OperationStatus) {
        this.statusFilter.set(status);
        await this.load(true);
    }

    public async openOperation(operation: any) {
        if (!operation?.id) return;
        this.selectedOperation.set(operation);
        this.detailOpen.set(true);
        await this.refreshDetail();
        this.startPolling();
    }

    public closeDetail() {
        this.stopPolling();
        this.detailOpen.set(false);
        this.selectedOperation.set(null);
    }

    public async refreshDetail(showBusy: boolean = true) {
        const operationId = this.selectedOperation()?.id;
        if (!operationId) return;
        if (showBusy) this.detailBusy.set(true);
        const { code, data } = await wiz.call('detail', { operation_id: operationId });
        if (code === 200) {
            this.selectedOperation.set(data.operation || null);
        } else if (showBusy) {
            this.error.set(data?.message || '작업 로그 상세를 불러올 수 없습니다.');
        }
        this.detailBusy.set(false);
        await this.service.render();
    }

    private startPolling() {
        this.stopPolling();
        if (!this.isActiveOperation(this.selectedOperation())) return;
        this.pollTimer = setInterval(async () => {
            await this.refreshDetail(false);
            if (!this.isActiveOperation(this.selectedOperation())) this.stopPolling();
        }, 2000);
    }

    private stopPolling() {
        if (!this.pollTimer) return;
        clearInterval(this.pollTimer);
        this.pollTimer = null;
    }

    public isActiveOperation(operation: any) {
        return ['pending', 'running'].includes(String(operation?.status || '').toLowerCase());
    }

    public operationOutput() {
        return this.selectedOperation()?.output || [];
    }

    public statusLabel(status: string) {
        const labels: any = {
            ok: 'OK',
            pending: 'Pending',
            running: 'Running',
            succeeded: 'Succeeded',
            failed: 'Failed',
            canceled: 'Canceled',
        };
        return labels[status] || status || '-';
    }

    public statusClass(status: string) {
        if (['ok', 'active', 'succeeded'].includes(status)) return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        if (['running', 'pending', 'degraded'].includes(status)) return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        if (['failed', 'canceled', 'error'].includes(status)) return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }

    public statusButtonClass(status: OperationStatus) {
        const active = this.statusFilter() === status;
        if (active) return 'border-zinc-950 bg-zinc-950 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-950';
        return 'border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800';
    }

    public statusCount(status: OperationStatus) {
        if (!status) return Object.values(this.statusCounts()).reduce((sum: number, value: any) => sum + Number(value || 0), 0);
        return Number(this.statusCounts()?.[status] || 0);
    }

    public operationServerText(operation: any) {
        const label = operation?.server?.label;
        if (label && label !== '-') return label;
        return operation?.node_name || operation?.node_host || '서버 미기록';
    }

    public operationTargetText(operation: any) {
        const label = operation?.target_label;
        if (label && label !== '-') return label;
        return operation?.target_type || '대상 미기록';
    }

    public operationSummary(operation: any) {
        return operation?.action_text || operation?.operation_label || operation?.type || '-';
    }

    public outputCountText(operation: any) {
        const count = Number(operation?.output_count || operation?.output?.length || 0);
        return `${count}개 로그`;
    }

    public operationDurationText(operation: any) {
        const started = new Date(operation?.started_at || operation?.created_at || '');
        const finished = new Date(operation?.finished_at || operation?.updated_at || '');
        if (Number.isNaN(started.getTime()) || Number.isNaN(finished.getTime()) || finished.getTime() < started.getTime()) return '-';
        const seconds = Math.round((finished.getTime() - started.getTime()) / 1000);
        if (seconds < 60) return `${seconds}초`;
        return `${Math.floor(seconds / 60)}분 ${seconds % 60}초`;
    }

    public operationStreamClass(stream: string) {
        if (stream === 'stderr') return 'text-rose-300';
        if (stream === 'system') return 'text-amber-200';
        return 'text-zinc-100';
    }

    public formatDate(value: any) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString();
    }
}
