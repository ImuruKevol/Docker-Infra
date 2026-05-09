import { HostListener, OnDestroy, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

type EditorTab = 'compose' | 'defaults' | 'schema' | 'readme' | 'preview';
type VersionFileTab = 'compose' | 'defaults' | 'schema' | 'readme';

export class Component implements OnInit, OnDestroy {
    public loading = signal<boolean>(true);
    public busy = signal<boolean>(false);
    public detailLoading = signal<boolean>(false);
    public previewBusy = signal<boolean>(false);
    public versionBusy = signal<boolean>(false);
    public error = signal<string>('');
    public search = signal<string>('');
    public templateRoot = signal<string>('');
    public templates = signal<any[]>([]);
    public selectedTemplateId = signal<string>('');
    public detail = signal<any>(null);
    public currentTab = signal<EditorTab>('compose');
    public createModalOpen = signal<boolean>(false);
    public fileTreeOpen = signal<boolean>(false);
    public selectedVersionId = signal<string>('');
    public selectedVersion = signal<any>(null);
    public selectedVersionTab = signal<VersionFileTab>('compose');
    public editorOptions: any = {
        language: 'yaml',
        theme: 'vs',
        fontSize: 13,
        minimap: { enabled: false },
        automaticLayout: true,
        wordWrap: 'on',
        scrollBeyondLastLine: false,
        roundedSelection: false,
    };
    public schemaEditorOptions: any = {
        ...this.editorOptions,
        language: 'json',
    };
    public readmeEditorOptions: any = {
        ...this.editorOptions,
        language: 'markdown',
    };
    public createForm: any = this.emptyCreateForm();
    private themeObserver: MutationObserver | null = null;

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        this.syncEditorTheme();
        this.startThemeObserver();
        await this.load();
    }

    public ngOnDestroy() {
        this.stopThemeObserver();
    }

    @HostListener('document:keydown', ['$event'])
    public handleDocumentKeydown(event: KeyboardEvent) {
        const isSave = (event.ctrlKey || event.metaKey) && String(event.key || '').toLowerCase() === 's';
        if (!isSave || !this.detail()) return;
        event.preventDefault();
        void this.saveTemplate();
    }

    private emptyCreateForm() {
        return {
            name: '',
            description: '',
            image_name: 'nginx',
            image_version: 'alpine',
        };
    }

    private isDarkMode() {
        return Boolean(document.documentElement.classList.contains('dark'));
    }

    private syncEditorTheme() {
        this.editorOptions = {
            ...this.editorOptions,
            theme: this.isDarkMode() ? 'vs-dark' : 'vs',
        };
        this.schemaEditorOptions = {
            ...this.editorOptions,
            language: 'json',
        };
        this.readmeEditorOptions = {
            ...this.editorOptions,
            language: 'markdown',
        };
    }

    private startThemeObserver() {
        if (typeof MutationObserver === 'undefined') return;
        this.themeObserver = new MutationObserver(() => this.syncEditorTheme());
        this.themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    }

    private stopThemeObserver() {
        if (!this.themeObserver) return;
        this.themeObserver.disconnect();
        this.themeObserver = null;
    }

    private parseImageRef(value: any) {
        const raw = String(value || '').trim();
        if (!raw) {
            return { image_name: '', image_version: '' };
        }
        const lastSlash = raw.lastIndexOf('/');
        const lastColon = raw.lastIndexOf(':');
        if (lastColon > lastSlash) {
            return {
                image_name: raw.slice(0, lastColon),
                image_version: raw.slice(lastColon + 1),
            };
        }
        return {
            image_name: raw,
            image_version: '',
        };
    }

    private composeImageRef(imageName: any, imageVersion: any) {
        const name = String(imageName || '').trim();
        const version = String(imageVersion || '').trim();
        if (!name) return '';
        return version ? `${name}:${version}` : name;
    }

    private ensureTemplateFields(detail: any) {
        if (!detail?.template) return detail;
        const metadata = detail.template.metadata || {};
        const parsed = this.parseImageRef(metadata.primary_image);
        detail.template.metadata = {
            ...metadata,
            image_name: metadata.image_name || parsed.image_name,
            image_version: metadata.image_version || parsed.image_version,
        };
        return detail;
    }

    private suggestNamespace(raw: any) {
        const base = String(raw || '')
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9_]+/g, '_')
            .replace(/^_+|_+$/g, '') || 'template';
        const existing = new Set(this.templates().map((item: any) => String(item.namespace || '')));
        if (!existing.has(base)) return base;
        let index = 2;
        while (existing.has(`${base}_${index}`)) {
            index += 1;
        }
        return `${base}_${index}`;
    }

    private buildTemplatePayload() {
        const detail = this.detail();
        const metadata = {
            ...(detail?.template?.metadata || {}),
            primary_image: this.composeImageRef(detail?.template?.metadata?.image_name, detail?.template?.metadata?.image_version),
        };
        delete metadata.image_name;
        delete metadata.image_version;
        return {
            id: detail?.template?.id || undefined,
            name: detail?.template?.name,
            namespace: detail?.template?.namespace,
            description: detail?.template?.description || '',
            enabled: detail?.template?.enabled !== false,
            metadata,
            compose: detail?.files?.['docker-compose.yaml'] || '',
            values_default: detail?.files?.['values.default.yaml'] || '',
            values_schema: detail?.files?.['values.schema.json'] || '',
            readme: detail?.files?.['README.md'] || '',
        };
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

    public async confirm(message: string, action: string = '삭제', status: string = 'warning') {
        return await this.service.modal.show({
            title: '',
            message,
            cancel: true,
            cancelLabel: '취소',
            actionBtn: status,
            action,
            status,
        });
    }

    public async load(selectedId: string = '') {
        this.loading.set(true);
        this.error.set('');
        const { code, data } = await wiz.call('load', {});
        if (code === 200) {
            this.templateRoot.set(data.template_root || '');
            const templates = data.templates || [];
            this.templates.set(templates);
            const next = templates.find((item: any) => item.id === selectedId) || templates[0] || null;
            if (next?.id) await this.selectTemplate(next.id, true);
            else {
                this.detail.set(null);
                this.selectedVersion.set(null);
                this.selectedVersionId.set('');
            }
        } else {
            this.error.set(data?.message || '템플릿 정보를 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
    }

    public filteredTemplates() {
        const query = String(this.search() || '').trim().toLowerCase();
        if (!query) return this.templates();
        return this.templates().filter((item: any) => `${item.name} ${item.description || ''} ${item?.metadata?.primary_image || ''}`.toLowerCase().includes(query));
    }

    public enabledTemplatesCount() {
        return this.templates().filter((item: any) => item.enabled !== false).length;
    }

    public releasedVersionCount() {
        return this.templates().reduce((total: number, item: any) => total + Number(item.version_count || 0), 0);
    }

    public templateImageLabel(item: any) {
        return item?.metadata?.primary_image || '-';
    }

    public async selectTemplate(templateId: string, silent: boolean = false) {
        this.detailLoading.set(true);
        this.selectedTemplateId.set(templateId);
        this.selectedVersionId.set('');
        this.selectedVersion.set(null);
        const { code, data } = await wiz.call('detail', { template_id: templateId });
        if (code === 200) {
            this.detail.set(this.ensureTemplateFields(data));
            this.currentTab.set('compose');
        } else if (!silent) {
            await this.alert(data?.message || '템플릿 상세를 불러올 수 없습니다.');
        }
        this.detailLoading.set(false);
        await this.service.render();
    }

    public openCreateModal() {
        this.createForm = this.emptyCreateForm();
        this.createModalOpen.set(true);
    }

    public closeCreateModal() {
        if (this.busy()) return;
        this.createModalOpen.set(false);
        this.createForm = this.emptyCreateForm();
    }

    public openFileTree() {
        this.fileTreeOpen.set(true);
    }

    public closeFileTree() {
        this.fileTreeOpen.set(false);
    }

    public templateFileTreeContext() {
        return { template_id: this.detail()?.template?.id || '' };
    }

    public createDraftTemplate() {
        const name = String(this.createForm.name || '').trim() || '새 템플릿';
        const namespace = this.suggestNamespace(name);
        const primaryImage = this.composeImageRef(this.createForm.image_name, this.createForm.image_version) || 'nginx:alpine';
        this.detail.set({
            template: {
                id: '',
                name,
                namespace,
                description: this.createForm.description || '',
                enabled: true,
                metadata: {
                    primary_image: primaryImage,
                    image_name: this.createForm.image_name || 'nginx',
                    image_version: this.createForm.image_version || 'alpine',
                },
            },
            files: {
                'docker-compose.yaml': `services:\n  {{ service_name }}:\n    image: {{ image }}\n    ports:\n      - "{{ service_port }}:80"\n    healthcheck:\n      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1/ || exit 1"]\n      interval: 30s\n      timeout: 5s\n      retries: 3\n`,
                'values.default.yaml': `namespace: ${namespace}\nservice_name: web\nimage: ${primaryImage}\nservice_port: 8080\n`,
                'values.schema.json': `{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "${name}",
  "type": "object",
  "properties": {
    "namespace": { "type": "string", "default": "${namespace}" },
    "service_name": { "type": "string", "default": "web" },
    "image": { "type": "string", "default": "${primaryImage}" },
    "service_port": { "type": "integer", "default": 8080 }
  },
  "required": ["namespace", "service_name", "image", "service_port"]
}
`,
                'README.md': `# ${name}\n\n${this.createForm.description || '서비스 생성과 바로 호환되는 Docker Compose 템플릿입니다.'}\n`,
            },
            versions: [],
            preview: null,
        });
        this.selectedTemplateId.set('');
        this.selectedVersion.set(null);
        this.selectedVersionId.set('');
        this.currentTab.set('compose');
        this.createModalOpen.set(false);
    }

    public async saveTemplate() {
        if (!this.detail()?.template?.name) {
            await this.alert('템플릿 이름을 입력해주세요.');
            return;
        }
        this.busy.set(true);
        const { code, data } = await wiz.call('save_template', this.buildTemplatePayload());
        if (code === 200) {
            await this.load(data?.template?.id || this.selectedTemplateId());
            await this.alert('템플릿을 저장했습니다.', 'success');
        } else {
            const details = (data?.details || []).map((item: any) => item.path ? `- ${item.path}: ${item.message || item.error_code}` : `- ${item.message || item.error_code}`);
            await this.alert([data?.message || '템플릿을 저장할 수 없습니다.', ...details].join('\n'));
        }
        this.busy.set(false);
        await this.service.render();
    }

    public async createReleaseVersion() {
        if (!this.detail()?.template?.name) {
            await this.alert('템플릿 이름을 입력해주세요.');
            return;
        }
        this.busy.set(true);
        const { code, data } = await wiz.call('release_template', this.buildTemplatePayload());
        if (code === 200) {
            await this.load(data?.template?.id || this.selectedTemplateId());
            if (data?.version?.id) {
                await this.selectVersion(data.version.id, true);
            }
            await this.alert('버전을 생성했습니다.', 'success');
        } else {
            const details = (data?.details || []).map((item: any) => item.path ? `- ${item.path}: ${item.message || item.error_code}` : `- ${item.message || item.error_code}`);
            await this.alert([data?.message || '버전을 생성할 수 없습니다.', ...details].join('\n'));
        }
        this.busy.set(false);
        await this.service.render();
    }

    public async refreshPreview() {
        const detail = this.detail();
        if (!detail?.template) return;
        this.previewBusy.set(true);
        const { code, data } = await wiz.call('preview_template', {
            namespace: detail.template.namespace,
            compose: detail.files?.['docker-compose.yaml'] || '',
            values_default: detail.files?.['values.default.yaml'] || '',
        });
        if (code === 200) {
            this.detail.set({
                ...detail,
                preview: data.preview,
            });
        } else {
            await this.alert(data?.message || '템플릿 미리보기를 갱신할 수 없습니다.');
        }
        this.previewBusy.set(false);
        await this.service.render();
    }

    public async deleteTemplate() {
        if (!this.detail()?.template?.id) {
            this.detail.set(null);
            return;
        }
        const ok = await this.confirm(`${this.detail()?.template?.name} 템플릿을 삭제합니다.`);
        if (!ok) return;
        this.busy.set(true);
        const { code, data } = await wiz.call('delete_template', { template_id: this.detail()?.template?.id });
        if (code === 200) {
            this.detail.set(null);
            this.selectedVersion.set(null);
            this.selectedVersionId.set('');
            await this.load();
        } else {
            await this.alert(data?.message || '템플릿을 삭제할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public async selectVersion(versionId: string, silent: boolean = false) {
        if (!versionId) return;
        this.versionBusy.set(true);
        this.selectedVersionId.set(versionId);
        const { code, data } = await wiz.call('version_detail', { version_id: versionId });
        if (code === 200) {
            this.selectedVersion.set(data);
            this.selectedVersionTab.set('compose');
        } else if (!silent) {
            await this.alert(data?.message || '버전 내용을 불러올 수 없습니다.');
        }
        this.versionBusy.set(false);
        await this.service.render();
    }

    public setEditorTab(tab: EditorTab) {
        this.currentTab.set(tab);
        if (tab === 'preview') {
            void this.refreshPreview();
        }
    }

    public setVersionTab(tab: VersionFileTab) {
        this.selectedVersionTab.set(tab);
    }

    public selectedVersionContent() {
        const files = this.selectedVersion()?.files || {};
        if (this.selectedVersionTab() === 'defaults') return files['values.default.yaml'] || '';
        if (this.selectedVersionTab() === 'schema') return files['values.schema.json'] || '';
        if (this.selectedVersionTab() === 'readme') return files['README.md'] || '';
        return files['docker-compose.yaml'] || '';
    }

    public selectedVersionTitle() {
        const version = this.selectedVersion()?.version;
        return version ? `v${version.version}` : '';
    }

    public formatDate(value: any) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString();
    }

    public statusClass(enabled: any) {
        if (enabled === true || enabled === 'active') return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }
}
