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

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        this.syncMacroEditorTheme();
        this.startThemeObserver();
        await this.load();
    }

    public ngOnDestroy() {
        this.stopThemeObserver();
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
        this.themeObserver = new MutationObserver(() => this.syncMacroEditorTheme());
        this.themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    }

    private stopThemeObserver() {
        if (!this.themeObserver) return;
        this.themeObserver.disconnect();
        this.themeObserver = null;
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
            const macros = data.macros || [];
            this.macros.set(macros);
            this.summary.set(data.summary || { total: macros.length, enabled: 0, disabled: 0 });
            if (!this.selectedMacroId() && macros.length) {
                this.selectedMacroId.set(macros[0].id);
            }
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

    public selectMacro(macroId: string) {
        this.selectedMacroId.set(macroId);
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
        const { code, data } = await wiz.call("save_macro", {
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
