import { AfterViewInit, OnDestroy, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import ApexCharts from 'apexcharts';

export class Component implements OnInit, AfterViewInit, OnDestroy {
    public loading = signal<boolean>(true);
    public data = signal<any>({});
    public error = signal<string>('');
    public resourceChartBusy = signal<boolean>(false);
    public resourceChartError = signal<string>('');
    public resourceStartDate = signal<string>(this.dateInputOffset(-1));
    public resourceEndDate = signal<string>(this.dateInputOffset(0));
    public nodeChartsOpen = signal<boolean>(false);
    public activeNodeChartId = signal<string>('');
    private resourceChartInstances: any[] = [];
    private nodeChartInstances: any[] = [];
    private resourceChartTitleObservers: MutationObserver[] = [];
    private nodeChartTitleObservers: MutationObserver[] = [];
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
            this.ensureActiveNodeChart();
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

    public backupSystem() {
        return this.data()?.backup_system || {};
    }

    public backupBadgeText() {
        const backup = this.backupSystem();
        if (!backup?.enabled) return '백업 꺼짐';
        if (backup.status === 'running') return '백업 사용';
        if (backup.status === 'failed') return '백업 오류';
        return '백업 대기';
    }

    public backupBadgeClass() {
        const backup = this.backupSystem();
        if (backup?.enabled && backup.status === 'running') return this.statusClass('ok');
        if (backup?.enabled && backup.status === 'failed') return this.statusClass('failed');
        if (backup?.enabled) return this.statusClass('pending');
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }

    public nodes() {
        return this.data()?.nodes || [];
    }

    public operations() {
        return this.data()?.recent_operations || [];
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

    public domainUsage() {
        return this.data()?.domain_usage || { domains: [], summary: {} };
    }

    public domainRows() {
        return this.domainUsage()?.domains || [];
    }

    public domainSummary() {
        return this.domainUsage()?.summary || {};
    }

    public domainStatusLabel(domain: any) {
        if (domain?.last_sync_status === 'unregistered') return '미등록';
        if (!domain?.enabled) return '꺼짐';
        if (!domain?.usable_for_service) return '서비스 제외';
        if (Number(domain?.service_count || 0) > 0) return '사용 중';
        return '대기';
    }

    public domainServiceSummary(domain: any) {
        const count = Number(domain?.service_count || 0);
        if (!count) return '연결 서비스 없음';
        const names = Array.isArray(domain?.service_names) ? domain.service_names.filter((name: any) => Boolean(name)) : [];
        const preview = names.slice(0, 2).join(', ');
        if (!preview) return `연결 서비스 ${count}개`;
        const hiddenCount = Math.max(0, count - names.slice(0, 2).length);
        return hiddenCount > 0 ? `연결 서비스 ${count}개 · ${preview} 외 ${hiddenCount}개` : `연결 서비스 ${count}개 · ${preview}`;
    }

    public domainBadgeClass(domain: any) {
        if (Number(domain?.service_count || 0) > 0) return this.statusClass('ok');
        if (domain?.enabled) return this.statusClass('pending');
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
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

    private nodeChartId(chart: any) {
        return String(chart?.node_id || '');
    }

    private ensureActiveNodeChart() {
        const charts = this.nodeResourceCharts();
        if (!charts.length) {
            this.activeNodeChartId.set('');
            return;
        }
        const activeId = String(this.activeNodeChartId() || '');
        if (activeId && charts.some((chart: any) => this.nodeChartId(chart) === activeId)) return;
        this.activeNodeChartId.set(this.nodeChartId(charts[0]));
    }

    public activeNodeChart() {
        const activeId = String(this.activeNodeChartId() || '');
        const charts = this.nodeResourceCharts();
        return charts.find((chart: any) => this.nodeChartId(chart) === activeId) || charts[0] || null;
    }

    public isActiveNodeChart(chart: any) {
        return this.nodeChartId(chart) === String(this.activeNodeChartId() || '');
    }

    public async selectNodeChart(nodeId: any) {
        this.activeNodeChartId.set(String(nodeId || ''));
        await this.service.render();
        this.scheduleResourceChartRender();
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
        const count = chart?.count ?? this.nodeChartRows(chart).length;
        const sourceCount = chart?.source_count ?? chart?.sample_count ?? count;
        const host = node?.host || chart?.node_id || '-';
        return `${host} · ${count || 0}개 구간 · ${sourceCount || 0}개 샘플`;
    }

    public resourceRangeText() {
        const chart = this.resourceChart();
        const count = chart?.count ?? this.resourceRows().length;
        const sourceCount = chart?.source_count ?? chart?.sample_count ?? count;
        return `${this.resourceStartDate()} ~ ${this.resourceEndDate()} · ${count || 0}개 구간 · ${sourceCount || 0}개 샘플`;
    }

    public async openNodeCharts() {
        this.ensureActiveNodeChart();
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

    private chartStatValue(row: any, key: string, stat: string) {
        const statKey = `${key}_${stat}`;
        const statValue = Number(row?.[statKey]);
        if (!Number.isNaN(statValue)) return Math.max(0, Math.min(100, statValue));
        return this.chartValue(row, key);
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

    private chartDateFromValue(value: any) {
        if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
        if (typeof value === 'number') {
            const date = new Date(value);
            return Number.isNaN(date.getTime()) ? null : date;
        }
        const raw = String(value || '').trim();
        if (!raw) return null;
        if (/^\d+$/.test(raw)) {
            const date = new Date(Number(raw));
            return Number.isNaN(date.getTime()) ? null : date;
        }
        const hasTimezone = /(?:z|[+-]\d{2}:?\d{2})$/i.test(raw);
        const looksLikeDateTime = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(raw);
        const normalized = looksLikeDateTime && !hasTimezone ? `${raw.replace(' ', 'T')}Z` : raw;
        const date = new Date(normalized);
        return Number.isNaN(date.getTime()) ? null : date;
    }

    private formatChartAxisTime(value: any) {
        const date = this.chartDateFromValue(value);
        if (!date) return String(value || '');
        return new Intl.DateTimeFormat('ko-KR', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false,
        }).format(date);
    }

    private formatChartTooltipTime(value: any) {
        const date = this.chartDateFromValue(value);
        if (!date) return String(value || '');
        return new Intl.DateTimeFormat('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
            timeZoneName: 'short',
        }).format(date);
    }

    private formatChartTooltipPercent(value: any) {
        if (Array.isArray(value)) {
            return `${value.map((item) => Number(item || 0).toFixed(1)).join(' - ')}%`;
        }
        return `${Number(value || 0).toFixed(1)}%`;
    }

    private chartTooltipTime(value: any, options: any) {
        const seriesX = options?.seriesX || options?.w?.globals?.seriesX || [];
        const seriesIndex = Number(options?.seriesIndex ?? 0);
        const dataPointIndex = Number(options?.dataPointIndex ?? -1);
        const raw = seriesX?.[seriesIndex]?.[dataPointIndex] ?? value;
        return this.formatChartTooltipTime(raw);
    }

    private escapeChartTooltipText(value: any) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    private rangeTooltipOptions(rows: any[], metricKey: string, label: string, color: string) {
        return {
            theme: this.isDarkMode() ? 'dark' : 'light',
            custom: (options: any) => {
                const dataPointIndex = Number(options?.dataPointIndex ?? -1);
                const seriesIndex = Number(options?.seriesIndex ?? 0);
                const row = rows[dataPointIndex] || {};
                const seriesX = options?.w?.globals?.seriesX || options?.seriesX || [];
                const rawTime = seriesX?.[seriesIndex]?.[dataPointIndex] ?? row?.reported_at;
                const bg = this.isDarkMode() ? '#18181b' : '#ffffff';
                const fg = this.isDarkMode() ? '#f4f4f5' : '#18181b';
                const muted = this.isDarkMode() ? '#a1a1aa' : '#71717a';
                const border = this.isDarkMode() ? '#3f3f46' : '#e4e4e7';
                const time = this.escapeChartTooltipText(this.formatChartTooltipTime(rawTime));
                const min = this.escapeChartTooltipText(this.formatChartTooltipPercent(this.chartStatValue(row, metricKey, 'min')));
                const avg = this.escapeChartTooltipText(this.formatChartTooltipPercent(this.chartStatValue(row, metricKey, 'avg')));
                const max = this.escapeChartTooltipText(this.formatChartTooltipPercent(this.chartStatValue(row, metricKey, 'max')));
                const title = this.escapeChartTooltipText(label);
                return `
                    <div style="min-width: 170px; border: 1px solid ${border}; background: ${bg}; color: ${fg}; border-radius: 6px; box-shadow: 0 10px 24px rgba(15, 23, 42, 0.16);">
                        <div style="border-bottom: 1px solid ${border}; padding: 7px 10px; font-size: 12px; font-weight: 600;">${time}</div>
                        <div style="display: grid; gap: 5px; padding: 8px 10px; font-size: 12px;">
                            <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px;"><span style="color: ${muted};"><span style="display: inline-block; width: 8px; height: 8px; margin-right: 6px; border-radius: 999px; background: ${color}; opacity: 0.45;"></span>${title} Min</span><strong>${min}</strong></div>
                            <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px;"><span style="color: ${muted};"><span style="display: inline-block; width: 8px; height: 8px; margin-right: 6px; border-radius: 999px; background: ${color};"></span>${title} Average</span><strong>${avg}</strong></div>
                            <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px;"><span style="color: ${muted};"><span style="display: inline-block; width: 8px; height: 8px; margin-right: 6px; border-radius: 999px; background: ${color}; opacity: 0.75;"></span>${title} Max</span><strong>${max}</strong></div>
                        </div>
                    </div>
                `;
            },
        };
    }

    private stripApexChartTitles(element: HTMLElement) {
        element.querySelectorAll('[title]').forEach((node: Element) => node.removeAttribute('title'));
        element.querySelectorAll('title').forEach((node: Element) => node.remove());
    }

    private watchApexChartTitles(element: HTMLElement, observers: MutationObserver[]) {
        this.stripApexChartTitles(element);
        if (typeof MutationObserver === 'undefined') return;
        const observer = new MutationObserver(() => this.stripApexChartTitles(element));
        observer.observe(element, { subtree: true, childList: true, attributes: true, attributeFilter: ['title'] });
        observers.push(observer);
    }

    private disconnectChartTitleObservers(observers: MutationObserver[]) {
        observers.forEach((observer: MutationObserver) => observer.disconnect());
        observers.length = 0;
    }

    private chartTimestamp(row: any) {
        const date = this.chartDateFromValue(row?.reported_at);
        return date ? date.getTime() : String(row?.reported_at || '');
    }

    private apexBaseOptions(height: number = 240) {
        return {
            chart: {
                height,
                toolbar: { show: false },
                zoom: { enabled: false },
                animations: { enabled: false },
                background: 'transparent',
            },
            theme: { mode: this.isDarkMode() ? 'dark' : 'light' },
            dataLabels: { enabled: false },
            legend: { labels: { colors: this.chartTextColor() } },
            grid: { borderColor: this.chartGridColor(), strokeDashArray: 3 },
            xaxis: {
                type: 'datetime',
                labels: {
                    datetimeUTC: false,
                    style: { colors: this.chartTextColor() },
                    formatter: (value: any, timestamp: number) => this.formatChartAxisTime(timestamp || value),
                },
                axisBorder: { color: this.chartGridColor() },
                axisTicks: { color: this.chartGridColor() },
            },
            yaxis: {
                min: 0,
                max: 100,
                labels: { style: { colors: this.chartTextColor() }, formatter: (value: number) => `${value.toFixed(0)}%` },
            },
            tooltip: {
                theme: this.isDarkMode() ? 'dark' : 'light',
                x: { formatter: (value: any, options: any) => this.chartTooltipTime(value, options) },
                y: { formatter: (value: any) => this.formatChartTooltipPercent(value) },
            },
        };
    }

    private cpuChartOptions(rows: any[], height: number = 240) {
        return {
            ...this.apexBaseOptions(height),
            chart: { ...this.apexBaseOptions(height).chart, type: 'rangeArea' },
            tooltip: this.rangeTooltipOptions(rows, 'cpu_percent', 'CPU', '#0ea5e9'),
            colors: ['rgba(14,165,233,0.22)', '#0ea5e9'],
            stroke: { curve: 'smooth', width: [0, 2] },
            fill: { opacity: [0.22, 1] },
            series: [
                {
                    name: 'Min/Max',
                    type: 'rangeArea',
                    data: rows.map((row: any) => ({ x: this.chartTimestamp(row), y: [this.chartStatValue(row, 'cpu_percent', 'min'), this.chartStatValue(row, 'cpu_percent', 'max')] })),
                },
                {
                    name: 'Average',
                    type: 'line',
                    data: rows.map((row: any) => ({ x: this.chartTimestamp(row), y: this.chartStatValue(row, 'cpu_percent', 'avg') })),
                },
            ],
        };
    }

    private memoryChartOptions(rows: any[], height: number = 240) {
        return {
            ...this.apexBaseOptions(height),
            chart: { ...this.apexBaseOptions(height).chart, type: 'rangeArea' },
            tooltip: this.rangeTooltipOptions(rows, 'memory_used_percent', 'Memory', '#10b981'),
            colors: ['#bbf7d0', '#10b981'],
            stroke: { curve: 'smooth', width: [0, 2] },
            fill: { opacity: [0.22, 1] },
            series: [
                {
                    name: 'Min/Max',
                    type: 'rangeArea',
                    data: rows.map((row: any) => ({ x: this.chartTimestamp(row), y: [this.chartStatValue(row, 'memory_used_percent', 'min'), this.chartStatValue(row, 'memory_used_percent', 'max')] })),
                },
                {
                    name: 'Average',
                    type: 'line',
                    data: rows.map((row: any) => ({ x: this.chartTimestamp(row), y: this.chartStatValue(row, 'memory_used_percent', 'avg') })),
                },
            ],
        };
    }

    private storageChartOptions(rows: any[], height: number = 240) {
        return {
            ...this.apexBaseOptions(height),
            chart: { ...this.apexBaseOptions(height).chart, type: 'line' },
            colors: ['#f59e0b'],
            stroke: { curve: 'smooth', width: 2 },
            series: [
                { name: 'Storage Used', data: rows.map((row: any) => ({ x: this.chartTimestamp(row), y: this.chartStatValue(row, 'storage_used_percent', 'avg') })) },
            ],
        };
    }

    private chartOptions(rows: any[], metric: string, height: number = 240) {
        if (metric === 'memory') return this.memoryChartOptions(rows, height);
        if (metric === 'storage') return this.storageChartOptions(rows, height);
        return this.cpuChartOptions(rows, height);
    }

    private createApexChart(element: HTMLElement, rows: any[], metric: string, height: number = 240, titleObservers: MutationObserver[] = this.resourceChartTitleObservers) {
        const chart = new ApexCharts(element, this.chartOptions(rows, metric, height) as any);
        const rendered = chart.render();
        this.watchApexChartTitles(element, titleObservers);
        Promise.resolve(rendered).then(() => this.stripApexChartTitles(element));
        return chart;
    }

    private destroyResourceChart() {
        this.disconnectChartTitleObservers(this.resourceChartTitleObservers);
        this.resourceChartInstances.forEach((chart: any) => chart.destroy());
        this.resourceChartInstances = [];
    }

    private destroyNodeCharts() {
        this.disconnectChartTitleObservers(this.nodeChartTitleObservers);
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

    private resourceChartElements() {
        return Array.from(document.querySelectorAll('[data-resource-chart]')) as HTMLElement[];
    }

    private nodeChartElements() {
        return Array.from(document.querySelectorAll('[data-node-resource-chart]')) as HTMLElement[];
    }

    private renderResourceChart() {
        const rows = this.resourceRows();
        this.destroyResourceChart();
        if (rows.length) {
            this.resourceChartElements().forEach((element: HTMLElement) => {
                const metric = String(element.getAttribute('data-resource-chart') || 'cpu');
                this.resourceChartInstances.push(this.createApexChart(element, rows, metric, 240, this.resourceChartTitleObservers));
            });
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
        this.nodeChartElements().forEach((element: HTMLElement) => {
            const nodeId = String(element.getAttribute('data-node-resource-chart') || '');
            const metric = String(element.getAttribute('data-node-resource-metric') || 'cpu');
            const chart = chartByNodeId.get(nodeId);
            const rows = chart?.rows || [];
            if (!rows.length) return;
            this.nodeChartInstances.push(this.createApexChart(element, rows, metric, 180, this.nodeChartTitleObservers));
        });
    }

    public metricHistoryText() {
        const history = this.metricHistory();
        if (!history?.files) return '기록 파일 없음';
        return `${history.files}개 기록 파일`;
    }
}
