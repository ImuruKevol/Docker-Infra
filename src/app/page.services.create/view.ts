import { OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

type StepId = 1 | 2 | 3 | 4;
type CreationMode = 'template' | 'ai' | 'manual';
type CreateCheckStatus = 'idle' | 'checking' | 'creating' | 'error' | 'success';

export class Component implements OnInit {
    public loading = signal<boolean>(true);
    public busy = signal<boolean>(false);
    public preflightLoading = signal<boolean>(false);
    public domainsLoading = signal<boolean>(false);
    public error = signal<string>('');
    public step = signal<StepId>(1);
    public creationMode = signal<CreationMode>('template');
    public advancedSettings = signal<boolean>(false);
    public manualComposeOpen = signal<boolean>(false);
    public importLoading = signal<boolean>(false);
    public manualBusy = signal<boolean>(false);
    public aiBusy = signal<boolean>(false);
    public templateBusy = signal<boolean>(false);
    public templateLoading = signal<boolean>(false);
    public createCheck = signal<any>({
        open: false,
        status: 'idle' as CreateCheckStatus,
        title: '',
        message: '',
        items: [],
    });
    public importSource = signal<any>(null);
    public importWarnings = signal<any[]>([]);
    public draftSource = signal<string>('');
    public templates = signal<any[]>([]);
    public selectedTemplateId = signal<string>('');
    public templateDetail = signal<any>(null);
    public readmeOpen = signal<boolean>(false);
    public secretVisibility = signal<any>({});
    public zones = signal<any[]>([]);
    public baseContent = '';
    public manualCompose = '';
    public manualComposeEditorOptions: any = {
        language: 'yaml',
        theme: 'vs',
        fontSize: 13,
        minimap: { enabled: false },
        automaticLayout: true,
        wordWrap: 'on',
        scrollBeyondLastLine: false,
        roundedSelection: false,
    };
    public generatedSecretKeys: string[] = [];
    public draftMetadata: any = {};
    public draftSourceRef: any = null;
    public templateValues: any = {};
    public imageChecks: any = {};
    public preflight = signal<any>(null);
    public form: any = {
        name: '',
        description: '',
        domain_mode: 'none',
        zone_id: '',
        domain_prefix: '',
        domain_target_key: '',
        domain_target_port: 80,
    };
    public components: any[] = [];
    public aiForm: any = { intent: '', model_ref: 'auto' };
    public aiResult: any = null;
    public aiModelOptions = signal<any[]>([]);
    public aiDefaultModelRef = signal<string>('auto');
    public aiAvailable = signal<boolean>(false);
    public aiUnavailableMessage = signal<string>('');
    public aiStreamEvents = signal<any[]>([]);
    public aiOutputTokenCount = signal<number>(0);
    public preflightSignature = '';
    public preflightReady = false;
    public preflightOk = false;
    private preflightErrorMessage = '';
    public createSessionId = `svc-create-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    public createdServiceId = '';
    private templateDetailRequestSeq = 0;
    private zonesLoaded = false;
    private zonesRequest: Promise<boolean> | null = null;
    private domainModeTouched = false;
    private aiModelOptionsLoaded = false;
    private aiModelOptionsRequest: Promise<boolean> | null = null;

    constructor(public service: Service) { }

    private serviceDetailRoute(serviceId: string) {
        const encodedId = this.service.encodeRouteSegment(serviceId);
        return encodedId ? `/services/${encodedId}` : '/services';
    }

    public async ngOnInit() {
        await this.service.init();
        this.syncManualComposeEditorTheme();
        await this.load();
        if (!this.error()) await this.ensureDomainOptions(true);
    }

    private hasOwn(value: any, key: string) {
        return Object.prototype.hasOwnProperty.call(value || {}, key);
    }

    public async load() {
        this.loading.set(true);
        this.error.set('');
        await this.service.render();
        const { code, data } = await wiz.call('load', {});
        if (code === 200) {
            if (this.hasOwn(data, 'zones')) {
                this.zones.set(data.zones || []);
                this.zonesLoaded = true;
            }
            const templates = data.templates || [];
            this.templates.set(templates);
            const templateFromQuery = this.templateIdFromQuery();
            this.selectedTemplateId.set(templateFromQuery || templates[0]?.id || templates[0]?.namespace || '');
            this.creationMode.set('template');
            this.baseContent = '';
            this.manualCompose = '';
            this.draftSource.set('');
            this.generatedSecretKeys = [];
            this.draftMetadata = {};
            this.draftSourceRef = null;
            this.components = [];
            this.ensureDomainTarget();
            this.templateDetail.set(null);
        } else {
            this.error.set(data?.message || '서비스 생성 정보를 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
        if (code === 200 && this.selectedTemplateId()) {
            this.loadTemplateDetail(this.selectedTemplateId(), true).catch(() => null);
        }
    }

    private applyComposeDraft(data: any, source: string) {
        const content = data?.content || data?.base_content || data?.rendered || data?.preview?.rendered_compose || '';
        if (content) {
            this.baseContent = content;
            this.manualCompose = content;
        }
        this.generatedSecretKeys = this.mergeGeneratedSecretKeys(
            this.generatedSecretKeys,
            data?.generated_secret_keys,
            data?.draft?.generated_secret_keys,
        );
        if (data?.values && source === 'compose_template') {
            this.templateValues = { ...this.templateValues, ...(data.values || {}) };
        }
        this.components = data?.components || data?.draft?.components || this.components || [];
        this.importWarnings.set(data?.warnings || []);
        this.draftSource.set(source || data?.source || 'manual_compose');
        this.draftMetadata = this.composeDraftMetadata(data, this.draftSource());
        this.draftSourceRef = data?.source_ref || null;
        if (!String(this.form.name || '').trim()) {
            this.form.name = data?.suggested_name || data?.draft?.form?.name || this.form.name;
        }
        if (!String(this.form.description || '').trim()) {
            this.form.description = data?.draft?.form?.description || data?.description || this.form.description;
        }
        this.imageChecks = {};
        this.invalidatePreflight();
        this.ensureDomainTarget();
        this.syncDomain();
    }

    private composeDraftMetadata(data: any, source: string) {
        const draft = data?.draft || {};
        return {
            source,
            summary: data?.summary || draft?.summary || null,
            warnings: data?.warnings || [],
            notes: draft?.notes || data?.notes || [],
            provider: data?.provider || null,
            template: data?.template || null,
            values: data?.values || null,
            intent: source === 'ai_draft' ? String(this.aiForm.intent || '').trim() : '',
            model_ref: source === 'ai_draft' ? (this.aiForm.model_ref || this.aiDefaultModelRef() || 'auto') : '',
        };
    }

    private templateIdFromQuery() {
        const params = new URLSearchParams(window.location.search || '');
        return String(params.get('template_id') || params.get('template') || '').trim();
    }

    public templateSelectorItems() {
        return this.templates().map((item: any) => ({
            value: item.id || item.namespace,
            label: item.name || item.namespace,
            description: item.description || item.metadata?.description || item.metadata?.summary || '',
            badge: this.templateBadge(item),
            badgeClass: 'border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-900/70 dark:bg-indigo-950/40 dark:text-indigo-300',
        }));
    }

    private normalizeTemplateTags(item: any) {
        const metadata = item?.metadata || {};
        const raw = Array.isArray(metadata.tags) ? metadata.tags : String(metadata.tags || metadata.category || '').split(',');
        const tags: string[] = [];
        for (const value of raw) {
            const tag = String(value || '').trim();
            if (tag && !tags.includes(tag)) tags.push(tag);
        }
        return tags;
    }

    public templateBadge(item: any) {
        return this.normalizeTemplateTags(item)[0] || 'compose';
    }

    public selectedTemplate() {
        const id = this.selectedTemplateId();
        return this.templates().find((item: any) => (item.id || item.namespace) === id) || null;
    }

    public templateFields() {
        const fields = this.templateDetail()?.fields || [];
        return fields.filter((field: any) => field.name !== 'namespace' && field.name !== 'service_name');
    }

    public isManagedTemplateField(field: any) {
        const name = String(field?.name || '').trim().toLowerCase();
        const title = String(field?.title || '').trim().toLowerCase();
        const wrapped = `_${name.replace(/[^a-z0-9]+/g, '_')}_`;
        if (wrapped.includes('_image_') || wrapped.includes('_image_ref_') || wrapped.includes('_image_name_') || wrapped.includes('_image_tag_')) return true;
        if (wrapped.includes('_port_') || wrapped.includes('_ports_') || wrapped.includes('_published_') || wrapped.includes('_published_port_') || wrapped.includes('_target_port_') || wrapped.includes('_host_port_')) return true;
        if (title.includes('이미지') || title.includes('image')) return true;
        if (title.includes('포트') || title.includes('port')) return true;
        return false;
    }

    public editableTemplateFields() {
        return this.templateFields().filter((field: any) => !this.isManagedTemplateField(field));
    }

    public managedTemplateFieldCount() {
        return this.templateFields().length - this.editableTemplateFields().length;
    }

    public visibleTemplateFields() {
        return this.editableTemplateFields().filter((field: any) => !field.secret);
    }

    public secretTemplateFields() {
        return this.editableTemplateFields().filter((field: any) => field.secret);
    }

    public selectedTemplateReadme() {
        return String(this.templateDetail()?.files?.readme || this.templateDetail()?.readme || '').trim();
    }

    public toggleTemplateReadme() {
        this.readmeOpen.set(!this.readmeOpen());
    }

    public closeTemplateReadme() {
        this.readmeOpen.set(false);
    }

    private initialTemplateValues(detail: any) {
        const values = { ...(detail?.values || {}) };
        const generated: string[] = [];
        for (const field of detail?.fields || []) {
            if (values[field.name] === undefined && field.default !== undefined) values[field.name] = field.default;
            if (field?.secret && this.shouldGenerateTemplateSecret(values[field.name])) {
                values[field.name] = this.generateTemplateSecret();
                generated.push(field.name);
            }
        }
        this.generatedSecretKeys = this.mergeGeneratedSecretKeys([], generated);
        this.secretVisibility.set(Object.fromEntries(generated.map((key: string) => [key, true])));
        return values;
    }

    private shouldGenerateTemplateSecret(value: any) {
        const clean = String(value || '').trim();
        if (!clean) return true;
        const lower = clean.toLowerCase();
        return ['change_me', 'changeme', 'password', 'secret'].includes(lower) || lower.endsWith('_change_me');
    }

    private generateTemplateSecret(length: number = 40) {
        const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789';
        const bytes = new Uint8Array(length);
        if (globalThis.crypto?.getRandomValues) {
            globalThis.crypto.getRandomValues(bytes);
        } else {
            for (let index = 0; index < bytes.length; index += 1) bytes[index] = Math.floor(Math.random() * 256);
        }
        return Array.from(bytes).map((value) => alphabet[value % alphabet.length]).join('');
    }

    private mergeGeneratedSecretKeys(...groups: any[]) {
        const result: string[] = [];
        for (const group of groups) {
            for (const key of group || []) {
                const clean = String(key || '').trim();
                if (clean && !result.includes(clean)) result.push(clean);
            }
        }
        return result;
    }

    public async selectTemplate(templateId: string) {
        this.selectedTemplateId.set(templateId || '');
        this.templateDetail.set(null);
        this.closeTemplateReadme();
        this.secretVisibility.set({});
        this.generatedSecretKeys = [];
        await this.loadTemplateDetail(templateId, true);
    }

    public async loadTemplateDetail(templateId: string = this.selectedTemplateId(), rerender: boolean = true) {
        templateId = String(templateId || '').trim();
        if (!templateId) return;
        const requestSeq = ++this.templateDetailRequestSeq;
        this.templateLoading.set(true);
        if (rerender) await this.service.render();
        try {
            const { code, data } = await wiz.call('template_detail', { template_id: templateId });
            if (requestSeq !== this.templateDetailRequestSeq || this.selectedTemplateId() !== templateId) return;
            if (code === 200) {
                const detail = data.template || null;
                this.templateDetail.set(detail);
                this.templateValues = this.initialTemplateValues(detail);
            } else {
                await this.alert(data?.message || '템플릿 정보를 불러올 수 없습니다.');
            }
        } catch (error: any) {
            if (requestSeq === this.templateDetailRequestSeq && this.selectedTemplateId() === templateId) {
                await this.alert(error?.message || '템플릿 정보를 불러올 수 없습니다.');
            }
        } finally {
            if (requestSeq === this.templateDetailRequestSeq) this.templateLoading.set(false);
        }
        if (rerender) await this.service.render();
    }

    public templateFieldInputType(field: any) {
        if (field?.secret) return this.secretFieldVisible(field) ? 'text' : 'password';
        if (field?.type === 'integer' || field?.type === 'number') return 'number';
        return 'text';
    }

    public templateFieldPlaceholder(field: any) {
        if (field?.secret) return '비워두면 자동 생성';
        return '';
    }

    public secretFieldVisible(field: any) {
        const key = String(field?.name || '');
        return !!this.secretVisibility()[key];
    }

    public toggleSecretField(field: any) {
        const key = String(field?.name || '');
        if (!key) return;
        this.secretVisibility.set({
            ...this.secretVisibility(),
            [key]: !this.secretFieldVisible(field),
        });
    }

    public secretFieldToggleLabel(field: any) {
        return this.secretFieldVisible(field) ? '비밀 값 숨기기' : '비밀 값 보기';
    }

    public secretFieldToggleIcon(field: any) {
        return this.secretFieldVisible(field) ? 'fa-eye-slash' : 'fa-eye';
    }

    public async applyTemplateDraft(options: any = {}) {
        const advance = options.advance === true;
        const showSuccess = options.showSuccess === true;
        const templateId = this.selectedTemplateId();
        if (!templateId) {
            await this.alert('사용할 템플릿을 선택해주세요.');
            return false;
        }
        if (!String(this.form.name || '').trim()) {
            await this.alert('서비스 이름을 입력해주세요.');
            return false;
        }
        this.templateBusy.set(true);
        const { code, data } = await wiz.call('prepare_template_draft', {
            template_id: templateId,
            name: this.form.name,
            values: this.templateValues,
        });
        if (code === 200) {
            this.importSource.set(null);
            this.applyComposeDraft(data, 'compose_template');
            if (advance) this.step.set(1);
            if (showSuccess) await this.alert('템플릿 구성을 적용했습니다.', 'success');
            this.templateBusy.set(false);
            await this.service.render();
            return true;
        } else {
            await this.alert(this.formatComposeError(data, '템플릿 초안을 적용할 수 없습니다.'));
        }
        this.templateBusy.set(false);
        await this.service.render();
        return false;
    }

    public async loadAiModelOptions() {
        try {
            const { code, data } = await wiz.call('ai_model_options', {});
            this.aiModelOptionsLoaded = true;
            if (code === 200) {
                const options = data.options || [];
                this.aiModelOptions.set(options);
                this.aiAvailable.set(options.length > 0);
                this.aiUnavailableMessage.set(options.length ? '' : (data.message || '시스템 설정에서 사용 중인 AI 모델이 없습니다.'));
                this.aiDefaultModelRef.set(data.default_model_ref || '');
                this.aiForm.model_ref = data.default_model_ref || '';
                this.normalizeCreationMode();
                await this.service.render();
                return options.length > 0;
            }
            this.aiModelOptions.set([]);
            this.aiAvailable.set(false);
            this.aiUnavailableMessage.set(data?.message || 'AI 모델 목록을 불러올 수 없습니다.');
            this.normalizeCreationMode();
            await this.service.render();
            return false;
        } catch (error: any) {
            this.aiModelOptionsLoaded = true;
            this.aiModelOptions.set([]);
            this.aiAvailable.set(false);
            this.aiUnavailableMessage.set(error?.message || 'AI 모델 목록을 불러올 수 없습니다.');
            this.normalizeCreationMode();
            await this.service.render();
            return false;
        }
    }

    private async ensureAiModelOptions(silent: boolean = false) {
        if (this.aiModelOptionsLoaded) return this.hasAiModels();
        if (this.aiModelOptionsRequest) return await this.aiModelOptionsRequest;
        this.aiModelOptionsRequest = this.loadAiModelOptions();
        try {
            return await this.aiModelOptionsRequest;
        } finally {
            this.aiModelOptionsRequest = null;
        }
    }

    private async loadDomainOptions(silent: boolean = false) {
        this.domainsLoading.set(true);
        try {
            const { code, data } = await wiz.call('domain_options', {});
            if (code === 200) {
                this.zones.set(data.zones || []);
                this.zonesLoaded = true;
                if (!this.domainModeTouched && this.zones().length > 0) {
                    this.form.domain_mode = 'registered';
                }
                if (this.form.domain_mode === 'registered' && !this.form.zone_id && this.zones()[0]) {
                    this.form.zone_id = this.zones()[0].id;
                }
                this.syncDomain();
                return true;
            }
            if (!silent) await this.alert(data?.message || '도메인 목록을 불러올 수 없습니다.');
            return false;
        } catch (error: any) {
            if (!silent) await this.alert(error?.message || '도메인 목록을 불러올 수 없습니다.');
            return false;
        } finally {
            this.domainsLoading.set(false);
            await this.service.render();
        }
    }

    private async ensureDomainOptions(silent: boolean = false) {
        if (this.zonesLoaded) return true;
        if (this.zonesRequest) return await this.zonesRequest;
        this.zonesRequest = this.loadDomainOptions(silent);
        try {
            return await this.zonesRequest;
        } finally {
            this.zonesRequest = null;
        }
    }

    public hasAiModels() {
        return this.aiAvailable() && this.aiModelOptions().length > 0;
    }

    private importQuery() {
        const params = new URLSearchParams(window.location.search || '');
        const nodeId = String(params.get('import_node_id') || '').trim();
        const path = String(params.get('import_path') || '').trim();
        if (!nodeId || !path) return null;
        return {
            node_id: nodeId,
            path,
            suggested_name: String(params.get('import_name') || '').trim(),
        };
    }

    public async loadImportFromQuery() {
        const query = this.importQuery();
        if (!query) return;
        this.importLoading.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('load_import', query);
        if (code === 200) {
            this.importSource.set(data.source_ref || null);
            this.applyComposeDraft(data, 'server_compose_import');
            this.creationMode.set('manual');
            this.manualComposeOpen.set(true);
            this.form.name = data.suggested_name || query.suggested_name || this.form.name;
            this.form.description = this.form.description || '서버에 있던 Compose 파일을 가져와 생성합니다.';
        } else {
            await this.alert(this.formatComposeError(data, 'Compose 파일을 서비스 생성 화면으로 가져올 수 없습니다.'));
        }
        this.importLoading.set(false);
        await this.service.render();
    }

    public steps() {
        return [
            { id: 1, title: '서비스 생성', description: '템플릿과 도메인 설정' },
        ];
    }

    public creationModeCards() {
        return [
            {
                id: 'template',
                icon: 'fa-layer-group',
                title: '템플릿 기반',
                description: this.templates().length ? '표준 Compose 템플릿에 필요한 변수만 입력합니다.' : '등록된 템플릿이 없습니다.',
                badge: this.templates().length ? `${this.templates().length}개` : '',
                disabled: !this.templates().length,
            },
        ];
    }

    public creationModeCardClass(mode: any) {
        const active = this.creationMode() === mode.id;
        if (!active) {
            return 'border-zinc-200 bg-white text-zinc-800 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-200 dark:hover:bg-zinc-800';
        }
        if (mode.id === 'template') {
            return 'border-indigo-200 bg-indigo-50 text-indigo-950 dark:border-indigo-900/70 dark:bg-indigo-950/30 dark:text-indigo-100';
        }
        if (mode.id === 'ai') {
            return 'border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-900/70 dark:bg-sky-950/30 dark:text-sky-100';
        }
        return 'border-zinc-300 bg-zinc-100 text-zinc-950 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100';
    }

    public creationModeIconClass(mode: any) {
        const active = this.creationMode() === mode.id;
        if (!active) {
            return 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-300';
        }
        if (mode.id === 'template') {
            return 'bg-indigo-600 text-white dark:bg-indigo-400 dark:text-indigo-950';
        }
        if (mode.id === 'ai') {
            return 'bg-sky-600 text-white dark:bg-sky-400 dark:text-sky-950';
        }
        return 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-950';
    }

    public creationModeBadgeClass(mode: any) {
        const active = this.creationMode() === mode.id;
        if (!active) {
            return 'border-zinc-200 bg-white text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300';
        }
        if (mode.id === 'template') {
            return 'border-indigo-200 bg-white text-indigo-700 dark:border-indigo-800 dark:bg-indigo-950 dark:text-indigo-200';
        }
        if (mode.id === 'ai') {
            return 'border-sky-200 bg-white text-sky-700 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-200';
        }
        return 'border-zinc-300 bg-white text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200';
    }

    public serviceNamePlaceholder() {
        return '예: wiz-dev';
    }

    public createBusy() {
        return this.busy() || this.templateBusy() || this.preflightLoading();
    }

    public createButtonLabel() {
        return this.createBusy() ? '생성 중' : '생성';
    }

    public createButtonIconClass() {
        return this.createBusy() ? 'fa-spinner fa-spin' : 'fa-plus';
    }

    private normalizeCreationMode() {
        this.creationMode.set('template');
        this.manualComposeOpen.set(false);
    }

    public async selectCreationMode(mode: string) {
        const nextMode = mode as CreationMode;
        if (nextMode !== 'template') {
            await this.alert('템플릿 기반 생성만 사용할 수 있습니다.');
            return;
        }
        if (nextMode === 'template' && !this.templates().length) {
            await this.alert('사용할 수 있는 템플릿이 없습니다.');
            return;
        }
        this.creationMode.set(nextMode);
        await this.service.render();
    }

    public zoneSelectorItems() {
        return this.zones().map((zone: any) => {
            return {
                value: zone.id,
                label: zone.domain,
                description: 'DDNS 관리 서버로 DNS 레코드를 등록합니다.',
                badge: 'DDNS',
                badgeClass: 'border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-900/70 dark:bg-violet-950/40 dark:text-violet-300',
            };
        });
    }

    public selectedZone() {
        return this.zones().find((zone: any) => zone.id === this.form.zone_id) || null;
    }

    public serviceAiInputRows() {
        return [
            { key: 'intent', value: '배포 요구사항' },
            { key: 'model', value: 'AI 설정에서 사용 가능한 모델' },
            { key: 'form', value: '서비스 이름, 설명, 도메인' },
            { key: 'components', value: '이미지, 포트, 환경변수, 볼륨' },
            { key: 'base_content', value: '현재 Compose 초안' },
        ];
    }

    public serviceAiOutputRows() {
        return [
            { key: 'form', value: '서비스 기본 정보와 도메인 대상' },
            { key: 'components', value: '컴포넌트별 실행 설정' },
            { key: 'warnings', value: '지원 불가 또는 확인 필요 항목' },
        ];
    }

    private aiAutomationRows() {
        return [
            { icon: 'fa-layer-group', title: '서비스 구성', description: '이미지, 포트, 환경변수, 데이터 보관' },
            { icon: 'fa-globe', title: '도메인 연결', description: 'DDNS suffix, 공개 포트, nginx 연결' },
            { icon: 'fa-rotate-right', title: '자동 보정', description: '검증 실패 시 AI 재호출 후 다시 검사' },
        ];
    }

    public aiExamples() {
        return [
            {
                title: '위키',
                prompt: '내부용 Wiki 서비스를 만들고 싶습니다. PostgreSQL을 같이 사용하고, wiki 화면만 도메인으로 공개하며 데이터는 유지해주세요. 관리자 비밀번호는 자동 생성해주세요.',
            },
            {
                title: '업무 도구',
                prompt: '사내에서 쓰는 간단한 업무 관리 도구를 만들고 싶습니다. 웹 화면은 도메인으로 접속하고, 데이터베이스와 업로드 파일은 재배포해도 유지되게 해주세요.',
            },
            {
                title: '정적 사이트',
                prompt: '회사 소개용 정적 웹사이트를 nginx로 배포하고 싶습니다. 도메인 연결이 필요하고, 나중에 파일만 교체해서 운영할 수 있으면 좋겠습니다.',
            },
        ];
    }

    public async useAiExample(prompt: string) {
        this.aiForm.intent = prompt;
        await this.service.render();
    }

    public async setAiModel(modelRef: string) {
        this.aiForm.model_ref = modelRef || 'auto';
        await this.service.render();
    }

    public async toggleManualCompose() {
        this.manualComposeOpen.set(!this.manualComposeOpen());
        if (this.manualComposeOpen()) this.syncManualComposeEditorTheme();
        await this.service.render();
    }

    private syncManualComposeEditorTheme() {
        const dark = document.documentElement.classList.contains('dark');
        this.manualComposeEditorOptions = {
            ...this.manualComposeEditorOptions,
            theme: dark ? 'vs-dark' : 'vs',
        };
    }

    private aiIntentText() {
        const intent = String(this.aiForm.intent || '').trim();
        if (intent) return intent;
        const rows = [
            String(this.form.name || '').trim(),
            String(this.form.description || '').trim(),
        ].filter((item) => !!item);
        return rows.join('\n');
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
        if (text.includes('"docker-compose.yaml"') || text.includes('"compose"') || text.includes('"base_content"')) stage = 'Compose 작성 중';
        else if (text.includes('"components"')) stage = '컴포넌트 설정 작성 중';
        else if (text.includes('"form"')) stage = '서비스 기본 정보 작성 중';
        else if (text.includes('"notes"')) stage = '운영 메모 작성 중';
        const latest = this.latestStreamLine(text);
        return latest ? `${stage} · ${latest}` : stage;
    }

    private providerStreamMessage(provider: any) {
        const label = String(provider?.label || provider?.type || 'AI').trim();
        const model = String(provider?.model || '').trim();
        const cliLabel = String(provider?.cli_label || '').trim();
        const modelLabel = model ? `${label} / ${model}` : label;
        return [modelLabel, cliLabel].filter((item) => !!item).join(' · ');
    }

    private heartbeatStreamMessage(event: any) {
        if (event?.message) return String(event.message);
        const elapsed = Number(event?.elapsed_seconds || 0);
        if (elapsed > 0) return `Codex CLI가 선택한 모델 응답을 기다리는 중입니다. (${elapsed}초 경과)`;
        return 'Codex CLI가 선택한 모델 응답을 기다리는 중입니다.';
    }

    private compactAiStreamRows(events: any[]) {
        const rows: any[] = [];
        let thinkingBuffer = '';
        let deltaBuffer = '';
        let progressIndex = -1;
        let heartbeatIndex = -1;
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
        const upsertHeartbeat = (event: any) => {
            const row = {
                ...event,
                type: 'heartbeat',
                label: event?.label || '대기 중',
                message: this.heartbeatStreamMessage(event),
            };
            if (heartbeatIndex >= 0) rows[heartbeatIndex] = row;
            else {
                heartbeatIndex = rows.length;
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
            if (!['provider', 'status', 'thinking', 'error', 'delta', 'heartbeat'].includes(event?.type)) continue;
            if (event.type === 'delta') {
                deltaBuffer += String(event.text || '');
                upsertProgress();
                continue;
            }
            if (event.type === 'heartbeat') {
                flushThinking(true);
                upsertHeartbeat(event);
                continue;
            }
            if (event.type === 'thinking') {
                thinkingBuffer += String(event.text || event.message || '');
                flushThinking(false);
                continue;
            }
            flushThinking(true);
            if (event.type === 'provider') {
                pushRow({ ...event, message: this.providerStreamMessage(event.provider) });
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
        const response = await fetch(`/wiz/api/page.services.create/${functionName}`, { method: 'POST', body: formData });
        if (!response.ok || !response.body) {
            throw new Error(`AI 스트림 요청 실패: HTTP ${response.status}`);
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let completed = false;
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
                    completed = true;
                    await onDone(event.data);
                }
            }
            await this.service.render();
        }
        if (!completed) {
            throw new Error('AI 응답이 완료되기 전에 종료되었습니다.');
        }
    }

    public async applyManualCompose(options: any = {}) {
        const advance = options.advance !== false;
        const showSuccess = options.showSuccess !== false;
        const content = String(this.manualCompose || '').trim();
        if (!content) {
            await this.alert('Compose 내용을 입력해주세요.');
            return false;
        }
        this.manualBusy.set(true);
        const { code, data } = await wiz.call('prepare_compose_draft', {
            content,
            name: this.form.name,
            suggested_name: this.form.name,
        });
        if (code === 200) {
            this.importSource.set(null);
            this.applyComposeDraft(data, 'manual_compose');
            this.manualComposeOpen.set(false);
            if (advance) this.step.set(2);
            if (showSuccess) await this.alert('Compose 초안을 적용했습니다. 다음 단계에서 구성을 확인하세요.', 'success');
            this.manualBusy.set(false);
            await this.service.render();
            return true;
        } else {
            await this.alert(this.formatComposeError(data, 'Compose 초안을 적용할 수 없습니다.'));
        }
        this.manualBusy.set(false);
        await this.service.render();
        return false;
    }

    private applyAiServiceDraft(data: any) {
        const draft = data?.draft || {};
        if (draft?.form) {
            this.form = {
                ...this.form,
                ...draft.form,
            };
        }
        if (draft?.base_content || data?.rendered) {
            this.baseContent = data?.rendered || draft.base_content;
            this.manualCompose = this.baseContent;
        }
        if (Array.isArray(draft?.components) && draft.components.length) {
            this.components = draft.components;
        }
        this.generatedSecretKeys = draft?.generated_secret_keys || data?.generated_secret_keys || this.generatedSecretKeys;
        this.importSource.set(null);
        this.importWarnings.set(data?.warnings || []);
        this.draftSource.set('ai_draft');
        this.draftSourceRef = data?.source_ref || null;
        this.draftMetadata = this.composeDraftMetadata(data, 'ai_draft');
        this.ensureDomainTarget();
        this.syncDomain();
        this.invalidatePreflight();
    }

    private invalidatePreflight() {
        this.preflight.set(null);
        this.preflightSignature = '';
        this.preflightReady = false;
        this.preflightOk = false;
    }

    public async generateServiceWithAi(options: any = {}) {
        const advance = options.advance !== false;
        const showSuccess = options.showSuccess !== false;
        await this.ensureAiModelOptions();
        if (!this.hasAiModels()) {
            this.manualComposeOpen.set(true);
            await this.alert(this.aiUnavailableMessage() || '시스템 설정에서 사용할 AI 모델을 먼저 켜주세요.');
            await this.service.render();
            return false;
        }
        const intent = this.aiIntentText();
        if (!intent) {
            await this.alert('만들고 싶은 서비스를 한 줄 이상 입력해주세요.');
            return false;
        }
        await this.ensureDomainOptions(true);
        this.aiBusy.set(true);
        this.resetAiStream();
        try {
            await this.streamAi('stream_service_ai', {
                mode: 'service_create',
                intent,
                model_ref: this.aiForm.model_ref || this.aiDefaultModelRef() || 'auto',
                form: this.form,
                components: this.components,
                base_content: this.baseContent,
                zones: this.zones(),
                service: {},
                user_level: 'beginner',
                creation_mode: 'ai_first',
                docker_infra_inputs: this.serviceAiInputRows(),
                docker_infra_outputs: this.serviceAiOutputRows(),
                automation_scope: this.aiAutomationRows().map((row: any) => ({
                    title: row.title,
                    description: row.description,
                })),
            }, async (data: any) => {
                this.aiResult = data;
                this.applyAiServiceDraft(data);
            });
            if (advance) this.step.set(2);
            if (showSuccess) await this.alert(this.aiResult?.summary || 'AI 서비스 구성을 적용했습니다. 다음 단계에서 검토하세요.', 'success');
            this.aiBusy.set(false);
            await this.service.render();
            return true;
        } catch (error: any) {
            await this.alert(error?.message || 'AI 서비스 구성을 생성할 수 없습니다.');
        }
        this.aiBusy.set(false);
        await this.service.render();
        return false;
    }

    public async setStep(step: StepId) {
        if (step <= this.step()) {
            this.step.set(step);
            return;
        }
        for (let index = 1; index < step; index += 1) {
            if (!(await this.validateStep(index as StepId))) {
                this.step.set(index as StepId);
                await this.service.render();
                return;
            }
        }
        if (step === 3) await this.ensureDomainOptions(true);
        this.step.set(step);
        if (step === 4) await this.runPreflight(false);
        await this.service.render();
    }

    public nextStepLabel() {
        return this.templateBusy() ? '적용 중' : '생성';
    }

    public nextStepBusy() {
        return this.busy() || this.templateBusy() || this.templateLoading() || this.preflightLoading();
    }

    public nextStepIconClass() {
        return this.nextStepBusy() ? 'fa-spinner fa-spin' : 'fa-plus';
    }

    public async nextStep() {
        if (this.nextStepBusy()) return;
        await this.save(true);
    }

    public previousStep() {
        this.step.set(Math.max(1, this.step() - 1) as StepId);
    }

    public async validateStep(step: StepId = this.step()) {
        if (step === 1 && !this.selectedTemplateId()) {
            await this.alert('사용할 템플릿을 선택해주세요.');
            return false;
        }
        if (step === 1 && !String(this.form.name || '').trim()) {
            await this.alert('서비스 이름을 입력해주세요.');
            return false;
        }
        if (step === 1 && !this.baseContent.trim()) {
            await this.alert('템플릿 구성을 먼저 적용해주세요.');
            return false;
        }
        if (step === 1 || step === 2) {
            if (!this.components.length) {
                await this.alert('서비스 구성을 불러오지 못했습니다. 템플릿을 다시 확인해주세요.');
                return false;
            }
            for (const item of this.components) {
                if (!String(item.image_name || '').trim()) {
                    await this.alert('모든 구성의 이미지 이름을 입력해주세요.');
                    return false;
                }
            }
        }
        if ((step === 1 || step === 3) && this.form.domain_mode === 'registered') {
            if (!(await this.ensureDomainOptions())) return false;
            this.syncDomain();
            if (!this.hasConnectablePorts()) {
                await this.alert('선택한 템플릿에 도메인으로 연결할 포트가 없습니다.');
                return false;
            }
            if (!this.form.zone_id || !this.form.domain) {
                await this.alert('사용할 DDNS suffix를 선택해주세요.');
                return false;
            }
        }
        return true;
    }

    public imageRef(item: any) {
        const tag = String(item.image_tag || 'latest').trim();
        return tag.startsWith('sha256:') ? `${item.image_name}@${tag}` : `${item.image_name}:${tag}`;
    }

    public ports(item: any) {
        return (item.ports || []).filter((port: any) => Number(port.target || 0) > 0);
    }

    public connectablePortCount() {
        return this.components.reduce((total: number, item: any) => total + this.ports(item).length, 0);
    }

    public hasConnectablePorts() {
        return this.connectablePortCount() > 0;
    }

    public async addPort(item: any) {
        item.ports = item.ports || [];
        item.ports.push({ target: 80, protocol: 'tcp' });
        this.ensureDomainTarget();
        await this.service.render();
    }

    public async removePort(item: any, index: number) {
        item.ports.splice(index, 1);
        this.ensureDomainTarget();
        await this.service.render();
    }

    public addEnv(item: any) {
        item.env_vars = item.env_vars || [];
        item.env_vars.push({ key: '', value: '' });
    }

    public removeEnv(item: any, index: number) {
        item.env_vars.splice(index, 1);
    }

    public addVolume(item: any) {
        item.volumes = item.volumes || [];
        item.volumes.push({ source: `${item.key}_data`, target: '/data' });
    }

    public removeVolume(item: any, index: number) {
        item.volumes.splice(index, 1);
    }

    public domainTargetOptions() {
        const options: any[] = [];
        for (const item of this.components) {
            for (const port of this.ports(item)) {
                const serviceLabel = item.label || item.key;
                const protocol = port.protocol || 'tcp';
                options.push({
                    key: `${item.key}:${port.target}`,
                    label: `${serviceLabel} · ${port.target}/${protocol}`,
                    service_label: serviceLabel,
                    service_key: item.key,
                    port: port.target,
                    protocol,
                    recommended: !!port.public_endpoint,
                });
            }
        }
        return options.sort((a: any, b: any) => Number(!!b.recommended) - Number(!!a.recommended));
    }

    public selectedDomainTargetLabel() {
        const option = this.domainTargetOptions().find((item: any) => item.key === this.form.domain_target_key);
        if (!option) return this.form.domain_mode === 'registered' ? '포트 확인 필요' : '-';
        return `${option.service_label || option.label} · ${option.port}/${option.protocol || 'tcp'}`;
    }

    public ensureDomainTarget() {
        const first = this.domainTargetOptions()[0];
        const current = this.domainTargetOptions().find((item: any) => item.key === this.form.domain_target_key);
        if (!first) {
            this.form.domain_target_key = '';
            this.form.domain_target_port = 0;
            return;
        }
        if ((!this.form.domain_target_key || !current) && first) {
            this.form.domain_target_key = first.key;
            this.form.domain_target_port = first.port;
        }
    }

    public selectDomainTarget(key: string) {
        const option = this.domainTargetOptions().find((item: any) => item.key === key);
        this.form.domain_target_key = key;
        this.form.domain_target_port = option?.port || 80;
    }

    public async setDomainMode(mode: 'none' | 'registered') {
        this.domainModeTouched = true;
        if (mode === 'registered' && !(await this.ensureDomainOptions(true))) return;
        if (mode === 'registered' && this.zones().length === 0) {
            this.form.domain_mode = 'none';
            this.syncDomain();
            await this.service.render();
            return;
        }
        this.form.domain_mode = mode;
        if (mode === 'registered' && !this.form.zone_id && this.zones()[0]) {
            this.form.zone_id = this.zones()[0].id;
        }
        this.syncDomain();
        await this.service.render();
    }

    public selectZone(zoneId: string) {
        this.form.zone_id = zoneId || '';
        this.syncDomain();
    }

    private isDdnsZone(zone: any) {
        return zone?.provider === 'ddns' || zone?.ddns === true;
    }

    private domainPrefixForZone(zone: any, prefix: any, fallback: any) {
        const cleaned = String(prefix || '').trim().replace(/^\.+|\.+$/g, '');
        if (cleaned || !this.isDdnsZone(zone)) return cleaned;
        const value = String(fallback || 'service').toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/-+/g, '-').replace(/^-+|-+$/g, '');
        return (value.replace(/-(service|app)$/g, '') || value || 'service').slice(0, 50);
    }

    public syncDomain() {
        if (this.form.domain_mode !== 'registered') {
            this.form.domain = '';
            return;
        }
        const zone = this.selectedZone();
        if (!zone?.domain) return;
        const prefix = this.domainPrefixForZone(zone, this.form.domain_prefix, this.form.name);
        if (this.isDdnsZone(zone) && !String(this.form.domain_prefix || '').trim()) {
            this.form.domain_prefix = prefix;
        }
        this.form.domain = prefix ? `${prefix}.${zone.domain}` : zone.domain;
    }

    public domainPreview() {
        if (this.form.domain_mode !== 'registered') return '도메인 사용 안 함';
        const zone = this.selectedZone();
        const prefix = this.domainPrefixForZone(zone, this.form.domain_prefix, this.form.name);
        return zone?.domain ? (prefix ? `${prefix}.${zone.domain}` : zone.domain) : '도메인 선택 필요';
    }

    public async checkImage(item: any) {
        const ref = this.imageRef(item);
        this.imageChecks[ref] = { loading: true };
        await this.service.render();
        const { code, data } = await wiz.call('check_image', { image_ref: ref });
        this.imageChecks[ref] = code === 200 ? data : { exists: false, message: data?.message || '이미지를 확인할 수 없습니다.' };
        await this.service.render();
    }

    public imageCheck(item: any) {
        return this.imageChecks[this.imageRef(item)] || null;
    }

    public payload() {
        this.syncDomain();
        this.ensureDomainTarget();
        const source = this.importSource() ? 'server_compose_import' : (this.draftSource() || 'manual_compose');
        const draftMetadata = { ...(this.draftMetadata || {}), create_session_id: this.createSessionId };
        const sourceRef = this.importSource()
            ? { ...this.importSource(), create_session_id: this.createSessionId }
            : { ...(this.draftSourceRef || { source, wizard: 'services.create' }), source, create_session_id: this.createSessionId };
        return {
            ...this.form,
            base_content: this.baseContent,
            generated_secret_keys: this.generatedSecretKeys,
            draft_metadata: draftMetadata,
            components: this.components,
            create_session_id: this.createSessionId,
            source,
            import_source: this.importSource(),
            source_ref: sourceRef,
        };
    }

    public importSourcePath() {
        return this.importSource()?.path || '';
    }

    public importWarningCount() {
        return this.importWarnings().length;
    }

    public preflightItems() {
        return this.preflight()?.items || [];
    }

    public preflightSummaryText() {
        const summary = this.preflight()?.summary;
        if (!summary) return '아직 자동 점검을 실행하지 않았습니다.';
        if (summary.blocking > 0) return `${summary.blocking}개 항목을 수정해야 합니다.`;
        if (summary.warnings > 0) return `${summary.warnings}개 항목은 자동 조정 또는 배포 중 확인됩니다.`;
        return '저장과 배포에 필요한 기본 점검을 통과했습니다.';
    }

    public preflightStatusLabel(status: string) {
        const labels: any = {
            ok: '통과',
            warning: '확인',
            adjusted: '자동 조정',
            error: '수정 필요',
            info: '정보',
        };
        return labels[status] || status || '-';
    }

    public preflightStatusClass(status: string) {
        if (status === 'ok') return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300';
        if (status === 'adjusted') return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        if (status === 'warning') return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        if (status === 'error') return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }

    public preflightActionText(item: any) {
        const key = String(item?.key || '');
        if (key.includes('image')) return '조치: 이미지 이름과 버전을 확인하거나, 먼저 해당 이미지를 서버 또는 공개 저장소에 준비해주세요.';
        if (key.includes('ports')) return '조치: Docker Infra가 가능한 포트를 자동 조정합니다. 계속 문제가 나면 해당 서버에서 사용 중인 포트를 정리해주세요.';
        if (key.includes('domain')) return '조치: 도메인 관리에서 도메인과 인증서 상태를 확인하거나 도메인을 사용하지 않도록 선택해주세요.';
        if (key.includes('volume')) return '조치: 데이터 보관 경로는 /로 시작하는 컨테이너 내부 경로를 사용해주세요.';
        if (key.includes('namespace')) return '조치: 서비스 이름을 조금 다르게 입력한 뒤 다시 저장해주세요.';
        if (key.includes('placement')) return '조치: 서버 관리에서 실행 서버의 Docker와 SSH 상태를 먼저 확인해주세요.';
        if (key.includes('nginx')) return '조치: nginx 설치와 설정 경로는 Ubuntu 24.04 기본값으로 자동 확인됩니다. 설치 상태를 확인해주세요.';
        return '조치: 표시된 항목을 수정한 뒤 다시 점검해주세요.';
    }

    private validationDetails(details: any[] = []) {
        return (details || [])
            .filter((detail: any) => detail)
            .map((detail: any) => {
                if (typeof detail === 'string') return detail;
                const message = detail.message || detail.reason || detail.error_code || '검사에 실패했습니다.';
                return detail.path ? `- ${detail.path}: ${message}` : `- ${message}`;
            });
    }

    private formatComposeError(data: any, fallback: string) {
        const base = data?.error_code === 'COMPOSE_VALIDATION_FAILED'
            ? 'Compose 검사를 통과하지 못했습니다.'
            : (data?.message || fallback);
        const detailRows = Array.isArray(data?.details) ? data.details : [];
        const details = this.validationDetails([data?.reason, ...detailRows])
            .filter((detail: string, index: number, rows: string[]) => detail !== base && rows.indexOf(detail) === index);
        if (!details.length) return base;
        return `${base}\n\n${details.join('\n')}`;
    }

    private formatPreflightError(data: any) {
        const preflight = data?.preflight || data?.result?.preflight;
        const blocking = preflight?.blocking || [];
        if (blocking.length) {
            return [
                '서비스를 만들기 전에 아래 항목을 수정해야 합니다.',
                ...blocking.map((item: any) => `- 원인: ${item.title} - ${item.message}\n  ${this.preflightActionText(item)}`),
            ].join('\n');
        }
        return this.formatComposeError(data, data?.message || '자동 점검을 통과하지 못했습니다.');
    }

    private currentPreflightPayload() {
        const payload = this.payload();
        return { payload, signature: JSON.stringify(payload) };
    }

    private async updateCreateCheck(update: any) {
        this.createCheck.set({
            ...this.createCheck(),
            ...update,
            open: update.open === undefined ? this.createCheck().open : update.open,
        });
        await this.service.render();
    }

    public createCheckItems() {
        return this.createCheck()?.items || [];
    }

    public createCheckStatusClass(status: CreateCheckStatus) {
        if (status === 'success') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300';
        if (status === 'error') return 'bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300';
        return 'bg-sky-100 text-sky-700 dark:bg-sky-950/50 dark:text-sky-300';
    }

    public createCheckIconClass(status: CreateCheckStatus) {
        if (status === 'checking' || status === 'creating') return 'fa-spinner fa-spin';
        if (status === 'success') return 'fa-circle-check';
        if (status === 'error') return 'fa-triangle-exclamation';
        return 'fa-circle-info';
    }

    public createCheckActionLabel() {
        return this.createCheck().status === 'error' ? '돌아가기' : '확인';
    }

    public async closeCreateCheck() {
        const status = this.createCheck().status as CreateCheckStatus;
        if (status === 'checking' || status === 'creating') return;
        this.createCheck.set({ ...this.createCheck(), open: false });
        await this.service.render();
    }

    public async runPreflight(showMessage: boolean = false, force: boolean = false) {
        const { payload, signature } = this.currentPreflightPayload();
        if (!force && this.preflightReady && this.preflightSignature === signature) {
            if (!this.preflightOk && showMessage) {
                await this.alert(this.formatPreflightError({ preflight: this.preflight() }));
            }
            return this.preflightOk;
        }
        this.preflightLoading.set(true);
        this.preflight.set(null);
        this.preflightReady = false;
        this.preflightOk = false;
        this.preflightErrorMessage = '';
        const { code, data } = await wiz.call('preflight', payload);
        this.preflightLoading.set(false);
        if (code === 200) {
            const preflight = data.preflight || null;
            this.preflight.set(preflight);
            this.preflightSignature = signature;
            this.preflightReady = true;
            this.preflightOk = !!preflight?.ok;
            this.preflightErrorMessage = preflight?.ok ? '' : this.formatPreflightError(data);
            await this.service.render();
            if (!preflight?.ok && showMessage) {
                await this.alert(this.formatPreflightError(data));
            }
            return !!preflight?.ok;
        }
        this.preflightSignature = signature;
        this.preflightReady = true;
        this.preflightOk = false;
        this.preflightErrorMessage = this.formatPreflightError(data);
        if (showMessage) await this.alert(this.formatPreflightError(data));
        await this.service.render();
        return false;
    }

    public async save(deploy: boolean = true) {
        if (this.busy() || this.templateBusy() || this.preflightLoading()) return;
        if (this.createdServiceId) {
            this.service.href(this.serviceDetailRoute(this.createdServiceId));
            return;
        }
        if (!(await this.applyTemplateDraft({ advance: false, showSuccess: false }))) return;
        if (!(await this.validateStep(1))) return;

        this.busy.set(true);
        await this.updateCreateCheck({
            open: true,
            status: 'checking' as CreateCheckStatus,
            title: '생성 전 확인',
            message: '템플릿 구성, 이미지, 포트, 도메인 설정을 확인하는 중입니다.',
            items: [],
        });

        if (!(await this.runPreflight(false, true))) {
            this.busy.set(false);
            await this.updateCreateCheck({
                status: 'error' as CreateCheckStatus,
                title: '생성 전 확인 필요',
                message: this.preflightErrorMessage || this.formatPreflightError({ preflight: this.preflight() }),
                items: this.preflightItems(),
            });
            return;
        }

        await this.updateCreateCheck({
            status: 'creating' as CreateCheckStatus,
            title: '서비스 생성 중',
            message: '자동 확인을 통과했습니다. 서비스를 생성하고 있습니다.',
            items: this.preflightItems(),
        });
        const { code, data } = await wiz.call('create_service', this.payload());
        if (code !== 200) {
            this.busy.set(false);
            await this.updateCreateCheck({
                status: 'error' as CreateCheckStatus,
                title: '서비스 생성 실패',
                message: this.formatPreflightError(data),
                items: [],
            });
            return;
        }
        const serviceId = data.result?.service?.id;
        if (serviceId) this.createdServiceId = serviceId;
        let deployStartMessage = '서비스가 생성되었습니다. 상세 화면으로 이동합니다.';
        if (deploy !== false && serviceId) {
            const deployResult = await wiz.call('deploy_service_background', { service_id: serviceId });
            if ([200, 202].includes(deployResult.code)) {
                deployStartMessage = '서비스가 생성되었고 서버 배포가 시작되었습니다. 상세 화면에서 이미지 pull과 컨테이너 상태를 확인합니다.';
            } else {
                deployStartMessage = `서비스는 생성되었지만 배포를 시작하지 못했습니다. 상세 화면에서 다시 적용해주세요.\n\n${deployResult.data?.message || '배포 시작 실패'}`;
            }
        }
        await this.updateCreateCheck({
            status: 'success' as CreateCheckStatus,
            title: '서비스 생성 완료',
            message: deployStartMessage,
            items: this.preflightItems(),
        });
        await this.service.sleep(450);
        this.createCheck.set({ ...this.createCheck(), open: false });
        this.busy.set(false);
        this.service.href(serviceId ? this.serviceDetailRoute(serviceId) : '/services');
    }

    public cancel() {
        this.service.href('/services');
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
