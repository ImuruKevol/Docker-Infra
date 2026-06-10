import { OnDestroy, OnInit, signal } from '@angular/core';
import { Router, NavigationEnd } from '@angular/router';
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
    public limit = signal<number>(20);
    public pagination = signal<any>({ current: 1, start: 1, end: 1, total: 0, limit: 20 });
    private pollTimer: any = null;
    private routeSub: any = null;

    public statusFilters: { value: OperationStatus; label: string }[] = [
        { value: '', label: '전체' },
        { value: 'running', label: '실행 중' },
        { value: 'pending', label: '대기' },
        { value: 'succeeded', label: '성공' },
        { value: 'failed', label: '실패' },
        { value: 'canceled', label: '취소' },
    ];

    constructor(public service: Service, private router: Router) { }

    public async ngOnInit() {
        await this.service.init();
        await this.load(1);
        const operationId = this.routeOperationId();
        if (operationId) {
            const operation = this.operations().find((item: any) => item.id === operationId) || { id: operationId };
            await this.openOperation(operation, true);
        }
        this.routeSub = this.router.events.subscribe((event: any) => {
            if (event instanceof NavigationEnd) void this.handleRouteNavigation();
        });
    }

    public ngOnDestroy() {
        if (this.routeSub) this.routeSub.unsubscribe();
        this.stopPolling();
    }

    private routeOperationId() {
        return this.service.routeSegment('operation_id') || this.service.queryParam('operation_id') || this.service.queryParam('selected_operation_id');
    }

    private operationDetailRoute(operationId: string = this.selectedOperation()?.id || '') {
        const encodedId = this.service.encodeRouteSegment(operationId);
        return encodedId ? `/operations/${encodedId}` : '/operations';
    }

    private async handleRouteNavigation() {
        const operationId = this.routeOperationId();
        const currentId = this.selectedOperation()?.id || '';
        if (operationId === currentId) return;
        if (!operationId) {
            if (this.detailOpen()) await this.closeDetail();
            return;
        }
        const operation = this.operations().find((item: any) => item.id === operationId) || { id: operationId };
        await this.openOperation(operation, true);
    }

    private async syncOperationRoute(operationId: string = this.selectedOperation()?.id || '', replace: boolean = false) {
        const target = this.operationDetailRoute(operationId);
        if (this.service.currentPath() !== target) await this.service.routeTo(target, replace);
    }

    public async load(page: number = this.pagination().current || 1, showLoading: boolean = true) {
        if (showLoading) this.loading.set(true);
        this.error.set('');
        const requestedPage = Math.max(1, Number(page || 1));
        const requestedLimit = 20;
        if (showLoading) await this.service.render();
        const { code, data } = await wiz.call('load', {
            query: this.query(),
            status: this.statusFilter(),
            limit: requestedLimit,
            page: requestedPage,
        });
        if (code === 200) {
            const operations = data.operations || [];
            const pagination = data.pagination || {};
            const statusTotal = this.query().trim() ? 0 : this.totalFromStatusCounts(data.status_counts || {}, this.statusFilter());
            const total = this.numberValue(pagination.total, data.total, statusTotal || undefined, operations.length, 0);
            const limit = Math.max(1, this.numberValue(pagination.limit, data.page_size, requestedLimit));
            const fallbackEnd = total > 0 ? Math.ceil(total / limit) : 1;
            const end = Math.max(1, this.numberValue(pagination.end, data.pages, fallbackEnd));
            const current = Math.min(Math.max(1, this.numberValue(pagination.current, data.page, requestedPage)), end);
            this.operations.set(operations);
            this.statusCounts.set(data.status_counts || {});
            this.limit.set(limit);
            this.pagination.set({
                current,
                start: Math.max(1, Number(pagination.start || this.paginationStart(current))),
                end,
                total,
                limit,
            });
        } else {
            this.error.set(data?.message || '작업 로그를 불러올 수 없습니다.');
        }
        if (showLoading) this.loading.set(false);
        await this.service.render();
    }

    public async applyFilters() {
        await this.load(1, true);
    }

    public async selectStatus(status: OperationStatus) {
        this.statusFilter.set(status);
        await this.load(1, true);
    }

    public isOperationDetailScreen() {
        return this.detailOpen();
    }

    public async openOperation(operation: any, replaceRoute: boolean = false) {
        if (!operation?.id) return;
        this.selectedOperation.set(operation);
        this.detailOpen.set(true);
        await this.syncOperationRoute(operation.id, replaceRoute);
        await this.refreshDetail();
        this.startPolling();
    }

    public async closeDetail() {
        this.stopPolling();
        this.detailOpen.set(false);
        this.selectedOperation.set(null);
        await this.syncOperationRoute('');
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

    private numberValue(...values: any[]) {
        for (const value of values) {
            if (value === null || value === undefined || value === '') continue;
            const number = Number(value);
            if (Number.isFinite(number) && number >= 0) return number;
        }
        return 0;
    }

    private totalFromStatusCounts(counts: any, status: OperationStatus) {
        if (status) return Number(counts?.[status] || 0);
        return Object.values(counts || {}).reduce((sum: number, value: any) => sum + Number(value || 0), 0);
    }

    private paginationStart(page: number) {
        return Math.floor((Math.max(1, page) - 1) / 10) * 10 + 1;
    }

    public showPagination() {
        return Number(this.pagination()?.end || 1) > 1;
    }

    public visiblePages() {
        const pagination = this.pagination();
        const current = Number(pagination?.current || 1);
        const end = Number(pagination?.end || 1);
        const windowSize = 7;
        let start = Math.max(1, current - Math.floor(windowSize / 2));
        let finish = Math.min(end, start + windowSize - 1);
        start = Math.max(1, finish - windowSize + 1);
        const pages: number[] = [];
        for (let page = start; page <= finish; page++) pages.push(page);
        return pages;
    }

    public pageButtonClass(page: number) {
        if (Number(page) === Number(this.pagination()?.current || 1)) return 'border-zinc-950 bg-zinc-950 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-950';
        return 'border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800';
    }

    public paginationSummary() {
        const pagination = this.pagination();
        const total = Number(pagination?.total || 0);
        if (!total) return '총 0개';
        const current = Number(pagination?.current || 1);
        const limit = Number(pagination?.limit || this.limit() || 20);
        const start = (current - 1) * limit + 1;
        const end = Math.min(total, current * limit);
        return `총 ${total}개 · ${start}-${end}`;
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
