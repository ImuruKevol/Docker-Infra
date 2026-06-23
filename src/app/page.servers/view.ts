import { HostListener, OnDestroy, OnInit, signal } from '@angular/core';
import { Router, NavigationEnd } from '@angular/router';
import { Service } from '@wiz/libs/portal/season/service';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import ApexCharts from 'apexcharts';

export class Component implements OnInit, OnDestroy {
    public loading = signal<boolean>(true);
    public busy = signal<boolean>(false);
    public detailLoading = signal<boolean>(false);
    public panelRefreshing = signal<boolean>(false);
    public error = signal<string>('');
    public detailError = signal<string>('');
    public nodes = signal<any[]>([]);
    public nodesPagination = signal<any>({ current: 1, start: 1, end: 1, total: 0, limit: 20 });
    public selected = signal<any>(null);
    public detailTab = signal<string>('overview');
    public containerStats = signal<any>({ total: 0, running: 0, stopped: 0 });
    public serviceGroups = signal<any[]>([]);
    public macros = signal<any[]>([]);
    public globalMacros = signal<any[]>([]);
    public macroLoading = signal<boolean>(false);
    public macroError = signal<string>('');
    public selectedMacroId = signal<string>('');
    public macroArgsEnabled = signal<boolean>(false);
    public macroArgsInput = signal<string>('');
    public macroRunResult = signal<any>(null);
    public lastOperation = signal<any>(null);
    public serverModalOpen = signal<boolean>(false);
    public editingNodeId = signal<string>('');
    public deleteModalOpen = signal<boolean>(false);
    public deleteConfirmInput = signal<string>('');
    public deletingNode = signal<any>(null);
    public actionModalOpen = signal<boolean>(false);
    public actionTitle = signal<string>('');
    public actionResult = signal<any>(null);
    public monitoringBusy = signal<boolean>(false);
    public monitoringState = signal<any>({ running: false, collecting_node_ids: [] });
    public refreshSeconds = signal<number>(5);
    public refreshOptions = [1, 3, 5, 10];
    public resourceChartOpen = signal<boolean>(false);
    public resourceHistoryBusy = signal<boolean>(false);
    public resourceHistoryError = signal<string>('');
    public resourceHistory = signal<any>({ rows: [] });
    public resourceHistoryStartDate = signal<string>(this.todayDateInput());
    public resourceHistoryEndDate = signal<string>(this.todayDateInput());
    public pageSize = 20;
    public fileBrowserOpen = signal<boolean>(false);
    public fileBrowserBusy = signal<boolean>(false);
    public fileBrowserPath = signal<string>('');
    public fileBrowserInput = signal<string>('');
    public fileBrowserShowHidden = signal<boolean>(false);
    public composeImportName = signal<string>('');
    public fileBrowserItems = signal<any[]>([]);
    public importCandidate = signal<any>(null);
    public terminalConnecting = signal<boolean>(false);
    public terminalConnected = signal<boolean>(false);
    public terminalStatus = signal<string>('연결되지 않음');
    public terminalError = signal<string>('');
    public terminalExpanded = signal<boolean>(false);
    public serverForm: any = this.emptyServerForm();
    private refreshTimer: ReturnType<typeof setInterval> | null = null;
    private metricRequestRunning = false;
    private autoRefreshRequestRunning = false;
    private backgroundRefreshToken = 0;
    private selectionEpoch = 0;
    private macroRequestToken = 0;
    private macroRunTimer: ReturnType<typeof setTimeout> | null = null;
    private macroRunToken = 0;
    private themeObserver: MutationObserver | null = null;
    private terminalRoom = '';
    private terminalSocket: any = null;
    private terminalInstance: Terminal | null = null;
    private terminalFitAddon: FitAddon | null = null;
    private resourceChartInstances: any[] = [];
    private resourceChartTitleObservers: MutationObserver[] = [];
    private resourceChartRenderTimer: ReturnType<typeof setTimeout> | null = null;
    private routeSub: any = null;
    private agentCommandHandler: ((event: Event) => void) | null = null;

    constructor(public service: Service, private router: Router) { }

    public async ngOnInit() {
        await this.service.init();
        this.startThemeObserver();
        this.startAgentCommandListener();
        const selectedId = this.routeNodeId();
        this.detailTab.set(this.routeDetailTab());
        await this.load(selectedId, true);
        this.routeSub = this.router.events.subscribe((event: any) => {
            if (event instanceof NavigationEnd) void this.handleRouteNavigation();
        });
    }

    public ngOnDestroy() {
        if (this.routeSub) this.routeSub.unsubscribe();
        this.stopAutoRefresh();
        this.stopMacroRunPolling();
        this.disconnectTerminal(true);
        this.cancelResourceChartRender();
        this.destroyResourceChart();
        this.stopThemeObserver();
        this.stopAgentCommandListener();
    }

    @HostListener('window:resize')
    public handleWindowResize() {
        this.fitTerminal();
    }

    private emptyServerForm() {
        return { node_id: '', name: '', host: '', username: '', password: '', ssh_port: 22 };
    }

    private resetServerForm() {
        this.serverForm = this.emptyServerForm();
    }

    private detailTabKeys() {
        return ['overview', 'files', 'terminal'];
    }

    private routeNodeId() {
        return this.service.routeSegment('node_id') || this.service.queryParam('node_id') || this.service.queryParam('selected_node_id');
    }

    private routeDetailTab() {
        const tab = this.service.routeSegment('detail_tab');
        return this.detailTabKeys().includes(tab) ? tab : 'overview';
    }

    private async handleRouteNavigation() {
        const nodeId = this.routeNodeId();
        const currentId = this.selected()?.id || '';
        if (nodeId !== currentId) {
            await this.load(nodeId, true);
            return;
        }
        const tab = this.routeDetailTab();
        if (tab === this.detailTab()) return;
        this.detailTab.set(tab);
        if (tab !== 'terminal') this.terminalExpanded.set(false);
        if (tab === 'terminal') {
            await this.service.render(0);
            this.fitTerminal();
            return;
        }
        await this.service.render();
    }

    private nodeDetailRoute(nodeId: string = this.selected()?.id || '', tab: string = this.detailTab()) {
        const encodedId = this.service.encodeRouteSegment(nodeId);
        if (!encodedId) return '/servers';
        if (tab && tab !== 'overview') return `/servers/${encodedId}/${this.service.encodeRouteSegment(tab)}`;
        return `/servers/${encodedId}`;
    }

    private async syncNodeRoute(nodeId: string = this.selected()?.id || '', replace: boolean = false) {
        if (!nodeId) {
            if (this.service.currentPath().startsWith('/servers/')) await this.service.routeTo('/servers', true);
            return;
        }
        const target = this.nodeDetailRoute(nodeId);
        if (this.service.currentPath() !== target) await this.service.routeTo(target, replace);
    }

    private todayDateInput() {
        const date = new Date();
        date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
        return date.toISOString().slice(0, 10);
    }

    private startThemeObserver() {
        if (typeof MutationObserver === 'undefined') return;
        this.themeObserver = new MutationObserver(() => {
            this.applyTerminalTheme();
            this.scheduleResourceChartRender();
        });
        this.themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    }

    private stopThemeObserver() {
        if (!this.themeObserver) return;
        this.themeObserver.disconnect();
        this.themeObserver = null;
    }

    private startAgentCommandListener() {
        if (this.agentCommandHandler || typeof window === 'undefined') return;
        this.agentCommandHandler = (event: Event) => {
            void this.handleAgentCommand(event as CustomEvent);
        };
        window.addEventListener('docker-infra-agent-action', this.agentCommandHandler);
    }

    private stopAgentCommandListener() {
        if (!this.agentCommandHandler || typeof window === 'undefined') return;
        window.removeEventListener('docker-infra-agent-action', this.agentCommandHandler);
        this.agentCommandHandler = null;
    }

    private async handleAgentCommand(event: CustomEvent) {
        const detail = event?.detail || {};
        if (detail.target !== 'server.run_macro') return;
        const requestId = String(detail.request_id || '');
        try {
            const result = await this.runMacroFromAgent(detail.payload || {});
            this.publishAgentCommandResult(requestId, { ok: true, ...result });
        } catch (error: any) {
            this.publishAgentCommandResult(requestId, {
                ok: false,
                message: error?.message || '서버 매크로를 실행하지 못했습니다.',
            });
        }
    }

    private async runMacroFromAgent(payload: any) {
        await this.waitForServerLoad();
        const node = await this.ensureAgentNodeSelected(payload || {});
        this.detailTab.set('overview');
        await this.syncNodeRoute(node.id);
        await this.loadMacros(node.id);
        await this.service.render();

        const macro = await this.ensureAgentMacro(payload || {}, node.id);
        this.selectMacro(macro.id);
        const args = String(payload?.args || '');
        this.macroArgsInput.set(args);
        this.macroArgsEnabled.set(Boolean(args));
        await this.runSelectedMacro();

        const operation = this.macroRunResult()?.operation || null;
        if (!operation) throw new Error('매크로 실행 작업을 시작하지 못했습니다.');
        return { node, macro, operation };
    }

    private async ensureAgentNodeSelected(payload: any) {
        const node = this.agentTargetNode(payload);
        if (!node?.id) throw new Error('실행할 서버를 찾을 수 없습니다.');
        if (this.selected()?.id !== node.id) {
            const epoch = this.beginSelection(node);
            await this.syncNodeRoute(node.id, true);
            await this.service.render();
            void this.fetchCachedDetail(node.id, true, epoch);
        }
        return this.selected()?.id === node.id ? this.selected() : node;
    }

