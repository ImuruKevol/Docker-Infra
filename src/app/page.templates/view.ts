import { OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

type TemplateTab = 'readme' | 'compose' | 'values' | 'schema' | 'preview';
type NewTemplateMode = '' | 'choose' | 'ai' | 'manual';

export class Component implements OnInit {
    public loading = signal<boolean>(true);
    public busy = signal<boolean>(false);
    public error = signal<string>('');
    public detailLoading = signal<boolean>(false);
    public detailLoadError = signal<string>('');
    public templates = signal<any[]>([]);
    public selectedId = signal<string>('');
    public detail = signal<any>(null);
    public activeTab = signal<TemplateTab>('readme');
    public preview = signal<any>(null);
    public aiBusy = signal<boolean>(false);
    public aiAvailable = signal<boolean>(false);
    public aiUnavailableMessage = signal<string>('');
    public aiModelOptions = signal<any[]>([]);
    public aiDefaultModelRef = signal<string>('auto');
    public aiIntent = signal<string>('');
    public aiModelRef = signal<string>('auto');
    public aiStreamEvents = signal<any[]>([]);
    public aiOutputTokenCount = signal<number>(0);
    public aiContract = signal<any>(null);
    public templateAiModalOpen = signal<boolean>(false);
    public newTemplateMode = signal<NewTemplateMode>('');
    public newTemplateDraftReady = signal<boolean>(false);
    public cloneSourceId = signal<string>('');
    public cloneLoading = signal<boolean>(false);
    public previewValues: any = {};
    public tagInput = '';
    public aiResult: any = null;
    public form: any = {
        namespace: '',
        name: '',
        enabled: true,
        tags: [],
    };
    public files: any = {
        compose: '',
        values_default: '',
        values_schema: '',
        readme: '',
    };
    private editorBaseOptions: any = {
        fontSize: 13,
        minimap: { enabled: false },
        automaticLayout: true,
        wordWrap: 'on',
        scrollBeyondLastLine: false,
    };
    public editorOptionsByTab: any = {};
    public activeEditorOptions: any = {};
    private detailLoadRequestId = 0;
    private detailCache: Record<string, any> = {};

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        this.syncEditorTheme();
        await this.load();
        this.loadAuxiliaryData().catch(() => null);
    }

    private async loadAuxiliaryData() {
        await Promise.all([
            this.loadAiContract().catch(() => null),
            this.loadAiModelOptions().catch(() => null),
        ]);
        await this.service.render();
    }

    private syncEditorTheme() {
        const dark = document.documentElement.classList.contains('dark');
        const theme = dark ? 'vs-dark' : 'vs';
        this.editorOptionsByTab = {
            compose: { ...this.editorBaseOptions, theme, language: 'yaml' },
            values: { ...this.editorBaseOptions, theme, language: 'yaml' },
            schema: { ...this.editorBaseOptions, theme, language: 'json' },
            readme: { ...this.editorBaseOptions, theme, language: 'markdown' },
            preview: { ...this.editorBaseOptions, theme, language: 'yaml' },
        };
        this.activeEditorOptions = this.editorOptionsByTab[this.activeTab()] || this.editorOptionsByTab.compose;
    }

    private emptyFiles() {
        return {
            compose: '',
            values_default: '',
            values_schema: '',
            readme: '',
        };
    }

    private emptyForm(namespace: string = '') {
        return {
            namespace,
            name: '',
            enabled: true,
            tags: [],
        };
    }

    private namespaceSlug(value: string = 'compose_template') {
        const clean = String(value || 'compose_template')
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9_]+/g, '_')
            .replace(/_+/g, '_')
            .replace(/^_+|_+$/g, '');
        return clean || 'compose_template';
    }

    private nextTemplateNamespace(base: string = 'compose_template') {
        return `${this.namespaceSlug(base).slice(0, 42)}_${Date.now()}`;
    }

    private resetDetailState(namespace: string = '') {
        this.detail.set(null);
        this.form = this.emptyForm(namespace);
        this.files = this.emptyFiles();
        this.previewValues = {};
        this.preview.set(null);
        this.tagInput = '';
        this.detailLoadError.set('');
        this.setActiveTab('readme');
    }

    private resetNewDraftState(namespace: string = '') {
        this.selectedId.set('');
        this.detail.set(null);
        this.form = this.emptyForm(namespace);
        this.files = this.emptyFiles();
        this.previewValues = {};
        this.preview.set(null);
        this.tagInput = '';
        this.detailLoading.set(false);
        this.detailLoadError.set('');
        this.aiResult = null;
        this.resetAiStream();
        this.setActiveTab('readme');
    }

    private resetNewTemplateFlow(mode: NewTemplateMode = 'choose') {
        this.detailLoadRequestId += 1;
        this.resetNewDraftState();
        this.newTemplateMode.set(mode);
        this.newTemplateDraftReady.set(false);
        this.cloneLoading.set(false);
        this.cloneSourceId.set('');
        this.aiIntent.set('');
    }

    private detailCacheItem(templateId: string) {
        return this.detailCache[String(templateId || '').trim()] || null;
    }

    private normalizeTags(value: any) {
        const raw = Array.isArray(value) ? value : String(value || '').split(',');
        const tags: string[] = [];
        for (const item of raw) {
            const tag = String(item || '').trim();
            if (tag && !tags.includes(tag)) tags.push(tag);
        }
        return tags;
    }

    private metadataTags(metadata: any) {
        const tags = this.normalizeTags(metadata?.tags);
        if (tags.length) return tags;
        return this.normalizeTags(metadata?.category);
    }

    private applyTemplateDetail(template: any, templateId: string) {
        const key = String(templateId || template?.id || template?.namespace || '').trim();
        if (!key || !template) return;
        this.detailCache = { ...this.detailCache, [key]: template };
        if (this.selectedId() !== key) return;
        const metadata = template.metadata || {};
        this.detail.set(template);
        this.form = {
            namespace: template.namespace || '',
            name: template.name || '',
            enabled: template.enabled !== false,
            tags: this.metadataTags(metadata),
        };
        this.files = { ...this.emptyFiles(), ...(template.files || {}) };
        this.previewValues = { ...(template.values || {}) };
        this.preview.set(null);
        this.tagInput = '';
        this.detailLoadError.set('');
        this.setActiveTab('readme');
    }

    public async load(selectFirst: boolean = true) {
        this.loading.set(true);
        this.error.set('');
        this.detailLoading.set(false);
        this.detailLoadError.set('');
        this.selectedId.set('');
        this.newTemplateMode.set('');
        this.newTemplateDraftReady.set(false);
        this.cloneSourceId.set('');
        this.resetDetailState();
        this.detailCache = {};
        this.detailLoadRequestId += 1;
        const { code, data } = await wiz.call('load', {});
        if (code === 200) {
            this.templates.set(data.templates || []);
            const first = this.templates()[0];
            this.loading.set(false);
            await this.service.render();
            if (selectFirst && first) this.selectInitialTemplate(first.id || first.namespace);
            return;
        } else {
            this.error.set(data?.message || '템플릿 목록을 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
    }

    private async selectInitialTemplate(templateId: string) {
        try {
            await this.selectTemplate(templateId, true, true);
        } catch (error: any) {
            this.detailLoading.set(false);
            this.detailLoadError.set(error?.message || '템플릿 정보를 불러올 수 없습니다.');
            await this.service.render();
        }
    }

    public templateTags(item: any) {
        return this.metadataTags(item?.metadata || {});
    }

    public templateBadge(item: any) {
        return this.templateTags(item)[0] || 'compose';
    }

    public isSelected(item: any) {
        return (item.id || item.namespace) === this.selectedId();
    }

    public async selectTemplate(templateId: string, render: boolean = true, force: boolean = false) {
        if (!templateId) return;
        const key = String(templateId || '').trim();
        const requestId = ++this.detailLoadRequestId;
        const isTemplateChange = this.selectedId() !== key;
        this.newTemplateMode.set('');
        this.newTemplateDraftReady.set(false);
        this.cloneSourceId.set('');
        this.cloneLoading.set(false);
        this.selectedId.set(key);
        this.preview.set(null);
        this.detailLoadError.set('');
        const cached = force ? null : this.detailCacheItem(key);
        if (cached) {
            this.detailLoading.set(false);
            this.applyTemplateDetail(cached, key);
            if (render) await this.service.render();
            return;
        }
        this.detailLoading.set(true);
        if (isTemplateChange || !this.detail()) {
            this.resetDetailState(key);
        }
        if (render) await this.service.render();
        const { code, data } = await wiz.call('detail', { template_id: templateId });
        if (requestId !== this.detailLoadRequestId || this.selectedId() !== key) return;
        this.detailLoading.set(false);
        if (code !== 200) {
            const message = data?.message || '템플릿 정보를 불러올 수 없습니다.';
            this.detailLoadError.set(message);
            if (render) await this.alert(message);
            if (render) await this.service.render();
            return;
        }
        this.applyTemplateDetail(data.template || {}, key);
        if (render) await this.service.render();
    }

    private defaultTemplateDraft() {
        const namespace = this.nextTemplateNamespace('compose_template');
        this.selectedId.set('');
        this.detail.set(null);
        this.form = {
            namespace,
            name: '새 Compose 템플릿',
            enabled: true,
            tags: ['custom'],
        };
        this.files = {
            compose: 'services:\n  app:\n    image: {{ image }}\n    ports:\n      - "{{ service_port }}:80"\n    healthcheck:\n      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:80/ || exit 1"]\n      interval: 30s\n      timeout: 5s\n      retries: 5\n',
            values_default: 'namespace: custom_service\nimage: nginx:alpine\nservice_port: 8080\n',
            values_schema: JSON.stringify({
                $schema: 'https://json-schema.org/draft/2020-12/schema',
                title: '새 Compose 템플릿',
                type: 'object',
                properties: {
                    namespace: { title: '서비스 내부 이름', type: 'string', default: 'custom_service' },
                    image: { title: '이미지', type: 'string', default: 'nginx:alpine' },
                    service_port: { title: '공개 포트', type: 'integer', default: 8080 },
                },
                required: ['namespace', 'image', 'service_port'],
            }, null, 2),
            readme: '# 새 Compose 템플릿\n',
        };
        this.previewValues = { namespace: 'custom_service', image: 'nginx:alpine', service_port: 8080 };
        this.preview.set(null);
        this.detailLoading.set(false);
        this.detailLoadError.set('');
        this.tagInput = '';
        this.setActiveTab('readme');
        this.newTemplateDraftReady.set(true);
    }

    public newTemplate() {
        this.defaultTemplateDraft();
    }

    public async createNewTemplate() {
        this.resetNewTemplateFlow('choose');
        await this.service.render();
    }

    public cloneTemplateOptions() {
        return [
            {
                value: '',
                label: '빈 템플릿',
                description: '기존 템플릿을 사용하지 않고 새 표준 파일로 시작',
                badge: 'new',
                badgeClass: 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300',
            },
            ...this.templates().map((item: any) => ({
                value: item.id || item.namespace,
                label: item.name || item.namespace,
                description: item.readme_excerpt || item.namespace || item.id || '',
                badge: this.templateBadge(item),
                badgeClass: 'border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-900/70 dark:bg-indigo-950/40 dark:text-indigo-300',
            })),
        ];
    }

    public isNewTemplateFlow() {
        return !this.isEditingTemplate() && !!this.newTemplateMode();
    }

    public showTemplateEditor() {
        return this.isEditingTemplate() || this.newTemplateMode() === 'manual' || this.newTemplateDraftReady();
    }

    public canSaveTemplate() {
        return this.showTemplateEditor() && !this.cloneLoading();
    }

    public editorTitle() {
        if (this.isNewTemplateFlow()) return this.form.name || '새 Compose 템플릿';
        return this.form.name || '템플릿 편집';
    }

    public editorSubtitle() {
        if (this.isNewTemplateFlow()) {
            if (this.newTemplateMode() === 'ai') return 'AI 초안 작성';
            if (this.newTemplateMode() === 'manual') return '직접 작성';
            return '작성 방식을 선택하세요';
        }
        return this.form.namespace || '-';
    }

    private async loadCloneTemplateDetail(templateId: string) {
        const key = String(templateId || '').trim();
        if (!key) return null;
        const cached = this.detailCacheItem(key);
        if (cached?.files) return cached;
        const { code, data } = await wiz.call('detail', { template_id: key });
        if (code !== 200) {
            await this.alert(data?.message || '기반 템플릿을 불러올 수 없습니다.');
            return null;
        }
        const template = data.template || null;
        if (template) this.detailCache = { ...this.detailCache, [key]: template };
        return template;
    }

    private applyCloneDraft(template: any, markReady: boolean = true) {
        const metadata = template?.metadata || {};
        const sourceNamespace = template?.namespace || template?.id || template?.name || 'compose_template';
        this.selectedId.set('');
        this.detail.set(null);
        this.form = {
            namespace: this.nextTemplateNamespace(sourceNamespace),
            name: `${template?.name || sourceNamespace} 복제`,
            enabled: true,
            tags: this.metadataTags(metadata),
        };
        this.files = { ...this.emptyFiles(), ...(template?.files || {}) };
        this.previewValues = { ...(template?.values || {}) };
        this.preview.set(null);
        this.detailLoading.set(false);
        this.detailLoadError.set('');
        this.tagInput = '';
        this.aiResult = null;
        this.setActiveTab('readme');
        this.newTemplateDraftReady.set(markReady);
    }

    private async prepareNewDraftFromClone(markReady: boolean) {
        const sourceId = this.cloneSourceId();
        if (!sourceId) {
            this.resetNewDraftState();
            this.newTemplateDraftReady.set(false);
            return true;
        }
        this.cloneLoading.set(true);
        await this.service.render();
        const template = await this.loadCloneTemplateDetail(sourceId);
        this.cloneLoading.set(false);
        if (!template) {
            await this.service.render();
            return false;
        }
        this.applyCloneDraft(template, markReady);
        await this.service.render();
        return true;
    }

    public async setCloneSource(templateId: string) {
        this.cloneSourceId.set(String(templateId || '').trim());
        if (this.newTemplateMode() === 'manual') {
            await this.prepareManualNewTemplate();
            return;
        }
        if (this.newTemplateMode() === 'ai') {
            await this.prepareNewDraftFromClone(false);
        }
    }

    public async chooseNewTemplateMode(mode: NewTemplateMode) {
        if (mode !== 'ai' && mode !== 'manual') return;
        this.newTemplateMode.set(mode);
        this.newTemplateDraftReady.set(false);
        this.aiResult = null;
        this.resetAiStream();
        if (mode === 'manual') {
            await this.prepareManualNewTemplate();
            return;
        }
        await this.prepareNewDraftFromClone(false);
    }

    public async resetNewTemplateChoice() {
        if (this.aiBusy() || this.cloneLoading()) return;
        this.resetNewDraftState();
        this.newTemplateMode.set('choose');
        this.newTemplateDraftReady.set(false);
        await this.service.render();
    }

    private async prepareManualNewTemplate() {
        if (this.cloneSourceId()) {
            await this.prepareNewDraftFromClone(true);
            return;
        }
        this.defaultTemplateDraft();
        await this.service.render();
    }

    public async loadAiModelOptions() {
        const { code, data } = await wiz.call('ai_model_options', {});
        if (code === 200) {
            const options = data.options || [];
            this.aiModelOptions.set(options);
            this.aiAvailable.set(options.length > 0);
            this.aiUnavailableMessage.set(options.length ? '' : (data.message || '시스템 설정에서 사용 중인 AI 모델이 없습니다.'));
            this.aiDefaultModelRef.set(data.default_model_ref || '');
            this.aiModelRef.set(data.default_model_ref || 'auto');
            return;
        }
        this.aiModelOptions.set([]);
        this.aiAvailable.set(false);
        this.aiUnavailableMessage.set(data?.message || 'AI 모델 목록을 불러올 수 없습니다.');
    }

    public async loadAiContract() {
        const { code, data } = await wiz.call('ai_contract', {});
        this.aiContract.set(code === 200 ? (data.contract || null) : null);
    }

    public hasAiModels() {
        return this.aiAvailable() && this.aiModelOptions().length > 0;
    }

    public aiPolicy() {
        return this.aiContract()?.policy || {};
    }

    public isEditingTemplate() {
        return Boolean(this.selectedId() || this.detail()?.id || this.detail()?.namespace);
    }

    public async openTemplateAiModal() {
        if (!this.isEditingTemplate()) return;
        if (this.detailLoading()) return;
        if (!this.hasAiModels()) {
            await this.alert(this.aiUnavailableMessage() || '시스템 설정에서 사용할 AI 모델을 먼저 켜주세요.');
            return;
        }
        this.templateAiModalOpen.set(true);
        this.aiResult = null;
        this.resetAiStream();
        await this.service.render();
    }

    public closeTemplateAiModal() {
        if (this.aiBusy()) return;
        this.templateAiModalOpen.set(false);
    }

    public templateStandardGuide() {
        const standard = this.aiPolicy().standard || {};
        const placeholder = standard.placeholder_format || '{{ variable_name }}';
        const guides: any = {
            compose: {
                icon: 'fa-file-code',
                title: 'Compose 탭 표준',
                description: '서비스 생성 시 렌더링될 docker-compose.yaml 템플릿입니다. 운영 환경에 고정된 값보다 재사용 가능한 변수와 안전한 기본 구성을 우선합니다.',
                rows: [
                    { label: '변수', value: `사용자 입력값은 ${placeholder} 형식으로 작성하고 기본값/Schema에 같은 이름으로 등록` },
                    { label: '구성', value: 'container_name, hostname, 등록 서버 ID, 실제 도메인처럼 배포 환경에 묶이는 값은 제외' },
                    { label: '검증', value: '기본값으로 렌더링했을 때 Docker Compose 검증을 통과하고 필수 healthcheck를 포함' },
                ],
            },
            values: {
                icon: 'fa-sliders',
                title: '기본값 탭 표준',
                description: 'values.default.yaml은 Compose placeholder를 즉시 렌더링할 수 있게 만드는 기본 입력값입니다.',
                rows: [
                    { label: '일치', value: 'Compose에 등장하는 모든 placeholder 키를 빠짐없이 포함' },
                    { label: '기본값', value: '서비스 이름, 포트, 이미지 태그처럼 사용자가 바로 이해할 수 있는 안전한 예시값 사용' },
                    { label: '비밀값', value: 'password, token, secret 계열은 실제 비밀값 대신 change_me 형태의 교체용 값 사용' },
                ],
            },
            schema: {
                icon: 'fa-list-check',
                title: 'Schema 탭 표준',
                description: 'values.schema.json은 서비스 생성 화면의 입력 폼과 검증 규칙을 결정합니다.',
                rows: [
                    { label: 'properties', value: '기본값의 모든 키를 title, type, default와 함께 정의' },
                    { label: 'required', value: 'Compose 렌더링에 필요한 placeholder는 required에 포함' },
                    { label: '입력 UX', value: 'secret=true, enum, description을 활용해 서비스 생성자가 입력 의미를 바로 파악하게 구성' },
                ],
            },
        };
        return guides[this.activeTab()] || null;
    }

    public templateStandardRows() {
        return this.templateStandardGuide()?.rows || [];
    }

    public templateAiTargetRows() {
        return [
            { label: 'README', value: '템플릿 목적과 값 설명을 한국어로 보완' },
            { label: 'Compose', value: 'placeholder 기반 재사용 구조와 Docker Infra 표준 검증' },
            { label: '기본값/Schema', value: '누락된 변수, 타입, 필수 입력, secret 표시 동기화' },
            { label: '저장', value: 'AI 결과는 화면에만 반영되며 저장 버튼을 눌러야 확정' },
        ];
    }

    private currentTemplateForAi() {
        return {
            id: this.selectedId(),
            name: this.form.name,
            namespace: this.form.namespace,
            enabled: this.form.enabled,
            metadata: this.payloadMetadata(),
            files: this.files,
            values: this.previewValues,
        };
    }

    private resetAiStream() {
        this.aiStreamEvents.set([]);
        this.aiOutputTokenCount.set(0);
    }

    private pushAiEvent(event: any) {
        this.aiStreamEvents.set([...this.aiStreamEvents(), event].slice(-120));
        if (event?.type === 'delta') {
            this.aiOutputTokenCount.set(this.aiOutputTokenCount() + String(event.text || '').length);
        }
    }

    private streamLines(value: any) {
        return String(value || '')
            .replace(/\r/g, '')
            .split('\n')
            .map((line: string) => line.replace(/\s+/g, ' ').trim())
            .filter((line: string) => !!line)
            .map((line: string) => line.length > 180 ? `${line.slice(0, 177)}...` : line);
    }

    public aiStreamRows() {
        const rows: any[] = [];
        let deltaSeen = false;
        const push = (row: any) => {
            const message = row?.message || row?.text || row?.provider?.label;
            if (!message && row?.type !== 'provider') return;
            const last = rows[rows.length - 1];
            if (last?.type === row?.type && (last?.message || last?.text) === message) return;
            rows.push(row);
        };
        for (const event of this.aiStreamEvents()) {
            if (event?.type === 'delta') {
                deltaSeen = true;
                continue;
            }
            if (event?.type === 'provider') {
                push(event);
                continue;
            }
            if (!['status', 'thinking', 'heartbeat', 'error'].includes(event?.type)) continue;
            for (const text of this.streamLines(event.message || event.text || '')) {
                push({ ...event, message: text, text });
            }
        }
        if (deltaSeen) push({ type: 'progress', label: '작성 중', message: 'AI가 템플릿 파일을 작성하고 있습니다.' });
        return rows.slice(-8);
    }

    private async streamTemplateAi(payload: any, onDone: (data: any) => Promise<void>) {
        const formData = new FormData();
        formData.append('payload', JSON.stringify(payload || {}));
        const response = await fetch('/wiz/api/page.templates/stream_template_ai', { method: 'POST', body: formData });
        if (!response.ok || !response.body) {
            throw new Error(`AI 스트림 요청 실패: HTTP ${response.status}`);
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let doneSeen = false;
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
                    doneSeen = true;
                    await onDone(event.data);
                }
            }
            await this.service.render();
        }
        if (!doneSeen) {
            throw new Error('AI 스트림이 완료 이벤트 없이 종료되었습니다.');
        }
    }

    private applyAiTemplateDraft(data: any) {
        const template = data?.template || {};
        const files = template.files || {};
        const metadata = template.metadata || {};
        const current = this.detail();
        const editingExisting = this.isEditingTemplate();
        const keepCurrent = editingExisting || (this.selectedId() && current?.namespace === template.namespace);
        if (!keepCurrent) {
            this.selectedId.set('');
            this.detail.set(null);
        }
        const nextTags = this.normalizeTags(template.tags || metadata.tags);
        const keepCurrentNamespace = editingExisting || (!editingExisting && !!String(this.form.namespace || '').trim());
        this.form = {
            namespace: keepCurrentNamespace ? this.form.namespace : (template.namespace || this.form.namespace),
            name: template.name || this.form.name,
            enabled: template.enabled !== false,
            tags: nextTags.length ? nextTags : this.form.tags,
        };
        this.files = {
            compose: files.compose || this.files.compose,
            values_default: files.values_default || this.files.values_default,
            values_schema: files.values_schema || this.files.values_schema,
            readme: files.readme || this.files.readme,
        };
        this.previewValues = { ...(template.values || this.previewValues || {}) };
        this.preview.set(null);
        this.aiResult = data;
        this.detailCache = {};
        if (!editingExisting) this.newTemplateDraftReady.set(true);
        this.setActiveTab('readme');
    }

    public async generateTemplateWithAi() {
        const intent = String(this.aiIntent() || '').trim();
        if (!intent) {
            await this.alert('AI 요청 내용을 입력해주세요.');
            return;
        }
        if (!this.hasAiModels()) {
            await this.alert(this.aiUnavailableMessage() || '시스템 설정에서 사용할 AI 모델을 먼저 켜주세요.');
            return;
        }
        this.aiBusy.set(true);
        this.resetAiStream();
        try {
            await this.streamTemplateAi({
                mode: this.isEditingTemplate() ? 'template_update' : 'template_create',
                intent,
                model_ref: this.aiModelRef() || this.aiDefaultModelRef() || 'auto',
                current_template: this.currentTemplateForAi(),
            }, async (data: any) => {
                this.applyAiTemplateDraft(data);
            });
            if (this.templateAiModalOpen()) this.templateAiModalOpen.set(false);
            await this.alert(this.aiResult?.summary || 'AI 템플릿 초안을 적용했습니다. 저장 전 내용을 검토하세요.', 'success');
        } catch (error: any) {
            await this.alert(error?.message || 'AI 템플릿 초안을 생성할 수 없습니다.');
        }
        this.aiBusy.set(false);
        await this.service.render();
    }

    private payload() {
        return {
            namespace: this.form.namespace,
            name: this.form.name,
            enabled: this.form.enabled,
            metadata: this.payloadMetadata(),
            files: this.files,
            created_at: this.detail()?.created_at,
        };
    }

    private payloadMetadata() {
        const metadata = { ...(this.detail()?.metadata || {}) };
        delete metadata.category;
        delete metadata.primary_image;
        return {
            ...metadata,
            tags: this.normalizeTags(this.form.tags),
        };
    }

    public async save() {
        if (!String(this.form.name || '').trim()) {
            await this.alert('템플릿 이름을 입력해주세요.');
            return;
        }
        if (!String(this.form.namespace || '').trim()) {
            await this.alert('템플릿 namespace를 입력해주세요.');
            return;
        }
        if (!String(this.files.readme || '').trim()) {
            await this.alert('README.md는 필수입니다.');
            return;
        }
        this.busy.set(true);
        const { code, data } = await wiz.call('save_template', this.payload());
        this.busy.set(false);
        if (code === 200) {
            await this.alert('템플릿을 저장했습니다.', 'success');
            await this.load(false);
            await this.selectTemplate(data.template?.id || data.template?.namespace || this.form.namespace, true, true);
            return;
        }
        await this.alert(data?.message || '템플릿을 저장할 수 없습니다.');
    }

    public async remove() {
        const id = this.selectedId();
        if (!id) return;
        const confirmed = await this.service.modal.show({
            title: '템플릿 삭제',
            message: '선택한 템플릿을 삭제합니다.',
            cancel: true,
            action: '삭제',
            actionBtn: 'error',
            status: 'error',
        });
        if (!confirmed) return;
        this.busy.set(true);
        const { code, data } = await wiz.call('delete_template', { template_id: id });
        this.busy.set(false);
        if (code === 200) {
            await this.alert('템플릿을 삭제했습니다.', 'success');
            await this.load();
        } else {
            await this.alert(data?.message || '템플릿을 삭제할 수 없습니다.');
        }
    }

    public async runPreview() {
        const id = this.selectedId() || this.form.namespace;
        if (!id) {
            await this.alert('먼저 템플릿을 저장해주세요.');
            return;
        }
        this.busy.set(true);
        const { code, data } = await wiz.call('preview_template', {
            template_id: id,
            name: this.form.name,
            values: this.previewValues,
        });
        this.busy.set(false);
        if (code === 200) {
            this.preview.set(data);
            this.setActiveTab('preview');
            await this.service.render();
        } else {
            await this.alert(data?.message || '미리보기를 만들 수 없습니다.');
        }
    }

    public setActiveTab(tab: TemplateTab) {
        this.activeTab.set(tab);
        this.activeEditorOptions = this.editorOptionsByTab[tab] || this.editorOptionsByTab.compose;
    }

    public addTagFromInput() {
        const tag = String(this.tagInput || '').trim();
        if (!tag) return;
        const tags = this.normalizeTags([...(this.form.tags || []), tag]);
        this.form = { ...this.form, tags };
        this.tagInput = '';
    }

    public removeTag(tag: string) {
        const target = String(tag || '').trim();
        this.form = {
            ...this.form,
            tags: this.normalizeTags(this.form.tags).filter((item: string) => item !== target),
        };
    }

    public handleTagKeydown(event: KeyboardEvent) {
        if (event.key === 'Enter' || event.key === ',') {
            event.preventDefault();
            this.addTagFromInput();
            return;
        }
        if (event.key === 'Backspace' && !this.tagInput && this.form.tags?.length) {
            this.removeTag(this.form.tags[this.form.tags.length - 1]);
        }
    }

    public editorValue() {
        if (this.activeTab() === 'compose') return this.files.compose;
        if (this.activeTab() === 'values') return this.files.values_default;
        if (this.activeTab() === 'schema') return this.files.values_schema;
        return this.files.readme;
    }

    public setEditorValue(value: string) {
        if (this.activeTab() === 'compose') this.files.compose = value;
        else if (this.activeTab() === 'values') this.files.values_default = value;
        else if (this.activeTab() === 'schema') this.files.values_schema = value;
        else this.files.readme = value;
    }

    public useTemplate() {
        const id = this.selectedId();
        if (!id) return;
        this.service.href(`/services/create?template_id=${encodeURIComponent(id)}`);
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
}
