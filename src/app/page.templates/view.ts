import { HostListener, OnDestroy, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

type EditorTab = 'compose' | 'defaults' | 'schema' | 'readme' | 'preview' | 'versions';
type VersionFileTab = 'compose' | 'defaults' | 'schema' | 'readme';
type VersionPanelTab = 'history' | 'content';

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
    public aiModalOpen = signal<boolean>(false);
    public aiBusy = signal<boolean>(false);
    public fileTreeOpen = signal<boolean>(false);
    public selectedVersionId = signal<string>('');
    public selectedVersion = signal<any>(null);
    public selectedVersionTab = signal<VersionFileTab>('compose');
    public versionPanelTab = signal<VersionPanelTab>('history');
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
    public aiForm: any = { intent: '', model_ref: 'auto' };
    public aiResult: any = null;
    public aiModelOptions = signal<any[]>([]);
    public aiDefaultModelRef = signal<string>('auto');
    public aiStreamEvents = signal<any[]>([]);
    public aiOutputTokenCount = signal<number>(0);
    public aiEditBusy = signal<boolean>(false);
    public aiEditForm: any = { intent: '', model_ref: 'auto' };
    public aiEditResult: any = null;
    public aiEditProposal: any = null;
    public aiEditOriginal: any = null;
    public aiEditRollbackSnapshot: any = null;
    public aiEditApplied = signal<boolean>(false);
    public aiEditStreamEvents = signal<any[]>([]);
    public aiEditOutputTokenCount = signal<number>(0);
    private themeObserver: MutationObserver | null = null;

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        this.syncEditorTheme();
        this.startThemeObserver();
        await this.load();
        await this.loadAiModelOptions();
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

    private currentTemplateDefinition() {
        const payload = this.buildTemplatePayload();
        return {
            template: {
                id: payload.id || '',
                name: payload.name || '',
                namespace: payload.namespace || '',
                description: payload.description || '',
                enabled: payload.enabled !== false,
                metadata: payload.metadata || {},
            },
            files: {
                'docker-compose.yaml': payload.compose || '',
                'values.default.yaml': payload.values_default || '',
                'values.schema.json': payload.values_schema || '',
                'README.md': payload.readme || '',
            },
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

    public async loadAiModelOptions() {
        const { code, data } = await wiz.call('ai_model_options', {});
        if (code === 200) {
            this.aiModelOptions.set(data.options || []);
            this.aiDefaultModelRef.set(data.default_model_ref || 'auto');
            this.aiEditForm.model_ref = data.default_model_ref || 'auto';
        }
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
            this.resetAiEditState();
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

    public openAiModal() {
        this.aiForm = {
            intent: '',
            model_ref: this.aiDefaultModelRef() || 'auto',
        };
        this.aiResult = null;
        this.resetAiStream();
        this.aiModalOpen.set(true);
    }

    public closeAiModal() {
        if (this.aiBusy()) return;
        this.aiModalOpen.set(false);
    }

    public templateAiInputRows() {
        return [
            { key: 'intent', value: '요구사항' },
            { key: 'model', value: 'AI 설정에서 사용 가능한 모델' },
            { key: 'constraints', value: '포트, 보안, 볼륨 제약' },
        ];
    }

    public templateAiOutputRows() {
        return [
            { key: 'template', value: '이름, 네임스페이스, 설명, 메타데이터' },
            { key: 'compose', value: 'docker-compose.yaml' },
            { key: 'values', value: '기본값 YAML, Schema JSON' },
            { key: 'result', value: '요약, 경고, 렌더 미리보기' },
        ];
    }

    private resetAiStream() {
        this.aiStreamEvents.set([]);
        this.aiOutputTokenCount.set(0);
    }

    private pushAiEvent(event: any) {
        const events = [...this.aiStreamEvents(), event].slice(-120);
        this.aiStreamEvents.set(events);
        if (event?.type === 'delta') {
            this.aiOutputTokenCount.set(this.aiOutputTokenCount() + String(event.text || '').length);
        }
    }

    public aiStreamRows() {
        return this.compactAiStreamRows(this.aiStreamEvents());
    }

    private streamLines(value: any) {
        return String(value || '')
            .replace(/\r/g, '')
            .split('\n')
            .map((line: string) => line.replace(/\s+/g, ' ').trim())
            .filter((line: string) => !!line)
            .map((line: string) => line.length > 220 ? `${line.slice(0, 217)}...` : line);
    }

    private latestStreamLine(value: any) {
        const lines = this.streamLines(value);
        if (!lines.length) return '';
        const cleaned = lines[lines.length - 1]
            .replace(/^[\s"',:{}\[\]]+|[\s"',:{}\[\]]+$/g, '')
            .replace(/\\"/g, '"')
            .trim();
        if (!cleaned || /^[{}\[\],:"]+$/.test(cleaned)) return '';
        return cleaned.length > 120 ? `${cleaned.slice(0, 117)}...` : cleaned;
    }

    private streamProgressMessage(value: any) {
        const text = String(value || '');
        let stage = 'AI 응답 작성 중';
        if (text.includes('"README.md"')) stage = 'README 작성 중';
        else if (text.includes('"values.schema.json"')) stage = 'Schema 작성 중';
        else if (text.includes('"values.default.yaml"')) stage = '기본값 작성 중';
        else if (text.includes('"docker-compose.yaml"') || text.includes('"compose"')) stage = 'Compose 작성 중';
        else if (text.includes('"components"')) stage = '컴포넌트 설정 작성 중';
        else if (text.includes('"form"')) stage = '서비스 기본 정보 작성 중';
        else if (text.includes('"template"')) stage = '템플릿 메타데이터 작성 중';
        const latest = this.latestStreamLine(text);
        return latest ? `${stage} · ${latest}` : stage;
    }

    private compactAiStreamRows(events: any[]) {
        const rows: any[] = [];
        let thinkingBuffer = '';
        let deltaBuffer = '';
        let progressIndex = -1;
        const pushRow = (row: any) => {
            const message = row?.message || row?.text || row?.provider?.label;
            if (!message && row?.type !== 'provider') return;
            const last = rows[rows.length - 1];
            if (last?.type === row?.type && (last?.message || last?.text) === (row?.message || row?.text)) return;
            rows.push(row);
        };
        const upsertProgress = () => {
            if (!deltaBuffer) return;
            const row = { type: 'progress', label: '생각 중', message: this.streamProgressMessage(deltaBuffer) };
            if (progressIndex >= 0) rows[progressIndex] = row;
            else {
                progressIndex = rows.length;
                rows.push(row);
            }
        };
        const flushThinking = (force: boolean = false) => {
            if (!thinkingBuffer) return;
            const parts = thinkingBuffer.split('\n');
            thinkingBuffer = parts.pop() || '';
            for (const line of parts) {
                for (const text of this.streamLines(line)) {
                    pushRow({ type: 'thinking', message: text, text });
                }
            }
            if (force && thinkingBuffer.trim()) {
                const text = this.streamLines(thinkingBuffer).join(' ');
                if (text) pushRow({ type: 'thinking', message: text, text });
                thinkingBuffer = '';
            }
        };
        for (const event of events || []) {
            if (!['provider', 'status', 'thinking', 'error', 'delta'].includes(event?.type)) continue;
            if (event.type === 'delta') {
                deltaBuffer += String(event.text || '');
                upsertProgress();
                continue;
            }
            if (event.type === 'thinking') {
                thinkingBuffer += String(event.text || event.message || '');
                flushThinking(false);
                continue;
            }
            flushThinking(true);
            if (event.type === 'provider') {
                pushRow(event);
                continue;
            }
            for (const text of this.streamLines(event.message || event.text || '')) {
                pushRow({ ...event, message: text, text });
            }
        }
        flushThinking(true);
        return rows.slice(-8);
    }

    private async streamAi(functionName: string, payload: any, onDone: (data: any) => Promise<void>) {
        const formData = new FormData();
        formData.append('payload', JSON.stringify(payload || {}));
        const response = await fetch(`/wiz/api/page.templates/${functionName}`, { method: 'POST', body: formData });
        if (!response.ok || !response.body) {
            throw new Error(`AI 스트림 요청 실패: HTTP ${response.status}`);
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const blocks = buffer.split('\n\n');
            buffer = blocks.pop() || '';
            for (const block of blocks) {
                const line = block.split('\n').find((item: string) => item.startsWith('data: '));
                if (!line) continue;
                const event = JSON.parse(line.slice(6));
                this.pushAiEvent(event);
                if (event.type === 'error') {
                    throw new Error(event.message || 'AI 스트림 처리 중 오류가 발생했습니다.');
                }
                if (event.type === 'done') {
                    await onDone(event.data);
                }
            }
            await this.service.render();
        }
    }

    private resetAiEditStream() {
        this.aiEditStreamEvents.set([]);
        this.aiEditOutputTokenCount.set(0);
    }

    private resetAiEditState() {
        this.aiEditResult = null;
        this.aiEditProposal = null;
        this.aiEditOriginal = null;
        this.aiEditRollbackSnapshot = null;
        this.aiEditApplied.set(false);
        this.resetAiEditStream();
    }

    private pushAiEditEvent(event: any) {
        const events = [...this.aiEditStreamEvents(), event].slice(-80);
        this.aiEditStreamEvents.set(events);
        if (event?.type === 'delta') {
            this.aiEditOutputTokenCount.set(this.aiEditOutputTokenCount() + String(event.text || '').length);
        }
    }

    public aiEditStreamRows() {
        return this.compactAiStreamRows(this.aiEditStreamEvents());
    }

    private async streamAiEdit(payload: any, onDone: (data: any) => Promise<void>) {
        const formData = new FormData();
        formData.append('payload', JSON.stringify(payload || {}));
        const response = await fetch('/wiz/api/page.templates/stream_template_ai', { method: 'POST', body: formData });
        if (!response.ok || !response.body) {
            throw new Error(`AI 스트림 요청 실패: HTTP ${response.status}`);
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const blocks = buffer.split('\n\n');
            buffer = blocks.pop() || '';
            for (const block of blocks) {
                const line = block.split('\n').find((item: string) => item.startsWith('data: '));
                if (!line) continue;
                const event = JSON.parse(line.slice(6));
                this.pushAiEditEvent(event);
                if (event.type === 'error') {
                    throw new Error(event.message || 'AI 스트림 처리 중 오류가 발생했습니다.');
                }
                if (event.type === 'done') {
                    await onDone(event.data);
                }
            }
            await this.service.render();
        }
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

    private clone(value: any) {
        return JSON.parse(JSON.stringify(value || null));
    }

    private applyAiTemplateDraft(draft: any, preview: any, target: string = 'update') {
        const current = target === 'update' ? this.detail() : null;
        const template = {
            ...(current?.template || {}),
            ...(draft?.template || {}),
        };
        if (target === 'update' && !template.id && current?.template?.id) {
            template.id = current.template.id;
        } else if (target !== 'update') {
            template.id = '';
        }
        const files = {
            'docker-compose.yaml': '',
            'values.default.yaml': '{}\n',
            'values.schema.json': '{}',
            'README.md': '',
            ...(current?.files || {}),
            ...(draft?.files || {}),
        };
        this.detail.set(this.ensureTemplateFields({
            template,
            files,
            versions: target === 'update' ? (current?.versions || []) : [],
            preview: preview || current?.preview || null,
        }));
        this.selectedTemplateId.set(template.id || '');
        this.selectedVersion.set(null);
        this.selectedVersionId.set('');
        this.currentTab.set('preview');
    }

    public async generateTemplateWithAi() {
        const intent = String(this.aiForm.intent || '').trim();
        if (!intent) {
            await this.alert('AI 요청 내용을 입력해주세요.');
            return;
        }
        this.aiBusy.set(true);
        this.resetAiStream();
        try {
            await this.streamAi('stream_template_ai', {
                intent,
                mode: 'template_create',
                model_ref: this.aiForm.model_ref || 'auto',
                current: null,
            }, async (data: any) => {
                this.aiResult = data;
                this.applyAiTemplateDraft(data?.draft, data?.preview, 'new');
            });
            this.aiModalOpen.set(false);
            await this.alert(this.aiResult?.summary || 'AI 템플릿 초안을 적용했습니다. 저장 전 내용을 검토하세요.', 'success');
        } catch (error: any) {
            await this.alert(error?.message || 'AI 템플릿 초안을 생성할 수 없습니다.');
        }
        this.aiBusy.set(false);
        await this.service.render();
    }

    public async generateTemplateEditWithAi() {
        const intent = String(this.aiEditForm.intent || '').trim();
        if (!this.detail()?.template) {
            await this.alert('수정할 템플릿을 먼저 선택해주세요.');
            return;
        }
        if (!intent) {
            await this.alert('AI 수정 요청 내용을 입력해주세요.');
            return;
        }
        this.aiEditBusy.set(true);
        this.aiEditResult = null;
        this.aiEditProposal = null;
        this.aiEditApplied.set(false);
        this.resetAiEditStream();
        this.aiEditOriginal = this.clone(this.currentTemplateDefinition());
        this.aiEditRollbackSnapshot = this.clone(this.currentTemplateDefinition());
        try {
            await this.streamAiEdit({
                intent,
                mode: 'template_update',
                model_ref: this.aiEditForm.model_ref || this.aiDefaultModelRef() || 'auto',
                current: this.currentTemplateDefinition(),
            }, async (data: any) => {
                this.aiEditResult = data;
                this.aiEditProposal = data?.draft || null;
            });
        } catch (error: any) {
            await this.alert(error?.message || 'AI 수정안을 생성할 수 없습니다.');
        }
        this.aiEditBusy.set(false);
        await this.service.render();
    }

    public aiEditChanges() {
        const before = this.aiEditOriginal;
        const after = this.aiEditProposal;
        if (!before?.template || !after?.template) return [];
        const rows: any[] = [];
        const add = (label: string, beforeValue: any, afterValue: any) => {
            const previous = this.compactValue(beforeValue);
            const next = this.compactValue(afterValue);
            if (previous !== next) rows.push({ label, before: previous || '-', after: next || '-' });
        };
        add('이름', before.template.name, after.template.name);
        add('네임스페이스', before.template.namespace, after.template.namespace);
        add('설명', before.template.description, after.template.description);
        add('사용 여부', before.template.enabled !== false ? '사용' : '꺼짐', after.template.enabled !== false ? '사용' : '꺼짐');
        add('대표 이미지', before.template.metadata?.primary_image, after.template.metadata?.primary_image);
        for (const file of ['docker-compose.yaml', 'values.default.yaml', 'values.schema.json', 'README.md']) {
            const previous = before.files?.[file] || '';
            const next = after.files?.[file] || '';
            if (previous !== next) {
                rows.push({
                    label: file,
                    before: `${this.lineCount(previous)} lines · ${previous.length} chars`,
                    after: `${this.lineCount(next)} lines · ${next.length} chars`,
                });
            }
        }
        return rows;
    }

    private compactValue(value: any) {
        if (value === undefined || value === null) return '';
        return String(value).replace(/\s+/g, ' ').trim();
    }

    private lineCount(value: any) {
        const text = String(value || '');
        if (!text) return 0;
        return text.split(/\r?\n/).length;
    }

    public async applyAiEditProposal() {
        if (!this.aiEditProposal) return;
        this.applyAiTemplateDraft(this.aiEditProposal, this.aiEditResult?.preview, 'update');
        this.aiEditApplied.set(true);
        await this.alert('AI 수정안을 편집기에 적용했습니다. 저장 전 내용을 검토하세요.', 'success');
        await this.service.render();
    }

    public async rollbackAiEditProposal() {
        if (!this.aiEditRollbackSnapshot) return;
        const current = this.detail();
        this.detail.set(this.ensureTemplateFields({
            template: this.clone(this.aiEditRollbackSnapshot.template),
            files: this.clone(this.aiEditRollbackSnapshot.files),
            versions: current?.versions || [],
            preview: null,
        }));
        this.aiEditApplied.set(false);
        this.currentTab.set('compose');
        await this.service.render();
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

    public setVersionPanelTab(tab: VersionPanelTab) {
        this.versionPanelTab.set(tab);
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