    private agentTargetNode(payload: any) {
        const nodes = this.nodes();
        const nodeId = String(payload?.node_id || payload?.nodeId || '').trim();
        if (nodeId) return nodes.find((node: any) => node.id === nodeId) || (this.selected()?.id === nodeId ? this.selected() : null);

        const selector = String(payload?.node_selector || payload?.nodeSelector || '').trim().toLowerCase();
        if (['local_master', 'master', '마스터', '중심'].includes(selector)) {
            return nodes.find((node: any) => node.is_local_master) || this.selected() || nodes[0] || null;
        }

        const name = String(payload?.node_name || payload?.node || '').trim().toLowerCase();
        if (name) {
            const exact = nodes.find((node: any) => {
                const labels = [node?.id, node?.name, node?.host].map((value) => String(value || '').trim().toLowerCase());
                return labels.includes(name);
            });
            if (exact) return exact;
            return nodes.find((node: any) => String(`${node?.name || ''} ${node?.host || ''}`).toLowerCase().includes(name)) || null;
        }

        return this.selected() || nodes.find((node: any) => node.is_local_master) || nodes[0] || null;
    }

    private async ensureAgentMacro(payload: any, nodeId: string) {
        const macroPayload = payload?.macro && typeof payload.macro === 'object' ? payload.macro : {};
        const macroName = String(payload?.macro_name || payload?.macroName || macroPayload?.name || '').trim();
        if (!macroName) throw new Error('실행할 매크로 이름이 비어 있습니다.');

        let macro = this.findAgentMacroByName(macroName);
        if (macroPayload?.script && (!macro || macroPayload.update_existing !== false)) {
            macro = await this.saveAgentGlobalMacro({ ...macroPayload, name: macroPayload?.name || macroName }, macro);
            await this.loadMacros(nodeId);
            macro = this.macros().find((item: any) => item.id === macro?.id) || this.findAgentMacroByName(macroName) || macro;
        }
        if (!macro) throw new Error(`실행할 매크로를 찾을 수 없습니다: ${macroName}`);
        return macro;
    }

    private findAgentMacroByName(name: string) {
        const target = String(name || '').trim().toLowerCase();
        if (!target) return null;
        return this.macros().find((macro: any) => String(macro?.name || '').trim().toLowerCase() === target) || null;
    }

    private async saveAgentGlobalMacro(payload: any, existing: any = null) {
        const name = String(payload?.name || existing?.name || '').trim();
        const script = String(payload?.script || existing?.script || '').trim();
        if (!name) throw new Error('Agent 매크로 이름이 비어 있습니다.');
        if (!script) throw new Error('Agent 매크로 스크립트가 비어 있습니다.');

        const formData = new FormData();
        if (existing?.id) formData.append('id', existing.id);
        formData.append('name', name);
        formData.append('description', String(payload?.description || existing?.description || '').trim());
        formData.append('script', script);
        formData.append('enabled', String(payload?.enabled !== false));
        formData.append('scope_type', 'global');
        formData.append('keep_file_ids', JSON.stringify((existing?.files || []).map((item: any) => item.id).filter((id: string) => !!id)));

        const response = await fetch('/wiz/api/page.macros/save_macro', { method: 'POST', body: formData });
        const json = await response.json().catch(() => ({}));
        const code = Number(json?.code || response.status || 500);
        const data = json?.data || json || {};
        if (!response.ok || code >= 400) {
            throw new Error(data?.message || 'Agent 매크로를 저장할 수 없습니다.');
        }
        return data?.macro || null;
    }

    private async waitForServerLoad() {
        for (let index = 0; index < 40; index++) {
            if (!this.loading()) return;
            await this.sleep(100);
        }
    }

    private publishAgentCommandResult(requestId: string, detail: any) {
        if (!requestId || typeof window === 'undefined') return;
        window.dispatchEvent(new CustomEvent('docker-infra-agent-action-result', {
            detail: {
                request_id: requestId,
                target: 'server.run_macro',
                ...detail,
            },
        }));
    }

    private sleep(ms: number) {
        return new Promise((resolve) => window.setTimeout(resolve, Math.max(0, ms || 0)));
    }

    private mergeSelectedNode(node: any) {
        if (!node?.id) return;
        this.nodes.set(this.nodes().map((item) => item.id === node.id ? { ...item, ...node } : item));
    }

    private setSelectedNode(node: any) {
        this.selected.set(node || null);
        this.mergeSelectedNode(node);
    }

    private beginSelection(node: any) {
        this.selectionEpoch += 1;
        this.backgroundRefreshToken += 1;
        this.macroRequestToken += 1;
        this.macroRunToken += 1;
        this.stopAutoRefresh();
        this.stopMacroRunPolling();
        this.disconnectTerminal(true);
        this.setSelectedNode(node || null);
        this.applyContainerPanel({ summary: { total: 0, running: 0, stopped: 0 }, service_groups: [] }, false);
        this.terminalExpanded.set(false);
        this.globalMacros.set([]);
        this.macros.set([]);
        this.selectedMacroId.set('');
        this.macroArgsEnabled.set(false);
        this.macroArgsInput.set('');
        this.macroRunResult.set(null);
        this.lastOperation.set(null);
        this.resourceChartOpen.set(false);
        this.resourceHistory.set({ rows: [] });
        this.resourceHistoryError.set('');
        this.detailError.set('');
        this.detailLoading.set(false);
        this.panelRefreshing.set(false);
        return this.selectionEpoch;
    }

    private isActiveSelection(nodeId: string, epoch: number) {
        return Boolean(nodeId) && this.selectionEpoch === epoch && this.selected()?.id === nodeId;
    }

    private applyOverview(data: any, syncSelected: boolean = true) {
        this.nodes.set(data.nodes || []);
        this.nodesPagination.set(this.paginationFor(this.nodes().length, this.nodesPagination().current));
        if (data.monitoring) this.monitoringState.set(data.monitoring);
        if (syncSelected) this.setSelectedNode(data.selected || null);
        this.detailError.set('');
    }

    private applyContainerPanel(data: any, syncSelectedSummary: boolean = true) {
        const summary = data.summary || { total: 0, running: 0, stopped: 0 };
        const serviceGroups = data.service_groups || [];
        this.containerStats.set(summary);
        this.serviceGroups.set(serviceGroups);
        if (syncSelectedSummary && this.selected()?.id) {
            this.mergeSelectedNode({
                id: this.selected().id,
                runtime_summary: {
                    service_count: serviceGroups.length,
                    container_total: Number(summary.total || 0),
                    container_running: Number(summary.running || 0),
                    container_stopped: Number(summary.stopped || 0),
                },
            });
        }
    }

    private errorDetails(details: any[] = []) {
        return (details || [])
            .filter((detail: any) => detail)
            .map((detail: any) => {
                const message = detail.message || detail.error_code || '검사에 실패했습니다.';
                return detail.path ? `- ${detail.path}: ${message}` : `- ${message}`;
            });
    }

    private formatErrorMessage(data: any, fallback: string) {
        const base = data?.error_code === 'COMPOSE_VALIDATION_FAILED'
            ? 'Compose 검사를 통과하지 못했습니다.'
            : (data?.message || fallback);
        const details = this.errorDetails(data?.details || []);
        if (!details.length) return base;
        return `${base}\n\n${details.join('\n')}`;
    }

    private applyCachedDetail(data: any) {
        if (data.monitoring) this.monitoringState.set(data.monitoring);
        this.setSelectedNode(data.node || null);
        this.applyContainerPanel(data);
        this.detailError.set('');
    }

    private async fetchCachedDetail(nodeId: string, silent: boolean = false, epoch: number = this.selectionEpoch) {
        if (!nodeId) return;
        this.detailLoading.set(true);
        const { code, data } = await wiz.call("cached_detail", { node_id: nodeId });
        if (!this.isActiveSelection(nodeId, epoch)) return;
        if (code === 200) {
            this.applyCachedDetail(data);
            this.restartAutoRefresh();
        } else if (silent) {
            this.detailError.set(data?.message || '저장된 서버 상세 정보를 불러올 수 없습니다.');
        } else {
            await this.alert(data?.message || '서버 상세를 불러올 수 없습니다.');
        }
        this.detailLoading.set(false);
        await this.service.render();
    }

    private async refreshCachedDetailInBackground(nodeId: string, epoch: number = this.selectionEpoch) {
        if (!nodeId || this.autoRefreshRequestRunning) return;
        const token = ++this.backgroundRefreshToken;
        this.autoRefreshRequestRunning = true;
        try {
            if (!this.isActiveSelection(nodeId, epoch) || token !== this.backgroundRefreshToken) return;
            const { code, data } = await wiz.call("cached_detail", { node_id: nodeId });
            if (!this.isActiveSelection(nodeId, epoch) || token !== this.backgroundRefreshToken) return;
            if (code === 200) {
                this.applyCachedDetail(data);
            } else {
                this.detailError.set(data?.message || '저장된 서버 상세 정보를 불러올 수 없습니다.');
            }
        } finally {
            this.autoRefreshRequestRunning = false;
            if (token === this.backgroundRefreshToken && this.isActiveSelection(nodeId, epoch)) await this.service.render();
        }
    }

    private stopAutoRefresh() {
        if (!this.refreshTimer) return;
        clearInterval(this.refreshTimer);
        this.refreshTimer = null;
    }

    private restartAutoRefresh() {
        this.stopAutoRefresh();
        if (!this.selected()?.id) return;
        const epoch = this.selectionEpoch;
        this.refreshTimer = setInterval(() => {
            if (this.busy() || this.metricRequestRunning || this.autoRefreshRequestRunning) return;
            void this.fetchMetrics(true, this.selected()?.id, epoch);
        }, this.refreshSeconds() * 1000);
    }

    private stopMacroRunPolling() {
        if (!this.macroRunTimer) return;
        clearTimeout(this.macroRunTimer);
        this.macroRunTimer = null;
    }

    private isTerminalOperationStatus(status: string) {
        return ['succeeded', 'failed', 'canceled'].includes(String(status || '').toLowerCase());
    }

    private scheduleMacroRunPoll(operationId: string, token: number, delayMs: number = 500) {
        this.stopMacroRunPolling();
        if (!operationId || token !== this.macroRunToken) return;
        this.macroRunTimer = setTimeout(() => {
            void this.pollMacroRun(operationId, token);
        }, delayMs);
    }

