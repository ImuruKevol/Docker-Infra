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
    public pageSize = 10;
    private themeObserver: MutationObserver | null = null;
    private agentCommandHandler: ((event: Event) => void) | null = null;
    private macroRunTimer: ReturnType<typeof setTimeout> | null = null;
    private macroRunToken = 0;

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

    public formatDate(value: any) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString();
    }
}
