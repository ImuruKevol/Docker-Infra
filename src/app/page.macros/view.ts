import { HostListener, OnDestroy, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit, OnDestroy {
    public loading = signal<boolean>(true);
    public busy = signal<boolean>(false);
    public error = signal<string>('');
    public search = signal<string>('');
    public selectedMacroId = signal<string>('');
    public editorMode = signal<string>('view');
    public macros = signal<any[]>([]);
    public nodes = signal<any[]>([]);
    public serviceTargets = signal<any[]>([]);
    public macroPagination = signal<any>({ current: 1, start: 1, end: 1, total: 0, limit: 10 });
    public runTargetType = signal<string>('server');
    public selectedNodeId = signal<string>('');
    public selectedServiceId = signal<string>('');
    public selectedServiceTargetId = signal<string>('');
    public macroArgsEnabled = signal<boolean>(false);
    public macroArgsInput = signal<string>('');
    public macroRunResult = signal<any>(null);
    public scheduleModalOpen = signal<boolean>(false);
    public scheduleHistoryResultOpen = signal<boolean>(false);
    public scheduleHistoryResultItem = signal<any>(null);
    public scheduleHistoryResultOperationId = signal<string>('');
    public scheduleHistoryLoading = signal<boolean>(false);
    public scheduleHistoryError = signal<string>('');
    public scheduleHistoryPagination = signal<any>({ current: 1, start: 1, end: 1, total: 0, limit: 10 });
    public scheduleTargetSearch = signal<string>('');
    public scheduleFormMode = signal<string>('create');
    public macroForm: any = this.emptyMacroForm();
    public scheduleForm: any = this.emptyScheduleForm();
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
    public pageSize = 10;
    public scheduleHistoryPageSize = 10;
    private themeObserver: MutationObserver | null = null;
    private agentCommandHandler: ((event: Event) => void) | null = null;
    private macroRunTimer: ReturnType<typeof setTimeout> | null = null;
    private macroRunToken = 0;
    private scheduleHistoryToken = 0;

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        this.syncMacroEditorTheme();
        this.startThemeObserver();
        this.startAgentCommandListener();
        const macroId = this.routeMacroId();
        if (macroId) this.selectedMacroId.set(macroId);
        await this.load(true);
    }

    public ngOnDestroy() {
        this.stopThemeObserver();
        this.stopAgentCommandListener();
        this.stopMacroRunPolling();
    }

    @HostListener('document:keydown', ['$event'])
    public handleDocumentKeydown(event: KeyboardEvent) {
        if (!this.isEditingMacro()) return;
        const isSave = (event.ctrlKey || event.metaKey) && String(event.key || '').toLowerCase() === 's';
        if (!isSave) return;
        event.preventDefault();
        void this.saveMacro();
    }

    private emptyMacroForm() {
        return {
            id: '',
            name: '',
            description: '',
            script: '#!/usr/bin/env bash\n',
            existing_files: [],
            files: [],
        };
    }

    private resetMacroForm() {
        this.macroForm = this.emptyMacroForm();
    }

    private emptyScheduleForm(macroId: string = this.selectedMacroId()) {
        return {
            id: '',
            macro_id: macroId || '',
            name: '',
            enabled: true,
            schedule_type: 'weekly',
            schedule_weekday: 0,
            schedule_weekdays: [0],
            schedule_month_day: 1,
            schedule_time: '02:00',
            target_type: 'server',
            target_ids: [],
            targets: [],
            args: '',
            cron_file: '',
            history: [],
        };
    }

    public existingMacroFiles() {
        return this.macroForm?.existing_files || [];
    }

    public pendingMacroFiles() {
        return this.macroForm?.files || [];
    }

    public macroFilesFor(macro: any) {
        return macro?.files || [];
    }

    public macroFileCount(macro: any) {
        const files = this.macroFilesFor(macro);
        return Number(macro?.file_count ?? files.length ?? 0);
    }

    public formatFileSize(value: any) {
        const size = Number(value || 0);
        if (size < 1024) return `${size} B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
        return `${(size / 1024 / 1024).toFixed(1)} MB`;
    }

    public async selectMacroFiles(event: Event) {
        const input = event.target as HTMLInputElement;
        const files = Array.from(input.files || []);
        if (!files.length) return;
        this.macroForm.files = [...this.pendingMacroFiles(), ...files];
        input.value = '';
        await this.service.render();
    }

    public async removeExistingMacroFile(fileId: string) {
        this.macroForm.existing_files = this.existingMacroFiles().filter((item: any) => item.id !== fileId);
        await this.service.render();
    }

    public async removePendingMacroFile(index: number) {
        this.macroForm.files = this.pendingMacroFiles().filter((_: any, itemIndex: number) => itemIndex !== index);
        await this.service.render();
    }

    private keepMacroFileIds() {
        return this.existingMacroFiles().map((item: any) => item.id).filter((id: string) => !!id);
    }

    private async saveMacroRequest(payload: any) {
        const formData = new FormData();
        Object.entries(payload || {}).forEach(([key, value]) => {
            if (value === undefined || value === null) return;
            formData.append(key, String(value));
        });
        formData.append('keep_file_ids', JSON.stringify(this.keepMacroFileIds()));
        for (const file of this.pendingMacroFiles()) {
            formData.append('files', file, file.name);
        }
        const response = await fetch('/wiz/api/page.macros/save_macro', { method: 'POST', body: formData });
        const json = await response.json();
        return { code: json?.code || response.status, data: json?.data || json };
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
        this.themeObserver = new MutationObserver(() => this.syncMacroEditorTheme());
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
        if (!['macro.create_global', 'macro.run'].includes(detail.target)) return;
        const requestId = String(detail.request_id || '');
        try {
            await this.waitForMacroLoad();
            if (detail.target === 'macro.run') {
                const result = await this.runMacroFromAgent(detail.payload || {});
                this.publishAgentCommandResult(requestId, 'macro.run', { ok: true, ...result });
                return;
            }
            const macro = await this.createGlobalMacroFromAgent(detail.payload || {});
            this.publishAgentCommandResult(requestId, 'macro.create_global', { ok: true, macro });
        } catch (error: any) {
            this.publishAgentCommandResult(requestId, detail.target, {
                ok: false,
                message: error?.message || (detail.target === 'macro.run' ? '매크로를 실행하지 못했습니다.' : '매크로를 생성하지 못했습니다.'),
            });
        }
    }

    private async createGlobalMacroFromAgent(payload: any) {
        const name = String(payload?.name || '').trim();
        const script = String(payload?.script || '').trim();
        if (!name) throw new Error('Agent 매크로 이름이 비어 있습니다.');
        if (!script) throw new Error('Agent 매크로 스크립트가 비어 있습니다.');

        const updateExisting = payload?.update_existing !== false;
        const existing = updateExisting
            ? this.macros().find((item: any) => String(item?.name || '').trim().toLowerCase() === name.toLowerCase())
            : null;
        this.macroForm = {
            id: existing?.id || '',
            name,
            description: String(payload?.description || existing?.description || '').trim(),
            script,
            existing_files: [...(existing?.files || [])],
            files: [],
        };
        this.busy.set(true);
        let result: any = null;
        try {
            result = await this.saveMacroRequest({
                id: this.macroForm?.id || undefined,
                name,
                description: this.macroForm?.description || '',
                script: this.macroForm?.script || '',
                enabled: true,
            });
        } finally {
            this.busy.set(false);
        }
        const { code, data } = result || {};
        if (code !== 200) {
            throw new Error(data?.message || '매크로를 저장할 수 없습니다.');
        }
        this.selectedMacroId.set(data?.macro?.id || '');
        this.editorMode.set('view');
        this.resetMacroForm();
        await this.load();
        await this.service.render();
        return data?.macro || null;
    }

    private async waitForMacroLoad() {
        for (let index = 0; index < 40; index++) {
            if (!this.loading()) return;
            await this.sleep(100);
        }
    }

    private async runMacroFromAgent(payload: any) {
        const node = this.agentTargetNode(payload);
        if (!node?.id) throw new Error('실행할 서버를 찾을 수 없습니다.');
        const macro = await this.ensureAgentMacro(payload || {});
        this.editorMode.set('view');
        this.selectedMacroId.set(macro.id);
        this.runTargetType.set('server');
        this.selectedNodeId.set(node.id);
        this.macroRunResult.set(null);
        const args = String(payload?.args || '');
        this.macroArgsInput.set(args);
        this.macroArgsEnabled.set(Boolean(args));
        await this.syncMacroRoute(macro.id);
        await this.service.render();
        await this.runSelectedMacro(args);
        const operation = this.macroRunResult()?.operation || null;
        if (!operation) throw new Error('매크로 실행 작업을 시작하지 못했습니다.');
        return { node, macro, operation };
    }

    private agentTargetNode(payload: any) {
        const nodes = this.nodes();
        const nodeId = String(payload?.node_id || payload?.nodeId || '').trim();
        if (nodeId) return nodes.find((node: any) => node.id === nodeId) || null;
        const selector = String(payload?.node_selector || payload?.nodeSelector || '').trim().toLowerCase();
        if (['local_master', 'master', '마스터', '중심'].includes(selector)) {
            return nodes.find((node: any) => node.is_local_master) || nodes[0] || null;
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
        const selected = this.nodes().find((node: any) => node.id === this.selectedNodeId());
        return selected || nodes.find((node: any) => node.is_local_master) || nodes[0] || null;
    }

    private async ensureAgentMacro(payload: any) {
        const macroPayload = payload?.macro && typeof payload.macro === 'object' ? payload.macro : {};
        const macroName = String(payload?.macro_name || payload?.macroName || macroPayload?.name || '').trim();
        if (!macroName) throw new Error('실행할 매크로 이름이 비어 있습니다.');

        let macro = this.findAgentMacroByName(macroName);
        if (macroPayload?.script && (!macro || macroPayload.update_existing !== false)) {
            macro = await this.createGlobalMacroFromAgent({ ...macroPayload, name: macroPayload?.name || macroName });
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

    private publishAgentCommandResult(requestId: string, target: string, detail: any) {
        if (!requestId || typeof window === 'undefined') return;
        window.dispatchEvent(new CustomEvent('docker-infra-agent-action-result', {
            detail: {
                request_id: requestId,
                target,
                ...detail,
            },
        }));
    }

    private sleep(ms: number) {
        return new Promise((resolve) => window.setTimeout(resolve, Math.max(0, ms || 0)));
    }

    public async alert(message: string, status: string = 'error') {
        return await this.service.modal.show({
            title: '',
            message,
            cancel: false,
            actionBtn: status,
            action: '확인',
            status,
        });
    }

    private routeMacroId() {
        return this.service.routeSegment('macro_id') || this.service.queryParam('macro_id') || this.service.queryParam('selected_macro_id');
    }

    private macroDetailRoute(macroId: string = this.selectedMacroId()) {
        const encodedId = this.service.encodeRouteSegment(macroId);
        return encodedId ? `/macros/${encodedId}` : '/macros';
    }

    private async syncMacroRoute(macroId: string = this.selectedMacroId(), replace: boolean = false) {
        const target = this.macroDetailRoute(macroId);
        if (this.service.currentPath() !== target) await this.service.routeTo(target, replace);
    }

    private defaultNodeId(nodes: any[] = this.nodes()) {
        return (nodes.find((node: any) => node?.is_local_master) || nodes[0] || {})?.id || '';
    }

    private syncRunTargets(nodes: any[], serviceTargets: any[]) {
        const currentNodeId = this.selectedNodeId();
        if (!currentNodeId || !nodes.some((node: any) => node.id === currentNodeId)) {
            this.selectedNodeId.set(this.defaultNodeId(nodes));
        }
        const services = this.serviceTargetServicesFrom(serviceTargets);
        const currentServiceId = this.selectedServiceId();
        const nextServiceId = services.some((item: any) => item.value === currentServiceId) ? currentServiceId : (services[0]?.value || '');
        if (nextServiceId !== currentServiceId) this.selectedServiceId.set(nextServiceId);

        const selectedServiceTargets = this.serviceContainerTargets(nextServiceId, serviceTargets);
        const currentServiceTargetId = this.selectedServiceTargetId();
        if (!currentServiceTargetId || !selectedServiceTargets.some((item: any) => item.id === currentServiceTargetId)) {
            this.selectedServiceTargetId.set(selectedServiceTargets[0]?.id || '');
        }
    }

    public async load(replaceRoute: boolean = false) {
        this.loading.set(true);
        this.error.set('');
        await this.service.render();
        const { code, data } = await wiz.call('load', {});
        if (code === 200) {
            const macros = data.macros || [];
            const nodes = data.nodes || [];
            const serviceTargets = data.service_targets || [];
            this.macros.set(macros);
            this.nodes.set(nodes);
            this.serviceTargets.set(serviceTargets);
            this.syncRunTargets(nodes, serviceTargets);
            const selectedId = this.selectedMacroId();
            const next = selectedId ? (macros.find((item: any) => item.id === selectedId) || null) : null;
            if (this.editorMode() === 'view') {
                this.selectedMacroId.set(next?.id || '');
                await this.syncMacroRoute(next?.id || '', replaceRoute);
            }
            this.macroPagination.set(this.paginationFor(this.filteredMacros().length, this.macroPagination().current));
        } else {
            this.error.set(data?.message || '매크로를 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
    }

    public filteredMacros() {
        const query = String(this.search() || '').trim().toLowerCase();
        if (!query) return this.macros();
        return this.macros().filter((macro: any) => {
            const target = `${macro?.name || ''} ${macro?.description || ''}`.toLowerCase();
            return target.includes(query);
        });
    }

    private paginationStart(page: number) {
        return Math.floor((Math.max(1, Number(page || 1)) - 1) / 10) * 10 + 1;
    }

    private paginationFor(total: number, page: number = 1, limit: number = this.pageSize) {
        const pageLimit = Math.max(1, Number(limit || this.pageSize));
        const end = Math.max(1, Math.ceil(Number(total || 0) / pageLimit));
        const current = Math.min(Math.max(1, Number(page || 1)), end);
        return {
            current,
            start: this.paginationStart(current),
            end,
            total: Number(total || 0),
            limit: pageLimit,
        };
    }

    public pagedMacros() {
        const rows = this.filteredMacros();
        const pagination = this.macroPagination();
        const limit = Number(pagination?.limit || this.pageSize);
        const start = (Number(pagination?.current || 1) - 1) * limit;
        return rows.slice(start, start + limit);
    }

    public macroBoardSummary() {
        const pagination = this.macroPagination();
        const total = Number(pagination?.total || 0);
        if (!total) return '총 0개';
        const current = Number(pagination?.current || 1);
        const limit = Number(pagination?.limit || this.pageSize);
        const start = (current - 1) * limit + 1;
        const end = Math.min(total, current * limit);
        return `총 ${total}개 · ${start}-${end}`;
    }

    public async moveMacroPage(page: number) {
        this.macroPagination.set(this.paginationFor(this.filteredMacros().length, page));
        await this.service.render();
    }

    public async setMacroSearch(value: string) {
        this.search.set(value);
        this.macroPagination.set(this.paginationFor(this.filteredMacros().length, 1));
        await this.service.render();
    }

    public selectedMacro() {
        const selectedId = this.selectedMacroId();
        return this.macros().find((item: any) => item.id === selectedId) || null;
    }

    public selectedMacroDescription() {
        return String(this.selectedMacro()?.description || '').trim() || '설명이 등록되지 않았습니다.';
    }

    public macroSchedules(macro: any = this.selectedMacro()) {
        return macro?.schedules || [];
    }

    public macroScheduleCount(macro: any = this.selectedMacro()) {
        return Number(macro?.schedule_count ?? this.macroSchedules(macro).length ?? 0);
    }

    public selectedMacroScheduleCount() {
        return this.macroScheduleCount(this.selectedMacro());
    }

    public macroScheduleTypes() {
        return [
            { key: 'weekly', label: '매주', icon: 'fa-calendar-week' },
            { key: 'monthly', label: '매월', icon: 'fa-calendar-days' },
        ];
    }

    public weekdayOptions() {
        return [
            { value: 0, label: '월' },
            { value: 1, label: '화' },
            { value: 2, label: '수' },
            { value: 3, label: '목' },
            { value: 4, label: '금' },
            { value: 5, label: '토' },
            { value: 6, label: '일' },
        ];
    }

    public scheduleWeekdays(schedule: any = this.scheduleForm) {
        const raw = Array.isArray(schedule?.schedule_weekdays) && schedule.schedule_weekdays.length
            ? schedule.schedule_weekdays
            : [schedule?.schedule_weekday ?? 0];
        const days: number[] = [];
        const seen = new Set<number>();
        for (const item of raw) {
            const day = Math.max(0, Math.min(6, Number(item) || 0));
            if (seen.has(day)) continue;
            seen.add(day);
            days.push(day);
        }
        return days.length ? days.sort((a: number, b: number) => a - b) : [0];
    }

    private scheduleTargetValue(target: any, targetType: string = this.scheduleForm?.target_type) {
        if (targetType === 'service') return String(target?.service_target_id || target?.id || target?.value || '').trim();
        return String(target?.node_id || target?.id || target?.value || '').trim();
    }

    private scheduleTargetIds(schedule: any) {
        const targetType = schedule?.target_type || 'server';
        return (schedule?.targets || []).map((target: any) => this.scheduleTargetValue(target, targetType)).filter((value: string) => !!value);
    }

    private itemMatchesQuery(item: any, query: string) {
        if (!query) return true;
        const haystack = `${item?.label || ''} ${item?.description || ''} ${item?.value || ''}`.toLowerCase();
        return haystack.includes(query);
    }

    public openScheduleModal(macro: any = this.selectedMacro()) {
        if (!macro?.id) return;
        this.selectedMacroId.set(macro.id);
        this.scheduleTargetSearch.set('');
        this.resetScheduleHistoryResult();
        this.scheduleModalOpen.set(true);
        const first = this.macroSchedules(macro)[0];
        if (first) {
            this.selectScheduleForm(first);
        } else {
            this.newScheduleForm();
        }
        void this.service.render();
    }

    public async closeScheduleModal() {
        this.scheduleModalOpen.set(false);
        this.resetScheduleHistoryResult();
        this.scheduleHistoryToken += 1;
        this.scheduleHistoryLoading.set(false);
        this.scheduleHistoryError.set('');
        this.scheduleHistoryPagination.set(this.paginationFor(0, 1, this.scheduleHistoryPageSize));
        this.scheduleTargetSearch.set('');
        this.scheduleForm = this.emptyScheduleForm();
        await this.service.render();
    }

    public newScheduleForm() {
        this.scheduleFormMode.set('create');
        this.resetScheduleHistoryResult();
        this.scheduleHistoryToken += 1;
        this.scheduleHistoryLoading.set(false);
        this.scheduleHistoryError.set('');
        this.scheduleHistoryPagination.set(this.paginationFor(0, 1, this.scheduleHistoryPageSize));
        this.scheduleTargetSearch.set('');
        this.scheduleForm = this.emptyScheduleForm(this.selectedMacroId());
        void this.service.render();
    }

    public selectScheduleForm(schedule: any) {
        this.scheduleFormMode.set('edit');
        this.resetScheduleHistoryResult();
        const scheduleWeekdays = this.scheduleWeekdays(schedule);
        const history = [...(schedule?.history || [])];
        this.scheduleHistoryLoading.set(Boolean(schedule?.id));
        this.scheduleHistoryError.set('');
        this.scheduleHistoryPagination.set(this.paginationFor(history.length, 1, this.scheduleHistoryPageSize));
        this.scheduleForm = {
            id: schedule?.id || '',
            macro_id: schedule?.macro_id || this.selectedMacroId(),
            name: schedule?.name || '',
            enabled: schedule?.enabled !== false,
            schedule_type: schedule?.schedule_type || 'weekly',
            schedule_weekday: scheduleWeekdays[0],
            schedule_weekdays: scheduleWeekdays,
            schedule_month_day: Number(schedule?.schedule_month_day ?? 1),
            schedule_time: schedule?.schedule_time || '02:00',
            target_type: schedule?.target_type || 'server',
            target_ids: this.scheduleTargetIds(schedule),
            targets: [...(schedule?.targets || [])],
            args: schedule?.args || '',
            cron_file: schedule?.cron_file || '',
            history,
        };
        if (this.scheduleForm.id) {
            void this.loadScheduleHistory(this.scheduleForm.id, 1);
        }
        void this.service.render();
    }

    public async setScheduleType(type: string) {
        this.scheduleForm.schedule_type = type === 'monthly' ? 'monthly' : 'weekly';
        await this.service.render();
    }

    public isScheduleWeekdaySelected(day: any) {
        return this.scheduleWeekdays(this.scheduleForm).includes(Number(day));
    }

    public async toggleScheduleWeekday(day: any) {
        const value = Math.max(0, Math.min(6, Number(day) || 0));
        const selected = new Set<number>(this.scheduleWeekdays(this.scheduleForm));
        if (selected.has(value) && selected.size > 1) {
            selected.delete(value);
        } else {
            selected.add(value);
        }
        const weekdays = Array.from(selected).sort((a: number, b: number) => a - b);
        this.scheduleForm.schedule_weekdays = weekdays;
        this.scheduleForm.schedule_weekday = weekdays[0] ?? 0;
        await this.service.render();
    }

    public async setScheduleTargetType(type: string) {
        if (!['server', 'service'].includes(type)) return;
        if (this.scheduleForm.target_type !== type) {
            this.scheduleForm.target_type = type;
            this.scheduleForm.target_ids = [];
            this.scheduleForm.targets = [];
            this.scheduleTargetSearch.set('');
        }
        await this.service.render();
    }

    public scheduleTargetItems() {
        const items = this.scheduleForm?.target_type === 'service' ? this.serviceTargetItems() : this.serverTargetItems();
        const query = String(this.scheduleTargetSearch() || '').trim().toLowerCase();
        return items.filter((item: any) => this.itemMatchesQuery(item, query));
    }

    public isScheduleTargetSelected(value: string) {
        const key = String(value || '').trim();
        return (this.scheduleForm?.target_ids || []).map((item: any) => String(item || '').trim()).includes(key);
    }

    public async toggleScheduleTarget(value: string) {
        const key = String(value || '').trim();
        if (!key) return;
        const selected = new Set((this.scheduleForm?.target_ids || []).map((item: any) => String(item || '').trim()).filter((item: string) => !!item));
        if (selected.has(key)) {
            selected.delete(key);
        } else {
            selected.add(key);
        }
        this.scheduleForm.target_ids = Array.from(selected);
        await this.service.render();
    }

    private existingScheduleTargetByValue(value: string) {
        const targetType = this.scheduleForm?.target_type || 'server';
        return (this.scheduleForm?.targets || []).find((target: any) => this.scheduleTargetValue(target, targetType) === value) || null;
    }

    private buildScheduleTargets() {
        const targetType = this.scheduleForm?.target_type || 'server';
        const ids = this.scheduleForm?.target_ids || [];
        if (targetType === 'service') {
            return ids.map((id: string) => {
                const target = this.serviceTargets().find((item: any) => item.id === id) || this.existingScheduleTargetByValue(id) || {};
                return {
                    target_type: 'service',
                    node_id: target.node_id,
                    service_target_id: target.id || target.service_target_id || id,
                    service_id: target.service_id || '',
                    service_name: target.service_name || '',
                    service_namespace: target.service_namespace || '',
                    container_id: target.container_id || '',
                    container_name: target.container_name || '',
                    container_display_name: target.container_display_name || '',
                    label: target.label || this.serviceTargetLabel(target),
                };
            }).filter((target: any) => target.node_id && target.service_target_id);
        }
        return ids.map((id: string) => {
            const node = this.nodes().find((item: any) => item.id === id) || this.existingScheduleTargetByValue(id) || {};
            return {
                target_type: 'server',
                node_id: node.id || node.node_id || id,
                label: node.label || this.nodeLabel(node),
            };
        }).filter((target: any) => target.node_id);
    }

    public scheduleTargetCount() {
        return (this.scheduleForm?.target_ids || []).length;
    }

    public canSaveSchedule() {
        return Boolean(this.selectedMacro()?.id && this.scheduleForm?.schedule_time && this.scheduleTargetCount() > 0 && !this.busy());
    }

    public async saveSchedule() {
        const macro = this.selectedMacro();
        if (!macro?.id) {
            await this.alert('스케줄을 등록할 매크로를 선택하세요.');
            return;
        }
        if (!this.scheduleTargetCount()) {
            await this.alert('실행 대상을 하나 이상 선택하세요.');
            return;
        }
        this.busy.set(true);
        const scheduleWeekdays = this.scheduleWeekdays(this.scheduleForm);
        const { code, data } = await wiz.call('save_schedule', {
            id: this.scheduleForm?.id || '',
            macro_id: macro.id,
            name: this.scheduleForm?.name || '',
            enabled: this.scheduleForm?.enabled ? 'true' : 'false',
            schedule_type: this.scheduleForm?.schedule_type || 'weekly',
            schedule_weekday: scheduleWeekdays[0],
            schedule_weekdays: JSON.stringify(scheduleWeekdays),
            schedule_month_day: Number(this.scheduleForm?.schedule_month_day ?? 1),
            schedule_time: this.scheduleForm?.schedule_time || '02:00',
            target_type: this.scheduleForm?.target_type || 'server',
            targets: JSON.stringify(this.buildScheduleTargets()),
            args: this.scheduleForm?.args || '',
        });
        this.busy.set(false);
        if (code === 200) {
            const savedId = data?.schedule?.id || '';
            await this.load();
            const saved = this.macroSchedules(this.selectedMacro()).find((item: any) => item.id === savedId);
            if (saved) this.selectScheduleForm(saved);
        } else {
            await this.alert(data?.message || '스케줄을 저장할 수 없습니다.');
        }
        await this.service.render();
    }

    public async deleteSchedule(schedule: any = this.scheduleForm) {
        if (!schedule?.id) return;
        const confirmed = await this.service.modal.show({
            title: '스케줄 삭제',
            message: '선택한 매크로 실행 스케줄을 삭제합니다.',
            cancel: '취소',
            action: '삭제',
            actionBtn: 'warning',
            status: 'warning',
        });
        if (!confirmed) return;

        const macroId = this.selectedMacro()?.id || schedule?.macro_id || '';
        this.busy.set(true);
        const { code, data } = await wiz.call('delete_schedule', { schedule_id: schedule.id, macro_id: macroId });
        this.busy.set(false);
        if (code === 200) {
            await this.load();
            const first = this.macroSchedules(this.selectedMacro())[0];
            if (first) {
                this.selectScheduleForm(first);
            } else {
                this.newScheduleForm();
            }
        } else {
            await this.alert(data?.message || '스케줄을 삭제할 수 없습니다.');
        }
        await this.service.render();
    }

    private scheduleWeekdayLabel(value: any) {
        return this.weekdayOptions().find((item: any) => item.value === Number(value))?.label || '월';
    }

    public scheduleSummary(schedule: any) {
        if (!schedule?.enabled) return '비활성화됨';
        const time = schedule?.schedule_time || '02:00';
        if (schedule?.schedule_type === 'monthly') {
            return `매월 ${Number(schedule?.schedule_month_day || 1)}일 ${time}`;
        }
        const weekdays = this.scheduleWeekdays(schedule).map((day: number) => `${this.scheduleWeekdayLabel(day)}요일`).join(', ');
        return `매주 ${weekdays} ${time}`;
    }

    public scheduleFormSummary() {
        return this.scheduleSummary(this.scheduleForm);
    }

    public scheduleTargetSummary(schedule: any) {
        const count = Number(schedule?.target_count ?? (schedule?.targets || []).length ?? 0);
        const typeLabel = schedule?.target_type === 'service' ? '서비스' : '서버';
        return `${typeLabel} ${count}개`;
    }

    public scheduleLastRunLabel(schedule: any) {
        if (!schedule?.last_run_at) return '실행 이력 없음';
        return `마지막 실행 ${this.formatDate(schedule.last_run_at)}`;
    }

    public scheduleHistory() {
        return this.scheduleForm?.history || [];
    }

    public scheduleHistorySummary() {
        if (this.scheduleHistoryLoading()) return '불러오는 중';
        const total = Number(this.scheduleHistoryPagination()?.total ?? this.scheduleHistory().length ?? 0);
        return total ? `총 ${total}건` : '이력 없음';
    }

    public scheduleHistoryPageSummary() {
        const pagination = this.scheduleHistoryPagination();
        const total = Number(pagination?.total || 0);
        if (!total) return '';
        const current = Number(pagination?.current || 1);
        const limit = Number(pagination?.limit || this.scheduleHistoryPageSize);
        const start = (current - 1) * limit + 1;
        const end = Math.min(total, current * limit);
        return `${start}-${end} / ${total}`;
    }

    private async loadScheduleHistory(scheduleId: string, page: number = 1) {
        const targetScheduleId = String(scheduleId || '').trim();
        if (!targetScheduleId) return;
        const token = ++this.scheduleHistoryToken;
        this.scheduleHistoryLoading.set(true);
        this.scheduleHistoryError.set('');
        await this.service.render();
        try {
            const { code, data } = await wiz.call('schedule_history', {
                schedule_id: targetScheduleId,
                macro_id: this.selectedMacro()?.id || this.scheduleForm?.macro_id || '',
                page,
                limit: this.scheduleHistoryPageSize,
            });
            if (token !== this.scheduleHistoryToken || this.scheduleForm?.id !== targetScheduleId) return;
            if (code === 200) {
                const history = Array.isArray(data?.history) ? data.history : [];
                this.scheduleForm.history = history;
                this.scheduleHistoryPagination.set(data?.pagination || this.paginationFor(history.length, page, this.scheduleHistoryPageSize));
            } else {
                this.scheduleForm.history = [];
                this.scheduleHistoryPagination.set(this.paginationFor(0, 1, this.scheduleHistoryPageSize));
                this.scheduleHistoryError.set(data?.message || '실행 이력을 불러올 수 없습니다.');
            }
        } catch (error: any) {
            if (token !== this.scheduleHistoryToken || this.scheduleForm?.id !== targetScheduleId) return;
            this.scheduleForm.history = [];
            this.scheduleHistoryPagination.set(this.paginationFor(0, 1, this.scheduleHistoryPageSize));
            this.scheduleHistoryError.set(error?.message || '실행 이력을 불러올 수 없습니다.');
        } finally {
            if (token === this.scheduleHistoryToken && this.scheduleForm?.id === targetScheduleId) {
                this.scheduleHistoryLoading.set(false);
                await this.service.render();
            }
        }
    }

    public async moveScheduleHistoryPage(page: number) {
        if (!this.scheduleForm?.id) return;
        await this.loadScheduleHistory(this.scheduleForm.id, page);
    }

    public scheduleHistoryDate(history: any) {
        if (history?.run_at) return history.run_at;
        if (history?.date) return history.date;
        return history?.finished_at || history?.started_at || history?.created_at || history?.updated_at;
    }

    public scheduleHistoryDayLabel(history: any) {
        const value = history?.date || this.scheduleHistoryDate(history);
        if (!value) return '-';
        const text = String(value);
        const date = new Date(text.length === 10 ? `${text}T00:00:00` : text);
        if (Number.isNaN(date.getTime())) return text;
        return date.toLocaleDateString();
    }

    public scheduleHistoryDateTimeLabel(history: any) {
        const value = this.scheduleHistoryDate(history);
        if (!value) return '-';
        const text = String(value);
        if (text.length === 10) return this.scheduleHistoryDayLabel(history);
        return this.formatDate(value);
    }

    private scheduleHistoryOperationRows(history: any) {
        if (Array.isArray(history?.operations)) {
            return history.operations.filter((item: any) => item?.id);
        }
        return history?.id ? [history] : [];
    }

    public scheduleHistoryResultOperations(history: any = this.scheduleHistoryResultItem()) {
        return this.scheduleHistoryOperationRows(history);
    }

    private scheduleHistoryOperationTargetLabel(operation: any) {
        const metadata = operation?.metadata || {};
        const context = operation?.requested_payload?.target_context || {};
        const targetType = metadata?.target_type || context?.target_type || '';
        if (targetType === 'service') {
            const service = metadata?.service_name || context?.service_name || metadata?.service_namespace || context?.service_namespace || '서비스';
            const container = metadata?.container_display_name || context?.container_display_name || metadata?.container_name || context?.container_name || '';
            return [service, container].filter((item: string) => !!item).join(' - ') || operation?.target_id || '-';
        }
        return metadata?.node_name || operation?.target_id || '-';
    }

    public scheduleHistoryTargetLabel(history: any) {
        const operations = this.scheduleHistoryOperationRows(history);
        if (operations.length > 1) {
            const labels = Array.from(new Set(operations.map((item: any) => this.scheduleHistoryOperationTargetLabel(item)).filter((item: string) => !!item && item !== '-')));
            const preview = labels.slice(0, 2).join(', ');
            const suffix = labels.length > 2 ? ` 외 ${labels.length - 2}개` : '';
            const count = Math.max(Number(history?.operation_count || 0), operations.length);
            return preview ? `${count}개 대상 · ${preview}${suffix}` : `${count}개 대상`;
        }
        if (operations.length === 1 && Array.isArray(history?.operations)) {
            return this.scheduleHistoryOperationTargetLabel(operations[0]);
        }
        return this.scheduleHistoryOperationTargetLabel(history);
    }

    public scheduleHistoryOperationTabLabel(operation: any, index: number) {
        return this.scheduleHistoryOperationTargetLabel(operation) || `대상 ${index + 1}`;
    }

    public scheduleHistoryActiveOperation() {
        const operations = this.scheduleHistoryResultOperations();
        const selectedId = String(this.scheduleHistoryResultOperationId() || '');
        return operations.find((item: any) => String(item?.id || '') === selectedId) || operations[0] || null;
    }

    public async selectScheduleHistoryResultOperation(operation: any) {
        this.scheduleHistoryResultOperationId.set(String(operation?.id || ''));
        await this.service.render();
    }

    private resetScheduleHistoryResult() {
        this.scheduleHistoryResultOpen.set(false);
        this.scheduleHistoryResultItem.set(null);
        this.scheduleHistoryResultOperationId.set('');
    }

    public async openScheduleHistoryResult(history: any) {
        const operations = this.scheduleHistoryOperationRows(history);
        this.scheduleHistoryResultItem.set(history || null);
        this.scheduleHistoryResultOperationId.set(String(operations[0]?.id || ''));
        this.scheduleHistoryResultOpen.set(Boolean(history));
        await this.service.render();
    }

    public async closeScheduleHistoryResult() {
        this.resetScheduleHistoryResult();
        await this.service.render();
    }

    private scheduleHistoryStreamText(history: any, streamName: string) {
        const output = Array.isArray(history?.output) ? history.output : [];
        if (!output.length) return '';
        const streamKey = String(streamName || '').toLowerCase();
        return output
            .filter((entry: any) => String(entry?.stream || '').toLowerCase() === streamKey)
            .map((entry: any) => entry?.message)
            .filter((message: any) => message !== undefined && message !== null && String(message).length > 0)
            .map((message: any) => String(message))
            .join('\n');
    }

    public scheduleHistoryStdoutText(history: any = this.scheduleHistoryActiveOperation()) {
        return this.scheduleHistoryStreamText(history, 'stdout');
    }

    public scheduleHistoryStderrText(history: any = this.scheduleHistoryActiveOperation()) {
        return this.scheduleHistoryStreamText(history, 'stderr');
    }

    public scheduleStatusClass(schedule: any) {
        if (schedule?.enabled) return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        return 'border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400';
    }

    public isEditingMacro() {
        return this.editorMode() !== 'view';
    }

    public async closeMacroDetail() {
        this.selectedMacroId.set('');
        this.editorMode.set('view');
        this.stopMacroRunPolling();
        this.macroRunResult.set(null);
        await this.syncMacroRoute('');
        await this.service.render();
    }

    public async selectMacro(macroId: string) {
        this.selectedMacroId.set(macroId);
        this.editorMode.set('view');
        this.resetMacroForm();
        this.stopMacroRunPolling();
        this.macroRunResult.set(null);
        await this.syncMacroRoute(macroId);
        await this.service.render();
    }

    public async openAddMacro() {
        this.selectedMacroId.set('');
        this.editorMode.set('create');
        this.stopMacroRunPolling();
        this.macroRunResult.set(null);
        this.resetMacroForm();
        this.syncMacroEditorTheme();
        await this.syncMacroRoute('');
        await this.service.render();
    }

    public openEditMacro(macro: any) {
        this.macroForm = {
            id: macro?.id || '',
            name: macro?.name || '',
            description: macro?.description || '',
            script: macro?.script || '#!/usr/bin/env bash\n',
            existing_files: [...(macro?.files || [])],
            files: [],
        };
        this.editorMode.set('edit');
        this.syncMacroEditorTheme();
    }

    public async cancelEditMacro() {
        this.editorMode.set('view');
        this.resetMacroForm();
        await this.service.render();
    }

    public formTitle() {
        return this.editorMode() === 'create' ? '매크로 추가' : '매크로 수정';
    }

    public formSubmitLabel() {
        if (this.busy()) return this.editorMode() === 'create' ? '등록 중' : '저장 중';
        return this.editorMode() === 'create' ? '등록' : '저장';
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
        const { code, data } = await this.saveMacroRequest({
            id: this.macroForm?.id || undefined,
            name,
            description: this.macroForm?.description || '',
            script: this.macroForm?.script || '',
            enabled: true,
        });
        if (code === 200) {
            this.selectedMacroId.set(data?.macro?.id || '');
            this.editorMode.set('view');
            this.resetMacroForm();
            await this.load();
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
        const { code, data } = await wiz.call('delete_macro', { macro_id: macro?.id });
        if (code === 200) {
            if (this.selectedMacroId() === macro?.id) this.selectedMacroId.set('');
            this.macroRunResult.set(null);
            await this.load();
        } else {
            await this.alert(data?.message || '매크로를 삭제할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public nodeLabel(node: any) {
        const name = String(node?.name || '').trim();
        const host = String(node?.host || node?.private_host || '').trim();
        if (name && host && name !== host) return `${name} (${host})`;
        return name || host || String(node?.id || '-');
    }

    public serverTargetItems() {
        return this.nodes().map((node: any) => ({
            value: node.id,
            label: this.nodeLabel(node),
            description: node?.is_local_master ? '현재 서버' : (node?.host || ''),
        }));
    }

    private serviceTargetServiceKey(target: any) {
        return String(target?.service_key || target?.service_id || target?.service_namespace || target?.service_name || '').trim();
    }

    private serviceTargetServiceLabel(target: any) {
        const serviceName = String(target?.service_name || target?.service_namespace || '서비스').trim();
        return serviceName || '서비스';
    }

    private serviceTargetServicesFrom(targets: any[] = this.serviceTargets()) {
        const groups: any[] = [];
        const byKey: any = {};
        for (const target of targets || []) {
            const key = this.serviceTargetServiceKey(target);
            if (!key) continue;
            if (!byKey[key]) {
                byKey[key] = {
                    value: key,
                    label: this.serviceTargetServiceLabel(target),
                    containerCount: 0,
                    nodes: [],
                };
                groups.push(byKey[key]);
            }
            byKey[key].containerCount += 1;
            const nodeName = String(target?.node_name || target?.node_host || '').trim();
            if (nodeName && !byKey[key].nodes.includes(nodeName)) byKey[key].nodes.push(nodeName);
        }
        return groups.map((group: any) => {
            const nodeText = group.nodes.length ? ` · ${group.nodes.slice(0, 2).join(', ')}${group.nodes.length > 2 ? ` 외 ${group.nodes.length - 2}` : ''}` : '';
            return {
                value: group.value,
                label: group.label,
                description: `${group.containerCount}개 컨테이너${nodeText}`,
            };
        });
    }

    public serviceTargetServiceItems() {
        return this.serviceTargetServicesFrom();
    }

    private serviceContainerTargets(serviceId: string = this.selectedServiceId(), targets: any[] = this.serviceTargets()) {
        const selectedServiceId = String(serviceId || '').trim();
        if (!selectedServiceId) return [];
        return (targets || []).filter((target: any) => this.serviceTargetServiceKey(target) === selectedServiceId);
    }

    public serviceTargetContainerLabel(target: any) {
        return String(target?.container_display_name || target?.container_name || target?.container_id || '컨테이너').trim();
    }

    public serviceTargetContainerDescription(target: any) {
        const rawName = String(target?.container_raw_name || target?.container_name || '').trim();
        const displayName = this.serviceTargetContainerLabel(target);
        return [
            target?.node_name || target?.node_host || '-',
            target?.container_status || target?.container_state || '-',
            rawName && rawName !== displayName ? rawName : '',
        ].filter((item: any) => Boolean(item)).join(' · ');
    }

    public serviceTargetLabel(target: any) {
        const serviceName = this.serviceTargetServiceLabel(target);
        const containerName = this.serviceTargetContainerLabel(target);
        return `${serviceName} - ${containerName}`;
    }

    public serviceTargetItems() {
        return this.serviceTargets().map((target: any) => ({
            value: target.id,
            label: this.serviceTargetLabel(target),
            description: `${target.node_name || target.node_host || '-'} · ${target.container_status || target.container_state || '-'}`,
        }));
    }

    public serviceContainerTargetItems() {
        return this.serviceContainerTargets().map((target: any) => ({
            value: target.id,
            label: this.serviceTargetContainerLabel(target),
            description: this.serviceTargetContainerDescription(target),
        }));
    }

    public setRunTargetType(type: string) {
        if (!['server', 'service'].includes(type)) return;
        this.runTargetType.set(type);
        if (type === 'service') this.syncRunTargets(this.nodes(), this.serviceTargets());
    }

    public async selectServiceTargetService(serviceId: string) {
        this.selectedServiceId.set(serviceId);
        const targets = this.serviceContainerTargets(serviceId);
        this.selectedServiceTargetId.set(targets[0]?.id || '');
        await this.service.render();
    }

    public async selectServiceContainerTarget(targetId: string) {
        this.selectedServiceTargetId.set(targetId);
        await this.service.render();
    }

    private selectedServiceTarget() {
        const id = this.selectedServiceTargetId();
        const serviceId = this.selectedServiceId();
        return this.serviceTargets().find((item: any) => item.id === id && (!serviceId || this.serviceTargetServiceKey(item) === serviceId)) || null;
    }

    private selectedRunTarget() {
        if (this.runTargetType() === 'service') {
            const target = this.selectedServiceTarget();
            if (!target?.node_id) return null;
            return {
                node_id: target.node_id,
                target_type: 'service',
                service_target_id: target.id,
                service_id: target.service_id,
                service_name: target.service_name,
                service_namespace: target.service_namespace,
                container_id: target.container_id,
                container_name: target.container_name,
                container_display_name: target.container_display_name,
                label: this.serviceTargetLabel(target),
            };
        }
        const node = this.nodes().find((item: any) => item.id === this.selectedNodeId()) || null;
        if (!node?.id) return null;
        return {
            node_id: node.id,
            target_type: 'server',
            label: this.nodeLabel(node),
        };
    }

    public runTargetError() {
        if (this.runTargetType() === 'server' && !this.selectedNodeId()) return '실행할 서버를 선택하세요.';
        if (this.runTargetType() === 'service' && !this.selectedServiceId()) return '실행할 서비스를 선택하세요.';
        if (this.runTargetType() === 'service' && !this.selectedServiceTargetId()) return '실행할 서비스 컨테이너를 선택하세요.';
        if (this.runTargetType() === 'service' && !this.selectedServiceTarget()) return '선택한 서비스의 컨테이너를 다시 선택하세요.';
        return '';
    }

    public canRunSelectedMacro() {
        return Boolean(this.selectedMacro()?.id && this.selectedRunTarget()?.node_id && !this.busy());
    }

    private stopMacroRunPolling() {
        if (!this.macroRunTimer) return;
        clearTimeout(this.macroRunTimer);
        this.macroRunTimer = null;
    }

    private scrollMacroRunOutputToBottom() {
        setTimeout(() => {
            const output = document.querySelector('[data-macro-run-output="true"]') as HTMLElement | null;
            if (!output) return;
            output.scrollTop = output.scrollHeight;
        }, 0);
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
            const { code, data } = await wiz.call('operation_status', { operation_id: operationId });
            if (token !== this.macroRunToken) return;
            const operation = data?.operation || null;
            if (code === 200 && operation) {
                const current = this.macroRunResult() || {};
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
        this.scrollMacroRunOutputToBottom();
    }

    public async runSelectedMacro(explicitArgs?: string) {
        const macro = this.selectedMacro();
        const target = this.selectedRunTarget();
        if (!macro?.id) {
            await this.alert('실행할 매크로를 선택하세요.');
            return;
        }
        if (!target?.node_id) {
            await this.alert(this.runTargetError() || '실행 대상을 선택하세요.');
            return;
        }

        const args = explicitArgs === undefined ? (this.macroArgsEnabled() ? this.macroArgsInput() : '') : String(explicitArgs || '');
        const token = ++this.macroRunToken;
        this.stopMacroRunPolling();
        this.busy.set(true);
        const { code, data } = await wiz.call('run_macro', {
            macro_id: macro.id,
            node_id: target.node_id,
            args,
            target_type: target.target_type,
            service_target_id: target.service_target_id,
            service_id: target.service_id,
            service_name: target.service_name,
            service_namespace: target.service_namespace,
            container_id: target.container_id,
            container_name: target.container_name,
            container_display_name: target.container_display_name,
        });
        if (code === 200) {
            const operation = data.operation || null;
            this.macroRunResult.set({
                operation,
                macro,
                target,
                args,
                targetLabel: target.label,
            });
            if (operation?.id && !this.isTerminalOperationStatus(operation.status) && token === this.macroRunToken) {
                this.scheduleMacroRunPoll(operation.id, token, 250);
            }
        } else {
            await this.alert(data?.message || '매크로를 실행할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
        this.scrollMacroRunOutputToBottom();
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

    public macroRunTargetLabel() {
        return this.macroRunResult()?.targetLabel || this.selectedRunTarget()?.label || '-';
    }

    public operationStatusLabel(status: any) {
        const labels: any = {
            pending: '대기',
            running: '실행 중',
            succeeded: '완료',
            failed: '실패',
            canceled: '취소',
        };
        return labels[String(status || '').toLowerCase()] || '확인 중';
    }

    public operationStatusClass(status: any) {
        const key = String(status || '').toLowerCase();
        if (key === 'succeeded') return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        if (key === 'failed' || key === 'canceled') return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        if (key === 'running' || key === 'pending') return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300';
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }

    public async downloadMacroFile(file: any, event?: Event) {
        event?.preventDefault();
        event?.stopPropagation();
        if (!file?.id) return;
        const { code, data } = await wiz.call('download_macro_file', {
            macro_id: this.selectedMacro()?.id || '',
            file_id: file.id,
        });
        if (code !== 200) {
            await this.alert(data?.message || '첨부 파일을 다운로드할 수 없습니다.');
            return;
        }
        const blob = this.blobFromBase64(data.content_base64 || '', data.content_type || 'application/octet-stream');
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = data.filename || file.filename || 'macro-attachment';
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    }

    private removeMacroFileFromState(fileId: string, macroId: string = this.selectedMacro()?.id || '') {
        const targetFileId = String(fileId || '').trim();
        const targetMacroId = String(macroId || '').trim();
        if (!targetFileId) return;
        this.macros.set(this.macros().map((macro: any) => {
            if (targetMacroId && macro?.id !== targetMacroId) return macro;
            if (!this.macroFilesFor(macro).some((item: any) => item.id === targetFileId)) return macro;
            const files = this.macroFilesFor(macro).filter((item: any) => item.id !== targetFileId);
            return { ...macro, files, file_count: files.length };
        }));
        if (!targetMacroId || this.macroForm?.id === targetMacroId) {
            this.macroForm.existing_files = this.existingMacroFiles().filter((item: any) => item.id !== targetFileId);
        }
    }

    public async deleteMacroFile(file: any, event?: Event) {
        event?.preventDefault();
        event?.stopPropagation();
        if (!file?.id) return;
        const confirmed = await this.service.modal.show({
            title: '첨부 파일 삭제',
            message: `${file?.filename || '첨부 파일'}을 삭제합니다.`,
            cancel: '취소',
            action: '삭제',
            actionBtn: 'warning',
            status: 'warning',
        });
        if (!confirmed) return;

        this.busy.set(true);
        const { code, data } = await wiz.call('delete_macro_file', {
            macro_id: this.selectedMacro()?.id || '',
            file_id: file.id,
        });
        this.busy.set(false);
        if (code === 200) {
            this.removeMacroFileFromState(file.id, data?.macro_id || this.selectedMacro()?.id || '');
        } else {
            await this.alert(data?.message || '첨부 파일을 삭제할 수 없습니다.');
        }
        await this.service.render();
    }

    private blobFromBase64(value: string, contentType: string) {
        const binary = atob(value || '');
        const chunks: Uint8Array[] = [];
        for (let index = 0; index < binary.length; index += 8192) {
            const slice = binary.slice(index, index + 8192);
            const bytes = new Uint8Array(slice.length);
            for (let offset = 0; offset < slice.length; offset += 1) {
                bytes[offset] = slice.charCodeAt(offset);
            }
            chunks.push(bytes);
        }
        return new Blob(chunks, { type: contentType || 'application/octet-stream' });
    }

    private normalizeDateInput(value: any) {
        if (typeof value !== 'string') return value;
        const text = value.trim();
        const hasTime = /^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}/.test(text);
        const hasTimezone = /(Z|[+-]\d{2}:?\d{2})$/.test(text);
        if (!hasTime) return text;
        const normalized = text.replace(' ', 'T');
        return hasTimezone ? normalized : `${normalized}Z`;
    }

    public formatDate(value: any) {
        if (!value) return '-';
        const date = new Date(this.normalizeDateInput(value));
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString();
    }
}