    private async pollMacroRun(operationId: string, token: number) {
        if (!operationId || token !== this.macroRunToken) return;
        try {
            const { code, data } = await wiz.call("operation_status", { operation_id: operationId });
            if (token !== this.macroRunToken) return;
            const operation = data?.operation || null;
            if (code === 200 && operation) {
                const current = this.macroRunResult() || {};
                this.lastOperation.set(operation);
                this.macroRunResult.set({ ...current, operation });
                if (!this.isTerminalOperationStatus(operation.status)) {
                    this.scheduleMacroRunPoll(operationId, token);
                }
            } else if (!this.isTerminalOperationStatus(this.macroRunStatus())) {
                this.scheduleMacroRunPoll(operationId, token, 1200);
            }
        } catch {
            if (token === this.macroRunToken && !this.isTerminalOperationStatus(this.macroRunStatus())) {
                this.scheduleMacroRunPoll(operationId, token, 1200);
            }
        }
        await this.service.render();
    }

    private async fetchMetrics(silent: boolean = false, targetNodeId: string | null = null, epoch: number = this.selectionEpoch) {
        const nodeId = targetNodeId || this.selected()?.id;
        if (!nodeId || this.metricRequestRunning) return;
        this.metricRequestRunning = true;
        const { code, data } = await wiz.call("refresh_metrics", { node_id: nodeId, persist: false });
        this.metricRequestRunning = false;
        if (!this.isActiveSelection(nodeId, epoch)) return;
        if (code === 200) {
            if (data.monitoring) this.monitoringState.set(data.monitoring);
            if (data?.latest_metric) {
                const current = this.selected() || {};
                this.setSelectedNode({ ...current, id: data.node_id || current.id, latest_metric: data.latest_metric });
            } else {
                this.setSelectedNode(data.node || null);
            }
            this.detailError.set('');
        } else if (silent) {
            this.detailError.set(data?.message || 'CPU/Memory/Storage 정보를 자동으로 갱신할 수 없습니다.');
        } else {
            await this.alert(data?.message || '서버 자원 정보를 갱신할 수 없습니다.');
        }
        this.restartAutoRefresh();
        await this.service.render();
    }

    private async fetchDetail(nodeId: string, silent: boolean = false) {
        if (!nodeId) return;
        const { code, data } = await wiz.call("detail", { node_id: nodeId });
        if (code === 200) {
            if (data.monitoring) this.monitoringState.set(data.monitoring);
            this.setSelectedNode(data.node || null);
            this.applyContainerPanel(data);
            this.detailError.set('');
            this.restartAutoRefresh();
        } else if (silent) {
            this.detailError.set(data?.message || '서버 상세 정보를 불러올 수 없습니다.');
        } else {
            await this.alert(data?.message || '서버 상세를 불러올 수 없습니다.');
        }
        await this.service.render();
    }

