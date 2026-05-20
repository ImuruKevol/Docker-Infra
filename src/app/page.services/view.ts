import { OnDestroy, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

type EditSection = 'basic' | 'components' | 'domain' | 'advanced' | 'ai';
type DetailTab = 'overview' | 'logs' | 'source' | 'files' | 'versions';

export class Component implements OnInit, OnDestroy {
    public loading = signal<boolean>(true);
    public busy = signal<boolean>(false);
    public detailLoading = signal<boolean>(false);
    public detailTabLoading = signal<boolean>(false);
    public supportOptionsLoading = signal<boolean>(false);
    public error = signal<string>('');
    public services = signal<any[]>([]);
    public nodes = signal<any[]>([]);
    public zones = signal<any[]>([]);
    public selected = signal<any>(null);
    public detail = signal<any>(null);
    public detailTab = signal<DetailTab>('overview');
    public serviceModalOpen = signal<boolean>(false);
    public serviceMode = signal<'basic_web' | 'direct_compose'>('basic_web');
    public createStep = signal<number>(1);
    public advancedCompose = signal<boolean>(false);
    public validation = signal<any>(null);
    public composeConflicts = signal<any[]>([]);
    public lastCreated = signal<any>(null);
    public advancedDetailOpen = signal<boolean>(false);
    public advancedNginxEditOpen = signal<boolean>(false);
    public advancedComposeDraft = signal<string>('');
    public advancedEditorTarget = signal<any>(null);
    public advancedEditorContent = signal<string>('');
    public advancedEditorDirty = signal<boolean>(false);
    public advancedEditorOptions: any = {
        language: 'yaml',
        theme: 'vs',
        fontSize: 13,
        minimap: { enabled: false },
        automaticLayout: true,
        wordWrap: 'on',
        scrollBeyondLastLine: false,
        roundedSelection: false,
    };
    public fileBrowserOpen = signal<boolean>(false);
    public fileBrowserBusy = signal<boolean>(false);
    public fileBrowserPath = signal<string>('.');
    public fileBrowserItems = signal<any[]>([]);
    public filePreviewOpen = signal<boolean>(false);
    public filePreviewBusy = signal<boolean>(false);
    public filePreviewTitle = signal<string>('');
    public filePreviewContent = signal<string>('');
    public editModalOpen = signal<boolean>(false);
    public editSection = signal<EditSection>('basic');
    public editBusy = signal<boolean>(false);
    public editAiBusy = signal<boolean>(false);
    public runtimeAiBusy = signal<boolean>(false);
    public editAdvancedSettings = signal<boolean>(false);
    public rollbackModalOpen = signal<boolean>(false);
    public rollbackBusy = signal<boolean>(false);
    public rollbackTarget = signal<any>(null);
    public rollbackPlan = signal<any>(null);
    public releaseModalOpen = signal<boolean>(false);
    public releaseBusy = signal<boolean>(false);
    public releaseIncludeSnapshots = signal<boolean>(false);
    public releaseComment = signal<string>('');
    public migrationModalOpen = signal<boolean>(false);
    public migrationBusy = signal<boolean>(false);
    public migrationTargetNodeId = signal<string>('');
    public migrationPause = signal<boolean>(true);
    public operationModalOpen = signal<boolean>(false);
    public operationBusy = signal<boolean>(false);
    public operationDetail = signal<any>(null);
    public serviceForm: any = this.emptyForm();
    public compose: any = this.emptyCompose();
    public envVars: any[] = [];
    public volumes: any[] = [];
    public editForm: any = {};
    public editComponents: any[] = [];
    public editOperatorComment = signal<string>('');
    public editAiIntent = signal<string>('');
    public editAiResult: any = null;
    public runtimeAiResult: any = null;
    public runtimeAiModalOpen = signal<boolean>(false);
    public runtimeAiIntent = signal<string>('');
    public runtimeAiAllowContainerActions = signal<boolean>(true);
    public runtimeAiAllowSshDiagnostics = signal<boolean>(true);
    public runtimeAiStreamEvents = signal<any[]>([]);
    public runtimeAiOutputTokenCount = signal<number>(0);
    public editAiModelRef = signal<string>('auto');
    public runtimeAiModelRef = signal<string>('auto');
    public aiModelOptions = signal<any[]>([]);
    public aiDefaultModelRef = signal<string>('auto');
    public aiAvailable = signal<boolean>(false);
    public aiUnavailableMessage = signal<string>('');
    public editAiStreamEvents = signal<any[]>([]);
    public editAiOutputTokenCount = signal<number>(0);
    public nginxConfigDrafts: any = {};
    private operationPollTimer: any = null;
    private detailRequestSeq = 0;
    private editOptionsLoaded = false;
    private aiModelOptionsLoaded = false;
    private supportOptionsLoaded = false;
    private supportOptionsRequest: Promise<boolean> | null = null;
    private themeObserver: MutationObserver | null = null;

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        this.syncAdvancedEditorTheme();
        this.startThemeObserver();
        this.refreshCompose(true);
        const params = new URLSearchParams(window.location.search || '');
        await this.load(params.get('service_id') || params.get('selected_service_id') || '');
        this.loadAiModelOptions().catch(() => null);
    }

    public ngOnDestroy() {
        this.stopOperationPolling();
        this.stopThemeObserver();
    }

    private emptyForm() {
        return {
            name: '',
            description: '',
            namespace: '',
            domain: '',
            domain_mode: 'direct',
            zone_id: '',
            domain_prefix: '',
            port: 80,
            image: 'nginx:alpine',
            image_name: 'nginx',
            image_tag: 'alpine',
            service_name: 'web',
            proxy_type: 'nginx',
            ssl_mode: 'none',
            placement_mode: 'auto',
            node_id: '',
        };
    }

    private emptyCompose() {
        return {
            namespace: '',
            filename: 'docker-compose.yaml',
            content: '',
        };
    }

    private isDarkMode() {
        return Boolean(document.documentElement.classList.contains('dark'));
    }

    private syncAdvancedEditorTheme() {
        this.advancedEditorOptions = {
            ...this.advancedEditorOptions,
            theme: this.isDarkMode() ? 'vs-dark' : 'vs',
        };
    }

    private startThemeObserver() {
        if (typeof MutationObserver === 'undefined') return;
        this.themeObserver = new MutationObserver(() => this.syncAdvancedEditorTheme());
        this.themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    }

    private stopThemeObserver() {
        if (!this.themeObserver) return;
        this.themeObserver.disconnect();
        this.themeObserver = null;
    }

    private hasOwn(value: any, key: string) {
        return Object.prototype.hasOwnProperty.call(value || {}, key);
    }

    private mergeDetailSections(currentSections: any, incomingSections: any, sameService: boolean) {
        const merged = sameService ? { ...(currentSections || {}) } : {};
        for (const key of Object.keys(incomingSections || {})) {
            const value = incomingSections[key];
            if (value || !sameService || !this.hasOwn(merged, key)) {
                merged[key] = value;
            }
        }
        return merged;
    }

    private applyDetail(data: any) {
        if (!data) {
            this.detail.set(null);
            this.selected.set(null);
            this.detailLoading.set(false);
            this.advancedNginxEditOpen.set(false);
            this.advancedComposeDraft.set('');
            this.nginxConfigDrafts = {};
            this.advancedEditorTarget.set(null);
            this.advancedEditorContent.set('');
            this.advancedEditorDirty.set(false);
            return;
        }
        const previousEditorKey = this.advancedEditorTarget()?.key || 'compose';
        const current = this.detail();
        const incomingServiceId = data?.service?.id || '';
        const currentServiceId = current?.service?.id || '';
        const sameService = Boolean(current && (!incomingServiceId || incomingServiceId === currentServiceId));
        const merged = sameService
            ? {
                ...current,
                ...data,
                service: data.service ? { ...(current.service || {}), ...data.service } : current.service,
                detail_sections: this.mergeDetailSections(current.detail_sections, data.detail_sections, true),
            }
            : { ...data, detail_sections: this.mergeDetailSections({}, data.detail_sections, false) };
        this.detail.set(merged || null);
        this.selected.set(merged?.service || null);
        if (merged?.service) this.detailLoading.set(false);

        const refreshAdvancedState = !sameService || this.hasOwn(data, 'compose_content') || this.hasOwn(data, 'nginx_configs');
        if (refreshAdvancedState) {
            this.advancedNginxEditOpen.set(false);
            if (!sameService || this.hasOwn(data, 'compose_content')) {
                this.advancedComposeDraft.set(merged?.compose_content || '');
            }
            if (!sameService || this.hasOwn(data, 'nginx_configs')) {
                this.nginxConfigDrafts = {};
                for (const config of merged?.nginx_configs || []) {
                    this.nginxConfigDrafts[config.domain_id] = config.content || '';
                }
            }
            this.selectAdvancedEditorByKey(previousEditorKey);
        }
    }

    private detailSectionLoaded(section: string) {
        if (section === 'overview' || section === 'files') return true;
        if (section === 'source' || section === 'versions') {
            return Boolean(this.detail()?.detail_sections?.[section] || this.detail()?.detail_sections?.advanced);
        }
        return Boolean(this.detail()?.detail_sections?.[section]);
    }

    private async loadDetailSection(section: string, force: boolean = false, silent: boolean = false) {
        const serviceId = this.selected()?.id;
        if (!serviceId || section === 'overview') return true;
        if (!force && this.detailSectionLoaded(section)) return true;
        const endpoint: any = {
            logs: 'detail_service_logs',
            source: 'detail_service_advanced',
            versions: 'detail_service_advanced',
        };
        const functionName = endpoint[section];
        if (!functionName) return false;
        const requestSeq = this.detailRequestSeq;
        this.detailTabLoading.set(true);
        await this.service.render();
        const { code, data } = await wiz.call(functionName, { service_id: serviceId });
        if (requestSeq !== this.detailRequestSeq || this.selected()?.id !== serviceId) {
            this.detailTabLoading.set(false);
            await this.service.render();
            return false;
        }
        if (code === 200) {
            this.applyDetail(data);
            this.detailTabLoading.set(false);
            await this.service.render();
            return true;
        }
        this.detailTabLoading.set(false);
        if (!silent) await this.alert(data?.message || '서비스 상세 정보를 불러올 수 없습니다.');
        await this.service.render();
        return false;
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

    public async confirm(message: string, action: string = '확인', status: string = 'warning') {
        return await this.service.modal.show({
            title: '',
            message,
            cancel: '취소',
            action,
            actionBtn: status,
            status,
        });
    }

    private async loadSupportOptions(silent: boolean = false) {
        this.supportOptionsLoading.set(true);
        try {
            const { code, data } = await wiz.call('support_options', {});
            if (code === 200) {
                this.nodes.set(data.nodes || []);
                this.supportOptionsLoaded = true;
                return true;
            }
            if (!silent) await this.alert(data?.message || '서버 목록을 불러올 수 없습니다.');
            return false;
        } catch (error: any) {
            if (!silent) await this.alert(error?.message || '서버 목록을 불러올 수 없습니다.');
            return false;
        } finally {
            this.supportOptionsLoading.set(false);
            await this.service.render();
        }
    }

    private async ensureSupportOptions(silent: boolean = false) {
        if (this.supportOptionsLoaded) return true;
        if (this.supportOptionsRequest) return await this.supportOptionsRequest;
        this.supportOptionsRequest = this.loadSupportOptions(silent);
        try {
            return await this.supportOptionsRequest;
        } finally {
            this.supportOptionsRequest = null;
        }
    }

    private async refreshOverviewExtras(serviceId: string, requestSeq: number) {
        try {
            const { code, data } = await wiz.call('detail_service', { service_id: serviceId });
            if (requestSeq !== this.detailRequestSeq || this.selected()?.id !== serviceId) return;
            if (code === 200) {
                this.applyDetail(data);
                await this.service.render();
            }
        } catch (_) {
            return;
        }
    }

    private snapshotBackupErrorMessage(data: any, fallback: string) {
        const failures = Array.isArray(data?.failures) ? data.failures : [];
        if (!failures.length) return data?.message || fallback;
        const rows = failures.slice(0, 4).map((item: any) => {
            const target = item?.compose_service ? `${item.compose_service}: ` : '';
            return `- ${target}${item?.message || item?.error_code || fallback}`;
        });
        const suffix = failures.length > rows.length ? `\n- 외 ${failures.length - rows.length}개 실패` : '';
        return `${data?.message || fallback}\n\n${rows.join('\n')}${suffix}`;
    }

    public async load(selectedId: string = '') {
        this.loading.set(true);
        this.error.set('');
        await this.service.render();
        const { code, data } = await wiz.call('load', {});
        if (code === 200) {
            const services = data.services || [];
            this.services.set(services);
            if (this.hasOwn(data, 'nodes')) this.nodes.set(data.nodes || []);
            if (this.hasOwn(data, 'zones')) this.zones.set(data.zones || []);
            const next = services.find((item: any) => item.id === selectedId) || services[0] || null;
            if (next?.id) {
                this.detailRequestSeq += 1;
                this.selected.set(next);
                this.detail.set(null);
                this.detailTab.set('overview');
                this.detailTabLoading.set(false);
                this.advancedDetailOpen.set(false);
                this.advancedNginxEditOpen.set(false);
                this.loading.set(false);
                await this.service.render();
                this.selectService(next, true);
                return;
            } else {
                this.detailRequestSeq += 1;
                this.applyDetail(null);
            }
        } else {
            this.error.set(data?.message || '서비스 정보를 불러올 수 없습니다.');
        }
        this.loading.set(false);
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
            this.editAiModelRef.set(data.default_model_ref || '');
            this.runtimeAiModelRef.set(data.default_model_ref || '');
            this.aiModelOptionsLoaded = true;
            return options.length > 0;
        }
        this.aiAvailable.set(false);
        this.aiUnavailableMessage.set(data?.message || 'AI 모델 목록을 불러올 수 없습니다.');
        return false;
    }

    private async ensureAiModelOptions() {
        if (this.aiModelOptionsLoaded) return this.hasAiModels();
        return await this.loadAiModelOptions();
    }

    public hasAiModels() {
        return this.aiAvailable() && this.aiModelOptions().length > 0;
    }

    public async selectService(service: any, silent: boolean = false) {
        if (!service?.id) return;
        const requestSeq = ++this.detailRequestSeq;
        this.selected.set(service);
        if (this.detail()?.service?.id !== service.id) {
            this.detail.set(null);
            this.detailTab.set('overview');
        }
        this.detailTabLoading.set(false);
        this.advancedDetailOpen.set(false);
        this.advancedNginxEditOpen.set(false);
        this.detailLoading.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('detail_service', { service_id: service.id, lightweight: true });
        if (requestSeq !== this.detailRequestSeq) {
            if (this.detail()?.service?.id === this.selected()?.id) this.detailLoading.set(false);
            return;
        }
        if (code === 200) {
            this.applyDetail(data);
        } else if (!silent) {
            await this.alert(data?.message || '서비스 상세 정보를 불러올 수 없습니다.');
        }
        if (requestSeq !== this.detailRequestSeq) {
            if (this.detail()?.service?.id === this.selected()?.id) this.detailLoading.set(false);
            return;
        }
        this.detailLoading.set(false);
        await this.service.render();
        if (code === 200) this.refreshOverviewExtras(service.id, requestSeq);
    }

    private async loadEditOptions() {
        if (this.editOptionsLoaded) return true;
        const { code, data } = await wiz.call('edit_options', {});
        if (code === 200) {
            this.zones.set(data.zones || []);
            this.editOptionsLoaded = true;
            return true;
        }
        await this.alert(data?.message || '수정에 필요한 도메인 정보를 불러올 수 없습니다.');
        return false;
    }

    public openCreateModal(mode: 'basic_web' | 'direct_compose' = 'basic_web') {
        this.ensureSupportOptions(true);
        this.serviceMode.set(mode);
        this.serviceModalOpen.set(true);
        this.createStep.set(1);
        this.advancedCompose.set(mode === 'direct_compose');
        this.validation.set(null);
        this.composeConflicts.set([]);
        this.lastCreated.set(null);
        this.serviceForm = this.emptyForm();
        this.compose = this.emptyCompose();
        this.envVars = [];
        this.volumes = [];
        this.refreshCompose(true);
    }

    public closeCreateModal() {
        if (this.busy()) return;
        this.serviceModalOpen.set(false);
    }

    public setServiceMode(mode: 'basic_web' | 'direct_compose') {
        this.serviceMode.set(mode);
        this.advancedCompose.set(mode === 'direct_compose');
        this.refreshCompose(true);
    }

    public nodeSelectorItems() {
        return this.nodes().map((node: any) => ({
            value: node.id,
            label: node.name || node.host,
            description: `${node.host || '-'} · ${node.is_local_master ? '마스터' : '일반'} · ${this.statusLabel(node.status)}`,
            badge: node.is_local_master ? 'master' : 'node',
            badgeClass: node.is_local_master
                ? 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300'
                : 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300',
        }));
    }

    public zoneSelectorItems() {
        return this.zones().map((zone: any) => ({
            value: zone.id,
            label: zone.domain,
            description: zone.provider === 'ddns'
                ? 'DDNS 관리 서버로 DNS 레코드를 등록합니다.'
                : `DNS 레코드 ${zone.record_count || 0}개 · ${zone.secret_configured ? 'Cloudflare 연결됨' : '토큰 없음'}`,
            badge: zone.provider === 'ddns' ? 'DDNS' : (zone.status || 'domain'),
            badgeClass: zone.provider === 'ddns'
                ? 'border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-900/70 dark:bg-violet-950/40 dark:text-violet-300'
                : this.statusClass(zone.status || 'draft'),
        }));
    }

    public selectedZoneRecord() {
        return this.zones().find((zone: any) => zone.id === this.serviceForm.zone_id) || null;
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

    public setDomainMode(mode: 'registered' | 'direct') {
        this.serviceForm.domain_mode = mode;
        if (mode === 'registered') {
            const first = this.zones()[0];
            if (!this.serviceForm.zone_id && first) {
                this.serviceForm.zone_id = first.id;
            }
            this.syncDomainFromZone();
        }
    }

    public selectZone(zoneId: string) {
        this.serviceForm.zone_id = zoneId || '';
        this.serviceForm.domain_mode = zoneId ? 'registered' : 'direct';
        this.syncDomainFromZone();
    }

    public syncDomainFromZone() {
        if (this.serviceForm.domain_mode !== 'registered') return;
        const zone = this.selectedZoneRecord();
        if (!zone?.domain) return;
        const prefix = this.domainPrefixForZone(zone, this.serviceForm.domain_prefix, this.serviceForm.namespace || this.serviceForm.name);
        if (this.isDdnsZone(zone) && !String(this.serviceForm.domain_prefix || '').trim()) {
            this.serviceForm.domain_prefix = prefix;
        }
        this.serviceForm.domain = prefix ? `${prefix}.${zone.domain}` : zone.domain;
    }

    public domainPreview() {
        if (this.serviceForm.domain_mode === 'registered') {
            const zone = this.selectedZoneRecord();
            const prefix = this.domainPrefixForZone(zone, this.serviceForm.domain_prefix, this.serviceForm.namespace || this.serviceForm.name);
            if (zone?.domain) return prefix ? `${prefix}.${zone.domain}` : zone.domain;
        }
        return this.serviceForm.domain || '도메인 미입력';
    }

    private splitImageRef(ref: string) {
        const clean = String(ref || '').trim() || 'nginx:alpine';
        const digestIndex = clean.indexOf('@');
        if (digestIndex > 0) {
            return { name: clean.slice(0, digestIndex), tag: clean.slice(digestIndex + 1) };
        }
        const lastSlash = clean.lastIndexOf('/');
        const lastColon = clean.lastIndexOf(':');
        if (lastColon > lastSlash) {
            return { name: clean.slice(0, lastColon), tag: clean.slice(lastColon + 1) || 'latest' };
        }
        return { name: clean, tag: 'latest' };
    }

    private applyImageRef(ref: string) {
        const parsed = this.splitImageRef(ref);
        this.serviceForm.image_name = parsed.name;
        this.serviceForm.image_tag = parsed.tag;
        this.serviceForm.image = parsed.tag?.startsWith('sha256:')
            ? `${parsed.name}@${parsed.tag}`
            : `${parsed.name}:${parsed.tag}`;
    }

    private currentImageRef() {
        const name = String(this.serviceForm.image_name || '').trim() || 'nginx';
        const tag = String(this.serviceForm.image_tag || '').trim();
        if (!tag) return name;
        return tag.startsWith('sha256:') ? `${name}@${tag}` : `${name}:${tag}`;
    }

    private yamlScalar(value: any) {
        const clean = String(value ?? '');
        if (/^[A-Za-z0-9_./:@-]+$/.test(clean)) return clean;
        return JSON.stringify(clean);
    }

    private normalizedEnvVars() {
        return (this.envVars || [])
            .map((item: any) => ({
                key: String(item?.key || '').trim(),
                value: String(item?.value ?? ''),
            }))
            .filter((item: any) => item.key);
    }

    private normalizedVolumes() {
        return (this.volumes || [])
            .map((item: any) => ({
                source: String(item?.source || '').trim(),
                target: String(item?.target || '').trim(),
            }))
            .filter((item: any) => item.source && item.target);
    }

    public syncImageRef() {
        this.serviceForm.image = this.currentImageRef();
        this.refreshCompose();
    }

    public normalizeNamespace() {
        const raw = this.serviceForm.namespace || this.serviceForm.name || '';
        const normalized = String(raw)
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9_]+/g, '_')
            .replace(/^_+|_+$/g, '');
        this.serviceForm.namespace = normalized;
        this.refreshCompose();
    }

    public refreshCompose(force: boolean = false) {
        const namespace = this.serviceForm.namespace || 'my_service';
        const serviceName = this.serviceForm.service_name || 'web';
        const image = this.currentImageRef();
        const port = Number(this.serviceForm.port || 80);
        const envVars = this.normalizedEnvVars();
        const volumes = this.normalizedVolumes();
        this.serviceForm.image = image;
        this.compose.namespace = namespace;
        this.compose.filename = 'docker-compose.yaml';
        if (!force && this.advancedCompose() && this.compose.content) return;

        const lines = [
            'services:',
            `  ${serviceName}:`,
            `    image: ${image}`,
            '    ports:',
            `      - "${port}:${port}"`,
        ];
        if (envVars.length) {
            lines.push('    environment:');
            for (const item of envVars) {
                lines.push(`      ${item.key}: ${this.yamlScalar(item.value)}`);
            }
        }
        if (volumes.length) {
            lines.push('    volumes:');
            for (const item of volumes) {
                lines.push(`      - "${item.source}:${item.target}"`);
            }
        }
        lines.push(
            '    healthcheck:',
            `      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:${port}"]`,
            '      interval: 30s',
            '      timeout: 5s',
            '      retries: 3',
        );
        const namedVolumes = volumes
            .map((item: any) => item.source)
            .filter((source: string) => !source.startsWith('/') && !source.includes(':') && !source.includes('\\'));
        if (namedVolumes.length) {
            lines.push('volumes:');
            for (const source of Array.from(new Set(namedVolumes))) {
                lines.push(`  ${source}:`);
            }
        }
        this.compose.content = lines.join('\n');
    }

    public async validateCompose() {
        this.validation.set(null);
        this.refreshCompose();
        const { code, data } = await wiz.call('validate_compose', this.compose);
        if (code === 200) {
            this.validation.set({ ok: true, validation: data.validation });
        } else {
            this.validation.set({ ok: false, message: this.formatComposeError(data, 'Compose를 검사할 수 없습니다.'), details: data.details || [] });
        }
        await this.service.render();
    }

    private createPayload() {
        return {
            ...this.serviceForm,
            env_vars: this.normalizedEnvVars(),
            volumes: this.normalizedVolumes(),
            filename: this.compose.filename,
            content: this.compose.content,
            source: 'manual_compose',
            source_ref: { source: 'manual_compose', wizard: 'services.legacy_modal' },
        };
    }

    public async checkComposeConflicts(showMessage: boolean = false) {
        if (!this.advancedCompose()) {
            this.composeConflicts.set([]);
            return true;
        }
        this.syncImageRef();
        const { code, data } = await wiz.call('compose_conflicts', this.createPayload());
        if (code === 200) {
            const conflicts = data.conflicts || [];
            this.composeConflicts.set(conflicts);
            if (conflicts.length && showMessage) {
                return await this.confirm(`폼 입력값과 Compose 원문이 다른 항목이 ${conflicts.length}개 있습니다. Compose 원문 기준으로 계속 저장할까요?`, '계속 저장', 'warning');
            }
            return true;
        }
        if (showMessage) await this.alert(data?.message || 'Compose 충돌을 확인할 수 없습니다.');
        return false;
    }

    public async createService(deployAfterCreate: boolean = false) {
        for (const step of [1, 2, 3, 4, 5, 6]) {
            if (!(await this.validateCreateStep(step, true))) {
                this.createStep.set(step);
                return;
            }
        }
        this.syncImageRef();
        this.refreshCompose();
        if (!(await this.checkComposeConflicts(true))) return;
        this.busy.set(true);
        this.validation.set(null);
        const payload = this.createPayload();
        const { code, data } = await wiz.call('create_service', payload);
        if (code === 200) {
            this.validation.set({ ok: true, validation: data.result?.validation });
            this.lastCreated.set(data.result || null);
            this.serviceModalOpen.set(false);
            const serviceId = data.result?.service?.id || '';
            await this.load(serviceId);
            if (deployAfterCreate && serviceId) {
                await this.deployService(serviceId, true);
            } else {
                await this.alert('서비스 초안을 저장했습니다.', 'success');
            }
        } else {
            this.validation.set({ ok: false, message: this.formatComposeError(data, '서비스를 저장할 수 없습니다.'), details: data.details || [] });
            await this.alert(this.formatComposeError(data, '서비스를 저장할 수 없습니다.'));
        }
        this.busy.set(false);
        await this.service.render();
    }

    public toggleAdvancedCompose() {
        this.advancedCompose.set(!this.advancedCompose());
    }

    public createSteps() {
        return [
            { step: 1, title: '기본 정보', description: '이름과 설명' },
            { step: 2, title: '이미지', description: '버전과 포트' },
            { step: 3, title: '데이터', description: '환경변수와 볼륨' },
            { step: 4, title: '도메인', description: '접속 주소와 SSL' },
            { step: 5, title: '배치', description: '실행 서버' },
            { step: 6, title: '확인', description: '요약 후 저장' },
        ];
    }

    public async setCreateStep(step: number) {
        const target = Math.max(1, Math.min(6, Number(step || 1)));
        if (target <= this.createStep()) {
            this.createStep.set(target);
            await this.service.render();
            return;
        }
        for (let current = 1; current < target; current += 1) {
            if (!(await this.validateCreateStep(current, true))) {
                this.createStep.set(current);
                await this.service.render();
                return;
            }
        }
        this.createStep.set(target);
        await this.service.render();
    }

    public async nextCreateStep() {
        await this.setCreateStep(this.createStep() + 1);
    }

    public async previousCreateStep() {
        await this.setCreateStep(this.createStep() - 1);
    }

    public async validateCreateStep(step: number = this.createStep(), showMessage: boolean = false) {
        if (step === 1) {
            if (!String(this.serviceForm.name || '').trim()) {
                if (showMessage) await this.alert('서비스 이름을 입력해주세요.');
                return false;
            }
            if (!String(this.serviceForm.namespace || '').trim()) {
                if (showMessage) await this.alert('서비스 ID를 입력해주세요.');
                return false;
            }
        }
        if (step === 2) {
            if (!String(this.serviceForm.image_name || '').trim()) {
                if (showMessage) await this.alert('이미지 이름을 입력해주세요.');
                return false;
            }
            if (!String(this.serviceForm.image_tag || '').trim()) {
                if (showMessage) await this.alert('이미지 버전 또는 tag를 입력해주세요.');
                return false;
            }
            if (!Number(this.serviceForm.port || 0)) {
                if (showMessage) await this.alert('내부 port를 입력해주세요.');
                return false;
            }
            if (!String(this.serviceForm.service_name || '').trim()) {
                if (showMessage) await this.alert('컨테이너 이름을 입력해주세요.');
                return false;
            }
        }
        if (step === 3) {
            for (const item of this.normalizedVolumes()) {
                if (!item.target.startsWith('/')) {
                    if (showMessage) await this.alert('컨테이너 저장 경로는 /data 처럼 /로 시작해야 합니다.');
                    return false;
                }
            }
        }
        if (step === 4) {
            if (this.serviceForm.domain_mode === 'registered') {
                this.syncDomainFromZone();
            }
            const sslMode = this.serviceForm.ssl_mode || 'none';
            if (sslMode !== 'none' && !String(this.serviceForm.domain || '').trim()) {
                if (showMessage) await this.alert('SSL을 사용하려면 공개 도메인을 입력해주세요.');
                return false;
            }
        }
        if (step === 5) {
            if (this.serviceForm.placement_mode === 'manual' && !String(this.serviceForm.node_id || '').trim()) {
                if (showMessage) await this.alert('직접 배치할 서버를 선택해주세요.');
                return false;
            }
        }
        if (step === 6) {
            if (!String(this.compose.content || '').trim()) {
                if (showMessage) await this.alert('저장할 Compose 초안을 만들 수 없습니다.');
                return false;
            }
        }
        return true;
    }

    public createSummaryItems() {
        return [
            { label: '서비스 이름', value: this.serviceForm.name || '-' },
            { label: '서비스 ID', value: this.serviceForm.namespace || '-' },
            { label: '이미지', value: this.currentImageRef() },
            { label: '컨테이너', value: this.serviceForm.service_name || '-' },
            { label: '내부 port', value: String(this.serviceForm.port || '-') },
            { label: '환경변수', value: `${this.normalizedEnvVars().length}개` },
            { label: '데이터 볼륨', value: `${this.normalizedVolumes().length}개` },
            { label: '공개 도메인', value: this.serviceForm.domain || '나중에 연결' },
            { label: 'SSL', value: this.sslModeLabel(this.serviceForm.ssl_mode || 'none') },
            { label: '실행 서버', value: this.placementLabel() },
            { label: 'Nginx', value: this.serviceForm.domain ? `${this.serviceForm.domain} -> ${this.serviceForm.service_name}:${this.serviceForm.port}` : '도메인 입력 후 자동 연결' },
        ];
    }

    public addEnvVar() {
        this.envVars.push({ key: '', value: '' });
    }

    public removeEnvVar(index: number) {
        this.envVars.splice(index, 1);
        this.refreshCompose();
    }

    public addVolume() {
        const namespace = this.serviceForm.namespace || 'service';
        this.volumes.push({ source: `${namespace}_data`, target: '/data' });
        this.refreshCompose();
    }

    public removeVolume(index: number) {
        this.volumes.splice(index, 1);
        this.refreshCompose();
    }

    public selectPlacementMode(mode: 'auto' | 'manual') {
        this.serviceForm.placement_mode = mode;
        if (mode === 'auto') {
            this.serviceForm.node_id = '';
        }
    }

    public selectPlacementNode(nodeId: string) {
        this.serviceForm.node_id = nodeId || '';
        this.serviceForm.placement_mode = nodeId ? 'manual' : 'auto';
    }

    public selectedPlacementNode() {
        return this.nodes().find((node: any) => node.id === this.serviceForm.node_id) || null;
    }

    public placementLabel() {
        if (this.serviceForm.placement_mode !== 'manual') return '자동 배치';
        const node = this.selectedPlacementNode();
        return node ? `${node.name || node.host} (${node.host})` : '서버 선택 필요';
    }

    private servicePlacementNodeId() {
        const service = this.detail()?.service || this.selected() || {};
        const policy = service?.target_node_policy || {};
        const placement = service?.metadata?.placement || {};
        return String(policy.node_id || placement.node_id || '').trim();
    }

    public currentMigrationSourceNodeId() {
        return this.runtimeServerDetailNodeId() || this.servicePlacementNodeId();
    }

    public currentMigrationSourceNodeLabel() {
        const nodeId = this.currentMigrationSourceNodeId();
        const node = this.nodes().find((item: any) => item.id === nodeId);
        if (node) return `${node.name || node.host} (${node.host || 'host 없음'})`;
        return this.runtimeServerSummaryText();
    }

    public migrationNodeOptions() {
        const currentNodeId = this.currentMigrationSourceNodeId();
        return this.nodes()
            .filter((node: any) => node.id && node.id !== currentNodeId)
            .map((node: any) => ({
                value: node.id,
                label: node.name || node.host,
                description: `${node.host || '-'} · ${node.is_local_master ? '마스터' : '일반'} · ${this.statusLabel(node.status)}`,
                badge: node.is_local_master ? 'master' : 'node',
                badgeClass: node.is_local_master
                    ? 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300'
                    : 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300',
                disabled: ['failed', 'canceled'].includes(this.statusKey(node.status)),
            }));
    }

    public selectedMigrationNode() {
        return this.nodes().find((node: any) => node.id === this.migrationTargetNodeId()) || null;
    }

    public migrationDisabledReason() {
        if (!this.selected()?.id) return '서비스를 선택해주세요.';
        if (!this.backupSystemCanBackup()) return '백업 시스템이 실행 중이어야 마이그레이션할 수 있습니다.';
        if (!this.migrationNodeOptions().length) return '이동할 다른 서버가 없습니다.';
        if (!this.migrationTargetNodeId()) return '대상 서버를 선택해주세요.';
        return '';
    }

    public canSubmitMigration() {
        return !this.migrationBusy() && !this.busy() && !this.migrationDisabledReason();
    }

    public migrationTargetSummary() {
        const node = this.selectedMigrationNode();
        if (!node) return '대상 서버 선택 필요';
        return `${node.name || node.host} (${node.host || 'host 없음'})`;
    }

    public openMigrationModal() {
        this.openMigrationModalAsync();
    }

    private async openMigrationModalAsync() {
        if (!this.selected()?.id || this.migrationBusy() || this.supportOptionsLoading()) return;
        if (!(await this.ensureSupportOptions())) return;
        const first = this.migrationNodeOptions().find((item: any) => !item.disabled);
        this.migrationTargetNodeId.set(first?.value || '');
        this.migrationPause.set(true);
        this.migrationModalOpen.set(true);
        await this.service.render();
    }

    public closeMigrationModal() {
        if (this.migrationBusy()) return;
        this.migrationModalOpen.set(false);
        this.migrationTargetNodeId.set('');
    }

    public async submitServiceMigration() {
        const serviceId = this.selected()?.id;
        if (!serviceId || this.migrationBusy()) return;
        const disabledReason = this.migrationDisabledReason();
        if (disabledReason) {
            await this.alert(disabledReason);
            return;
        }
        const ok = await this.confirm(
            `${this.selected()?.name || '서비스'}를 ${this.migrationTargetSummary()} 서버로 마이그레이션합니다.\n\n현재 컨테이너 스냅샷을 만든 뒤 스냅샷 이미지로 새 서버에 다시 배포합니다.`,
            '마이그레이션',
            'warning',
        );
        if (!ok) return;
        this.migrationBusy.set(true);
        const { code, data } = await wiz.call('migrate_service', {
            service_id: serviceId,
            target_node_id: this.migrationTargetNodeId(),
            pause: this.migrationPause(),
        });
        this.migrationBusy.set(false);
        if ([200, 202].includes(code)) {
            this.migrationModalOpen.set(false);
            if (data?.service) this.selected.set({ ...this.selected(), ...data.service });
            if (data?.operation) await this.openOperationModal(data.operation, false);
            await this.load(serviceId);
        } else {
            await this.alert(data?.message || '서비스 마이그레이션을 시작할 수 없습니다.');
        }
        await this.service.render();
    }

    public async deploySelectedService() {
        const serviceId = this.selected()?.id;
        if (!serviceId || this.busy()) return;
        const ok = await this.confirm(`${this.selected()?.name || '서비스'} 설정을 서버에 다시 적용합니다. 접속 주소와 포트 설정도 함께 확인합니다.`, this.deployActionLabel(), 'warning');
        if (!ok) return;
        await this.deployService(serviceId, false);
    }

    public async deleteSelectedService() {
        const serviceId = this.selected()?.id;
        const serviceName = this.selected()?.name || '서비스';
        if (!serviceId || this.busy()) return;
        const ok = await this.confirm(`${serviceName} 서비스를 삭제합니다.\n\n실행 중인 Docker 서비스, 연결된 Docker 볼륨, nginx 연결 설정, 서비스 기록과 생성 파일이 함께 삭제됩니다. 이 작업은 되돌릴 수 없습니다.`, '서비스 삭제', 'error');
        if (!ok) return;
        this.busy.set(true);
        const { code, data } = await wiz.call('delete_service', { service_id: serviceId });
        this.busy.set(false);
        if (code === 200) {
            await this.load();
            await this.alert('서비스를 삭제했습니다.', 'success');
            return;
        }
        await this.alert(data?.message || '서비스를 삭제할 수 없습니다.');
        await this.service.render();
    }

    public async refreshRuntimeStatus() {
        const serviceId = this.selected()?.id;
        if (!serviceId || this.busy()) return;
        this.busy.set(true);
        const { code, data } = await wiz.call('refresh_deploy_status', { service_id: serviceId });
        if (code === 200) {
            this.applyDetail(data);
        } else {
            await this.alert(data?.message || '실행 상태를 확인할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public freeCertificates() {
        return this.detail()?.free_certificates || [];
    }

    public certificateStatusLabel(status: string) {
        const labels: any = {
            valid: '정상',
            expiring: '만료 임박',
            expired: '만료됨',
            missing: '파일 없음',
            error: '확인 실패',
            disabled: '비활성',
            key_insecure: '키 권한 확인',
            key_mismatch: '키 불일치',
        };
        return labels[status] || status || '발급 대기';
    }

    public certificateStatusClass(status: string) {
        if (['valid'].includes(status)) return this.statusClass('running');
        if (['expiring', 'disabled'].includes(status)) return this.statusClass('pending');
        if (['expired', 'missing', 'error', 'key_insecure', 'key_mismatch'].includes(status)) return this.statusClass('failed');
        return this.statusClass('');
    }

    public certificateExpiresText(item: any) {
        const cert = item?.certificate || {};
        if (!cert?.not_after) return '발급 후 표시됩니다.';
        const days = cert.days_remaining;
        if (Number.isFinite(Number(days))) {
            if (Number(days) < 0) return `${Math.abs(Number(days))}일 전 만료 · ${this.formatDate(cert.not_after)}`;
            return `${Number(days)}일 남음 · ${this.formatDate(cert.not_after)}`;
        }
        return this.formatDate(cert.not_after);
    }

    public certificateAutoRenewText(item: any) {
        const renewal = item?.auto_renewal || {};
        if (renewal.configured) return `자동 갱신 감지됨 · ${renewal.method || 'system'}`;
        if (renewal.status === 'ok') return '자동 갱신 작업 없음';
        return '자동 갱신 상태 확인 실패';
    }

    public certificateRenewTitle(item: any) {
        if (item?.manual_renew_enabled) return `${item.domain} 무료 인증서 수동 갱신`;
        return '발급된 certbot 인증서가 있을 때 갱신할 수 있습니다.';
    }

    public certificateAutoRenewTitle(item: any) {
        if (item?.auto_renewal?.configured) return '자동 갱신 작업이 이미 감지되었습니다.';
        return `${item.domain} 무료 인증서 자동 갱신 설정`;
    }

    public async ensureServiceCertificateRenewal(item: any) {
        const serviceId = this.selected()?.id;
        if (!serviceId || !item?.domain || item?.auto_renewal?.configured || this.busy()) return;
        const ok = await this.confirm('certbot renew를 주기적으로 실행하는 systemd timer 또는 cron 작업을 설정합니다.', '자동 갱신 설정', 'warning');
        if (!ok) return;
        this.busy.set(true);
        const { code, data } = await wiz.call('ensure_service_certificate_renewal', {
            service_id: serviceId,
            domain: item.domain,
        });
        this.busy.set(false);
        if (code === 200) {
            this.applyDetail(data);
            await this.alert('무료 인증서 자동 갱신 설정을 확인했습니다.', 'success');
        } else {
            await this.alert(data?.message || '무료 인증서 자동 갱신을 설정할 수 없습니다.');
        }
        await this.service.render();
    }

    public async renewServiceCertificate(item: any) {
        const serviceId = this.selected()?.id;
        if (!serviceId || !item?.domain || !item?.manual_renew_enabled || this.busy()) return;
        const ok = await this.confirm(`${item.domain} 무료 인증서를 지금 갱신합니다. 갱신 후 nginx 설정을 다시 적용합니다.`, '인증서 갱신', 'warning');
        if (!ok) return;
        this.busy.set(true);
        const { code, data } = await wiz.call('renew_service_certificate', {
            service_id: serviceId,
            domain: item.domain,
        });
        this.busy.set(false);
        if (code === 200) {
            this.applyDetail(data);
            await this.alert('무료 인증서를 갱신했습니다.', 'success');
        } else {
            await this.alert(data?.message || '무료 인증서를 갱신할 수 없습니다.');
        }
        await this.service.render();
    }

    public nginxConfigs() {
        return this.detail()?.nginx_configs || [];
    }

    public advancedEditorItems() {
        const detail = this.detail();
        if (!detail?.service) return [];
        const items: any[] = [{
            key: 'compose',
            kind: 'compose',
            label: 'Compose 원문',
            description: '서비스 실행 구성을 직접 수정합니다.',
            path: detail.service?.compose_path || 'docker-compose.yaml',
            editable: true,
            language: 'yaml',
            content: this.advancedComposeDraft() || detail.compose_content || '',
        }];
        for (const config of this.nginxConfigs()) {
            items.push({
                key: `nginx:${config.domain_id}`,
                kind: 'nginx',
                label: config.domain || 'nginx 설정',
                description: config.editable ? '접속 연결 설정을 직접 수정합니다.' : '읽기 전용 nginx 설정입니다.',
                path: config.path || '설정 파일 없음',
                editable: !!config.editable,
                language: 'nginx',
                domain_id: config.domain_id,
                config,
                content: this.nginxConfigDrafts[config.domain_id] ?? config.content ?? '',
            });
        }
        return items;
    }

    private selectAdvancedEditorByKey(key: string = 'compose') {
        const items = this.advancedEditorItems();
        const item = items.find((candidate: any) => candidate.key === key) || items[0] || null;
        if (!item) {
            this.advancedEditorTarget.set(null);
            this.advancedEditorContent.set('');
            this.advancedEditorDirty.set(false);
            return;
        }
        this.selectAdvancedEditor(item);
    }

    public selectAdvancedEditor(item: any) {
        if (!item) return;
        this.advancedEditorTarget.set(item);
        this.advancedEditorContent.set(item.content || '');
        this.advancedEditorDirty.set(false);
        this.advancedEditorOptions = {
            ...this.advancedEditorOptions,
            language: item.language || 'text',
            readOnly: !item.editable,
        };
    }

    public advancedEditorItemClass(item: any) {
        if (this.advancedEditorTarget()?.key === item?.key) {
            return 'border-zinc-950 bg-zinc-950 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-950';
        }
        return 'border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800';
    }

    public advancedEditorBadgeClass(item: any) {
        if (item?.kind === 'compose') return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300';
        if (item?.editable) return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300';
    }

    public advancedEditorTypeLabel(item: any = this.advancedEditorTarget()) {
        if (item?.kind === 'compose') return 'Compose';
        if (item?.kind === 'nginx') return 'nginx';
        return '원문';
    }

    public setAdvancedEditorContent(value: string) {
        const next = value || '';
        const target = this.advancedEditorTarget();
        this.advancedEditorContent.set(next);
        this.advancedEditorDirty.set(true);
        if (target?.kind === 'compose') {
            this.advancedComposeDraft.set(next);
        } else if (target?.kind === 'nginx' && target.domain_id) {
            this.nginxConfigDrafts[target.domain_id] = next;
        }
    }

    public async saveAdvancedEditor() {
        const target = this.advancedEditorTarget();
        if (!target?.editable) return;
        if (target.kind === 'compose') {
            await this.saveComposeContent();
            return;
        }
        if (target.kind === 'nginx') {
            await this.saveNginxConfig(target.config);
        }
    }

    public async saveComposeContent() {
        const serviceId = this.selected()?.id;
        if (!serviceId) return;
        const content = this.advancedComposeDraft() || this.advancedEditorContent();
        if (!String(content || '').trim()) {
            await this.alert('Compose 내용이 비어 있습니다.');
            return;
        }
        const ok = await this.confirm('Compose 원문을 검사한 뒤 초안으로 저장합니다. 버전 이력은 릴리즈 버튼을 눌렀을 때만 추가됩니다.', '검사 후 저장', 'warning');
        if (!ok) return;
        this.busy.set(true);
        const service = this.selected() || {};
        const metadata = service.metadata || {};
        const { code, data } = await wiz.call('save_compose_content', {
            service_id: serviceId,
            name: service.name,
            description: metadata.description || '',
            content,
        });
        this.busy.set(false);
        if (code === 200) {
            this.applyDetail(data);
            this.advancedEditorDirty.set(false);
            await this.alert('Compose 원문을 저장했습니다. 적용 버튼을 누르면 서버에 반영됩니다.', 'success');
        } else {
            await this.alert(this.formatPreflightError(data));
        }
        await this.service.render();
    }

    public async saveNginxConfig(config: any) {
        const serviceId = this.selected()?.id;
        if (!serviceId || !config?.domain_id) return;
        const ok = await this.confirm(`${config.domain} nginx 원문 설정을 저장하고 설정 검사를 실행합니다. 문제가 있으면 이전 내용으로 되돌립니다.`, '저장', 'warning');
        if (!ok) return;
        this.busy.set(true);
        const { code, data } = await wiz.call('save_nginx_config', {
            service_id: serviceId,
            domain_id: config.domain_id,
            content: this.nginxConfigDrafts[config.domain_id] || '',
        });
        this.busy.set(false);
        if (code === 200) {
            this.applyDetail(data);
            this.advancedEditorDirty.set(false);
            await this.alert('nginx 설정을 저장하고 다시 불러왔습니다.', 'success');
        } else {
            await this.alert(data?.message || 'nginx 설정을 저장할 수 없습니다.');
        }
        await this.service.render();
    }

    public async openAdvancedNginxEdit() {
        if (!this.nginxConfigs().length || this.advancedNginxEditOpen()) return;
        const ok = await this.confirm('자동 생성된 nginx 설정 원문을 직접 수정합니다. 잘못 저장하면 접속이 끊길 수 있으므로 필요한 경우에만 사용하세요.', '원문 수정 열기', 'warning');
        if (!ok) return;
        this.advancedNginxEditOpen.set(true);
        await this.service.render();
    }

    private clone(value: any) {
        return JSON.parse(JSON.stringify(value || null));
    }

    public editSections() {
        const domainBadge = this.editForm.domain_mode === 'registered' ? '연결' : '없음';
        const advancedCount = this.editAdvancedCount();
        return [
            { id: 'basic' as EditSection, icon: 'fa-pen-to-square', title: '기본 정보', description: '이름과 설명', badge: '' },
            { id: 'components' as EditSection, icon: 'fa-cubes', title: '구성', description: '이미지와 포트', badge: this.editComponents.length ? `${this.editComponents.length}개` : '' },
            { id: 'domain' as EditSection, icon: 'fa-globe', title: '도메인', description: '공개 주소와 대상', badge: domainBadge },
            { id: 'advanced' as EditSection, icon: 'fa-sliders', title: '고급', description: '환경변수와 볼륨', badge: advancedCount ? `${advancedCount}개` : '' },
            ...(this.hasAiModels() ? [{ id: 'ai' as EditSection, icon: 'fa-wand-magic-sparkles', title: 'AI 수정안', description: '요청으로 초안 반영', badge: this.editAiBusy() ? '생성 중' : (this.editAiResult ? '적용됨' : '') }] : []),
        ];
    }

    public async setEditSection(section: EditSection) {
        if (section === 'ai' && !(await this.ensureAiModelOptions())) {
            await this.alert(this.aiUnavailableMessage() || '시스템 설정에서 사용할 AI 모델을 먼저 켜주세요.');
            return;
        }
        this.editSection.set(section);
        if (section === 'ai') {
            await this.service.render();
        }
    }

    public editSectionTitle() {
        return this.editSections().find((item: any) => item.id === this.editSection())?.title || '서비스 수정';
    }

    public editSectionDescription() {
        return this.editSections().find((item: any) => item.id === this.editSection())?.description || '';
    }

    public editPortCount() {
        return this.editComponents.reduce((count: number, item: any) => count + this.editPorts(item).length, 0);
    }

    public editEnvVarCount() {
        return this.editComponents.reduce((count: number, item: any) => count + (item?.env_vars || []).length, 0);
    }

    public editVolumeCount() {
        return this.editComponents.reduce((count: number, item: any) => count + (item?.volumes || []).length, 0);
    }

    public editAdvancedCount() {
        return this.editEnvVarCount() + this.editVolumeCount();
    }

    public openEditModal() {
        this.openEditModalAsync();
    }

    private async openEditModalAsync() {
        let detail = this.detail();
        let service = detail?.service;
        if (!service) return;
        if (!(await this.loadDetailSection('source'))) return;
        detail = this.detail();
        service = detail?.service;
        if (!service) return;
        if (!(await this.loadEditOptions())) return;
        const domain = (detail.domains || [])[0] || null;
        this.editComponents = this.clone(detail.components || []) || [];
        this.editForm = {
            service_id: service.id,
            name: service.name || '',
            description: service?.metadata?.description || '',
            domain_mode: domain ? 'registered' : 'none',
            zone_id: '',
            domain_prefix: '',
            domain: domain?.domain || '',
            domain_target_key: '',
            domain_target_port: domain?.metadata?.target_port || domain?.port || 80,
        };
        if (domain?.domain) this.matchEditDomainZone(domain.domain);
        this.ensureEditDomainTarget();
        this.editAdvancedSettings.set(false);
        this.editOperatorComment.set(service?.metadata?.operator_comment || '');
        this.editAiIntent.set('');
        this.editAiModelRef.set(this.aiDefaultModelRef() || 'auto');
        this.resetEditAiStream();
        this.editAiResult = null;
        this.editSection.set('basic');
        this.editModalOpen.set(true);
    }

    public closeEditModal() {
        if (this.editBusy()) return;
        this.editModalOpen.set(false);
    }

    private matchEditDomainZone(domain: string) {
        const clean = String(domain || '').toLowerCase();
        const zones = [...this.zones()].sort((a: any, b: any) => String(b.domain || '').length - String(a.domain || '').length);
        const zone = zones.find((item: any) => clean === item.domain || clean.endsWith(`.${item.domain}`));
        if (!zone) {
            this.editForm.domain_mode = 'none';
            return;
        }
        this.editForm.zone_id = zone.id;
        const suffix = String(zone.domain || '').toLowerCase();
        this.editForm.domain_prefix = clean === suffix && this.isDdnsZone(zone)
            ? this.domainPrefixForZone(zone, '', this.editForm.name)
            : (clean === suffix ? '' : clean.slice(0, -(suffix.length + 1)));
    }

    public editPorts(item: any) {
        return (item?.ports || []).filter((port: any) => Number(port.target || 0) > 0);
    }

    public editDomainTargetOptions() {
        const options: any[] = [];
        for (const item of this.editComponents) {
            for (const port of this.editPorts(item)) {
                options.push({
                    key: `${item.key}:${port.target}`,
                    service_key: item.key,
                    service_label: item.label || item.key,
                    port: Number(port.target),
                    protocol: port.protocol || 'tcp',
                    recommended: !!port.public_endpoint,
                });
            }
        }
        return options.sort((a: any, b: any) => Number(!!b.recommended) - Number(!!a.recommended));
    }

    public editAiInputRows() {
        return [
            { key: 'intent', value: '수정 요구사항' },
            { key: 'operator_comment', value: '서비스 수정 추가 코멘트' },
            { key: 'model', value: 'AI 설정에서 사용 가능한 모델' },
            { key: 'form', value: '현재 서비스와 도메인' },
            { key: 'components', value: '현재 이미지, 포트, 환경변수, 볼륨' },
            { key: 'base_content', value: '현재 Compose 원문' },
        ];
    }

    private resetEditAiStream() {
        this.editAiStreamEvents.set([]);
        this.editAiOutputTokenCount.set(0);
    }

    private pushEditAiEvent(event: any) {
        this.editAiStreamEvents.set([...this.editAiStreamEvents(), event].slice(-120));
        if (event?.type === 'delta') {
            this.editAiOutputTokenCount.set(this.editAiOutputTokenCount() + String(event.text || '').length);
        }
    }

    public editAiStreamRows() {
        return this.compactAiStreamRows(this.editAiStreamEvents());
    }

    private isMcpToolExposureNoise(value: any) {
        const text = String(value || '').toLowerCase();
        if (!text) return false;
        const mentionsTool = text.includes('mcp') || text.includes('tool_search') || text.includes('도구');
        const unavailable = [
            'not exposed',
            'not available',
            'not provided',
            'not found',
            'unavailable',
            '노출되어',
            '노출되지',
            '사용할 수 없',
            '제공되지',
        ].some((token: string) => text.includes(token));
        return mentionsTool && unavailable;
    }

    private normalizeMcpToolExposureMessage(value: any) {
        const lines = String(value || '').replace(/\r/g, '').split('\n');
        const kept = lines.filter((line: string) => !this.isMcpToolExposureNoise(line));
        if (kept.length === lines.length) return value;
        const fallback = '일부 AI 보조 점검은 현재 허용된 도구와 서비스 상태 정보로 대체했습니다.';
        const normalized = [...kept.map((line: string) => line.trim()).filter(Boolean), fallback];
        return normalized.join('\n');
    }

    private streamLines(value: any) {
        return String(value || '')
            .replace(/\r/g, '')
            .split('\n')
            .map((line: string) => line.replace(/\s+/g, ' ').trim())
            .filter((line: string) => !this.isMcpToolExposureNoise(line))
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
                    pushRow({ type: 'thinking', label: '판단 요약', message: text, text });
                }
            }
            if (force && thinkingBuffer.trim()) {
                const text = this.streamLines(thinkingBuffer).join(' ');
                if (text) pushRow({ type: 'thinking', label: '판단 요약', message: text, text });
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

    private async streamAi(functionName: string, payload: any, pushEvent: (event: any) => void, onDone: (data: any) => Promise<void>) {
        const formData = new FormData();
        formData.append('payload', JSON.stringify(payload || {}));
        const response = await fetch(`/wiz/api/page.services/${functionName}`, { method: 'POST', body: formData });
        if (!response.ok || !response.body) {
            throw new Error(`AI 스트림 요청 실패: HTTP ${response.status}`);
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let doneSeen = false;
        let donePayload: any = null;
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
                pushEvent(event);
                if (event.type === 'error') {
                    throw new Error(event.message || 'AI 스트림 처리 중 오류가 발생했습니다.');
                }
                if (event.type === 'done') {
                    doneSeen = true;
                    donePayload = event.data;
                    await onDone(event.data);
                }
            }
            await this.service.render();
        }
        if (!doneSeen) {
            throw new Error('AI 스트림이 완료 이벤트 없이 종료되었습니다.');
        }
        return donePayload;
    }

    private async streamEditAi(functionName: string, payload: any, onDone: (data: any) => Promise<void>) {
        return await this.streamAi(functionName, payload, (event: any) => this.pushEditAiEvent(event), onDone);
    }

    private async streamRuntimeAi(functionName: string, payload: any, onDone: (data: any) => Promise<void>) {
        return await this.streamAi(functionName, payload, (event: any) => this.pushRuntimeAiEvent(event), onDone);
    }

    public editAiOutputRows() {
        return [
            { key: 'form', value: '서비스 정보와 도메인 대상' },
            { key: 'components', value: '수정된 컴포넌트 설정' },
            { key: 'warnings', value: '확인 필요 항목' },
        ];
    }

    public ensureEditDomainTarget() {
        const options = this.editDomainTargetOptions();
        const current = options.find((item: any) => item.key === this.editForm.domain_target_key || Number(item.port) === Number(this.editForm.domain_target_port));
        const selected = current || options[0];
        if (selected) {
            this.editForm.domain_target_key = selected.key;
            this.editForm.domain_target_port = selected.port;
        }
    }

    public selectEditDomainTarget(key: string) {
        const option = this.editDomainTargetOptions().find((item: any) => item.key === key);
        this.editForm.domain_target_key = key;
        this.editForm.domain_target_port = option?.port || 80;
    }

    public editSelectedZone() {
        return this.zones().find((zone: any) => zone.id === this.editForm.zone_id) || null;
    }

    public setEditDomainMode(mode: 'none' | 'registered') {
        this.editForm.domain_mode = mode;
        if (mode === 'registered' && !this.editForm.zone_id && this.zones()[0]) {
            this.editForm.zone_id = this.zones()[0].id;
        }
        this.syncEditDomain();
    }

    public selectEditZone(zoneId: string) {
        this.editForm.zone_id = zoneId || '';
        this.syncEditDomain();
    }

    public syncEditDomain() {
        if (this.editForm.domain_mode !== 'registered') {
            this.editForm.domain = '';
            return;
        }
        const zone = this.editSelectedZone();
        if (!zone?.domain) return;
        const prefix = this.domainPrefixForZone(zone, this.editForm.domain_prefix, this.editForm.name);
        if (this.isDdnsZone(zone) && !String(this.editForm.domain_prefix || '').trim()) {
            this.editForm.domain_prefix = prefix;
        }
        this.editForm.domain = prefix ? `${prefix}.${zone.domain}` : zone.domain;
    }

    public editDomainPreview() {
        if (this.editForm.domain_mode !== 'registered') return '도메인 사용 안 함';
        this.syncEditDomain();
        return this.editForm.domain || '도메인 선택 필요';
    }

    public editImageRef(item: any) {
        const tag = String(item?.image_tag || 'latest').trim();
        return tag.startsWith('sha256:') ? `${item.image_name}@${tag}` : `${item.image_name}:${tag}`;
    }

    public addEditPort(item: any) {
        item.ports = item.ports || [];
        item.ports.push({ target: 80, protocol: 'tcp' });
        this.ensureEditDomainTarget();
    }

    public removeEditPort(item: any, index: number) {
        item.ports.splice(index, 1);
        this.ensureEditDomainTarget();
    }

    public addEditEnv(item: any) {
        item.env_vars = item.env_vars || [];
        item.env_vars.push({ key: '', value: '' });
    }

    public removeEditEnv(item: any, index: number) {
        item.env_vars.splice(index, 1);
    }

    public addEditVolume(item: any) {
        item.volumes = item.volumes || [];
        item.volumes.push({ source: `${item.key}_data`, target: '/data' });
    }

    public removeEditVolume(item: any, index: number) {
        item.volumes.splice(index, 1);
    }

    private applyEditAiDraft(draft: any) {
        const serviceId = this.editForm.service_id;
        if (draft?.form) {
            this.editForm = {
                ...this.editForm,
                ...draft.form,
                service_id: serviceId,
            };
        }
        if (Array.isArray(draft?.components) && draft.components.length) {
            this.editComponents = draft.components;
            this.editAdvancedSettings.set(true);
        }
        this.ensureEditDomainTarget();
        this.syncEditDomain();
    }

    public async generateEditServiceWithAi() {
        const intent = String(this.editAiIntent() || '').trim();
        const operatorComment = String(this.editOperatorComment() || '').trim();
        if (!intent) {
            await this.alert('AI 요청 내용을 입력해주세요.');
            return;
        }
        if (!this.editComponents.length) {
            await this.alert('서비스 구성을 불러오지 못했습니다.');
            return;
        }
        if (!(await this.ensureAiModelOptions())) {
            await this.alert(this.aiUnavailableMessage() || '시스템 설정에서 사용할 AI 모델을 먼저 켜주세요.');
            return;
        }
        this.editAiBusy.set(true);
        this.resetEditAiStream();
        try {
            await this.streamEditAi('stream_service_ai', {
                mode: 'service_update',
                intent,
                operator_comment: operatorComment,
                model_ref: this.editAiModelRef() || this.aiDefaultModelRef() || 'auto',
                form: this.editForm,
                components: this.editComponents,
                base_content: this.detail()?.compose_content || '',
                zones: this.zones(),
                service: this.detail()?.service || {},
            }, async (data: any) => {
                this.editAiResult = data;
                this.applyEditAiDraft(data?.draft);
            });
            await this.alert(this.editAiResult?.summary || 'AI 수정안을 적용했습니다. 저장 전 내용을 검토하세요.', 'success');
        } catch (error: any) {
            await this.alert(error?.message || 'AI 수정안을 생성할 수 없습니다.');
        }
        this.editAiBusy.set(false);
        await this.service.render();
    }

    private editPayload() {
        this.syncEditDomain();
        this.ensureEditDomainTarget();
        const target = this.editDomainTargetOptions().find((item: any) => item.key === this.editForm.domain_target_key);
        return {
            ...this.editForm,
            operator_comment: String(this.editOperatorComment() || '').trim(),
            base_content: this.detail()?.compose_content || '',
            components: this.editComponents,
            port: this.editForm.domain_target_port,
            domain_metadata: target ? {
                compose_service: target.service_key,
                target_port: target.port,
                published_port: target.port,
                zone_id: this.editForm.zone_id,
            } : {},
            wizard: { components: this.editComponents, domain_mode: this.editForm.domain_mode },
        };
    }

    private formatPreflightError(data: any) {
        const preflight = data?.preflight || data?.result?.preflight;
        const blocking = preflight?.blocking || [];
        if (blocking.length) {
            return ['서비스 수정 전에 아래 항목을 확인해야 합니다.', ...blocking.map((item: any) => `- ${item.title}: ${item.message}`)].join('\n');
        }
        return this.formatComposeError(data, data?.message || '서비스를 수정할 수 없습니다.');
    }

    public async saveEditService(deployAfterSave: boolean = false) {
        if (this.editBusy()) return;
        if (!String(this.editForm.name || '').trim()) {
            await this.alert('서비스 이름을 입력해주세요.');
            return;
        }
        if (this.editComponents.some((item: any) => !String(item.image_name || '').trim() || !String(item.image_tag || '').trim())) {
            await this.alert('모든 구성의 이미지 이름과 버전을 입력해주세요.');
            return;
        }
        this.editBusy.set(true);
        const { code, data } = await wiz.call('update_service', this.editPayload());
        if (code !== 200) {
            this.editBusy.set(false);
            await this.alert(this.formatPreflightError(data));
            return;
        }
        this.applyDetail(data);
        this.editModalOpen.set(false);
        const serviceId = data.service?.id || this.selected()?.id;
        await this.load(serviceId);
        if (deployAfterSave && serviceId) {
            await this.deployService(serviceId, false);
        } else {
            await this.alert('서비스 수정 내용을 저장했습니다. 적용 버튼을 누르면 서버에 반영됩니다.', 'success');
        }
        this.editBusy.set(false);
        await this.service.render();
    }

    private async deployService(serviceId: string, fromCreate: boolean = false, options: any = {}) {
        this.busy.set(true);
        const { code, data } = await wiz.call('deploy_service_background', {
            service_id: serviceId,
            ...(options || {}),
        });
        if ([200, 202].includes(code)) {
            const operation = data?.operation || data?.result?.operation || null;
            const service = data?.service || data?.result?.service || null;
            if (service?.id && this.selected()?.id === service.id) this.selected.set({ ...this.selected(), ...service });
            const message = fromCreate
                ? '서비스를 저장했고 배포는 백그라운드에서 시작했습니다. 처리 로그에서 진행 상태를 확인할 수 있습니다.'
                : '서비스 배포를 백그라운드에서 시작했습니다. 처리 로그에서 진행 상태를 확인할 수 있습니다.';
            if (operation?.id) {
                await this.openOperationModal(operation, false);
            } else {
                await this.alert(message, 'success');
            }
        } else {
            await this.alert(data?.message || '서비스 배포에 실패했습니다.');
            if (serviceId) await this.load(serviceId);
        }
        this.busy.set(false);
        await this.service.render();
    }

    public async openFileBrowser() {
        if (!this.selected()?.id) return;
        this.fileBrowserOpen.set(true);
        this.filePreviewOpen.set(false);
        await this.browseFiles('.');
    }

    public async refreshImageRecords() {
        const serviceId = this.selected()?.id;
        if (!serviceId || this.busy()) return;
        this.busy.set(true);
        const { code, data } = await wiz.call('refresh_image_records', { service_id: serviceId });
        if (code === 200) {
            this.applyDetail(data);
            await this.alert('서비스 이미지 이력을 갱신했습니다.', 'success');
        } else {
            await this.alert(data?.message || '서비스 이미지 이력을 갱신할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public async restoreImageBackup(item: any) {
        const serviceId = this.selected()?.id;
        if (!serviceId || !item?.id || this.busy()) return;
        const target = item.backup_ref || item.image_ref;
        const ok = await this.confirm(`${item.compose_service} 구성을 ${target} 이미지 기준으로 되돌립니다.\n\n접속 주소는 유지되고, 실제 서버 반영은 다시 적용을 실행해야 합니다.`, '이미지 복원', 'warning');
        if (!ok) return;
        this.busy.set(true);
        const { code, data } = await wiz.call('restore_image_backup', { service_id: serviceId, backup_id: item.id });
        if (code === 200) {
            this.applyDetail(data);
            await this.alert('서비스 이미지 설정을 복원했습니다.', 'success');
        } else {
            await this.alert(data?.message || '서비스 이미지를 복원할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public openReleaseModal() {
        if (!this.selected()?.id || this.releaseBusy()) return;
        this.releaseIncludeSnapshots.set(false);
        this.releaseComment.set('');
        this.releaseModalOpen.set(true);
    }

    public closeReleaseModal() {
        if (this.releaseBusy()) return;
        this.releaseModalOpen.set(false);
        this.releaseIncludeSnapshots.set(false);
        this.releaseComment.set('');
    }

    public setReleaseIncludeSnapshots(value: boolean) {
        if (value && !this.backupSystemCanBackup()) return;
        this.releaseIncludeSnapshots.set(value);
    }

    public releaseSnapshotOptionTitle() {
        if (this.backupSystemCanBackup()) return '릴리즈 직후 현재 실행 컨테이너를 스냅샷으로 백업합니다.';
        return '백업 시스템이 실행 중일 때 선택할 수 있습니다.';
    }

    public releaseModeLabel() {
        return this.releaseIncludeSnapshots() ? 'Compose + 스냅샷' : 'Compose만';
    }

    public async runRelease() {
        const serviceId = this.selected()?.id;
        if (!serviceId || this.releaseBusy()) return;
        this.releaseBusy.set(true);
        const includeSnapshots = this.releaseIncludeSnapshots();
        const { code, data } = await wiz.call('release_service', {
            service_id: serviceId,
            include_snapshots: includeSnapshots,
            snapshot_pause: true,
            comment: this.releaseComment(),
        });
        if (![200, 202].includes(code)) {
            this.releaseBusy.set(false);
            await this.alert(this.formatComposeError(data, '서비스를 릴리즈할 수 없습니다.'));
            await this.service.render();
            return;
        }
        this.applyDetail(data);
        this.releaseModalOpen.set(false);
        this.releaseBusy.set(false);
        const operation = data.snapshot_operation || data.operation || data.result?.operation;
        if (includeSnapshots && operation?.id) {
            await this.openOperationModal(operation, false);
        } else {
            await this.alert('현재 Compose를 릴리즈 버전으로 기록했습니다.', 'success');
        }
        await this.service.render();
    }

    public async openRollbackModal(version: any) {
        const serviceId = this.selected()?.id;
        if (!serviceId || !version?.id || this.rollbackBusy()) return;
        this.rollbackTarget.set(version);
        this.rollbackPlan.set(null);
        this.rollbackModalOpen.set(true);
        this.rollbackBusy.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('rollback_plan', { service_id: serviceId, version_id: version.id });
        this.rollbackBusy.set(false);
        if (code === 200) {
            this.rollbackPlan.set(data);
        } else {
            this.rollbackModalOpen.set(false);
            await this.alert(this.formatComposeError(data, '되돌리기 영향을 확인할 수 없습니다.'));
        }
        await this.service.render();
    }

    public closeRollbackModal() {
        if (this.rollbackBusy()) return;
        this.rollbackModalOpen.set(false);
        this.rollbackTarget.set(null);
        this.rollbackPlan.set(null);
    }

    public rollbackSummaryItems() {
        const summary = this.rollbackPlan()?.summary || {};
        return [
            { label: '대상 버전', value: `버전 ${this.rollbackTarget()?.version || '-'}` },
            { label: '구성 수', value: `${summary.services || 0}개` },
            { label: '이미지 변경', value: `${summary.image_changes || 0}개` },
            { label: '이미지 롤백', value: this.rollbackImageRestoreValue() },
            { label: '포트 변경', value: `${summary.port_changes || 0}개` },
            { label: '추가/제거', value: `${summary.added_services || 0}개 추가 · ${summary.removed_services || 0}개 제거` },
            { label: '도메인 주의', value: `${summary.domain_warnings || 0}개` },
        ];
    }

    public backupSystemStatus() {
        return this.rollbackPlan()?.backup_system || this.detail()?.backup_system || {};
    }

    public backupSystemEnabled() {
        return Boolean(this.backupSystemStatus()?.enabled);
    }

    public backupSystemCanBackup() {
        const status = this.backupSystemStatus();
        return Boolean(status?.enabled && status?.status === 'running');
    }

    public serviceSnapshotBackupTitle() {
        if (this.backupSystemCanBackup()) {
            return '실행 중인 컨테이너를 스냅샷으로 백업합니다.';
        }
        return '백업 시스템이 실행 중일 때 사용할 수 있습니다.';
    }

    public versionRollbackHint() {
        if (this.backupSystemEnabled()) {
            return '수동 릴리즈한 버전만 이력에 남고, 스냅샷이 있는 버전은 이미지까지 함께 되돌릴 수 있습니다.';
        }
        return '릴리즈 버튼으로 현재 Compose를 되돌릴 수 있는 버전으로 확정합니다.';
    }

    public backupSystemBadgeText() {
        const status = this.backupSystemStatus();
        if (!status?.enabled) return '이미지 롤백 꺼짐';
        if (status?.status === 'running') return '이미지 롤백 가능';
        return `백업 저장소 ${status?.status || '확인 필요'}`;
    }

    public backupSystemBadgeClass() {
        const status = this.backupSystemStatus();
        if (status?.enabled && status?.status === 'running') {
            return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        }
        if (status?.enabled) {
            return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        }
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300';
    }

    public rollbackImageRestoreSummary() {
        return this.rollbackPlan()?.image_restore || {};
    }

    public rollbackImageRestoreRows() {
        return this.rollbackImageRestoreSummary()?.items || [];
    }

    public rollbackImageRestoreValue() {
        const restore = this.rollbackImageRestoreSummary();
        const count = Number(restore.available_count || 0);
        if (count > 0) {
            const snapshotCount = Number(restore.snapshot_count || 0);
            if (snapshotCount > 0) return snapshotCount === count ? `스냅샷 ${snapshotCount}개` : `스냅샷 ${snapshotCount}개 포함`;
            return `${count}개 가능`;
        }
        if (!this.backupSystemEnabled()) return '꺼짐';
        return '백업 없음';
    }

    public rollbackImageRestoreText() {
        const restore = this.rollbackImageRestoreSummary();
        const count = Number(restore.available_count || 0);
        if (count > 0) {
            const snapshotCount = Number(restore.snapshot_count || 0);
            if (snapshotCount > 0) {
                const backupCount = Math.max(0, count - snapshotCount);
                return backupCount > 0
                    ? `저장된 컨테이너 스냅샷 ${snapshotCount}개와 이미지 백업 ${backupCount}개를 Compose에 함께 반영합니다.`
                    : `저장된 컨테이너 스냅샷 ${snapshotCount}개를 Compose에 함께 반영합니다.`;
            }
            return `백업 저장소에 백업된 이미지 ${count}개를 Compose에 함께 반영합니다.`;
        }
        if (!this.backupSystemEnabled()) return '백업 저장소가 꺼져 있어 Compose 설정만 되돌립니다.';
        return '이 Compose 버전에 연결된 이미지 백업이 없어 Compose 설정만 되돌립니다.';
    }

    public rollbackImageRestoreClass() {
        const restore = this.rollbackImageRestoreSummary();
        if (Number(restore.available_count || 0) > 0) {
            return 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/70 dark:bg-emerald-950/30 dark:text-emerald-200';
        }
        if (this.backupSystemEnabled()) {
            return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-200';
        }
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300';
    }

    public rollbackImageChanges() {
        return this.rollbackPlan()?.changes?.image_changes || [];
    }

    public rollbackPortChanges() {
        return this.rollbackPlan()?.changes?.port_changes || [];
    }

    public rollbackDomainImpacts() {
        return this.rollbackPlan()?.changes?.domain_impacts || [];
    }

    public rollbackServiceList(key: string) {
        return this.rollbackPlan()?.changes?.[key] || [];
    }

    public rollbackPortLabels(values: any[]) {
        return (values || []).length ? values.join(', ') : '없음';
    }

    public async runRollback(deployAfterRollback: boolean = true) {
        const serviceId = this.selected()?.id;
        const versionId = this.rollbackTarget()?.id;
        if (!serviceId || !versionId || this.rollbackBusy()) return;
        this.rollbackBusy.set(true);
        const { code, data } = await wiz.call('rollback_service', { service_id: serviceId, version_id: versionId, restore_images: true });
        if (code !== 200) {
            this.rollbackBusy.set(false);
            await this.alert(this.formatComposeError(data, '서비스를 되돌릴 수 없습니다.'));
            await this.service.render();
            return;
        }
        this.applyDetail(data);
        this.rollbackModalOpen.set(false);
        this.rollbackBusy.set(false);
        const nextServiceId = data.service?.id || serviceId;
        await this.load(nextServiceId);
        if (deployAfterRollback) {
            const imageRestoreCount = Number(data.result?.operation?.result_payload?.image_restore_count || 0);
            await this.deployService(nextServiceId, false, {
                force_recreate: true,
                ensure_backup_registry: imageRestoreCount > 0,
                deployment_reason: 'compose_rollback',
            });
        } else {
            await this.alert('선택한 버전으로 되돌렸습니다. 적용 버튼을 누르면 서버에 반영됩니다.', 'success');
        }
        await this.service.render();
    }

    public async backupServiceImage(item: any) {
        const serviceId = this.selected()?.id;
        if (!serviceId || !item?.id || this.busy()) return;
        const ok = await this.confirm(`${item.image_ref} 이미지를 서비스 백업 시스템에 저장합니다. 이미지 크기에 따라 시간이 걸릴 수 있습니다.`, '백업 실행', 'warning');
        if (!ok) return;
        this.busy.set(true);
        const { code, data } = await wiz.call('backup_service_image', { service_id: serviceId, backup_id: item.id });
        if (code === 200) {
            this.applyDetail(data);
            await this.alert('이미지 백업을 완료했습니다.', 'success');
        } else {
            await this.alert(data?.message || '이미지를 백업할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public async snapshotSelectedService() {
        const serviceId = this.selected()?.id;
        if (!serviceId || this.busy() || !this.backupSystemCanBackup()) return;
        const ok = await this.confirm('현재 서비스의 실행 중인 컨테이너를 스냅샷으로 백업합니다.\n\n파일 상태까지 저장하기 위해 컨테이너가 잠깐 일시 정지될 수 있으며, 그 동안 서비스 응답이 일시적으로 지연될 수 있습니다. 진행할까요?', '스냅샷 백업', 'warning');
        if (!ok) return;
        this.busy.set(true);
        const { code, data } = await wiz.call('snapshot_service_image', { service_id: serviceId, pause: true, background: true });
        this.busy.set(false);
        if (code === 200) {
            if (data?.service) this.selected.set(data.service);
            if (data?.operation) {
                await this.openOperationModal(data.operation);
            } else {
                await this.alert('서비스 스냅샷 백업을 시작했습니다.', 'success');
            }
        } else {
            await this.alert(this.snapshotBackupErrorMessage(data, '서비스 스냅샷을 백업할 수 없습니다.'));
        }
        await this.service.render();
    }

    public async snapshotServiceImage(item: any) {
        const serviceId = this.selected()?.id;
        if (!serviceId || !item?.id || this.busy()) return;
        const ok = await this.confirm(`${item.compose_service} 컨테이너를 현재 상태 그대로 스냅샷 백업합니다.\n\n파일 상태까지 저장하기 위해 실행 중인 컨테이너가 잠깐 일시 정지될 수 있습니다. 접속이 중요한 시간대라면 나중에 실행해주세요.`, '스냅샷 백업', 'warning');
        if (!ok) return;
        this.busy.set(true);
        const { code, data } = await wiz.call('snapshot_service_image', { service_id: serviceId, backup_id: item.id, pause: true, background: true });
        this.busy.set(false);
        if (code === 200) {
            if (data?.service) this.selected.set(data.service);
            if (data?.operation) {
                await this.openOperationModal(data.operation);
            } else {
                await this.alert('컨테이너 스냅샷 백업을 시작했습니다.', 'success');
            }
        } else {
            await this.alert(this.snapshotBackupErrorMessage(data, '컨테이너 스냅샷을 백업할 수 없습니다.'));
        }
        await this.service.render();
    }

    public backupKindLabel(item: any) {
        return item?.source === 'container_snapshot' ? '스냅샷' : '이미지';
    }

    public async openOperationModal(operation: any, refreshNow: boolean = true) {
        if (!operation?.id) return;
        this.operationDetail.set(operation);
        this.operationModalOpen.set(true);
        if (refreshNow) await this.refreshOperationDetail();
        else await this.service.render();
        this.startOperationPolling();
    }

    public closeOperationModal() {
        this.stopOperationPolling();
        this.operationModalOpen.set(false);
        this.operationDetail.set(null);
    }

    private startOperationPolling() {
        this.stopOperationPolling();
        if (!this.isActiveOperation(this.operationDetail())) return;
        this.operationPollTimer = setInterval(async () => {
            await this.refreshOperationDetail(false);
            if (!this.isActiveOperation(this.operationDetail())) this.stopOperationPolling();
        }, 2000);
    }

    private stopOperationPolling() {
        if (this.operationPollTimer) {
            clearInterval(this.operationPollTimer);
            this.operationPollTimer = null;
        }
    }

    public async refreshOperationDetail(showBusy: boolean = true) {
        const operationId = this.operationDetail()?.id;
        if (!operationId) return;
        if (showBusy) this.operationBusy.set(true);
        const { code, data } = await wiz.call('operation_detail', { operation_id: operationId });
        if (code === 200) {
            const operation = data.operation || null;
            this.operationDetail.set(operation);
            if (operation && !this.isActiveOperation(operation) && this.selected()?.id) {
                const endpoint = ['source', 'versions'].includes(this.detailTab()) ? 'detail_service_advanced' : 'detail_service';
                const detailResult = await wiz.call(endpoint, { service_id: this.selected().id });
                if (detailResult.code === 200) this.applyDetail(detailResult.data);
            }
        } else if (showBusy) {
            await this.alert(data?.message || '처리 내역을 불러올 수 없습니다.');
        }
        this.operationBusy.set(false);
        await this.service.render();
    }

    public operationOutput() {
        const rows = (this.operationDetail()?.output || []).map((item: any) => {
            const message = this.normalizeMcpToolExposureMessage(item?.message || '');
            if (message === item?.message) return item;
            return {
                ...item,
                message,
                stream: item?.stream === 'stderr' ? 'system' : item?.stream,
                metadata: {
                    ...(item?.metadata || {}),
                    step: item?.metadata?.step || 'ai tool fallback',
                    normalized_mcp_tool_exposure: true,
                },
            };
        });
        const compacted: any[] = [];
        let lastKey = '';
        let lastItem: any = null;
        let duplicateCount = 0;
        const flush = () => {
            if (duplicateCount > 0 && lastItem) {
                compacted.push({
                    ...lastItem,
                    message: `동일한 로그 ${duplicateCount}회를 생략했습니다.`,
                    stream: 'system',
                    metadata: {
                        ...(lastItem.metadata || {}),
                        suppressed_duplicate_logs: duplicateCount,
                    },
                });
            }
            duplicateCount = 0;
        };
        for (const item of rows) {
            const key = `${item?.stream || ''}|${item?.message || ''}|${item?.metadata?.step || ''}`;
            if (lastItem && key === lastKey && !String(item?.message || '').includes('생략했습니다')) {
                duplicateCount += 1;
                continue;
            }
            flush();
            compacted.push(item);
            lastItem = item;
            lastKey = key;
        }
        flush();
        return compacted;
    }

    public operationStreamClass(stream: string) {
        if (stream === 'stderr') return 'text-rose-300';
        if (stream === 'system') return 'text-amber-200';
        return 'text-zinc-100';
    }

    public serviceFileTreeContext() {
        return { service_id: this.selected()?.id || '' };
    }

    public closeFileBrowser() {
        if (this.fileBrowserBusy()) return;
        this.fileBrowserOpen.set(false);
        this.fileBrowserPath.set('.');
        this.fileBrowserItems.set([]);
    }

    public async browseFiles(path: string) {
        const serviceId = this.selected()?.id;
        if (!serviceId) return;
        this.fileBrowserBusy.set(true);
        const { code, data } = await wiz.call('browse_files', { service_id: serviceId, path });
        if (code === 200) {
            this.fileBrowserPath.set(data.path || '.');
            this.fileBrowserItems.set(data.items || []);
        } else {
            await this.alert(data?.message || '서비스 파일 목록을 불러올 수 없습니다.');
        }
        this.fileBrowserBusy.set(false);
        await this.service.render();
    }

    public async openFile(item: any) {
        if (!item || item.type !== 'file') return;
        const serviceId = this.selected()?.id;
        if (!serviceId) return;
        this.filePreviewBusy.set(true);
        const { code, data } = await wiz.call('read_file', { service_id: serviceId, path: item.path });
        if (code === 200) {
            this.filePreviewTitle.set(item.path);
            this.filePreviewContent.set(data.content || '');
            this.filePreviewOpen.set(true);
        } else {
            await this.alert(data?.message || '파일 내용을 불러올 수 없습니다.');
        }
        this.filePreviewBusy.set(false);
        await this.service.render();
    }

    public closeFilePreview() {
        this.filePreviewOpen.set(false);
        this.filePreviewTitle.set('');
        this.filePreviewContent.set('');
    }

    public fileBrowserParent() {
        const current = this.fileBrowserPath();
        if (!current || current === '.') return '';
        const parts = current.split('/').filter(Boolean);
        if (parts.length <= 1) return '.';
        return parts.slice(0, -1).join('/');
    }

    public fileBrowserCrumbs() {
        const current = this.fileBrowserPath();
        const parts = current === '.' ? [] : current.split('/').filter(Boolean);
        const crumbs = [{ label: this.selected()?.namespace || 'root', path: '.' }];
        let currentPath = '';
        for (const part of parts) {
            currentPath = currentPath ? `${currentPath}/${part}` : part;
            crumbs.push({ label: part, path: currentPath });
        }
        return crumbs;
    }

    public isSelected(service: any) {
        return this.selected()?.id === service?.id;
    }

    public serviceDescription(service: any) {
        return service?.metadata?.description || service?.description || '설명이 없습니다.';
    }

    public servicePrimaryDomain(service: any) {
        return service?.primary_domain || (Number(service?.domain_count || 0) > 0 ? '도메인 연결됨' : '도메인 미연결');
    }

    public serviceListMeta(service: any) {
        const domain = this.servicePrimaryDomain(service);
        const changed = this.formatDate(service?.updated_at || service?.created_at);
        return `${domain} · 최근 변경 ${changed}`;
    }

    public primaryDomain() {
        const domains = this.detail()?.domains || [];
        return domains.length ? domains[0] : null;
    }

    public primaryDomainText() {
        const domain = this.primaryDomain();
        return domain?.domain || '아직 연결된 주소가 없습니다.';
    }

    public domainHref(domain: any) {
        const value = typeof domain === 'string' ? domain : domain?.domain;
        return value ? `https://${value}` : '';
    }

    public deployActionLabel() {
        return '다시 적용';
    }

    public serviceStateTitle() {
        const operation = this.latestOperation();
        if (this.isActiveOperation(operation)) return '작업이 진행 중입니다.';
        const summary = this.runtimeContainerSummary();
        const total = Number(summary.total || 0);
        const running = Number(summary.running || 0);
        if (total > 0 && running === total) return '컨테이너가 실행 중입니다.';
        if (total > 0 && running > 0) return `${running}/${total}개 컨테이너 실행 중`;
        if (this.primaryDomain()) return '접속 주소가 연결되어 있습니다.';
        return '실행 상태를 확인하세요.';
    }

    public serviceStateMessage() {
        const operation = this.latestOperation();
        if (this.isActiveOperation(operation)) {
            return operation?.message || '처리 로그에서 진행 상태를 확인할 수 있습니다.';
        }
        const checkedAt = this.runtimeStatus()?.checked_at;
        const checkedText = checkedAt ? `상태 확인 ${this.formatDate(checkedAt)}` : '';
        const summary = this.runtimeContainerSummary();
        const total = Number(summary.total || 0);
        const running = Number(summary.running || 0);
        const domains = this.runtimeDomainSummary();
        if (this.primaryDomain() && Number(domains.nginx_configured || 0) > 0) {
            return checkedText ? `nginx 연결 확인됨 · ${checkedText}` : 'nginx 연결 설정이 확인되었습니다.';
        }
        if (total > 0) {
            const text = `${running}/${total}개 컨테이너 실행 중`;
            return checkedText ? `${text} · ${checkedText}` : text;
        }
        if (this.primaryDomain()) return '접속 주소가 등록되어 있습니다. 실행 탭에서 컨테이너 상태를 확인하세요.';
        return '상태 확인을 눌러 실제 컨테이너와 연결 정보를 갱신하세요.';
    }

    public backupSummary() {
        const rows = this.detail()?.image_backups || [];
        if (!rows.length) return '백업 기록 없음';
        const succeeded = rows.filter((item: any) => item.backup_status === 'backup_succeeded').length;
        if (succeeded > 0) return `${succeeded}개 백업됨`;
        return `${rows.length}개 백업 대기`;
    }

    public backupActionHint(item: any) {
        if (item?.source === 'container_snapshot') {
            return '이미 저장된 현재 상태 백업입니다. 필요하면 이 버전으로 되돌릴 수 있습니다.';
        }
        if (item?.backup_status === 'backup_succeeded') {
            return '이미지 백업이 완료되었습니다. 실행 중인 서비스에는 영향을 주지 않습니다.';
        }
        if (item?.backup_status === 'backup_failed') {
            return '최근 백업이 실패했습니다. 다시 실행하면 이미지 저장소에 재시도합니다.';
        }
        return '이미지 백업은 서비스 중단 없이 실행됩니다. 현재 상태 백업은 컨테이너를 잠깐 멈출 수 있습니다.';
    }

    public detailTabs() {
        return [
            { key: 'overview', label: '구성', icon: 'fa-diagram-project' },
            { key: 'logs', label: '로그', icon: 'fa-terminal' },
            { key: 'source', label: 'Compose/Nginx', icon: 'fa-code' },
            { key: 'files', label: '서비스 파일', icon: 'fa-folder-tree' },
            { key: 'versions', label: '버전 이력', icon: 'fa-clock-rotate-left' },
        ];
    }

    public async setDetailTab(tab: any) {
        if (!['overview', 'logs', 'source', 'files', 'versions'].includes(tab)) return;
        this.detailTab.set(tab);
        await this.service.render();
        await this.loadDetailSection(tab);
    }

    public serviceFlow() {
        return this.detail()?.service_flow || {};
    }

    public serviceFlowPaths() {
        return this.serviceFlow()?.public_paths || [];
    }

    public serviceFlowWarnings() {
        return this.serviceFlow()?.warnings || [];
    }

    public serviceFlowUnexposedNodes() {
        return this.serviceFlow()?.unexposed_nodes || [];
    }

    public flowNodeIcon(node: any) {
        const type = node?.type;
        const role = String(node?.role || '').toLowerCase();
        const key = String(node?.key || node?.label || '').toLowerCase();
        if (type === 'actor') return 'fa-user';
        if (type === 'domain') return 'fa-globe';
        if (type === 'port') return 'fa-network-wired';
        if (type === 'firewall') return 'fa-shield-halved';
        if (type === 'server') return 'fa-server';
        if (type === 'proxy') return 'fa-shield-halved';
        if (role === 'public') return 'fa-window-maximize';
        if (key.includes('db') || key.includes('postgres') || key.includes('mysql') || key.includes('mariadb')) return 'fa-database';
        if (key.includes('redis') || key.includes('cache')) return 'fa-memory';
        return 'fa-cube';
    }

    public flowNodeClass(node: any) {
        const type = node?.type;
        if (type === 'actor') return 'border-zinc-300 bg-zinc-50 text-zinc-800 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100';
        if (type === 'firewall') return 'border-violet-300 bg-violet-50 text-violet-900 dark:border-violet-900/70 dark:bg-violet-950/50 dark:text-violet-100';
        if (type === 'server') return 'border-indigo-200 bg-indigo-50 text-indigo-800 dark:border-indigo-900/70 dark:bg-indigo-950/40 dark:text-indigo-200';
        if (type === 'domain' || type === 'port') return 'border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-200';
        if (type === 'proxy') return 'border-violet-200 bg-violet-50 text-violet-800 dark:border-violet-900/70 dark:bg-violet-950/40 dark:text-violet-200';
        const status = node?.containers?.status;
        if (status === 'running') return 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-200';
        if (status === 'pending') return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-200';
        if (status === 'failed') return 'border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200';
        return 'border-zinc-200 bg-white text-zinc-800 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100';
    }

    public flowNodeStatusText(node: any) {
        if (node?.type !== 'service') return node?.subtitle || '';
        return node?.containers?.label || '상태 확인 전';
    }

    public flowNodePortText(node: any) {
        const ports = (node?.ports || []).filter((port: any) => port);
        if (!ports.length) return '외부 포트 없음';
        return ports.map((port: any) => port.label || `${port.published || '내부'} -> ${port.target}/${port.protocol || 'tcp'}`).join(' · ');
    }

    public flowImageText(node: any) {
        const image = String(node?.image || '').trim();
        if (!image) return '';
        return image.length > 56 ? `${image.slice(0, 53)}...` : image;
    }

    private flowSpread(index: number, total: number, min: number = 150, max: number = 280) {
        if (total <= 1) return Math.round((min + max) / 2);
        return Math.round(min + ((max - min) * index) / Math.max(1, total - 1));
    }

    private flowCanvasEdge(from: any, to: any, label: string, color: string = '#94a3b8', dashed: boolean = false) {
        const x1 = from.x + from.w;
        const y1 = from.y + Math.round(from.h / 2);
        const x2 = to.x;
        const y2 = to.y + Math.round(to.h / 2);
        const mid = Math.round((x1 + x2) / 2);
        return {
            from: from.id,
            to: to.id,
            label,
            color,
            dashed,
            path: `M ${x1} ${y1} H ${mid} V ${y2} H ${x2}`,
            labelX: mid,
            labelY: Math.round((y1 + y2) / 2) - 8,
        };
    }

    private flowServerFromPath(path: any) {
        const route = String(path?.proxy?.route || '').trim();
        const chunks = route.split('·').map((item: string) => item.trim()).filter((item: string) => item);
        const fallback = this.runtimeServerNames()[0] || '연결 서버';
        const label = chunks.length > 1 ? chunks[chunks.length - 1] : fallback;
        return {
            id: `server:${label}`,
            type: 'server',
            label,
            subtitle: '등록 서버',
            route: chunks[0] || route || 'nginx upstream',
        };
    }

    public flowCanvasLayers() {
        return [
            { label: '사용자', x: 48, width: 140 },
            { label: '접속 주소', x: 230, width: 160 },
            { label: 'Docker Infra', x: 430, width: 160 },
            { label: '서비스', x: 630, width: 160 },
            { label: '내부 구성', x: 805, width: 145 },
        ];
    }

    public flowCanvasLayerStyle(layer: any) {
        return {
            left: `${layer.x}px`,
            width: `${layer.width}px`,
        };
    }

    public flowCanvas() {
        const paths = this.serviceFlowPaths();
        const unexposed = this.serviceFlowUnexposedNodes();
        const nodes: any[] = [];
        const badges: any[] = [];
        const nodeMap: any = {};
        const addNode = (id: string, source: any, x: number, y: number, w: number = 168, h: number = 86) => {
            if (!id) return null;
            if (nodeMap[id]) return nodeMap[id];
            const node = { ...(source || {}), id, x, y, w, h };
            nodeMap[id] = node;
            nodes.push(node);
            return node;
        };

        const actor = addNode('actor:user', this.serviceFlow()?.actor || { type: 'actor', label: '사용자', subtitle: '브라우저 접속' }, 52, 58, 180, 72);
        paths.forEach((path: any, index: number) => {
            const entry = path.entry || {};
            badges.push({
                id: entry.id || `badge:${index}`,
                type: 'domain',
                label: entry.label || '접속 주소',
                subtitle: entry.url || entry.subtitle || '',
                x: 52,
                y: 146 + index * 36,
                w: 230,
                h: 30,
            });
        });

        const firewall = addNode('firewall:nginx', {
            type: 'firewall',
            label: 'nginx',
            subtitle: 'Docker Infra',
        }, 336, 72, 68, 248);

        const serverItems: any[] = [];
        for (const path of paths) {
            const server = this.flowServerFromPath(path);
            if (!serverItems.find((item: any) => item.id === server.id)) serverItems.push(server);
        }
        if (!serverItems.length && (paths.length || unexposed.length)) {
            serverItems.push({ id: 'server:default', type: 'server', label: this.runtimeServerNames()[0] || '서비스 서버', subtitle: '등록 서버', route: 'nginx upstream' });
        }
        serverItems.forEach((server: any, index: number) => addNode(server.id, server, 470, this.flowSpread(index, serverItems.length, 86, 150), 170, 76));

        const targetItems: any[] = [];
        for (const path of paths) {
            if (!path.target?.id) continue;
            if (!targetItems.find((item: any) => item.id === path.target.id)) targetItems.push(path.target);
        }
        targetItems.forEach((target: any, index: number) => addNode(target.id, target, 500, this.flowSpread(index, targetItems.length, 205, 292), 175, 104));

        const internalItems: any[] = [];
        for (const path of paths) {
            for (const node of path.internal_targets || []) {
                if (node?.id && !internalItems.find((item: any) => item.id === node.id)) internalItems.push(node);
            }
        }
        for (const node of unexposed || []) {
            if (node?.id && !internalItems.find((item: any) => item.id === node.id)) internalItems.push({ ...node, isolated: true });
        }
        internalItems.forEach((node: any, index: number) => addNode(node.id, node, 750, this.flowSpread(index, internalItems.length, 220, 310), 160, 96));

        const edges: any[] = [];
        for (const badge of badges) {
            if (firewall) edges.push(this.flowCanvasEdge(badge, firewall, '접속', '#38bdf8'));
        }
        for (const server of serverItems) {
            const serverNode = nodeMap[server.id];
            if (firewall && serverNode) edges.push(this.flowCanvasEdge(firewall, serverNode, 'nginx', '#8b5cf6'));
        }
        for (const path of paths) {
            const target = nodeMap[path.target?.id];
            const server = nodeMap[this.flowServerFromPath(path).id] || nodeMap[serverItems[0]?.id];
            if (server && target) edges.push(this.flowCanvasEdge(server, target, '실행', '#6366f1'));
            for (const internal of path.internal_targets || []) {
                const node = nodeMap[internal?.id];
                if (target && node) edges.push(this.flowCanvasEdge(target, node, '내부 연결', '#10b981', true));
            }
        }

        if (!paths.length && internalItems.length) {
            const first = nodeMap[internalItems[0]?.id];
            const server = nodeMap[serverItems[0]?.id];
            if (server && first) edges.push(this.flowCanvasEdge(server, first, '내부 구성', '#94a3b8', true));
        }

        return { width: 980, height: 420, nodes, badges, edges };
    }

    public flowCanvasNodeStyle(node: any) {
        return {
            left: `${node.x}px`,
            top: `${node.y}px`,
            width: `${node.w}px`,
            minHeight: `${node.h}px`,
        };
    }

    public runtimeStatus() {
        return this.detail()?.runtime_status || this.detail()?.service?.metadata?.runtime_status || {};
    }

    public runtimeContainerSummary() {
        return this.runtimeStatus()?.containers?.summary || { total: 0, running: 0, stopped: 0 };
    }

    public runtimeHealthSummary() {
        return this.runtimeStatus()?.containers?.health || {};
    }

    public runtimeStackSummary() {
        return this.runtimeStatus()?.stack?.summary || {};
    }

    public runtimeDomainSummary() {
        return this.runtimeStatus()?.domains?.summary || {};
    }

    public runtimeContainers() {
        return this.runtimeStatus()?.containers?.containers || [];
    }

    private runtimePublicServiceNames() {
        const names: string[] = [];
        const push = (value: any) => {
            const text = String(value || '').trim();
            if (text && !names.includes(text)) names.push(text);
        };
        for (const domain of this.detail()?.domains || []) {
            const metadata = domain?.metadata || {};
            push(metadata.compose_service);
        }
        for (const domain of this.runtimeDomains()) {
            push(domain?.compose_service);
            push(domain?.metadata?.compose_service);
        }
        for (const component of this.detail()?.components || []) {
            const role = String(component?.role || '').toLowerCase();
            const hasPublicPort = (component?.ports || []).some((port: any) => port?.public_endpoint);
            if (role === 'public' || hasPublicPort) {
                push(component.key);
                push(component.service_name);
                push(component.label);
            }
        }
        return names;
    }

    private runtimeContainerNameCandidates(container: any) {
        const namespace = this.detail()?.service?.namespace || '';
        const values: string[] = [];
        const push = (value: any) => {
            const text = String(value || '').trim();
            if (text && !values.includes(text)) values.push(text);
        };
        push(container?.runtime_service_name);
        push(container?.name);
        push(this.containerDisplayName(container));
        for (const value of [...values]) {
            if (namespace && value.startsWith(`${namespace}_`)) push(value.slice(namespace.length + 1));
            if (namespace && value.startsWith(`${namespace}-`)) push(value.slice(namespace.length + 1));
        }
        return values;
    }

    public isRuntimeContainerPublic(container: any) {
        const ports = container?.port_bindings || [];
        if (ports.some((port: any) => port?.published && !port?.internal_only)) return true;
        const publicNames = this.runtimePublicServiceNames();
        const candidates = this.runtimeContainerNameCandidates(container);
        return candidates.some((name: string) => publicNames.includes(name));
    }

    public runtimePublicContainers() {
        return this.runtimeContainers().filter((container: any) => this.isRuntimeContainerPublic(container));
    }

    public runtimeInternalContainers() {
        return this.runtimeContainers().filter((container: any) => !this.isRuntimeContainerPublic(container));
    }

    public containerExposureLabel(container: any) {
        return this.isRuntimeContainerPublic(container) ? '외부 오픈' : '내부 전용';
    }

    public containerExposureClass(container: any) {
        if (this.isRuntimeContainerPublic(container)) {
            return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300';
        }
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300';
    }

    public containerDisplayName(container: any) {
        const namespace = this.detail()?.service?.namespace || '';
        const raw = String(container?.runtime_service_name || container?.name || '').trim();
        if (namespace && raw.startsWith(`${namespace}_`)) return raw.slice(namespace.length + 1);
        return raw || '이름 없음';
    }

    public containerStatusLabel(container: any) {
        const state = String(container?.state || '').toLowerCase();
        const status = String(container?.status || '').toLowerCase();
        if (status.includes('unhealthy')) return '문제 있음';
        if (status.includes('health: starting')) return '시작 중';
        if (status.includes('healthy')) return '정상';
        if (state === 'running') return '실행 중';
        if (['exited', 'dead', 'created', 'paused', 'restarting'].includes(state)) {
            const labels: any = { exited: '중지됨', dead: '문제 있음', created: '생성됨', paused: '일시정지', restarting: '재시작 중' };
            return labels[state] || '확인 필요';
        }
        return state ? '확인 필요' : '상태 없음';
    }

    public containerStatusClass(container: any) {
        const label = this.containerStatusLabel(container);
        if (['정상', '실행 중'].includes(label)) return this.statusClass('running');
        if (['시작 중', '생성됨', '재시작 중'].includes(label)) return this.statusClass('pending');
        if (['문제 있음', '중지됨'].includes(label)) return this.statusClass('failed');
        return this.statusClass('');
    }

    public containerPortLabels(container: any) {
        return (container?.port_bindings || []).map((port: any) => {
            const protocol = port.protocol || 'tcp';
            if (port.internal_only) return `내부 ${port.target}/${protocol}`;
            const host = port.host && port.host !== '0.0.0.0' ? `${port.host}:` : '';
            return `${host}${port.published} -> ${port.target}/${protocol}`;
        });
    }

    public containerSignal(container: any) {
        const state = String(container?.state || '').toLowerCase();
        const status = String(container?.status || '').toLowerCase();
        if (status.includes('unhealthy')) return 'unhealthy';
        if (status.includes('health: starting')) return 'starting';
        if (status.includes('healthy')) return 'healthy';
        return state;
    }

    public canRunRuntimeContainerAction(container: any, action: string) {
        const state = this.containerSignal(container);
        if (action === 'delete') return Boolean(container?.id) && state !== 'removing';
        const allowed: any = {
            start: ['created', 'exited', 'dead'],
            restart: ['running', 'healthy', 'unhealthy', 'starting', 'paused', 'created', 'exited', 'dead'],
            stop: ['running', 'healthy', 'unhealthy', 'starting', 'paused', 'restarting'],
        };
        return Boolean(container?.id) && (allowed[action] || []).includes(state);
    }

    public runtimeContainerActionTitle(container: any, action: string) {
        const labels: any = { start: '실행', stop: '중지', restart: '재시작', delete: '삭제' };
        if (this.canRunRuntimeContainerAction(container, action)) return `${this.containerDisplayName(container)} ${labels[action]}`;
        const reasons: any = {
            start: '중지된 구성요소만 실행할 수 있습니다.',
            stop: '실행 중인 구성요소만 중지할 수 있습니다.',
            restart: '현재 상태에서는 재시작할 수 없습니다.',
            delete: '삭제할 수 없는 상태입니다.',
        };
        return reasons[action] || labels[action];
    }

    public runtimeBulkContainerTargets(action: string) {
        return this.runtimeContainers().filter((container: any) => this.canRunRuntimeContainerAction(container, action));
    }

    public canRunRuntimeBulkAction(action: string) {
        if (!['start', 'stop', 'restart'].includes(action)) return false;
        return this.runtimeBulkContainerTargets(action).length > 0;
    }

    public runtimeBulkActionTitle(action: string) {
        const labels: any = { start: '일괄 시작', stop: '일괄 중지', restart: '일괄 재시작' };
        const count = this.runtimeBulkContainerTargets(action).length;
        if (count > 0) return `${labels[action]} · 대상 ${count}개`;
        const reasons: any = {
            start: '시작할 수 있는 중지 컨테이너가 없습니다.',
            stop: '중지할 수 있는 실행 컨테이너가 없습니다.',
            restart: '재시작할 수 있는 컨테이너가 없습니다.',
        };
        return reasons[action] || labels[action];
    }

    public async runRuntimeBulkAction(action: string) {
        if (!this.canRunRuntimeBulkAction(action)) return;
        const labels: any = { start: '시작', stop: '중지', restart: '재시작' };
        const count = this.runtimeBulkContainerTargets(action).length;
        const confirmed = await this.service.modal.show({
            title: `컨테이너 일괄 ${labels[action]}`,
            message: `선택한 서비스의 대상 컨테이너 ${count}개를 일괄 ${labels[action]}합니다.`,
            cancel: '취소',
            action: `일괄 ${labels[action]}`,
            actionBtn: action === 'stop' ? 'warning' : 'primary',
            status: action === 'stop' ? 'warning' : 'info',
        });
        if (!confirmed) return;

        this.busy.set(true);
        const { code, data } = await wiz.call('service_container_bulk_action', {
            service_id: this.selected()?.id,
            action,
        });
        this.busy.set(false);
        if (code === 200) {
            this.applyDetail(data);
            const succeeded = data?.result?.succeeded_count ?? count;
            await this.alert(`컨테이너 ${succeeded}개에 일괄 ${labels[action]}을 실행했습니다.`, 'success');
        } else {
            await this.alert(data?.message || `컨테이너 일괄 ${labels[action]}을 실행할 수 없습니다.`);
        }
        await this.service.render();
    }

    public async runRuntimeContainerAction(container: any, action: string) {
        if (!this.canRunRuntimeContainerAction(container, action)) return;
        const labels: any = { start: '실행', stop: '중지', restart: '재시작', delete: '삭제' };
        const isDelete = action === 'delete';
        const confirmed = await this.service.modal.show({
            title: `구성요소 ${labels[action]}`,
            message: isDelete
                ? `${this.containerDisplayName(container)} 구성요소를 삭제합니다.\n\n실행 중이면 먼저 중지한 뒤 삭제합니다. 이 작업은 되돌릴 수 없습니다.`
                : `${this.containerDisplayName(container)} 구성요소를 ${labels[action]}합니다.`,
            cancel: '취소',
            action: labels[action],
            actionBtn: isDelete ? 'error' : (action === 'stop' ? 'warning' : 'primary'),
            status: isDelete ? 'error' : 'info',
        });
        if (!confirmed) return;

        this.busy.set(true);
        const { code, data } = await wiz.call('service_container_action', {
            service_id: this.selected()?.id,
            container_id: container.id,
            node_id: container.node_id,
            action,
        });
        this.busy.set(false);
        if (code === 200) {
            this.applyDetail(data);
            await this.alert(isDelete ? '구성요소를 삭제했습니다.' : '구성요소 동작을 실행했습니다.', 'success');
        } else {
            await this.alert(data?.message || '구성요소 동작을 실행할 수 없습니다.');
        }
        await this.service.render();
    }

    public runtimeDomains() {
        return this.runtimeStatus()?.domains?.domains || [];
    }

    public runtimeServerNames() {
        const values: string[] = [];
        const push = (value: any) => {
            const text = String(value || '').trim();
            if (text && !values.includes(text)) values.push(text);
        };
        for (const container of this.runtimeContainers()) {
            push(container?.node_name);
            if (!container?.node_name) push(container?.node_host);
        }
        for (const domain of this.runtimeDomains()) {
            push(domain?.proxy_node_display_name);
            push(domain?.proxy_registered_node_name);
        }
        for (const task of this.runtimeStatus()?.stack?.tasks || []) {
            push(task?.registered_node_label);
            push(task?.registered_node_name);
            push(task?.registered_node_host);
            push(task?.registered_node?.label);
        }
        return values;
    }

    public runtimeServerLinks() {
        const values: any[] = [];
        const push = (id: any, label: any) => {
            const nodeId = String(id || '').trim();
            if (!nodeId || values.some((item: any) => item.id === nodeId)) return;
            const text = String(label || '').trim();
            values.push({ id: nodeId, label: text || nodeId });
        };
        for (const container of this.runtimeContainers()) {
            push(container?.node_id, container?.node_name || container?.node_host);
        }
        for (const domain of this.runtimeDomains()) {
            push(domain?.proxy_registered_node_id || domain?.proxy_node_id, domain?.proxy_node_display_name || domain?.proxy_registered_node_name || domain?.proxy_registered_node_host);
        }
        for (const task of this.runtimeStatus()?.stack?.tasks || []) {
            const node = task?.registered_node || {};
            push(task?.registered_node_id || node?.id, task?.registered_node_label || node?.label || task?.registered_node_name || task?.registered_node_host || node?.name || node?.host);
        }
        return values;
    }

    public runtimeServerDetailNodeId() {
        return this.runtimeServerLinks()[0]?.id || '';
    }

    public runtimeServerDetailQueryParams() {
        const nodeId = this.runtimeServerDetailNodeId();
        return nodeId ? { node_id: nodeId } : {};
    }

    public runtimeServerDetailLinkTitle() {
        const target = this.runtimeServerLinks()[0];
        return target?.label ? `${target.label} 서버 상세로 이동` : '서버 상세로 이동';
    }

    public runtimeServerSummaryText() {
        const names = this.runtimeServerNames();
        if (names.length > 2) return `${names.slice(0, 2).join(', ')} 외 ${names.length - 2}대`;
        if (names.length > 0) return names.join(', ');
        if (!this.runtimeStatus()?.checked_at) return '상태 확인 전';
        return '서버 확인 필요';
    }

    public certificateSummaryText() {
        const runtime = this.runtimeDomainSummary();
        const total = Number(runtime.total || this.detail()?.domains?.length || 0);
        if (!total) return '도메인을 사용하지 않습니다.';
        const ssl = Number(runtime.ssl || 0);
        if (ssl > 0) return `인증서 ${ssl}/${total}개 적용`;
        const domains = this.detail()?.domains || [];
        const pending = domains.filter((item: any) => ['certbot', 'existing', 'upload'].includes(item?.ssl_mode)).length;
        if (pending > 0) return `인증서 ${pending}개 적용 대기`;
        return 'SSL 없이 연결됩니다.';
    }

    public serviceIssue() {
        const health = this.runtimeHealthSummary();
        const stack = this.runtimeStackSummary();
        const operation = this.latestOperation();
        const status = this.detail()?.service?.status || this.selected()?.status;
        if (Number(health.unhealthy || 0) > 0) {
            return {
                title: '상태 점검에 실패한 구성요소가 있습니다.',
                message: '서비스 일부가 응답하지 않습니다. 상태를 다시 확인한 뒤 계속 문제면 최근 처리 로그를 확인하세요.',
                operation,
            };
        }
        if (Number(stack.task_errors || 0) > 0) {
            return {
                title: 'Docker 배포 작업 확인이 필요합니다.',
                message: `${stack.task_errors}개 작업에서 문제가 감지되었습니다. 자동 조정 후에도 반복되면 다시 적용하거나 이전 버전으로 되돌리세요.`,
                operation,
            };
        }
        if (['failed', 'canceled'].includes(status)) {
            return {
                title: '최근 처리가 정상 완료되지 않았습니다.',
                message: operation?.message || '상태를 다시 확인하고 필요하면 서비스를 다시 적용하세요.',
                operation,
            };
        }
        return null;
    }

    public runtimeDomainProxyText(domain: any) {
        const host = domain?.proxy_host || '127.0.0.1';
        const port = domain?.published_port || domain?.target_port || '-';
        const nodeName = domain?.proxy_node_display_name || domain?.proxy_registered_node_name || '';
        const node = nodeName ? ` · ${nodeName}` : '';
        return `${host}:${port}${node}`;
    }

    public runtimeStatusText() {
        const stack = this.runtimeStackSummary();
        const containers = this.runtimeContainerSummary();
        if (!this.runtimeStatus()?.checked_at) return '아직 배포 상태를 확인하지 않았습니다.';
        if (Number(stack.task_errors || 0) > 0) return `${stack.task_errors}개 작업 확인 필요`;
        if (Number(containers.running || 0) > 0) return `컨테이너 ${containers.running}개 실행 중`;
        if (Number(stack.running || 0) > 0) return `Docker 작업 ${stack.running}개 실행 중`;
        return '실행 상태 확인 중';
    }

    public runtimeHealthText() {
        const health = this.runtimeHealthSummary();
        if (Number(health.unhealthy || 0) > 0) return `${health.unhealthy}개 이상`;
        if (Number(health.starting || 0) > 0) return `${health.starting}개 시작 중`;
        if (Number(health.healthy || 0) > 0) return `${health.healthy}개 정상`;
        if (Number(health.running || 0) > 0) return `${health.running}개 실행 중`;
        return '상태 정보 없음';
    }

    private statusKey(value: any) {
        return String(value || '').trim().toLowerCase();
    }

    public runtimeIssueOperations() {
        return (this.detail()?.operations || [])
            .filter((item: any) => ['failed', 'canceled'].includes(this.statusKey(item?.status)))
            .slice(0, 10);
    }

    private runtimeIssueSnapshot() {
        const containers = this.runtimeContainers()
            .slice(0, 30)
            .map((container: any) => ({
                id: container?.id,
                name: container?.name,
                image: container?.image,
                state: container?.state,
                status: container?.status,
                node_id: container?.node_id,
                node_name: container?.node_name,
                runtime_service_name: container?.runtime_service_name,
            }));
        const problemContainers = this.runtimeContainers()
            .filter((container: any) => !['running', 'healthy'].includes(this.containerSignal(container)))
            .slice(0, 10)
            .map((container: any) => ({
                id: container?.id,
                name: container?.name,
                image: container?.image,
                state: container?.state,
                status: container?.status,
                node_id: container?.node_id,
                node_name: container?.node_name,
                runtime_service_name: container?.runtime_service_name,
            }));
        return {
            has_runtime_issues: this.hasRuntimeIssues(),
            service_status: this.selected()?.status || this.detail()?.service?.status || '',
            stack_summary: this.runtimeStackSummary(),
            container_summary: this.runtimeContainerSummary(),
            container_health: this.runtimeHealthSummary(),
            containers,
            problem_containers: problemContainers,
            failed_operations: this.runtimeIssueOperations().map((operation: any) => ({
                id: operation?.id,
                type: operation?.type,
                status: operation?.status,
                message: operation?.message,
                created_at: operation?.created_at,
                started_at: operation?.started_at,
                finished_at: operation?.finished_at,
                result_payload: operation?.result_payload || {},
                output: (operation?.output || []).slice(-30),
            })),
        };
    }

    public hasRuntimeIssues() {
        if (['failed', 'canceled'].includes(this.statusKey(this.selected()?.status || this.detail()?.service?.status))) return true;
        if (this.runtimeIssueOperations().length > 0) return true;
        const stack = this.runtimeStackSummary();
        const containers = this.runtimeContainerSummary();
        const health = this.runtimeHealthSummary();
        if (Number(stack.task_errors || 0) > 0) return true;
        if (Number(health.unhealthy || 0) > 0) return true;
        if (Number(containers.stopped || 0) > 0) return true;
        if (Number(stack.desired || 0) > 0 && Number(stack.running || 0) < Number(stack.desired || 0)) return true;
        return this.runtimeContainers().some((container: any) => this.containerSignal(container) !== 'running' && this.containerSignal(container) !== 'healthy');
    }

    public async runRuntimeAiRepair() {
        const serviceId = this.selected()?.id;
        if (!serviceId || this.runtimeAiBusy()) return;
        if (!(await this.ensureAiModelOptions())) {
            await this.alert(this.aiUnavailableMessage() || '시스템 설정에서 사용할 AI 모델을 먼저 켜주세요.');
            return;
        }
        this.runtimeAiIntent.set('');
        this.runtimeAiAllowContainerActions.set(true);
        this.runtimeAiAllowSshDiagnostics.set(true);
        this.runtimeAiModalOpen.set(true);
        await this.service.render();
    }

    public closeRuntimeAiModal() {
        if (this.runtimeAiBusy()) return;
        this.runtimeAiModalOpen.set(false);
    }

    private resetRuntimeAiStream() {
        this.runtimeAiStreamEvents.set([]);
        this.runtimeAiOutputTokenCount.set(0);
    }

    private pushRuntimeAiEvent(event: any) {
        this.runtimeAiStreamEvents.set([...this.runtimeAiStreamEvents(), event].slice(-120));
        if (event?.type === 'delta') {
            this.runtimeAiOutputTokenCount.set(this.runtimeAiOutputTokenCount() + String(event.text || '').length);
        }
    }

    public runtimeAiStreamRows() {
        return this.compactAiStreamRows(this.runtimeAiStreamEvents());
    }

    public runtimeAiScopeItems() {
        return [
            { label: '실패 로그', value: `${this.runtimeIssueOperations().length}개` },
            { label: '컨테이너', value: `중지 ${this.runtimeContainerSummary()?.stopped || 0}개` },
            { label: 'Docker 작업', value: `${this.runtimeStackSummary()?.running || 0}/${this.runtimeStackSummary()?.desired || 0}` },
            { label: '브라우저 점검', value: this.runtimeDomains().length ? '포함' : '도메인 없음' },
        ];
    }

    public async submitRuntimeAiRepair() {
        const serviceId = this.selected()?.id;
        if (!serviceId || this.runtimeAiBusy()) return;
        if (!(await this.ensureAiModelOptions())) {
            await this.alert(this.aiUnavailableMessage() || '시스템 설정에서 사용할 AI 모델을 먼저 켜주세요.');
            return;
        }
        this.runtimeAiBusy.set(true);
        this.resetRuntimeAiStream();
        try {
            await this.loadDetailSection('logs', false, true);
            const { code, data } = await wiz.call('start_runtime_ai_verification', {
                service_id: serviceId,
                model_ref: this.runtimeAiModelRef() || this.aiDefaultModelRef() || 'auto',
                intent: String(this.runtimeAiIntent() || '').trim(),
                client_runtime_issues: this.runtimeIssueSnapshot(),
                allow_container_terminal_actions: this.runtimeAiAllowContainerActions(),
                allow_ssh_command: this.runtimeAiAllowSshDiagnostics(),
                apply: true,
                deploy: true,
            });
            if (![200, 202].includes(code)) {
                throw new Error(data?.message || 'AI 런타임 검사/수정을 시작할 수 없습니다.');
            }
            const result = data?.result || {};
            this.runtimeAiResult = result;
            this.runtimeAiModalOpen.set(false);
            const detailResult = await wiz.call('detail_service', { service_id: serviceId });
            if (detailResult.code === 200) this.applyDetail(detailResult.data);
            if (result.operation) await this.openOperationModal(result.operation);
        } catch (error: any) {
            this.pushRuntimeAiEvent({ type: 'error', message: error?.message || 'AI 런타임 검사/수정 중 오류가 발생했습니다.' });
            await this.alert(error?.message || 'AI 런타임 검사/수정을 실행할 수 없습니다.');
        }
        this.runtimeAiBusy.set(false);
        await this.service.render();
    }

    public runtimeNginxText() {
        const summary = this.runtimeDomainSummary();
        if (!Number(summary.total || 0)) return '도메인 없음';
        return `${summary.nginx_configured || 0}/${summary.total || 0}개 적용`;
    }

    public latestOperation() {
        const rows = this.detail()?.operations || [];
        return rows.length ? rows[0] : null;
    }

    private isActiveOperation(operation: any) {
        return ['pending', 'running'].includes(this.statusKey(operation?.status));
    }

    public activeBackgroundOperation() {
        return (this.detail()?.operations || []).find((operation: any) => (
            this.isActiveOperation(operation)
            && ['service.deploy', 'service.migrate', 'service.ai.verify', 'service.image.snapshot'].includes(String(operation?.type || ''))
        )) || null;
    }

    public operationLabel(type: string) {
        const labels: any = {
            'service.deploy': '설정 적용',
            'service.migrate': '서비스 마이그레이션',
            'service.ai.verify': 'AI 백그라운드 검증',
            'service.certbot.renew': '무료 인증서 갱신',
            'service.certbot.renewal.ensure': '무료 인증서 자동 갱신 설정',
            'service.compose.release': '수동 릴리즈',
            'service.compose.rollback': 'Compose 되돌리기',
            'service.image.backup': '이미지 백업',
            'service.image.restore': '이미지 복원',
            'service.image.snapshot': '현재 상태 백업',
        };
        if (labels[type]) return labels[type];
        return String(type || '').replace(/^service[._-]?/i, '').replace(/[._-]+/g, ' ') || '처리 내역';
    }

    public latestOperationText() {
        const operation = this.latestOperation();
        if (!operation) return '아직 처리 내역이 없습니다.';
        return `${this.operationLabel(operation.type)} · ${this.statusLabel(operation.status)}`;
    }

    public visibleImageBackups() {
        return (this.detail()?.image_backups || []).slice(0, 5);
    }

    public versionBackupSummary(version: any) {
        return version?.image_backup_summary || {};
    }

    public versionSnapshotBackupCount(version: any) {
        return Number(this.versionBackupSummary(version)?.snapshot_succeeded_count || 0);
    }

    public versionBackupCount(version: any) {
        return Number(this.versionBackupSummary(version)?.backup_succeeded_count || 0);
    }

    public imageDisplayName(item: any) {
        const value = item?.backup_ref || item?.image_ref || '-';
        return String(value).replace(/^docker\.io\//, '');
    }

    public toggleAdvancedDetail() {
        const next = !this.advancedDetailOpen();
        this.advancedDetailOpen.set(next);
        if (!next) this.advancedNginxEditOpen.set(false);
    }

    public sourceLabel(service: any) {
        const source = service?.metadata?.source || '';
        return this.sourceText(source);
    }

    public versionSourceLabel(version: any) {
        return this.sourceText(version?.metadata?.source || version?.metadata?.draft?.source || '');
    }

    private sourceText(source: string) {
        const labels: any = {
            ui_wizard: '화면에서 생성',
            ai_draft: 'AI 초안에서 생성',
            compose_template: 'Compose 템플릿',
            manual_compose: 'Compose 직접 작성',
            server_compose_import: '서버 Compose 가져오기',
            server_compose_import_wizard: '서버 Compose 가져오기',
            compose_rollback: '되돌리기',
            manual_release: '수동 릴리즈',
            manual_release_snapshot: '릴리즈 스냅샷',
            service_migration_snapshot: '마이그레이션 스냅샷',
        };
        return labels[source] || source || '-';
    }

    public versionDraftText(version: any) {
        const draft = version?.metadata?.draft || {};
        const notes = draft.notes;
        if (Array.isArray(notes) && notes.length) return String(notes[0] || '');
        if (typeof notes === 'string' && notes.trim()) return notes.trim();
        const summary = draft.summary;
        if (typeof summary === 'string' && summary.trim()) return summary.trim();
        if (summary && typeof summary === 'object') {
            const services = summary.services ?? summary.service_count;
            const ports = summary.ports ?? summary.port_count;
            if (services || ports) return `구성 ${services || 0}개, 포트 ${ports || 0}개`;
        }
        return '';
    }

    public statusLabel(status: string) {
        const labels: any = {
            draft: '저장됨',
            pending: '처리 중',
            active: '운영 중',
            running: '운영 중',
            deployed: '운영 중',
            failed: '문제 있음',
            canceled: '취소됨',
            succeeded: '완료',
            certbot: '무료 인증서 발급',
            existing: '업로드 인증서 사용',
            none: 'SSL 없음',
            recorded: '기록됨',
            backup_pending: '백업 대기',
            backup_succeeded: '백업 완료',
            backup_failed: '백업 실패',
        };
        return labels[status] || status || '-';
    }

    public sslModeLabel(mode: string) {
        const labels: any = {
            none: 'SSL 없음',
            certbot: '무료 인증서 발급',
            existing: '도메인 인증서 사용',
            upload: '도메인 인증서 사용'
        };
        return labels[mode] || mode || '-';
    }

    public domainConnectionLabel(domain: any) {
        if (!domain) return '-';
        return `Nginx 자동 연결 / ${this.sslModeLabel(domain.ssl_mode)}`;
    }

    public domainNginxLabel(domain: any) {
        const metadata = domain?.metadata || {};
        if (metadata.nginx_config_path) return 'nginx 적용됨';
        if (domain?.domain) return 'nginx 적용 대기';
        return 'nginx 미연결';
    }

    public domainPortText(domain: any) {
        const metadata = domain?.metadata || {};
        const target = metadata.target_port || domain?.port;
        const published = metadata.published_port;
        if (published && Number(published) !== Number(target)) {
            return `내부 ${target}번 / 서버 ${published}번`;
        }
        return `내부 ${target || '-'}번`;
    }

    public statusClass(status: string) {
        if (['active', 'running', 'succeeded', 'deployed', 'backup_succeeded'].includes(status)) {
            return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300';
        }
        if (['draft', 'pending', 'recorded', 'backup_pending'].includes(status)) {
            return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        }
        if (['failed', 'canceled', 'backup_failed'].includes(status)) {
            return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        }
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }

    public createModeDescription() {
        return this.serviceMode() === 'basic_web'
            ? '기본 웹 서비스 Compose를 자동 생성합니다.'
            : 'Compose 초안을 직접 조정하면서 서비스 초안을 저장합니다.';
    }

    public formatDate(value: any) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString();
    }
}
