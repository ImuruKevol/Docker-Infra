import { AfterViewInit, OnDestroy, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import Chart from 'chart.js/auto';

export class Component implements OnInit, AfterViewInit, OnDestroy {
    public loading = signal<boolean>(true);
    public data = signal<any>({});
    public error = signal<string>('');
    public resourceChartBusy = signal<boolean>(false);
    public resourceChartError = signal<string>('');
    public resourceStartDate = signal<string>(this.dateInputOffset(-1));
    public resourceEndDate = signal<string>(this.dateInputOffset(0));
    public nodeChartsOpen = signal<boolean>(false);
    private resourceChartInstance: any = null;
    private nodeChartInstances: any[] = [];
    private resourceChartRenderTimer: ReturnType<typeof setTimeout> | null = null;

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.load();
    }

    public ngAfterViewInit() {
        this.scheduleResourceChartRender();
    }

    public ngOnDestroy() {
        this.cancelResourceChartRender();
        this.destroyResourceChart();
        this.destroyNodeCharts();
    }

    private dateInputOffset(offsetDays: number) {
        const date = new Date();
        date.setDate(date.getDate() + offsetDays);
        date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
        return date.toISOString().slice(0, 10);
    }

    private dateStartIso(value: string) {
        if (!value) return '';
        const date = new Date(`${value}T00:00:00.000`);
        return Number.isNaN(date.getTime()) ? '' : date.toISOString();
    }

    private dateEndIso(value: string) {
        if (!value) return '';
        const date = new Date(`${value}T23:59:59.999`);
        return Number.isNaN(date.getTime()) ? '' : date.toISOString();
    }

    private resourceRangePayload() {
        const startDate = this.resourceStartDate() || this.dateInputOffset(-1);
        const endDate = this.resourceEndDate() || startDate;
        return {
            start_date: startDate,
            end_date: endDate,
            start_at: this.dateStartIso(startDate),
            end_at: this.dateEndIso(endDate),
        };
    }

    public async load(showPageLoading: boolean = true) {
        if (showPageLoading) this.loading.set(true);
        this.resourceChartBusy.set(!showPageLoading);
        if (showPageLoading) this.error.set('');
        this.resourceChartError.set('');
        await this.service.render();

        const { code, data } = await wiz.call("overview", this.resourceRangePayload());
        if (code === 200) {
            this.data.set(data || {});
        } else {
            const message = data?.message || 'Dashboard를 불러올 수 없습니다.';
            if (showPageLoading) this.error.set(message);
            else this.resourceChartError.set(message);
        }

        if (showPageLoading) this.loading.set(false);
        this.resourceChartBusy.set(false);
        await this.service.render();
        this.scheduleResourceChartRender();
    }

    public async applyResourceRange() {
        await this.load(false);
    }

    public counts() {
        return this.data()?.counts || {};
    }

    public stats() {
        const counts = this.counts();
        const operations = this.data()?.operation_statuses || {};
        return [
            { label: 'Servers', value: counts.nodes || 0, icon: 'fa-server', tone: 'emerald' },
            { label: 'Services', value: counts.services || 0, icon: 'fa-layer-group', tone: 'sky' },
            { label: 'Images', value: counts.images || 0, icon: 'fa-cubes', tone: 'violet' },
            { label: '실행 중 작업', value: operations.running || 0, icon: 'fa-bars-progress', tone: 'amber' },
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

    public operations() {
        return this.data()?.recent_operations || [];
    }

    public integrations() {
        return this.data()?.integrations || [];
    }

    public metricHistory() {
        return this.data()?.node_metric_history || {};
    }

    public resourceChart() {
        return this.data()?.node_resource_chart || { rows: [] };
    }

    public resourceRows() {
        return this.resourceChart()?.rows || [];
    }

    public nodeResourceCharts() {
        return this.data()?.node_resource_charts || [];
    }

    public nodeChartRows(chart: any) {
        return chart?.rows || [];
    }

    public nodeChartNode(chart: any) {
        if (chart?.node) return chart.node;
        const nodeId = String(chart?.node_id || '');
        return this.nodes().find((node: any) => String(node?.id || '') === nodeId) || {};
    }

    public nodeChartTitle(chart: any) {
        const node = this.nodeChartNode(chart);
        return node?.name || chart?.node_id || 'Server';
    }

    public nodeChartSubtitle(chart: any) {
        const node = this.nodeChartNode(chart);
        const count = chart?.source_count ?? chart?.count ?? this.nodeChartRows(chart).length;
        const host = node?.host || chart?.node_id || '-';
        return `${host} · ${count || 0}개 샘플`;
    }

    public resourceRangeText() {
        const chart = this.resourceChart();
        const count = chart?.source_count ?? chart?.count ?? this.resourceRows().length;
        return `${this.resourceStartDate()} ~ ${this.resourceEndDate()} · ${count || 0}개 샘플`;
    }

    public async openNodeCharts() {
        this.nodeChartsOpen.set(true);
        await this.service.render();
        this.scheduleResourceChartRender();
    }

    public closeNodeCharts() {
        this.nodeChartsOpen.set(false);
        this.destroyNodeCharts();
    }

    public nodeMetric(node: any) {
        return node?.latest_metric || {};
    }

    public nodeMetricPercent(node: any, key: string) {
        const metric = this.nodeMetric(node);
        let value: any = null;
        if (key === 'cpu') value = metric.cpu_percent;
        if (key === 'memory') value = metric.memory?.used_percent;
        if (key === 'storage') value = metric.storage?.used_percent;
        if (value === null || value === undefined || value === '') return '-';
        const numeric = Number(value);
        if (Number.isNaN(numeric)) return '-';
        return `${numeric.toFixed(1)}%`;
    }

    public nodeContainerSummary(node: any) {
        const containers = this.nodeMetric(node)?.containers || {};
        const summary = containers.summary || {};
        if (summary.total !== undefined) return summary;
        const items = Array.isArray(containers.items) ? containers.items : [];
        const running = items.filter((item: any) => String(item?.state || '').toLowerCase() === 'running').length;
        return { total: items.length, running, stopped: Math.max(0, items.length - running) };
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

    private chartValue(row: any, key: string) {
        const value = Number(row?.[key]);
        if (Number.isNaN(value)) return 0;
        return Math.max(0, Math.min(100, value));
    }

    public formatChartTime(value: any) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value).slice(0, 16);
        return date.toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    }

    private isDarkMode() {
        return Boolean(document.documentElement.classList.contains('dark'));
    }

    private chartTextColor() {
        return this.isDarkMode() ? '#d4d4d8' : '#3f3f46';
    }

    private chartGridColor() {
        return this.isDarkMode() ? 'rgba(63,63,70,0.9)' : 'rgba(228,228,231,0.95)';
    }

    private chartConfig(rows: any[]) {
        return {
            type: 'line',
            data: {
                labels: rows.map((row: any) => this.formatChartTime(row?.reported_at)),
                datasets: [
                    {
                        label: 'CPU',
                        data: rows.map((row: any) => this.chartValue(row, 'cpu_percent')),
                        borderColor: '#0ea5e9',
                        backgroundColor: 'rgba(14,165,233,0.12)',
                        tension: 0.25,
                        pointRadius: rows.length > 120 ? 0 : 2,
                    },
                    {
                        label: 'Memory',
                        data: rows.map((row: any) => this.chartValue(row, 'memory_used_percent')),
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16,185,129,0.12)',
                        tension: 0.25,
                        pointRadius: rows.length > 120 ? 0 : 2,
                    },
                    {
                        label: 'Storage',
                        data: rows.map((row: any) => this.chartValue(row, 'storage_used_percent')),
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245,158,11,0.12)',
                        tension: 0.25,
                        pointRadius: rows.length > 120 ? 0 : 2,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: this.chartTextColor(), usePointStyle: true, boxWidth: 8 },
                    },
                    tooltip: {
                        callbacks: {
                            label: (context: any) => `${context.dataset.label}: ${Number(context.parsed.y || 0).toFixed(1)}%`,
                        },
                    },
                },
                scales: {
                    x: {
                        ticks: { color: this.chartTextColor(), maxRotation: 0, autoSkip: true, maxTicksLimit: 6 },
                        grid: { color: this.chartGridColor() },
                    },
                    y: {
                        min: 0,
                        max: 100,
                        ticks: { color: this.chartTextColor(), callback: (value: any) => `${value}%` },
                        grid: { color: this.chartGridColor() },
                    },
                },
            },
        };
    }

    private destroyResourceChart() {
        if (!this.resourceChartInstance) return;
        this.resourceChartInstance.destroy();
        this.resourceChartInstance = null;
    }

    private destroyNodeCharts() {
        this.nodeChartInstances.forEach((chart: any) => chart.destroy());
        this.nodeChartInstances = [];
    }

    private cancelResourceChartRender() {
        if (!this.resourceChartRenderTimer) return;
        clearTimeout(this.resourceChartRenderTimer);
        this.resourceChartRenderTimer = null;
    }

    private scheduleResourceChartRender() {
        this.cancelResourceChartRender();
        this.resourceChartRenderTimer = setTimeout(() => {
            this.resourceChartRenderTimer = null;
            requestAnimationFrame(() => this.renderResourceChart());
        }, 0);
    }

    private resourceChartCanvasElement() {
        return document.querySelector('[data-resource-chart-canvas="dashboard"]') as HTMLCanvasElement | null;
    }

    private nodeChartCanvasElements() {
        return Array.from(document.querySelectorAll('[data-node-resource-chart-canvas]')) as HTMLCanvasElement[];
    }

    private renderResourceChart() {
        const canvas = this.resourceChartCanvasElement();
        const rows = this.resourceRows();
        this.destroyResourceChart();
        if (canvas && rows.length) {
            this.resourceChartInstance = new Chart(canvas, this.chartConfig(rows) as any);
        }
        if (this.nodeChartsOpen()) {
            this.renderNodeCharts();
        } else {
            this.destroyNodeCharts();
        }
    }

    private renderNodeCharts() {
        this.destroyNodeCharts();
        const charts = this.nodeResourceCharts();
        if (!charts.length) return;
        const chartByNodeId = new Map(charts.map((chart: any) => [String(chart?.node_id || ''), chart]));
        this.nodeChartCanvasElements().forEach((canvas: HTMLCanvasElement) => {
            const nodeId = String(canvas.getAttribute('data-node-resource-chart-canvas') || '');
            const chart = chartByNodeId.get(nodeId);
            const rows = chart?.rows || [];
            if (!rows.length) return;
            this.nodeChartInstances.push(new Chart(canvas, this.chartConfig(rows) as any));
        });
    }

    public metricHistoryText() {
        const history = this.metricHistory();
        if (!history?.files) return '기록 파일 없음';
        return `${history.files}개 기록 파일`;
    }
}