    public async refreshContainers(silent: boolean = false, targetNodeId: string | null = null, epoch: number = this.selectionEpoch) {
        const nodeId = targetNodeId || this.selected()?.id;
        if (!nodeId) return;
        const { code, data } = await wiz.call("refresh_containers", { node_id: nodeId });
        if (!this.isActiveSelection(nodeId, epoch)) return;
        if (code === 200) {
            if (data.monitoring) this.monitoringState.set(data.monitoring);
            this.setSelectedNode(data.node || null);
            this.applyContainerPanel(data);
            this.detailError.set('');
        } else if (silent) {
            this.detailError.set(data?.message || '컨테이너 목록을 갱신할 수 없습니다.');
        } else {
            await this.alert(data?.message || '컨테이너 목록을 갱신할 수 없습니다.');
        }
        await this.service.render();
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

    private paginationStart(page: number) {
        return Math.floor((Math.max(1, Number(page || 1)) - 1) / 10) * 10 + 1;
    }

    private paginationFor(total: number, page: number = 1) {
        const limit = this.pageSize;
        const end = Math.max(1, Math.ceil(Number(total || 0) / limit));
        const current = Math.min(Math.max(1, Number(page || 1)), end);
        return {
            current,
            start: this.paginationStart(current),
            end,
            total: Number(total || 0),
            limit,
        };
    }

    public pagedNodes() {
        const pagination = this.nodesPagination();
        const limit = Number(pagination?.limit || this.pageSize);
        const start = (Number(pagination?.current || 1) - 1) * limit;
        return this.nodes().slice(start, start + limit);
    }

    public nodesBoardSummary() {
        const pagination = this.nodesPagination();
        const total = Number(pagination?.total || 0);
        if (!total) return '총 0개';
        const current = Number(pagination?.current || 1);
        const limit = Number(pagination?.limit || this.pageSize);
        const start = (current - 1) * limit + 1;
        const end = Math.min(total, current * limit);
        return `총 ${total}개 · ${start}-${end}`;
    }

    public isServerDetailScreen() {
        return Boolean(this.selected()?.id);
    }

    public async closeServerDetail() {
        this.beginSelection(null);
        this.detailTab.set('overview');
        await this.syncNodeRoute('');
        await this.service.render();
    }

    public async moveNodePage(page: number) {
        this.nodesPagination.set(this.paginationFor(this.nodes().length, page));
        await this.service.render();
    }

    public async load(selectedId: string = '', replaceRoute: boolean = false) {
        this.loading.set(true);
        this.error.set('');
        this.detailLoading.set(false);
        this.panelRefreshing.set(false);
        this.stopAutoRefresh();
        await this.service.render();
        const { code, data } = await wiz.call("load", { selected_id: selectedId });
        if (code === 200) {
            this.detailTab.set(this.routeDetailTab());
            this.applyOverview(data, Boolean(selectedId));
            const selected = selectedId ? (data.selected || { id: selectedId }) : null;
            const epoch = this.beginSelection(selected);
            this.detailTab.set(this.routeDetailTab());
            await this.syncNodeRoute(selected?.id || '', replaceRoute);
            this.restartAutoRefresh();
            this.loading.set(false);
            await this.service.render();
            if (selected?.id) {
                void this.fetchCachedDetail(selected.id, true, epoch);
            }
            return;
        } else {
            this.error.set(data?.message || '서버 정보를 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
    }

    public async selectNode(node: any) {
        this.detailTab.set('overview');
        const epoch = this.beginSelection(node);
        await this.syncNodeRoute(node?.id || '');
        await this.service.render();
        void this.fetchCachedDetail(node.id, false, epoch);
    }

    public serverFileTreeContext() {
        return { node_id: this.selected()?.id || '' };
    }

    public async ensureMonitoringAgent() {
        const nodeId = this.selected()?.id;
        if (!nodeId || this.monitoringBusy()) return;
        this.monitoringBusy.set(true);
        const { code, data } = await wiz.call("ensure_monitoring_agent", { node_id: nodeId });
        if (code === 200) {
            this.applyOverview(data);
            this.actionTitle.set('모니터링 에이전트 구성 결과');
            this.actionResult.set({
                checks: { operation: data.failed ? 'error' : 'ok' },
                operation: data.operation,
                results: data.results || [],
            });
            this.actionModalOpen.set(true);
            await this.fetchCachedDetail(nodeId, true);
        } else {
            await this.alert(data?.message || '모니터링 에이전트를 구성할 수 없습니다.');
        }
        this.monitoringBusy.set(false);
        await this.service.render();
    }

    public openAddServer() {
        this.editingNodeId.set('');
        this.resetServerForm();
        this.serverModalOpen.set(true);
    }

    public openEditServer() {
        const node = this.selected();
        if (!node) return;
        if (node.is_local_master) {
            void this.alert('중심 서버 정보는 자동으로 동기화됩니다.', 'info');
            return;
        }
        const credential = node.credential || {};
        this.serverForm = {
            node_id: node.id,
            name: node.name || '',
            host: node.host || '',
            username: credential.username || '',
            password: '',
            ssh_port: node.ssh_port || 22
        };
        this.editingNodeId.set(node.id);
        this.serverModalOpen.set(true);
    }

    public closeServerModal() {
        if (this.busy()) return;
        this.serverModalOpen.set(false);
        this.editingNodeId.set('');
        this.resetServerForm();
    }

    public openDeleteServer() {
        const node = this.selected();
        if (!node) return;
        if (node.is_local_master) {
            void this.alert('중심 서버는 등록 해제할 수 없습니다.', 'info');
            return;
        }
        const runningServices = this.runningServiceGroups();
        if (runningServices.length > 0) {
            void this.alert(this.runningServicesBlockMessage(runningServices), 'warning');
            return;
        }
        this.deletingNode.set(node);
        this.deleteConfirmInput.set('');
        this.deleteModalOpen.set(true);
    }

    public closeDeleteModal() {
        if (this.busy()) return;
        this.deleteModalOpen.set(false);
        this.deleteConfirmInput.set('');
        this.deletingNode.set(null);
    }

    public closeActionModal() {
        this.actionModalOpen.set(false);
        this.actionResult.set(null);
    }

    public closeFileBrowser() {
        if (this.fileBrowserBusy()) return;
        this.fileBrowserOpen.set(false);
        this.fileBrowserPath.set('');
        this.fileBrowserInput.set('');
        this.fileBrowserShowHidden.set(false);
        this.composeImportName.set('');
        this.fileBrowserItems.set([]);
        this.importCandidate.set(null);
    }

    public macroFilesFor(macro: any) {
        return macro?.files || [];
    }

    public macroFileCount(macro: any) {
        const files = this.macroFilesFor(macro);
        return Number(macro?.file_count ?? files.length ?? 0);
    }

    public macroFileSummary(macro: any) {
        const count = this.macroFileCount(macro);
        return count ? `첨부 ${count}개` : '첨부 없음';
    }

    public formatFileSize(value: any) {
        const size = Number(value || 0);
        if (size < 1024) return `${size} B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
        return `${(size / 1024 / 1024).toFixed(1)} MB`;
    }

    public async loadMacros(nodeId: string | null = this.selected()?.id) {
        const targetNodeId = String(nodeId || '').trim();
        if (!targetNodeId) {
            this.globalMacros.set([]);
            this.macros.set([]);
            this.selectedMacroId.set('');
            return;
        }
        const token = ++this.macroRequestToken;
        this.macroLoading.set(true);
        this.macroError.set('');
        const { code, data } = await wiz.call("list_macros", {});
        if (token !== this.macroRequestToken || this.selected()?.id !== targetNodeId) return;
        if (code === 200) {
            const available = data.available_macros || data.global_macros || [];
            const previous = this.selectedMacroId();
            this.globalMacros.set(available);
            this.macros.set(available);
            const selectedId = available.some((item: any) => item.id === previous)
                ? previous
                : (available[0]?.id || '');
            this.selectedMacroId.set(selectedId);
        } else {
            this.macroError.set(data?.message || '매크로 목록을 불러올 수 없습니다.');
        }
        this.macroLoading.set(false);
        await this.service.render();
    }

    public selectedMacro() {
        const id = this.selectedMacroId();
        return this.macros().find((item: any) => item.id === id) || null;
    }

    public selectMacro(macroId: string) {
        this.macroRunToken += 1;
        this.stopMacroRunPolling();
        this.selectedMacroId.set(macroId);
        this.macroRunResult.set(null);
        this.lastOperation.set(null);
    }

    public async runSelectedMacro() {
        const node = this.selected();
        const macro = this.selectedMacro();
        if (!node || !macro) return;
        const args = this.macroArgsEnabled() ? this.macroArgsInput() : '';
        const token = ++this.macroRunToken;
        this.stopMacroRunPolling();
        this.busy.set(true);
        const { code, data } = await wiz.call("run_macro", {
            macro_id: macro.id,
            node_id: node.id,
            args,
        });
        if (code === 200) {
            const operation = data.operation || null;
            this.lastOperation.set(operation);
            this.macroRunResult.set({
                operation,
                macro,
                args,
            });
            if (operation?.id && !this.isTerminalOperationStatus(operation.status) && token === this.macroRunToken) {
                this.scheduleMacroRunPoll(operation.id, token, 250);
            }
        } else {
            await this.alert(data?.message || '매크로를 실행할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public macroSelectorItems() {
        return this.macros().map((macro: any) => ({
            value: macro.id,
            label: macro.name,
            description: `${macro.description || '설명이 등록되지 않았습니다.'}${this.macroFileCount(macro) ? ` · ${this.macroFileSummary(macro)}` : ''}`,
            badge: macro.enabled === false ? '비활성화' : '',
            badgeClass: macro.enabled === false
                ? this.statusClass('warning')
                : '',
            disabled: false,
        }));
    }

    public selectedMacroDescription() {
        return String(this.selectedMacro()?.description || '').trim() || '설명이 등록되지 않았습니다.';
    }

    public macroCountSummary() {
        return `실행 가능한 매크로 ${this.globalMacros().length}개`;
    }

    public setDetailTab(tab: string) {
        if (!this.detailTabKeys().includes(tab)) return;
        this.detailTab.set(tab);
        void this.syncNodeRoute();
        if (tab !== 'terminal') {
            this.terminalExpanded.set(false);
        }
        if (tab === 'terminal') {
            void this.service.render(0).then(() => this.fitTerminal());
        }
    }

    public isDetailTab(tab: string) {
        return this.detailTab() === tab;
    }

    public terminalExpandedView() {
        return this.isDetailTab('terminal') && this.terminalExpanded();
    }

    public async toggleTerminalExpanded() {
        this.terminalExpanded.set(!this.terminalExpanded());
        await this.service.render(0);
        this.fitTerminal();
    }

    private terminalTheme() {
        return {
            background: '#000000',
            foreground: '#f5f5f5',
            cursor: '#f5f5f5',
            cursorAccent: '#000000',
            selectionBackground: '#264f78',
            black: '#000000',
            red: '#cd3131',
            green: '#0dbc79',
            yellow: '#e5e510',
            blue: '#2472c8',
            magenta: '#bc3fbc',
            cyan: '#11a8cd',
            white: '#e5e5e5',
            brightBlack: '#666666',
            brightRed: '#f14c4c',
            brightGreen: '#23d18b',
            brightYellow: '#f5f543',
            brightBlue: '#3b8eea',
            brightMagenta: '#d670d6',
            brightCyan: '#29b8db',
            brightWhite: '#ffffff',
        };
    }

    private applyTerminalTheme() {
        if (!this.terminalInstance) return;
        this.terminalInstance.options.theme = this.terminalTheme();
    }

    private async ensureTerminalMounted() {
        await this.service.render();
        const host = document.querySelector('[data-testid="servers-terminal-host"]') as HTMLElement | null;
        if (!host) return;
        if (this.terminalInstance) {
            this.applyTerminalTheme();
            this.fitTerminal();
            return;
        }
        host.innerHTML = '';
        this.terminalInstance = new Terminal({
            allowProposedApi: false,
            convertEol: true,
            cursorBlink: true,
            scrollback: 5000,
            fontSize: 13,
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace',
            theme: this.terminalTheme(),
            allowTransparency: false,
            drawBoldTextInBrightColors: true,
        });
        this.terminalFitAddon = new FitAddon();
        this.terminalInstance.loadAddon(this.terminalFitAddon);
        this.terminalInstance.loadAddon(new WebLinksAddon());
        this.terminalInstance.open(host);
        this.terminalInstance.focus();
    }

    public fitTerminal() {
        try {
            this.terminalFitAddon?.fit();
        } catch (error) {
            return;
        }
        if (!this.terminalSocket || !this.terminalConnected() || !this.terminalInstance) return;
        this.terminalSocket.emit('resize', {
            namespace: this.terminalRoom,
            cols: this.terminalInstance.cols,
            rows: this.terminalInstance.rows,
        });
    }

    public clearTerminal() {
        this.terminalInstance?.clear();
    }

    public terminalDescription() {
        if (this.terminalConnected()) {
            return '선택한 서버의 실제 로그인 셸 세션이 연결되어 있습니다. 서버 기본 zsh/bash 설정과 ANSI 색상을 그대로 사용합니다.';
        }
        return '선택한 서버의 실제 로그인 셸에 연결합니다. 서버 기본 zsh/bash 설정과 ANSI 색상을 그대로 사용합니다.';
    }

    public terminalExpandLabel() {
        return this.terminalExpandedView() ? '기본 레이아웃' : '터미널 넓게 보기';
    }

    public disconnectTerminal(silent: boolean = false) {
        if (this.terminalSocket) {
            try {
                this.terminalSocket.emit('close', { namespace: this.terminalRoom });
            } catch (error) {
                // ignore socket close errors
            }
            try {
                this.terminalSocket.close();
            } catch (error) {
                // ignore disconnect errors
            }
        }
        this.terminalSocket = null;
        this.terminalRoom = '';
        this.terminalConnected.set(false);
        this.terminalConnecting.set(false);
        this.terminalError.set('');
        this.terminalStatus.set(silent ? '연결되지 않음' : '연결 종료됨');
        if (this.terminalInstance) {
            this.terminalInstance.dispose();
            this.terminalInstance = null;
            this.terminalFitAddon = null;
        }
    }

    public async connectTerminal() {
        const node = this.selected();
        if (!node?.id) return;
        this.disconnectTerminal(true);
        this.terminalConnecting.set(true);
        this.terminalConnected.set(false);
        this.terminalError.set('');
        this.terminalStatus.set('터미널 연결 중');
        await this.ensureTerminalMounted();
        if (!this.terminalInstance) {
            this.terminalConnecting.set(false);
            this.terminalError.set('터미널 영역을 초기화할 수 없습니다.');
            return;
        }

        const socket = wiz.socket();
        const room = `servers-terminal-${node.id}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
        this.terminalSocket = socket;
        this.terminalRoom = room;
        this.terminalInstance.clear();
        this.terminalInstance.focus();
        this.terminalInstance.onData((input) => {
            socket.emit('ptyinput', { namespace: room, input });
        });
        this.terminalInstance.onResize(({ cols, rows }) => {
            socket.emit('resize', { namespace: room, cols, rows });
        });

        socket.on('connect', () => {
            socket.emit('join', { namespace: room });
            socket.emit('create', {
                namespace: room,
                node_id: node.id,
                cols: this.terminalInstance?.cols || 120,
                rows: this.terminalInstance?.rows || 32,
            });
        });
        socket.on('terminal_status', async (data: any) => {
            if (room !== this.terminalRoom) return;
            this.terminalConnecting.set(false);
            this.terminalConnected.set(true);
            this.terminalStatus.set(`${data?.node_name || node.name || node.host} 연결됨`);
            this.fitTerminal();
            await this.service.render();
        });
        socket.on('ptyoutput', (data: any) => {
            if (room !== this.terminalRoom || !this.terminalInstance) return;
            this.terminalInstance.write(String(data?.output || ''));
        });
        socket.on('terminal_error', async (data: any) => {
            if (room !== this.terminalRoom) return;
            this.terminalConnecting.set(false);
            this.terminalConnected.set(false);
            this.terminalError.set(data?.message || '터미널을 연결할 수 없습니다.');
            this.terminalStatus.set('연결 실패');
            await this.service.render();
        });
        socket.on('exit', async (data: any) => {
            if (room !== this.terminalRoom) return;
            this.terminalConnecting.set(false);
            this.terminalConnected.set(false);
            this.terminalStatus.set(data?.closed ? '연결 종료됨' : `세션 종료 (${data?.exit_code ?? '-'})`);
            if (this.terminalInstance) {
                this.terminalInstance.write('\r\n[세션 종료]\r\n');
            }
            await this.service.render();
        });
    }

    public async ensureLocalMaster() {
        const confirmed = await this.service.modal.show({
            title: '중심 서버 확인',
            message: '현재 Docker Infra가 실행 중인 서버의 Docker 및 선택적 Swarm 상태를 다시 확인합니다.',
            cancel: '취소',
            action: '확인',
            actionBtn: 'primary',
            status: 'info'
        });
        if (!confirmed) return;

        this.busy.set(true);
        const { code, data } = await wiz.call("ensure_local_master", { network_name: 'docker_infra_overlay', timeout_seconds: 10 });
        if (code === 200) {
            this.applyOverview(data);
            this.applyContainerPanel(data);
            this.restartAutoRefresh();
            this.actionTitle.set('중심 서버 확인 결과');
            const monitoringStatus = data.monitoring_auto_configure
                ? ((data.monitoring_auto_configure.failed || data.monitoring_auto_configure.status === 'failed') ? 'warning' : 'ok')
                : undefined;
            this.actionResult.set({
                checks: {
                    docker: 'ok',
                    swarm: data.result?.swarm?.manager ? 'ok' : 'warning',
                    network: data.result?.overlay_network?.status || 'ok',
                    ...(monitoringStatus ? { monitoring: monitoringStatus } : {}),
                },
            });
            this.actionModalOpen.set(true);
        } else {
            await this.alert(data?.message || '중심 서버 상태를 확인할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public async saveServer() {
        if (!this.serverForm.host) {
            await this.alert('서버 IP 또는 host를 입력해주세요.');
            return;
        }
        if (!this.serverForm.username) {
            await this.alert('SSH 계정을 입력해주세요.');
            return;
        }
        if (!this.isEditing() && !this.serverForm.password) {
            await this.alert('최초 연결 확인에 사용할 SSH 비밀번호를 입력해주세요.');
            return;
        }

        this.busy.set(true);
        const payload = {
            node_id: this.serverForm.node_id || undefined,
            name: this.serverForm.name,
            host: this.serverForm.host,
            username: this.serverForm.username,
            password: this.serverForm.password || undefined,
            ssh_port: this.serverForm.ssh_port || 22
        };
        const { code, data } = await wiz.call("register_slave", payload);
        if (code === 200) {
            this.applyOverview(data);
            this.applyContainerPanel(data);
            this.restartAutoRefresh();
            this.actionTitle.set(this.isEditing() ? '서버 정보 수정 결과' : '서버 등록 결과');
            const monitoringStatus = data.monitoring_auto_configure
                ? ((data.monitoring_auto_configure.failed || data.monitoring_auto_configure.status === 'failed') ? 'warning' : 'ok')
                : undefined;
            this.actionResult.set({
                checks: { ...(data.node?.metadata?.connection_checks || {}), ...(monitoringStatus ? { monitoring: monitoringStatus } : {}) },
                monitoring: data.monitoring_auto_configure || null,
                node: data.node,
            });
            this.serverModalOpen.set(false);
            this.editingNodeId.set('');
            this.resetServerForm();
            this.actionModalOpen.set(true);
        } else {
            const fallback = this.isEditing() ? '서버 정보를 수정할 수 없습니다.' : '서버를 등록할 수 없습니다.';
            const detail = data?.check?.reason || data?.reason;
            await this.alert(data?.message || detail || fallback);
            this.serverForm.password = '';
        }
        this.busy.set(false);
        await this.service.render();
    }

    public deleteConfirmName() {
        return String(this.deletingNode()?.name || '').trim();
    }

    public deleteConfirmMatches() {
        return Boolean(this.deleteConfirmName()) && this.deleteConfirmInput().trim() === this.deleteConfirmName();
    }

    public deleteSubmitLabel() {
        return this.busy() ? '등록 해제 중' : '등록 해제';
    }

    public async unregisterSelectedServer() {
        const node = this.deletingNode() || this.selected();
        if (!node?.id || node.is_local_master) return;
        if (!this.deleteConfirmMatches()) {
            await this.alert('서버 이름을 정확히 입력해야 등록 해제가 가능합니다.');
            return;
        }

        this.busy.set(true);
        this.stopAutoRefresh();
        const { code, data } = await wiz.call("unregister_server", {
            node_id: node.id,
            confirmation_name: this.deleteConfirmInput().trim(),
        });
        if (code === 200) {
            this.deleteModalOpen.set(false);
            this.deleteConfirmInput.set('');
            this.deletingNode.set(null);
            if (data.monitoring) this.monitoringState.set(data.monitoring);
            this.nodes.set(data.nodes || []);
            const epoch = this.beginSelection(data.selected || null);
            this.restartAutoRefresh();
            this.actionTitle.set('서버 등록 해제 결과');
            const swarmRemoveStatus = data.cleanup?.master_cleanup?.swarm_remove?.status;
            const keyFileStatus = data.cleanup?.key_file?.status;
            this.actionResult.set({
                checks: {
                    remote_cleanup: data.cleanup?.remote_cleanup?.status || 'ok',
                    swarm_remove: swarmRemoveStatus === 'skipped' ? 'ok' : (swarmRemoveStatus || 'ok'),
                    known_hosts: 'ok',
                    database: data.cleanup?.database?.deleted ? 'ok' : 'warning',
                    key_file: ['removed', 'skipped'].includes(keyFileStatus) ? 'ok' : 'warning',
                    operation: data.operation?.status || 'unknown',
                },
                operation: data.operation,
            });
            this.actionModalOpen.set(true);
            if (data.selected?.id) void this.fetchCachedDetail(data.selected.id, true, epoch);
        } else {
            if (data?.operation) {
                this.actionTitle.set('서버 등록 해제 실패');
                this.actionResult.set({ checks: { operation: data.operation.status || 'failed' }, operation: data.operation });
                this.actionModalOpen.set(true);
            }
            this.restartAutoRefresh();
            await this.alert(data?.message || '서버 등록 해제를 완료할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public async checkSelected() {
        const node = this.selected();
        if (!node) return;
        if (node.is_local_master) {
            await this.ensureLocalMaster();
            return;
        }
        this.busy.set(true);
        const { code, data } = await wiz.call("check_node", { node_id: node.id });
        if (code === 200) {
            this.applyOverview(data);
            this.applyContainerPanel(data);
            this.restartAutoRefresh();
            this.actionTitle.set('서버 점검 결과');
            this.actionResult.set({ checks: { ssh: data.ssh?.status, docker: data.docker?.status, metric: data.selected?.latest_metric ? 'ok' : 'warning' } });
            this.actionModalOpen.set(true);
        } else {
            await this.alert(data?.message || '서버 점검을 실행할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public async joinSelected() {
        const node = this.selected();
        if (!node) return;
        if (node.is_local_master) {
            await this.alert('중심 서버는 이미 Docker Infra가 관리하는 서버입니다.', 'info');
            return;
        }
        if (this.isSwarmConnected(node)) {
            await this.alert('이미 Swarm으로 연결된 서버입니다.', 'info');
            return;
        }
        const confirmed = await this.service.modal.show({
            title: 'Swarm 연결',
            message: `${node.name || node.host} 서버를 Docker Infra 클러스터에 연결합니다.`,
            cancel: '취소',
            action: '연결',
            actionBtn: 'primary',
            status: 'info'
        });
        if (!confirmed) return;

        this.busy.set(true);
        const { code, data } = await wiz.call("join_node", { node_id: node.id });
        if (code === 200) {
            this.applyOverview(data);
            this.applyContainerPanel(data);
            this.restartAutoRefresh();
            this.lastOperation.set(data.operation || null);
            this.actionTitle.set('Swarm 연결 결과');
            this.actionResult.set({
                checks: { operation: data.operation?.status || 'unknown', swarm: this.isSwarmConnected(data.selected) ? 'ok' : 'warning' },
                operation: data.operation
            });
            this.actionModalOpen.set(true);
        } else {
            await this.alert(data?.message || 'Swarm 연결을 실행할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public async refreshSelectedMetrics() {
        await this.fetchMetrics(false);
    }

    public setRefreshSeconds(seconds: number) {
        this.refreshSeconds.set(seconds);
        this.restartAutoRefresh();
    }

    public async openResourceChart() {
        if (!this.selected()?.id) return;
        if (!this.resourceHistoryStartDate()) this.resourceHistoryStartDate.set(this.todayDateInput());
        if (!this.resourceHistoryEndDate()) this.resourceHistoryEndDate.set(this.resourceHistoryStartDate());
        this.resourceChartOpen.set(true);
        await this.service.render();
        await this.loadResourceHistory();
    }

    public closeResourceChart() {
        if (this.resourceHistoryBusy()) return;
        this.resourceChartOpen.set(false);
        this.cancelResourceChartRender();
        this.destroyResourceChart();
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

    private resourceHistoryRangePayload() {
        const startDate = this.resourceHistoryStartDate() || this.todayDateInput();
        const endDate = this.resourceHistoryEndDate() || startDate;
        return {
            start_date: startDate,
            end_date: endDate,
            start_at: this.dateStartIso(startDate),
            end_at: this.dateEndIso(endDate),
        };
    }

    public async loadResourceHistory() {
        const nodeId = this.selected()?.id;
        if (!nodeId) return;
        this.resourceHistoryBusy.set(true);
        this.resourceHistoryError.set('');
        const range = this.resourceHistoryRangePayload();
        const { code, data } = await wiz.call("resource_history", {
            node_id: nodeId,
            ...range,
            limit: 5000,
        });
        if (code === 200) {
            this.resourceHistory.set(data || { rows: [] });
        } else {
            this.resourceHistoryError.set(data?.message || '자원 기록을 불러올 수 없습니다.');
        }
        this.resourceHistoryBusy.set(false);
        await this.service.render();
        this.scheduleResourceChartRender();
    }

    public async deleteResourceHistoryRange() {
        const nodeId = this.selected()?.id;
        if (!nodeId || this.resourceHistoryBusy()) return;
        const start = this.resourceHistoryStartDate();
        const end = this.resourceHistoryEndDate();
        const range = this.resourceHistoryRangePayload();
        const confirmed = await this.service.modal.show({
            title: '자원 기록 삭제',
            message: `${this.selected()?.name || '선택한 서버'}의 ${start} ~ ${end} 자원 기록을 삭제합니다.`,
            cancel: '취소',
            action: '삭제',
            actionBtn: 'warning',
            status: 'warning',
        });
        if (!confirmed) return;

        this.resourceHistoryBusy.set(true);
        this.resourceHistoryError.set('');
        const { code, data } = await wiz.call("delete_resource_history", {
            node_id: nodeId,
            ...range,
        });
        if (code === 200) {
            await this.loadResourceHistory();
            await this.alert(`${data?.rows_removed || 0}개 기록을 삭제했습니다.`, 'info');
        } else {
            this.resourceHistoryError.set(data?.message || '자원 기록을 삭제할 수 없습니다.');
        }
        this.resourceHistoryBusy.set(false);
        await this.service.render();
    }

    private chartTextColor() {
        return this.isDarkMode() ? '#d4d4d8' : '#3f3f46';
    }

    private chartGridColor() {
        return this.isDarkMode() ? 'rgba(63,63,70,0.9)' : 'rgba(228,228,231,0.95)';
    }

    private chartStatValue(row: any, key: string, stat: string) {
        const statKey = `${key}_${stat}`;
        const statValue = Number(row?.[statKey]);
        if (!Number.isNaN(statValue)) return Math.max(0, Math.min(100, statValue));
        return this.chartValue(row, key);
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

    private chartTimestamp(row: any) {
        const date = this.chartDateFromValue(row?.reported_at);
        return date ? date.getTime() : String(row?.reported_at || '');
    }

    private apexBaseOptions(height: number = 250) {
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

    private cpuChartOptions(rows: any[], height: number = 250) {
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

    private memoryChartOptions(rows: any[], height: number = 250) {
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

    private storageChartOptions(rows: any[], height: number = 250) {
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

    private chartOptions(rows: any[], metric: string, height: number = 250) {
        if (metric === 'memory') return this.memoryChartOptions(rows, height);
        if (metric === 'storage') return this.storageChartOptions(rows, height);
        return this.cpuChartOptions(rows, height);
    }

    private stripApexChartTitles(element: HTMLElement) {
        element.querySelectorAll('[title]').forEach((node: Element) => node.removeAttribute('title'));
        element.querySelectorAll('title').forEach((node: Element) => node.remove());
    }

    private watchApexChartTitles(element: HTMLElement) {
        this.stripApexChartTitles(element);
        if (typeof MutationObserver === 'undefined') return;
        const observer = new MutationObserver(() => this.stripApexChartTitles(element));
        observer.observe(element, { subtree: true, childList: true, attributes: true, attributeFilter: ['title'] });
        this.resourceChartTitleObservers.push(observer);
    }

    private disconnectChartTitleObservers() {
        this.resourceChartTitleObservers.forEach((observer: MutationObserver) => observer.disconnect());
        this.resourceChartTitleObservers = [];
    }

    private createApexChart(element: HTMLElement, rows: any[], metric: string, height: number = 250) {
        const chart = new ApexCharts(element, this.chartOptions(rows, metric, height) as any);
        const rendered = chart.render();
        this.watchApexChartTitles(element);
        Promise.resolve(rendered).then(() => this.stripApexChartTitles(element));
        return chart;
    }

    private destroyResourceChart() {
        this.disconnectChartTitleObservers();
        this.resourceChartInstances.forEach((chart: any) => chart.destroy());
        this.resourceChartInstances = [];
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

    private renderResourceChart() {
        if (!this.resourceChartOpen()) return;
        const rows = this.resourceRows();
        this.destroyResourceChart();
        if (!rows.length) return;
        this.resourceChartElements().forEach((element: HTMLElement) => {
            const metric = String(element.getAttribute('data-resource-chart') || 'cpu');
            this.resourceChartInstances.push(this.createApexChart(element, rows, metric));
        });
    }

    public isEditing() {
        return Boolean(this.editingNodeId());
    }

    public serverModalTitle() {
        return this.isEditing() ? '서버 정보 수정' : '서버 추가';
    }

    public serverSubmitLabel() {
        if (this.busy()) return this.isEditing() ? '저장 중' : '확인 중';
        return this.isEditing() ? '연결 정보 저장' : '연결 후 등록';
    }

    public async openImportCompose(container: any = null) {
        const candidate = container || null;
        this.importCandidate.set(candidate);
        this.fileBrowserOpen.set(true);
        this.fileBrowserPath.set('');
        this.fileBrowserInput.set('');
        this.fileBrowserShowHidden.set(false);
        this.composeImportName.set(this.defaultComposeImportName(candidate));
        this.fileBrowserItems.set([]);
        await this.browseFiles('');
    }

    public async browseFiles(path: string = '') {
        const nodeId = this.selected()?.id;
        if (!nodeId) return;
        this.fileBrowserBusy.set(true);
        const { code, data } = await wiz.call("browse_files", {
            node_id: nodeId,
            path,
            show_hidden: this.fileBrowserShowHidden(),
        });
        if (code === 200) {
            this.fileBrowserPath.set(data.path || '');
            this.fileBrowserInput.set(data.path || '');
            this.fileBrowserItems.set(data.items || []);
        } else {
            await this.alert(data?.message || '파일 목록을 불러올 수 없습니다.');
        }
        this.fileBrowserBusy.set(false);
        await this.service.render();
    }

    public async jumpToBrowsePath() {
        const next = this.normalizedBrowseInput();
        await this.browseFiles(next);
    }

    public async toggleHiddenFiles() {
        this.fileBrowserShowHidden.set(!this.fileBrowserShowHidden());
        await this.browseFiles(this.fileBrowserPath() || '');
    }

    public async browseParent() {
        const current = this.fileBrowserPath();
        if (!current || current === '/') return;
        const parent = this.fileBrowserParent();
        if (parent) await this.browseFiles(parent);
    }

    public async importComposeFile(item: any) {
        if (!this.canImportFile(item)) return;
        const nodeId = this.selected()?.id;
        if (!nodeId) {
            await this.alert('서버를 먼저 선택해주세요.');
            return;
        }
        const serviceName = this.composeImportNameValue();
        if (!serviceName) {
            await this.alert('서비스 이름을 입력해주세요.');
            return;
        }
        const params = new URLSearchParams();
        params.set('import_node_id', String(nodeId));
        params.set('import_path', String(item.path || ''));
        params.set('import_name', serviceName);
        this.service.href(`/services/create?${params.toString()}`);
    }

    private async performImportCompose(item: any, allowWarnings: boolean) {
        this.busy.set(true);
        this.fileBrowserBusy.set(true);
        const candidate = this.importCandidate() || {};
        const serviceName = this.composeImportNameValue();
        const { code, data } = await wiz.call("import_compose_service", {
            node_id: this.selected()?.id,
            path: item.path,
            suggested_namespace: serviceName || candidate.service_namespace || candidate.name,
            suggested_name: serviceName || candidate.name || candidate.runtime_service_name || candidate.service_namespace,
            allow_warnings: allowWarnings,
        });
        if (code === 200) {
            this.setSelectedNode(data.node || null);
            this.applyContainerPanel(data);
            this.actionTitle.set('서비스 등록 결과');
            this.actionResult.set({
                checks: { import: 'ok', containers: 'ok' },
                service: data.imported_service?.service,
                compose_path: item.path
            });
            this.fileBrowserOpen.set(false);
            this.fileBrowserItems.set([]);
            this.fileBrowserPath.set('');
            this.fileBrowserInput.set('');
            this.composeImportName.set('');
            this.importCandidate.set(null);
            this.actionModalOpen.set(true);
        } else if (!allowWarnings && data?.warning && data?.can_continue) {
            this.fileBrowserBusy.set(false);
            this.busy.set(false);
            await this.service.render();
            const confirmed = await this.service.modal.show({
                title: 'Compose 확인 필요',
                message: this.formatErrorMessage(data, 'Compose에 확인이 필요한 항목이 있습니다.'),
                cancel: '취소',
                action: '그래도 등록',
                actionBtn: 'warning',
                status: 'warning',
            });
            if (confirmed) {
                await this.performImportCompose(item, true);
            }
            return;
        } else {
            await this.alert(this.formatErrorMessage(data, '서비스를 등록할 수 없습니다.'));
        }
        this.fileBrowserBusy.set(false);
        this.busy.set(false);
        await this.service.render();
    }

    public async runContainerAction(container: any, action: string) {
        if (!this.canRunContainerAction(container, action)) return;
        const labels: any = { start: '실행', stop: '중지', restart: '재시작', delete: '삭제' };
        const isDelete = action === 'delete';
        const confirmed = await this.service.modal.show({
            title: `컨테이너 ${labels[action]}`,
            message: isDelete
                ? `${container.name || container.id} 컨테이너를 삭제합니다.\n\n실행 중이면 먼저 중지한 뒤 삭제합니다. 이 작업은 되돌릴 수 없습니다.`
                : `${container.name || container.id} 컨테이너를 ${labels[action]}합니다.`,
            cancel: '취소',
            action: labels[action],
            actionBtn: isDelete ? 'error' : (action === 'stop' ? 'warning' : 'primary'),
            status: isDelete ? 'error' : 'info'
        });
        if (!confirmed) return;

        this.busy.set(true);
        const { code, data } = await wiz.call("container_action", { node_id: this.selected()?.id, container_id: container.id, action });
        if (code === 200) {
            this.setSelectedNode(data.node || null);
            this.applyContainerPanel(data);
            this.actionTitle.set(isDelete ? '컨테이너 삭제 결과' : '컨테이너 동작 결과');
            this.actionResult.set({ checks: { command: 'ok', containers: 'ok' }, command: data.result });
            this.actionModalOpen.set(true);
        } else {
            await this.alert(data?.message || '컨테이너 동작을 실행할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public async runServiceAction(group: any, action: string) {
        if (!this.canRunServiceAction(group, action)) return;
        const labels: any = { start: '일괄 실행', stop: '일괄 중지', restart: '일괄 재시작' };
        const confirmed = await this.service.modal.show({
            title: labels[action],
            message: `${group.service?.name || group.service?.namespace} 서비스를 ${labels[action]}합니다.`,
            cancel: '취소',
            action: labels[action],
            actionBtn: action === 'stop' ? 'warning' : 'primary',
            status: 'info'
        });
        if (!confirmed) return;

        this.busy.set(true);
        const { code, data } = await wiz.call("service_action", { node_id: this.selected()?.id, service_namespace: group.service?.namespace, action });
        if (code === 200) {
            this.setSelectedNode(data.node || null);
            this.applyContainerPanel(data);
            this.actionTitle.set('서비스 동작 결과');
            this.actionResult.set({ checks: { command: 'ok', containers: 'ok' }, command: data.result });
            this.actionModalOpen.set(true);
        } else {
            await this.alert(data?.message || '서비스 동작을 실행할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public metricValue(path: string, fallback: any = null) {
        const metric = this.selected()?.latest_metric || {};
        const parts = path.split(".");
        let value: any = metric;
        for (const part of parts) value = value?.[part];
        if (value === undefined || value === null || value === "") return fallback;
        return value;
    }

    public percent(value: any) {
        if (value === undefined || value === null || value === "") return "-";
        const num = Number(value);
        if (Number.isNaN(num)) return String(value);
        return `${num.toFixed(1)}%`;
    }

    public progressPercent(value: any) {
        const num = Number(value);
        if (Number.isNaN(num) || num < 0) return 0;
        if (num > 100) return 100;
        return num;
    }

    private chartValue(row: any, key: string) {
        const value = Number(row?.[key]);
        if (Number.isNaN(value)) return 0;
        return Math.max(0, Math.min(100, value));
    }

    public resourceRows() {
        return this.resourceHistory()?.rows || [];
    }

    public resourceHistorySummaryText() {
        const count = this.resourceHistory()?.count || this.resourceRows().length || 0;
        const sourceCount = this.resourceHistory()?.source_count ?? this.resourceHistory()?.sample_count ?? count;
        if (!count) return '선택한 기간에 기록이 없습니다.';
        return `${count}개 구간 · ${sourceCount || 0}개 샘플`;
    }

    public latestResourcePercent(key: string) {
        const rows = this.resourceRows();
        if (!rows.length) return '-';
        return this.percent(rows[rows.length - 1]?.[`${key}_last`] ?? rows[rows.length - 1]?.[key]);
    }

    public resourceStatSummary(key: string) {
        const rows = this.resourceRows();
        if (!rows.length) return '-';
        const row = rows[rows.length - 1] || {};
        const avg = this.percent(row[`${key}_avg`] ?? row[key]);
        const min = this.percent(row[`${key}_min`] ?? row[key]);
        const max = this.percent(row[`${key}_max`] ?? row[key]);
        return `평균 ${avg} · ${min} ~ ${max}`;
    }

    public formatChartTime(value: any) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value).slice(0, 16);
        return date.toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
    }

    public formatBytes(value: any) {
        const num = Number(value);
        if (!num || Number.isNaN(num)) return "-";
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let size = num;
        let index = 0;
        while (size >= 1024 && index < units.length - 1) {
            size = size / 1024;
            index += 1;
        }
        return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
    }

    public containerSummary() {
        return this.containerStats();
    }

    public localMasterCount() {
        return this.nodes().filter((node) => node.is_local_master).length;
    }

    public workerCount() {
        return this.nodes().filter((node) => !node.is_local_master).length;
    }

    private nodeRuntimeSummary(node: any) {
        return node?.runtime_summary || {};
    }

    public nodeServiceCount(node: any) {
        return Number(this.nodeRuntimeSummary(node).service_count || 0);
    }

    public nodeRunningContainerCount(node: any) {
        return Number(this.nodeRuntimeSummary(node).container_running || 0);
    }

    public nodeContainerCountTitle(node: any) {
        const summary = this.nodeRuntimeSummary(node);
        const total = Number(summary.container_total || 0);
        const running = Number(summary.container_running || 0);
        const stopped = Number(summary.container_stopped || Math.max(0, total - running));
        return `전체 ${total}개 · 실행 ${running}개 · 중지 ${stopped}개`;
    }

    public isSwarmConnected(node: any) {
        return Boolean(node?.swarm_connected || node?.swarm_node_id);
    }

    public showJoinSwarmButton(node: any) {
        return Boolean(node && !node.is_local_master && !this.isSwarmConnected(node));
    }

    public deploymentModeText(node: any) {
        return this.isSwarmConnected(node) ? '클러스터' : '독립 서버';
    }

    public swarmBadgeText(node: any) {
        return this.deploymentModeText(node);
    }

    public swarmBadgeClass(node: any) {
        if (this.isSwarmConnected(node)) {
            return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300';
        }
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300';
    }

    private nodeStatusTone(node: any) {
        const status = String(node?.status || '').toLowerCase();
        if (['unreachable', 'failed', 'error', 'canceled'].includes(status)) return 'danger';
        if (['pending', 'degraded', 'warning', 'unknown', 'skipped'].includes(status) || !status) return 'warning';
        return 'ok';
    }

    public nodeStatusIcon(node: any) {
        return this.nodeStatusTone(node) === 'ok' ? 'fa-circle-check' : 'fa-triangle-exclamation';
    }

    public nodeStatusIconClass(node: any) {
        const tone = this.nodeStatusTone(node);
        if (tone === 'danger') return 'text-rose-600 dark:text-rose-300';
        if (tone === 'warning') return 'text-amber-600 dark:text-amber-300';
        return 'text-emerald-600 dark:text-emerald-300';
    }

    public nodeStatusTitle(node: any) {
        return `서버 상태: ${this.statusLabel(String(node?.status || 'unknown').toLowerCase())}`;
    }

    public monitoringAgent(node: any = this.selected()) {
        return node?.monitoring_agent || node?.metadata?.monitoring_agent || {};
    }

    public monitoringConfigured(node: any = this.selected()) {
        return Boolean(this.monitoringAgent(node)?.configured);
    }

    public isNodeCollecting(node: any) {
        const ids = this.monitoringState()?.collecting_node_ids || [];
        return Boolean(node?.id && (ids.includes(node.id) || this.monitoringConfigured(node)));
    }

    public statusLabel(status: string) {
        const labels: any = {
            active: '정상',
            ready: '준비됨',
            degraded: '확인 필요',
            inactive: '정상',
            running: '실행 중',
            reachable: '접속 가능',
            pending: '확인 필요',
            unreachable: '접속 불가',
            failed: '실패',
            error: '오류',
            succeeded: '완료',
            canceled: '취소됨',
            skipped: '건너뜀',
            warning: '확인 필요',
            ok: '정상',
            unknown: '알 수 없음'
        };
        return labels[status] || status || '-';
    }

    public roleLabel(node: any) {
        if (!node) return '-';
        return node.is_local_master || node.role === 'local_master' ? '중심 서버' : '일반 서버';
    }

    private isLikelyPrivateHost(value: string) {
        const host = String(value || '').trim();
        if (!host) return false;
        if (['localhost', '127.0.0.1', '::1'].includes(host)) return true;
        const match = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
        if (!match) return false;
        const first = Number(match[1]);
        const second = Number(match[2]);
        return first === 10 || (first === 172 && second >= 16 && second <= 31) || (first === 192 && second === 168) || (first === 169 && second === 254);
    }

    public nodeHostLabel(node: any) {
        if (!node) return '-';
        const localMaster = node.is_local_master || node.role === 'local_master';
        const accessHost = String(node.private_host || node.metadata?.private_host || node.metadata?.node_access_host || '').trim();
        const host = accessHost || String(node.host || '').trim();
        if (!localMaster) return host || '-';
        const publicIp = String(node.public_ip || node.metadata?.public_ip || '').trim();
        const privateHost = host && this.isLikelyPrivateHost(host);
        if (privateHost && publicIp && host !== publicIp) {
            return `${host} · 공인 ${publicIp}`;
        }
        if (privateHost) return host;
        if (publicIp) return publicIp;
        return host || '-';
    }

    public statusClass(status: string) {
        if (['running'].includes(status)) {
            return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300';
        }
        if (['active', 'ready', 'inactive', 'ok', 'succeeded'].includes(status)) {
            return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        }
        if (['reachable', 'pending', 'warning', 'unknown', 'canceled', 'skipped'].includes(status)) {
            return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        }
        if (['unreachable', 'failed', 'error'].includes(status)) {
            return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        }
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }

    public containerState(container: any) {
        return String(container?.state || '').toLowerCase();
    }

    public containerStatusText(container: any) {
        return String(container?.status || '').toLowerCase();
    }

    public containerSignal(container: any) {
        const state = this.containerState(container);
        const status = this.containerStatusText(container);
        if (status.includes('unhealthy')) return 'unhealthy';
        if (status.includes('health: starting')) return 'starting';
        if (status.includes('healthy')) return 'healthy';
        return state;
    }

    public containerStatusLabel(container: any) {
        const state = this.containerSignal(container);
        const labels: any = {
            running: '실행 중',
            healthy: '실행 중',
            unhealthy: '이상',
            starting: '준비 중',
            restarting: '재시작 중',
            exited: '중지됨',
            created: '준비됨',
            paused: '일시 중지',
            dead: '비정상 종료',
            removing: '삭제 중'
        };
        return labels[state] || container?.status || state || '-';
    }

    public containerStatusClass(container: any) {
        const state = this.containerSignal(container);
        if (['running', 'healthy'].includes(state)) {
            return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300';
        }
        if (['restarting', 'starting', 'paused', 'created', 'removing'].includes(state)) {
            return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        }
        if (['dead', 'unhealthy'].includes(state)) {
            return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        }
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }

    public canRunContainerAction(container: any, action: string) {
        const state = this.containerSignal(container);
        if (action === 'delete') return Boolean(container?.id) && state !== 'removing';
        const allowed: any = {
            start: ['created', 'exited', 'dead'],
            restart: ['running', 'healthy', 'unhealthy', 'starting', 'paused', 'created', 'exited', 'dead'],
            stop: ['running', 'healthy', 'unhealthy', 'starting', 'paused', 'restarting'],
        };
        return (allowed[action] || []).includes(state);
    }

    public canRunServiceAction(group: any, action: string) {
        return (group?.containers || []).some((container: any) => this.canRunContainerAction(container, action));
    }

    public containerActionTitle(container: any, action: string) {
        const labels: any = { start: '실행', stop: '중지', restart: '재시작', delete: '삭제' };
        if (this.canRunContainerAction(container, action)) return `컨테이너 ${labels[action]}`;
        const reasons: any = {
            start: '중지된 컨테이너만 실행할 수 있습니다.',
            stop: '실행 중인 컨테이너만 중지할 수 있습니다.',
            restart: '현재 상태에서는 재시작할 수 없습니다.',
            delete: '삭제할 수 없는 상태입니다.',
        };
        return reasons[action] || labels[action];
    }

    public serviceActionTitle(group: any, action: string) {
        const labels: any = { start: '일괄 실행', stop: '일괄 중지', restart: '일괄 재시작' };
        if (this.canRunServiceAction(group, action)) return labels[action];
        const reasons: any = {
            start: '실행 가능한 중지 컨테이너가 없습니다.',
            stop: '중지할 실행 중 컨테이너가 없습니다.',
            restart: '재시작할 수 있는 컨테이너가 없습니다.',
        };
        return reasons[action] || labels[action];
    }

    public serviceDisplayName(group: any) {
        return group?.service?.name || group?.service?.namespace || '등록된 서비스';
    }

    public serviceDetailQueryParams(group: any) {
        const id = group?.service?.id;
        return id ? { service_id: id } : {};
    }

    public serviceDetailRoute(group: any) {
        const id = group?.service?.id;
        return id ? ['/services', id] : ['/services'];
    }

    public serviceRuntimeStatus(group: any) {
        const summary = group?.summary || {};
        const total = Number(summary.total || 0);
        const running = Number(summary.running || 0);
        if (!total) return { label: '상태 없음', status: 'unknown' };
        if (running === total) return { label: '정상 운영', status: 'running' };
        if (running > 0) return { label: `일부 운영 ${running}/${total}`, status: 'warning' };
        return { label: '중지됨', status: 'failed' };
    }

    public runningServiceCount(group: any) {
        const summary = group?.summary || {};
        const running = Number(summary.running || 0);
        if (running > 0) return running;
        return (group?.containers || []).filter((container: any) => this.containerState(container) === 'running').length;
    }

    public runningServiceGroups() {
        return this.serviceGroups().filter((group: any) => this.runningServiceCount(group) > 0);
    }

    public runningServicesBlockMessage(groups: any[] = this.runningServiceGroups()) {
        const names = groups.slice(0, 5).map((group: any) => this.serviceDisplayName(group)).join(', ');
        const suffix = groups.length > 5 ? ` 외 ${groups.length - 5}개` : '';
        return `실행 중인 서비스가 있어 서버 등록 해제를 진행할 수 없습니다. 먼저 서비스를 중지하거나 다른 서버로 이동해주세요. (${names}${suffix})`;
    }

    public serviceRuntimeLabel(group: any) {
        return this.serviceRuntimeStatus(group).label;
    }

    public serviceRuntimeClass(group: any) {
        return this.statusClass(this.serviceRuntimeStatus(group).status);
    }

    public servicePortBadges(group: any) {
        const badges: any[] = [];
        const seen = new Set<string>();
        for (const container of group?.containers || []) {
            for (const binding of container?.port_bindings || []) {
                let label = '';
                let tone = 'internal';
                if (binding?.mapped) {
                    label = `외부 ${this.portSourceLabel(binding)} -> 서비스 ${this.portTargetLabel(binding)}`;
                    tone = 'public';
                } else if (binding?.internal_only) {
                    label = `내부 ${this.portTargetLabel(binding)}`;
                }
                if (!label) continue;
                const key = `${tone}:${label}`;
                if (seen.has(key)) continue;
                seen.add(key);
                badges.push({ label, tone });
            }
        }
        return badges;
    }

    public servicePortBadgeClass(badge: any) {
        if (badge?.tone === 'public') {
            return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300';
        }
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300';
    }

    public isSelected(node: any) {
        return this.selected()?.id === node.id;
    }

    public actionRows() {
        const checks = this.actionResult()?.checks || {};
        const names: any = {
            password: '비밀번호 확인',
            fingerprint: '서버 fingerprint',
            key_install: '관리용 SSH key 등록',
            key: '관리용 SSH key 접속',
            oras_install: 'ORAS 설치',
            ssh: 'SSH 접속',
            docker: 'Docker 상태',
            metric: '자원 정보 수집',
            monitoring: '모니터링 자동 구성',
            operation: '작업 실행',
            import: '서비스 등록',
            command: '명령 실행',
            containers: '컨테이너 새로고침',
            swarm: 'Swarm 상태',
            network: '서비스 네트워크',
            remote_cleanup: '삭제 대상 서버 정리',
            swarm_remove: 'Swarm 노드 제거',
            known_hosts: 'known_hosts 정리',
            database: '등록 정보 삭제',
            key_file: 'SSH key 파일 정리'
        };
        return Object.keys(checks).map((key) => {
            const raw = checks[key];
            const status = typeof raw === 'string' ? raw : (raw?.status || (raw === true ? 'ok' : 'unknown'));
            const value = key === 'fingerprint' ? '' : (raw?.reason || raw?.value || '');
            return { key, name: names[key] || key, status, value };
        });
    }

    public selectedDockerState() {
        const node = this.selected() || {};
        if (node?.docker) return node.docker;
        const metadata = node?.metadata || {};
        const docker = (metadata.last_check || {}).docker;
        if (docker) {
            const available = docker.status === 'ok';
            return { available, status: docker.status || (available ? 'ok' : 'error'), reason: available ? null : this.commandReason(docker) };
        }
        if (metadata.docker) return { available: true, status: 'ok', reason: null };
        return { available: null, status: 'unknown', reason: null };
    }

    public dockerUnavailable() {
        return this.selectedDockerState()?.available === false;
    }

    public showRuntimePanels() {
        return !this.dockerUnavailable();
    }

    public dockerUnavailableReason() {
        return this.selectedDockerState()?.reason || 'Docker가 설치되어 있지 않거나 daemon에 연결할 수 없습니다.';
    }

    public commandReason(result: any) {
        for (const value of [result?.reason, result?.stderr, result?.stdout]) {
            if (!value) continue;
            const lines = String(value).split('\n').map((line) => line.trim()).filter(Boolean);
            if (lines.length) return lines[lines.length - 1];
        }
        return '';
    }

    public keyFilePath() {
        return this.selected()?.credential?.key_file_path || this.selected()?.credential?.key_file || '-';
    }

    public keyFileReady() {
        if (this.selected()?.is_local_master) return true;
        return Boolean(this.selected()?.credential?.has_key_file);
    }

    public keyFileStatusLabel() {
        return this.selected()?.is_local_master ? '키 파일 불필요' : (this.keyFileReady() ? 'key file 준비됨' : 'key file 없음');
    }

    public fingerprintRegistered() {
        if (this.selected()?.is_local_master) return true;
        return Boolean(this.selected()?.credential?.fingerprint_registered || this.selected()?.credential?.ssh_fingerprint);
    }

    public fingerprintStatusLabel() {
        return this.selected()?.is_local_master ? 'fingerprint 확인 불필요' : (this.fingerprintRegistered() ? 'fingerprint 등록됨' : 'fingerprint 미등록');
    }

    public actionOperationLogText() {
        const output = this.actionResult()?.operation?.output || [];
        if (!output.length) return '';
        return output.map((entry: any) => {
            const stream = entry?.stream || 'system';
            const message = entry?.message || '';
            return `[${stream}] ${message}`;
        }).join('\n');
    }

    public macroRunLogText() {
        const output = this.macroRunResult()?.operation?.output || [];
        if (!output.length) return '';
        return output.map((entry: any) => {
            const stream = entry?.stream || 'system';
            const message = entry?.message || '';
            return `[${stream}] ${message}`;
        }).join('\n');
    }

    public macroRunStatus() {
        return this.macroRunResult()?.operation?.status || 'unknown';
    }

    public mappedBindings(container: any) {
        return (container?.port_bindings || []).filter((item: any) => item.mapped);
    }

    public internalBindings(container: any) {
        return (container?.port_bindings || []).filter((item: any) => item.internal_only);
    }

    public portSourceLabel(binding: any) {
        if (!binding?.mapped) return '-';
        if (binding.host && binding.host !== '0.0.0.0') return `${binding.host}:${binding.published}`;
        return `${binding.published}`;
    }

    public portTargetLabel(binding: any) {
        return `${binding?.target || '-'}${binding?.protocol ? `/${binding.protocol}` : ''}`;
    }

    public canImportFile(item: any) {
        if (!item || item.type !== 'file') return false;
        return ['docker-compose.yaml', 'docker-compose.yml'].includes(String(item.name || '').toLowerCase());
    }

    public normalizedBrowseInput() {
        const raw = String(this.fileBrowserInput() || '').trim();
        if (!raw) return '';
        if (raw.startsWith('/') || raw.startsWith('~')) return raw;
        const current = this.fileBrowserPath();
        const base = current && current !== '/' ? current.replace(/\/+$/, '') : '';
        return `${base}/${raw}`.replace(/\/{2,}/g, '/');
    }

    public fileBrowserParent() {
        const current = this.fileBrowserPath();
        if (!current || current === '/') return '';
        const parts = current.split('/').filter(Boolean);
        if (parts.length <= 1) return '/';
        return `/${parts.slice(0, -1).join('/')}`;
    }

    public fileBrowserCrumbs() {
        const current = this.fileBrowserPath();
        if (!current) return [];
        const parts = current.split('/').filter(Boolean);
        const crumbs = [{ label: '/', path: '/' }];
        let currentPath = '';
        for (const part of parts) {
            currentPath += `/${part}`;
            crumbs.push({ label: part, path: currentPath });
        }
        return crumbs;
    }

    public composeImportNameValue() {
        return String(this.composeImportName() || '').trim();
    }

    public defaultComposeImportName(candidate: any = null) {
        const value = candidate?.name || candidate?.runtime_service_name || candidate?.service_namespace || '';
        return String(value || '').trim();
    }

    public formatDate(value: any) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString();
    }
}
