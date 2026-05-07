import { HostListener, OnDestroy, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';

export class Component implements OnInit, OnDestroy {
    public loading = signal<boolean>(true);
    public busy = signal<boolean>(false);
    public detailLoading = signal<boolean>(false);
    public panelRefreshing = signal<boolean>(false);
    public error = signal<string>('');
    public detailError = signal<string>('');
    public nodes = signal<any[]>([]);
    public selected = signal<any>(null);
    public detailTab = signal<string>('overview');
    public containerStats = signal<any>({ total: 0, running: 0, stopped: 0 });
    public serviceGroups = signal<any[]>([]);
    public unmanagedContainers = signal<any[]>([]);
    public macros = signal<any[]>([]);
    public globalMacros = signal<any[]>([]);
    public nodeMacros = signal<any[]>([]);
    public macroLoading = signal<boolean>(false);
    public macroError = signal<string>('');
    public selectedMacroId = signal<string>('');
    public macroArgsEnabled = signal<boolean>(false);
    public macroArgsInput = signal<string>('');
    public macroRunResult = signal<any>(null);
    public macroModalOpen = signal<boolean>(false);
    public lastJob = signal<any>(null);
    public serverModalOpen = signal<boolean>(false);
    public editingNodeId = signal<string>('');
    public actionModalOpen = signal<boolean>(false);
    public actionTitle = signal<string>('');
    public actionResult = signal<any>(null);
    public refreshSeconds = signal<number>(5);
    public refreshOptions = [1, 3, 5, 10];
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
    public serverForm: any = this.emptyServerForm();
    public macroForm: any = this.emptyMacroForm();
    public macroEditorOptions: any = {
        language: 'shell',
        theme: 'vs',
        fontSize: 13,
        minimap: { enabled: false },
        automaticLayout: true,
        wordWrap: 'on',
        scrollBeyondLastLine: false,
        roundedSelection: false,
    };
    private refreshTimer: ReturnType<typeof setInterval> | null = null;
    private metricRequestRunning = false;
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

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        this.syncMacroEditorTheme();
        this.startThemeObserver();
        await this.load();
    }

    public ngOnDestroy() {
        this.stopAutoRefresh();
        this.stopMacroRunPolling();
        this.disconnectTerminal(true);
        this.stopThemeObserver();
    }

    @HostListener('document:keydown', ['$event'])
    public handleDocumentKeydown(event: KeyboardEvent) {
        if (!this.macroModalOpen()) return;
        const isSave = (event.ctrlKey || event.metaKey) && String(event.key || '').toLowerCase() === 's';
        if (!isSave) return;
        event.preventDefault();
        void this.saveMacro();
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

    private emptyMacroForm() {
        return {
            id: '',
            name: '',
            description: '',
            script: '#!/usr/bin/env bash\n',
            enabled: true,
        };
    }

    private resetMacroForm() {
        this.macroForm = this.emptyMacroForm();
    }

    private isDarkMode() {
        return Boolean(document.documentElement.classList.contains('dark'));
    }

    private syncMacroEditorTheme() {
        this.macroEditorOptions = {
            ...this.macroEditorOptions,
            theme: this.isDarkMode() ? 'vs-dark' : 'vs',
        };
    }

    private startThemeObserver() {
        if (typeof MutationObserver === 'undefined') return;
        this.themeObserver = new MutationObserver(() => {
            this.syncMacroEditorTheme();
            this.applyTerminalTheme();
        });
        this.themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    }

    private stopThemeObserver() {
        if (!this.themeObserver) return;
        this.themeObserver.disconnect();
        this.themeObserver = null;
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
        this.applyContainerPanel({ summary: { total: 0, running: 0, stopped: 0 }, service_groups: [], unmanaged_containers: [] });
        this.globalMacros.set([]);
        this.nodeMacros.set([]);
        this.macros.set([]);
        this.selectedMacroId.set('');
        this.macroArgsEnabled.set(false);
        this.macroArgsInput.set('');
        this.macroRunResult.set(null);
        this.lastJob.set(null);
        this.detailError.set('');
        this.detailLoading.set(false);
        this.panelRefreshing.set(false);
        return this.selectionEpoch;
    }

    private isActiveSelection(nodeId: string, epoch: number) {
        return Boolean(nodeId) && this.selectionEpoch === epoch && this.selected()?.id === nodeId;
    }

    private applyOverview(data: any) {
        this.nodes.set(data.nodes || []);
        this.setSelectedNode(data.selected || null);
        this.detailError.set('');
    }

    private applyContainerPanel(data: any) {
        this.containerStats.set(data.summary || { total: 0, running: 0, stopped: 0 });
        this.serviceGroups.set(data.service_groups || []);
        this.unmanagedContainers.set(data.unmanaged_containers || []);
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

    private async fetchCachedDetail(nodeId: string, silent: boolean = false, epoch: number = this.selectionEpoch) {
        if (!nodeId) return;
        this.detailLoading.set(true);
        const { code, data } = await wiz.call("cached_detail", { node_id: nodeId });
        if (!this.isActiveSelection(nodeId, epoch)) return;
        if (code === 200) {
            this.setSelectedNode(data.node || null);
            this.applyContainerPanel(data);
            this.detailError.set('');
            this.restartAutoRefresh();
        } else if (silent) {
            this.detailError.set(data?.message || '저장된 서버 상세 정보를 불러올 수 없습니다.');
        } else {
            await this.alert(data?.message || '서버 상세를 불러올 수 없습니다.');
        }
        this.detailLoading.set(false);
        await this.service.render();
    }

    private async refreshDetailInBackground(nodeId: string, epoch: number = this.selectionEpoch) {
        if (!nodeId) return;
        const token = ++this.backgroundRefreshToken;
        this.panelRefreshing.set(true);
        await this.service.render();
        try {
            if (!this.isActiveSelection(nodeId, epoch) || token !== this.backgroundRefreshToken) return;
            await this.fetchMetrics(true, nodeId, epoch);
            if (!this.isActiveSelection(nodeId, epoch) || token !== this.backgroundRefreshToken) return;
            await this.refreshContainers(true, nodeId, epoch);
        } finally {
            if (token === this.backgroundRefreshToken && this.isActiveSelection(nodeId, epoch)) {
                this.panelRefreshing.set(false);
                await this.service.render();
            }
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
            if (this.busy() || this.metricRequestRunning) return;
            void this.fetchMetrics(true, this.selected()?.id, epoch);
        }, this.refreshSeconds() * 1000);
    }

    private stopMacroRunPolling() {
        if (!this.macroRunTimer) return;
        clearTimeout(this.macroRunTimer);
        this.macroRunTimer = null;
    }

    private isTerminalJobStatus(status: string) {
        return ['succeeded', 'failed', 'canceled'].includes(String(status || '').toLowerCase());
    }

    private scheduleMacroRunPoll(jobId: string, token: number, delayMs: number = 500) {
        this.stopMacroRunPolling();
        if (!jobId || token !== this.macroRunToken) return;
        this.macroRunTimer = setTimeout(() => {
            void this.pollMacroRun(jobId, token);
        }, delayMs);
    }

    private async pollMacroRun(jobId: string, token: number) {
        if (!jobId || token !== this.macroRunToken) return;
        try {
            const response = await fetch(`/api/jobs/${jobId}`, { credentials: 'same-origin' });
            const payload = await response.json().catch(() => null);
            if (token !== this.macroRunToken) return;
            const job = payload?.data?.job || null;
            if (response.ok && job) {
                const current = this.macroRunResult() || {};
                this.lastJob.set(job);
                this.macroRunResult.set({ ...current, job });
                if (!this.isTerminalJobStatus(job.status)) {
                    this.scheduleMacroRunPoll(jobId, token);
                }
            } else if (!this.isTerminalJobStatus(this.macroRunStatus())) {
                this.scheduleMacroRunPoll(jobId, token, 1200);
            }
        } catch {
            if (token === this.macroRunToken && !this.isTerminalJobStatus(this.macroRunStatus())) {
                this.scheduleMacroRunPoll(jobId, token, 1200);
            }
        }
        await this.service.render();
    }

    private async fetchMetrics(silent: boolean = false, targetNodeId: string | null = null, epoch: number = this.selectionEpoch) {
        const nodeId = targetNodeId || this.selected()?.id;
        if (!nodeId || this.metricRequestRunning) return;
        this.metricRequestRunning = true;
        const { code, data } = await wiz.call("refresh_metrics", { node_id: nodeId });
        this.metricRequestRunning = false;
        if (!this.isActiveSelection(nodeId, epoch)) return;
        if (code === 200) {
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

    public async load(selectedId: string = '') {
        this.loading.set(true);
        this.error.set('');
        this.detailLoading.set(false);
        this.panelRefreshing.set(false);
        this.stopAutoRefresh();
        const { code, data } = await wiz.call("load", { selected_id: selectedId });
        if (code === 200) {
            this.applyOverview(data);
            const epoch = this.beginSelection(data.selected || null);
            this.restartAutoRefresh();
            this.loading.set(false);
            await this.service.render();
            if (data.selected?.id) {
                void this.loadMacros(data.selected.id);
                void this.fetchCachedDetail(data.selected.id, true, epoch);
                void this.refreshDetailInBackground(data.selected.id, epoch);
            }
            return;
        } else {
            this.error.set(data?.message || '서버 정보를 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
    }

    public async selectNode(node: any) {
        const epoch = this.beginSelection(node);
        await this.service.render();
        void this.loadMacros(node.id);
        void this.fetchCachedDetail(node.id, false, epoch);
        void this.refreshDetailInBackground(node.id, epoch);
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
            void this.alert('중심 서버 정보는 이 서비스가 실행 중인 서버를 기준으로 자동 동기화됩니다.', 'info');
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

    public openAddMacro() {
        if (!this.selected()?.id) return;
        this.resetMacroForm();
        this.syncMacroEditorTheme();
        this.macroModalOpen.set(true);
    }

    public openEditMacro(macro: any) {
        this.macroForm = {
            id: macro?.id || '',
            name: macro?.name || '',
            description: macro?.description || '',
            script: macro?.script || '#!/usr/bin/env bash\n',
            enabled: macro?.enabled !== false,
        };
        this.syncMacroEditorTheme();
        this.macroModalOpen.set(true);
    }

    public closeMacroModal() {
        if (this.busy()) return;
        this.macroModalOpen.set(false);
        this.resetMacroForm();
    }

    public macroModalTitle() {
        return this.macroForm?.id ? '서버 전용 매크로 수정' : '서버 전용 매크로 추가';
    }

    public macroSubmitLabel() {
        if (this.busy()) return this.macroForm?.id ? '저장 중' : '등록 중';
        return this.macroForm?.id ? '저장' : '등록';
    }

    public async loadMacros(nodeId: string | null = this.selected()?.id) {
        const targetNodeId = String(nodeId || '').trim();
        if (!targetNodeId) {
            this.globalMacros.set([]);
            this.nodeMacros.set([]);
            this.macros.set([]);
            this.selectedMacroId.set('');
            return;
        }
        const token = ++this.macroRequestToken;
        this.macroLoading.set(true);
        this.macroError.set('');
        const { code, data } = await wiz.call("list_macros", { node_id: targetNodeId });
        if (token !== this.macroRequestToken || this.selected()?.id !== targetNodeId) return;
        if (code === 200) {
            const available = data.available_macros || [];
            const previous = this.selectedMacroId();
            this.globalMacros.set(data.global_macros || []);
            this.nodeMacros.set(data.node_macros || []);
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

    public async saveMacro() {
        const name = String(this.macroForm?.name || '').trim();
        const script = String(this.macroForm?.script || '').trim();
        if (!name) {
            await this.alert('매크로 이름을 입력해주세요.');
            return;
        }
        if (!script) {
            await this.alert('실행할 스크립트를 입력해주세요.');
            return;
        }

        this.busy.set(true);
        const { code, data } = await wiz.call("save_macro", {
            id: this.macroForm?.id || undefined,
            node_id: this.selected()?.id,
            name,
            description: this.macroForm?.description || '',
            script: this.macroForm?.script || '',
            enabled: this.macroForm?.enabled !== false,
        });
        if (code === 200) {
            this.macroModalOpen.set(false);
            this.resetMacroForm();
            await this.loadMacros(this.selected()?.id);
        } else {
            await this.alert(data?.message || '매크로를 저장할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public async deleteMacro(macro: any) {
        const confirmed = await this.service.modal.show({
            title: '매크로 삭제',
            message: `${macro?.name || '선택한 매크로'}를 삭제합니다.`,
            cancel: '취소',
            action: '삭제',
            actionBtn: 'warning',
            status: 'warning',
        });
        if (!confirmed) return;

        this.busy.set(true);
        const { code, data } = await wiz.call("delete_macro", { macro_id: macro?.id });
        if (code === 200) {
            if (this.selectedMacroId() === macro?.id) {
                this.selectedMacroId.set('');
                this.macroRunResult.set(null);
            }
            await this.loadMacros(this.selected()?.id);
        } else {
            await this.alert(data?.message || '매크로를 삭제할 수 없습니다.');
        }
        this.busy.set(false);
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
        this.lastJob.set(null);
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
            const job = data.job || null;
            this.lastJob.set(job);
            this.macroRunResult.set({
                job,
                macro,
                args,
            });
            if (job?.id && !this.isTerminalJobStatus(job.status) && token === this.macroRunToken) {
                this.scheduleMacroRunPoll(job.id, token, 250);
            }
        } else {
            await this.alert(data?.message || '매크로를 실행할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public macroScopeLabel(macro: any) {
        return macro?.scope_type === 'node' ? '이 서버 전용' : '전역';
    }

    public macroScopeClass(macro: any) {
        return macro?.scope_type === 'node'
            ? 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300'
            : 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300';
    }

    public macroSelectorItems() {
        return this.macros().map((macro: any) => ({
            value: macro.id,
            label: macro.name,
            description: macro.description || (macro.scope_type === 'node'
                ? '이 서버에서만 실행할 수 있는 매크로'
                : '여러 서버에서 공통으로 실행하는 전역 매크로'),
            badge: macro.enabled === false ? '비활성화' : this.macroScopeLabel(macro),
            badgeClass: macro.enabled === false ? this.statusClass('warning') : this.macroScopeClass(macro),
            disabled: false,
        }));
    }

    public macroCountSummary() {
        return `전역 ${this.globalMacros().length}개 · 서버 전용 ${this.nodeMacros().length}개`;
    }

    public setDetailTab(tab: string) {
        this.detailTab.set(tab);
        if (tab === 'terminal') {
            void this.service.render(0).then(() => this.fitTerminal());
        }
    }

    public isDetailTab(tab: string) {
        return this.detailTab() === tab;
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
            message: '현재 Docker Infra가 실행 중인 서버의 Docker/Swarm 상태를 다시 확인합니다.',
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
            this.actionResult.set({ checks: { docker: 'ok', swarm: data.result?.swarm?.manager ? 'ok' : 'warning', network: data.result?.overlay_network?.status || 'ok' } });
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
            this.actionResult.set({ checks: data.node?.metadata?.connection_checks || {}, node: data.node });
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
            this.lastJob.set(data.job || null);
            this.actionTitle.set('Swarm 연결 결과');
            this.actionResult.set({ checks: { job: data.job?.status || 'unknown', swarm: data.selected?.status === 'active' ? 'ok' : 'warning' }, job: data.job });
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
        const serviceName = this.composeImportNameValue();
        if (!serviceName) {
            await this.alert('서비스 이름을 입력해주세요.');
            return;
        }
        const confirmed = await this.service.modal.show({
            title: '서비스 등록',
            message: `${item.path} 파일로 ${serviceName} 서비스 초안을 등록합니다.`,
            cancel: '취소',
            action: '등록',
            actionBtn: 'primary',
            status: 'info'
        });
        if (!confirmed) return;
        await this.performImportCompose(item, false);
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
        const labels: any = { start: '실행', stop: '중지', restart: '재시작' };
        const confirmed = await this.service.modal.show({
            title: `컨테이너 ${labels[action]}`,
            message: `${container.name || container.id} 컨테이너를 ${labels[action]}합니다.`,
            cancel: '취소',
            action: labels[action],
            actionBtn: action === 'stop' ? 'warning' : 'primary',
            status: 'info'
        });
        if (!confirmed) return;

        this.busy.set(true);
        const { code, data } = await wiz.call("container_action", { node_id: this.selected()?.id, container_id: container.id, action });
        if (code === 200) {
            this.setSelectedNode(data.node || null);
            this.applyContainerPanel(data);
            this.actionTitle.set('컨테이너 동작 결과');
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
            message: `${group.service?.name || group.service?.namespace} 서비스 컨테이너를 ${labels[action]}합니다.`,
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
            this.actionTitle.set('서비스 컨테이너 동작 결과');
            this.actionResult.set({ checks: { command: 'ok', containers: 'ok' }, command: data.result });
            this.actionModalOpen.set(true);
        } else {
            await this.alert(data?.message || '서비스 컨테이너 동작을 실행할 수 없습니다.');
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

    public statusLabel(status: string) {
        const labels: any = {
            active: '정상',
            ready: '준비됨',
            running: '실행 중',
            reachable: '접속 가능',
            pending: '확인 필요',
            unreachable: '접속 불가',
            failed: '실패',
            error: '오류',
            succeeded: '완료',
            canceled: '취소됨',
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

    public roleDescription(node: any) {
        if (!node) return '-';
        return node.is_local_master || node.role === 'local_master' ? '이 서비스가 실행 중인 서버' : '저장된 SSH key로 관리하는 서버';
    }

    public statusClass(status: string) {
        if (['running'].includes(status)) {
            return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300';
        }
        if (['active', 'ready', 'ok', 'succeeded'].includes(status)) {
            return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        }
        if (['reachable', 'pending', 'warning', 'unknown', 'canceled'].includes(status)) {
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
        const labels: any = { start: '실행', stop: '중지', restart: '재시작' };
        if (this.canRunContainerAction(container, action)) return `컨테이너 ${labels[action]}`;
        const reasons: any = {
            start: '중지된 컨테이너만 실행할 수 있습니다.',
            stop: '실행 중인 컨테이너만 중지할 수 있습니다.',
            restart: '현재 상태에서는 재시작할 수 없습니다.',
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
            ssh: 'SSH 접속',
            docker: 'Docker 상태',
            metric: '자원 정보 수집',
            job: '작업 실행',
            import: '서비스 등록',
            command: '명령 실행',
            containers: '컨테이너 새로고침',
            swarm: 'Swarm 상태',
            network: 'Overlay 네트워크'
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

    public actionJobLogText() {
        const logs = this.actionResult()?.job?.logs || [];
        if (!logs.length) return '';
        return logs.map((log: any) => {
            const stream = log?.stream || 'system';
            const message = log?.message || '';
            return `[${stream}] ${message}`;
        }).join('\n');
    }

    public macroRunLogText() {
        const logs = this.macroRunResult()?.job?.logs || [];
        if (!logs.length) return '';
        return logs.map((log: any) => {
            const stream = log?.stream || 'system';
            const message = log?.message || '';
            return `[${stream}] ${message}`;
        }).join('\n');
    }

    public macroRunStatus() {
        return this.macroRunResult()?.job?.status || 'unknown';
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
