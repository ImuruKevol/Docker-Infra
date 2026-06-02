import { HostListener, OnDestroy, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit, OnDestroy {
    public loading = signal<boolean>(true);
    public busy = signal<boolean>(false);
    public error = signal<string>('');
    public search = signal<string>('');
    public selectedMacroId = signal<string>('');
    public modalOpen = signal<boolean>(false);
    public macros = signal<any[]>([]);
    public summary = signal<any>({ total: 0, enabled: 0, disabled: 0 });
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
    private themeObserver: MutationObserver | null = null;
    private agentCommandHandler: ((event: Event) => void) | null = null;

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
    }

    @HostListener('document:keydown', ['$event'])
    public handleDocumentKeydown(event: KeyboardEvent) {
        if (!this.modalOpen()) return;
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
            enabled: true,
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
        if (detail.target !== 'macro.create_global') return;
        const requestId = String(detail.request_id || '');
        try {
            await this.waitForMacroLoad();
            const macro = await this.createGlobalMacroFromAgent(detail.payload || {});
            this.publishAgentCommandResult(requestId, { ok: true, macro });
        } catch (error: any) {
            this.publishAgentCommandResult(requestId, {
                ok: false,
                message: error?.message || '매크로를 생성하지 못했습니다.',
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
            enabled: payload?.enabled !== false,
            existing_files: [...(existing?.files || [])],
            files: [],
        };
        this.syncMacroEditorTheme();
        this.modalOpen.set(true);
        await this.service.render();
        await this.sleep(120);

        this.busy.set(true);
        let result: any = null;
        try {
            result = await this.saveMacroRequest({
                id: this.macroForm?.id || undefined,
                name,
                description: this.macroForm?.description || '',
                script: this.macroForm?.script || '',
                enabled: this.macroForm?.enabled !== false,
            });
        } finally {
            this.busy.set(false);
        }
        const { code, data } = result || {};
        if (code !== 200) {
            throw new Error(data?.message || '매크로를 저장할 수 없습니다.');
        }
        this.modalOpen.set(false);
        this.selectedMacroId.set(data?.macro?.id || '');
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

    private publishAgentCommandResult(requestId: string, detail: any) {
        if (!requestId || typeof window === 'undefined') return;
        window.dispatchEvent(new CustomEvent('docker-infra-agent-action-result', {
            detail: {
                request_id: requestId,
                target: 'macro.create_global',
                ...detail,
            },
        }));
    }

    private sleep(ms: number) {
        return new Promise((resolve) => window.setTimeout(resolve, Math.max(0, ms || 0)));
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

    public async load(replaceRoute: boolean = false) {
        this.loading.set(true);
        this.error.set('');
        await this.service.render();
        const { code, data } = await wiz.call("load", {});
        if (code === 200) {
            const macros = data.macros || [];
            this.macros.set(macros);
            this.summary.set(data.summary || { total: macros.length, enabled: 0, disabled: 0 });
            const selectedId = this.selectedMacroId();
            const next = macros.find((item: any) => item.id === selectedId) || macros[0] || null;
            this.selectedMacroId.set(next?.id || '');
            await this.syncMacroRoute(next?.id || '', replaceRoute);
        } else {
            this.error.set(data?.message || '전역 매크로를 불러올 수 없습니다.');
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

    public selectedMacro() {
        const selectedId = this.selectedMacroId();
        return this.macros().find((item: any) => item.id === selectedId) || null;
    }

    public async selectMacro(macroId: string) {
        this.selectedMacroId.set(macroId);
        await this.syncMacroRoute(macroId);
    }

    public openAddMacro() {
        this.resetMacroForm();
        this.syncMacroEditorTheme();
        this.modalOpen.set(true);
    }

    public openEditMacro(macro: any) {
        this.macroForm = {
            id: macro?.id || '',
            name: macro?.name || '',
            description: macro?.description || '',
            script: macro?.script || '#!/usr/bin/env bash\n',
            enabled: macro?.enabled !== false,
            existing_files: [...(macro?.files || [])],
            files: [],
        };
        this.syncMacroEditorTheme();
        this.modalOpen.set(true);
    }

    public closeModal() {
        if (this.busy()) return;
        this.modalOpen.set(false);
        this.resetMacroForm();
    }

    public modalTitle() {
        return this.macroForm?.id ? '전역 매크로 수정' : '전역 매크로 추가';
    }

    public modalSubmitLabel() {
        if (this.busy()) return this.macroForm?.id ? '저장 중' : '등록 중';
        return this.macroForm?.id ? '저장' : '등록';
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
            enabled: this.macroForm?.enabled !== false,
        });
        if (code === 200) {
            this.modalOpen.set(false);
            this.selectedMacroId.set(data?.macro?.id || '');
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
            title: '전역 매크로 삭제',
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
            }
            await this.load();
        } else {
            await this.alert(data?.message || '매크로를 삭제할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public statusClass(enabled: any) {
        if (enabled === true || enabled === 'active') {
            return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
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
