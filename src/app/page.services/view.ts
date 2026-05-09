import { OnDestroy, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit, OnDestroy {
    public loading = signal<boolean>(true);
    public busy = signal<boolean>(false);
    public detailLoading = signal<boolean>(false);
    public templateLoading = signal<boolean>(false);
    public error = signal<string>('');
    public services = signal<any[]>([]);
    public templates = signal<any[]>([]);
    public nodes = signal<any[]>([]);
    public zones = signal<any[]>([]);
    public selected = signal<any>(null);
    public detail = signal<any>(null);
    public detailTab = signal<'overview' | 'logs' | 'backups' | 'advanced'>('overview');
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
    public editBusy = signal<boolean>(false);
    public editAdvancedSettings = signal<boolean>(false);
    public rollbackModalOpen = signal<boolean>(false);
    public rollbackBusy = signal<boolean>(false);
    public rollbackTarget = signal<any>(null);
    public rollbackPlan = signal<any>(null);
    public operationModalOpen = signal<boolean>(false);
    public operationBusy = signal<boolean>(false);
    public operationDetail = signal<any>(null);
    public selectedTemplateId = signal<string>('');
    public serviceForm: any = this.emptyForm();
    public compose: any = this.emptyCompose();
    public envVars: any[] = [];
    public volumes: any[] = [];
    public editForm: any = {};
    public editComponents: any[] = [];
    public nginxConfigDrafts: any = {};
    private operationPollTimer: any = null;
    private detailRequestSeq = 0;
    private editOptionsLoaded = false;
    private themeObserver: MutationObserver | null = null;

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        this.syncAdvancedEditorTheme();
        this.startThemeObserver();
        this.refreshCompose(true);
        const params = new URLSearchParams(window.location.search || '');
        await this.load(params.get('service_id') || params.get('selected_service_id') || '');
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

    private applyDetail(data: any) {
        const previousEditorKey = this.advancedEditorTarget()?.key || 'compose';
        this.detail.set(data || null);
        this.selected.set(data?.service || null);
        if (data?.service) this.detailLoading.set(false);
        this.advancedNginxEditOpen.set(false);
        this.advancedComposeDraft.set(data?.compose_content || '');
        this.nginxConfigDrafts = {};
        for (const config of data?.nginx_configs || []) {
            this.nginxConfigDrafts[config.domain_id] = config.content || '';
        }
        this.selectAdvancedEditorByKey(previousEditorKey);
    }

    private validationDetails(details: any[] = []) {
        return (details || [])
            .filter((detail: any) => detail)
            .map((detail: any) => {
                const message = detail.message || detail.error_code || '검사에 실패했습니다.';
                return detail.path ? `- ${detail.path}: ${message}` : `- ${message}`;
            });
    }

    private formatComposeError(data: any, fallback: string) {
        const base = data?.error_code === 'COMPOSE_VALIDATION_FAILED'
            ? 'Compose 검사를 통과하지 못했습니다.'
            : (data?.message || fallback);
        const details = this.validationDetails(data?.details || []);
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

    public async load(selectedId: string = '') {
        this.loading.set(true);
        this.error.set('');
        const { code, data } = await wiz.call('load', {});
        if (code === 200) {
            const services = data.services || [];
            this.services.set(services);
            this.templates.set(data.templates || []);
            this.nodes.set(data.nodes || []);
            this.zones.set(data.zones || []);
            const next = services.find((item: any) => item.id === selectedId) || services[0] || null;
            if (next?.id) {
                this.detailRequestSeq += 1;
                this.selected.set(next);
                this.detail.set(null);
                this.detailTab.set('overview');
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

    public async selectService(service: any, silent: boolean = false) {
        if (!service?.id) return;
        const requestSeq = ++this.detailRequestSeq;
        this.selected.set(service);
        if (this.detail()?.service?.id !== service.id) {
            this.detail.set(null);
            this.detailTab.set('overview');
        }
        this.advancedDetailOpen.set(false);
        this.advancedNginxEditOpen.set(false);
        this.detailLoading.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('detail_service', { service_id: service.id });
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
        this.serviceMode.set(mode);
        this.serviceModalOpen.set(true);
        this.createStep.set(1);
        this.advancedCompose.set(mode === 'direct_compose');
        this.validation.set(null);
        this.composeConflicts.set([]);
        this.lastCreated.set(null);
        this.selectedTemplateId.set('');
        this.templateLoading.set(false);
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
        if (this.selectedTemplateId()) {
            this.selectedTemplateId.set('');
        }
        this.advancedCompose.set(mode === 'direct_compose');
        this.refreshCompose(true);
    }

    public templateSelectorItems() {
        return this.templates()
            .filter((item: any) => item?.enabled !== false)
            .map((item: any) => ({
                value: item.id,
                label: item.name,
                description: `${item.namespace} · ${item.description || '설명 없음'}`,
                badge: item?.metadata?.category || 'template',
                badgeClass: this.templateCategoryBadgeClass(item?.metadata?.category || 'template'),
            }));
    }

    public selectedTemplateRecord() {
        return this.templates().find((item: any) => item.id === this.selectedTemplateId()) || null;
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
            description: `DNS 레코드 ${zone.record_count || 0}개 · ${zone.secret_configured ? 'Cloudflare 연결됨' : '토큰 없음'}`,
            badge: zone.status || 'domain',
            badgeClass: this.statusClass(zone.status || 'draft'),
        }));
    }

    public selectedZoneRecord() {
        return this.zones().find((zone: any) => zone.id === this.serviceForm.zone_id) || null;
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
        const prefix = String(this.serviceForm.domain_prefix || '').trim().replace(/^\.+|\.+$/g, '');
        this.serviceForm.domain = prefix ? `${prefix}.${zone.domain}` : zone.domain;
    }

    public domainPreview() {
        if (this.serviceForm.domain_mode === 'registered') {
            const zone = this.selectedZoneRecord();
            const prefix = String(this.serviceForm.domain_prefix || '').trim().replace(/^\.+|\.+$/g, '');
            if (zone?.domain) return prefix ? `${prefix}.${zone.domain}` : zone.domain;
        }
        return this.serviceForm.domain || '도메인 미입력';
    }

    public async selectTemplate(templateId: string) {
        this.selectedTemplateId.set(templateId || '');
        if (!templateId) {
            this.refreshCompose(true);
            return;
        }
        this.templateLoading.set(true);
        const { code, data } = await wiz.call('template_detail', { template_id: templateId });
        if (code === 200) {
            const values = data?.preview?.values || {};
            this.serviceForm.name = data?.template?.name || this.serviceForm.name;
            if (!this.serviceForm.description) {
                this.serviceForm.description = data?.template?.description || '';
            }
            this.serviceForm.namespace = String(values.namespace || data?.template?.namespace || this.serviceForm.namespace || '').trim();
            this.serviceForm.service_name = String(values.service_name || this.serviceForm.service_name || 'web').trim();
            this.applyImageRef(String(values.image || data?.template?.metadata?.primary_image || this.serviceForm.image || 'nginx:alpine').trim());
            this.serviceForm.port = Number(values.service_port || this.serviceForm.port || 80);
            this.normalizeNamespace();
            this.compose.namespace = this.serviceForm.namespace || 'my_service';
            this.compose.filename = 'docker-compose.yaml';
            this.compose.content = data?.preview?.rendered_compose || data?.files?.['docker-compose.yaml'] || '';
            this.advancedCompose.set(this.serviceMode() === 'direct_compose');
            this.validation.set(null);
        } else {
            this.selectedTemplateId.set('');
            await this.alert(data?.message || '템플릿을 불러올 수 없습니다.');
        }
        this.templateLoading.set(false);
        await this.service.render();
    }

    public clearSelectedTemplate() {
        this.selectedTemplateId.set('');
        this.serviceForm = this.emptyForm();
        this.compose = this.emptyCompose();
        this.envVars = [];
        this.volumes = [];
        this.advancedCompose.set(this.serviceMode() === 'direct_compose');
        this.validation.set(null);
        this.composeConflicts.set([]);
        this.refreshCompose(true);
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
            source: this.selectedTemplateId() ? 'template_catalog' : undefined,
            source_ref: this.selectedTemplateId() ? {
                template_id: this.selectedTemplateId(),
                template_namespace: this.selectedTemplateRecord()?.namespace || '',
            } : undefined,
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

    public async deploySelectedService() {
        const serviceId = this.selected()?.id;
        if (!serviceId || this.busy()) return;
        const ok = await this.confirm(`${this.selected()?.name || '서비스'} 설정을 서버에 적용합니다. 접속 주소와 포트 설정도 함께 확인합니다.`, this.deployActionLabel(), 'warning');
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
        const ok = await this.confirm('Compose 원문을 검사한 뒤 저장합니다. 저장 후 적용 버튼을 눌러야 서버 실행 상태에 반영됩니다.', '검사 후 저장', 'warning');
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

    public openEditModal() {
        this.openEditModalAsync();
    }

    private async openEditModalAsync() {
        const detail = this.detail();
        const service = detail?.service;
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
        this.editForm.domain_prefix = clean === suffix ? '' : clean.slice(0, -(suffix.length + 1));
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
        const prefix = String(this.editForm.domain_prefix || '').trim().replace(/^\.+|\.+$/g, '');
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

    private editPayload() {
        this.syncEditDomain();
        this.ensureEditDomainTarget();
        const target = this.editDomainTargetOptions().find((item: any) => item.key === this.editForm.domain_target_key);
        return {
            ...this.editForm,
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

    private async deployService(serviceId: string, fromCreate: boolean = false) {
        this.busy.set(true);
        const { code, data } = await wiz.call('deploy_service_background', { service_id: serviceId });
        if ([200, 202].includes(code)) {
            await this.load(serviceId);
            const message = fromCreate
                ? '서비스를 저장했고 배포는 백그라운드에서 시작했습니다. 처리 로그에서 진행 상태를 확인할 수 있습니다.'
                : '서비스 배포를 백그라운드에서 시작했습니다. 처리 로그에서 진행 상태를 확인할 수 있습니다.';
            await this.alert(message, 'success');
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
        const ok = await this.confirm(`${item.compose_service} 구성을 ${target} 이미지 기준으로 되돌립니다.\n\n접속 주소는 유지되고, 서비스는 준비 중 상태로 저장됩니다. 실제 서버 반영은 서비스 적용을 다시 실행해야 합니다.`, '이미지 복원', 'warning');
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
            { label: '포트 변경', value: `${summary.port_changes || 0}개` },
            { label: '추가/제거', value: `${summary.added_services || 0}개 추가 · ${summary.removed_services || 0}개 제거` },
            { label: '도메인 주의', value: `${summary.domain_warnings || 0}개` },
        ];
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

    public async runRollback(deployAfterRollback: boolean = false) {
        const serviceId = this.selected()?.id;
        const versionId = this.rollbackTarget()?.id;
        if (!serviceId || !versionId || this.rollbackBusy()) return;
        this.rollbackBusy.set(true);
        const { code, data } = await wiz.call('rollback_service', { service_id: serviceId, version_id: versionId });
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
            await this.deployService(nextServiceId, false);
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

    public async snapshotServiceImage(item: any) {
        const serviceId = this.selected()?.id;
        if (!serviceId || !item?.id || this.busy()) return;
        const ok = await this.confirm(`${item.compose_service} 컨테이너를 현재 상태 그대로 스냅샷 백업합니다.\n\n파일 상태까지 저장하기 위해 실행 중인 컨테이너가 잠깐 일시 정지될 수 있습니다. 접속이 중요한 시간대라면 나중에 실행해주세요.`, '스냅샷 백업', 'warning');
        if (!ok) return;
        this.busy.set(true);
        const { code, data } = await wiz.call('snapshot_service_image', { service_id: serviceId, backup_id: item.id, pause: true });
        if (code === 200) {
            this.applyDetail(data);
            await this.alert('컨테이너 스냅샷 백업을 완료했습니다.', 'success');
        } else {
            await this.alert(data?.message || '컨테이너 스냅샷을 백업할 수 없습니다.');
        }
        this.busy.set(false);
        await this.service.render();
    }

    public backupKindLabel(item: any) {
        return item?.source === 'container_snapshot' ? '스냅샷' : '이미지';
    }

    public async openOperationModal(operation: any) {
        if (!operation?.id) return;
        this.operationDetail.set(operation);
        this.operationModalOpen.set(true);
        await this.refreshOperationDetail();
        this.startOperationPolling();
    }

    public closeOperationModal() {
        this.stopOperationPolling();
        this.operationModalOpen.set(false);
        this.operationDetail.set(null);
    }

    private startOperationPolling() {
        this.stopOperationPolling();
        if (this.operationDetail()?.status !== 'running') return;
        this.operationPollTimer = setInterval(async () => {
            await this.refreshOperationDetail(false);
            if (this.operationDetail()?.status !== 'running') this.stopOperationPolling();
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
            this.operationDetail.set(data.operation || null);
        } else if (showBusy) {
            await this.alert(data?.message || '처리 내역을 불러올 수 없습니다.');
        }
        this.operationBusy.set(false);
        await this.service.render();
    }

    public operationOutput() {
        return this.operationDetail()?.output || [];
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
        const status = this.detail()?.service?.status || this.selected()?.status;
        return status === 'draft' ? '서비스 적용' : '다시 적용';
    }

    public serviceStateTitle() {
        const status = this.detail()?.service?.status || this.selected()?.status;
        if (['deployed', 'active', 'running'].includes(status)) return '서비스가 운영 중입니다.';
        if (status === 'draft') return '아직 서버에 적용되지 않았습니다.';
        if (['failed', 'canceled'].includes(status)) return '확인이 필요한 상태입니다.';
        return '처리 상태를 확인하는 중입니다.';
    }

    public serviceStateMessage() {
        const status = this.detail()?.service?.status || this.selected()?.status;
        if (['deployed', 'active', 'running'].includes(status)) {
            return this.primaryDomain() ? '접속 주소와 연결 설정이 준비되어 있습니다.' : '서비스는 적용되었지만 접속 주소는 아직 연결되지 않았습니다.';
        }
        if (status === 'draft') return '오른쪽 위의 서비스 적용 버튼을 누르면 서버에 반영됩니다.';
        if (['failed', 'canceled'].includes(status)) return '최근 처리 내역을 확인하고 다시 적용해 주세요.';
        return '작업이 끝나면 상태가 자동으로 바뀝니다.';
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
            { key: 'backups', label: '백업', icon: 'fa-box-archive' },
            { key: 'advanced', label: '고급', icon: 'fa-code' },
        ];
    }

    public setDetailTab(tab: any) {
        if (!['overview', 'logs', 'backups', 'advanced'].includes(tab)) return;
        this.detailTab.set(tab);
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

    public runtimeContainerRows() {
        return this.runtimeContainers().map((container: any) => {
            const status = this.containerStatusLabel(container);
            return {
                name: this.containerDisplayName(container),
                status,
                className: this.containerStatusClass(container),
                message: this.containerStatusMessage(container),
                ports: this.containerPortLabels(container),
            };
        });
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

    public containerStatusMessage(container: any) {
        const state = String(container?.state || '').toLowerCase();
        const status = String(container?.status || '').trim();
        if (status.toLowerCase().includes('unhealthy')) return '상태 점검이 실패했습니다. 최근 처리 내역과 로그를 확인하세요.';
        if (status.toLowerCase().includes('health: starting')) return '컨테이너가 시작되고 상태 점검을 기다리는 중입니다.';
        if (state === 'running') return '서비스 구성요소가 실행 중입니다.';
        if (state === 'exited') return '중지된 구성요소입니다. 다시 적용 또는 되돌리기가 필요할 수 있습니다.';
        return status || 'Docker에서 받은 상태 정보가 없습니다.';
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
        for (const domain of this.runtimeDomains()) {
            push(domain?.proxy_node_name);
        }
        for (const task of this.runtimeStatus()?.stack?.tasks || []) {
            push(task?.Node || task?.node || task?.Hostname || task?.hostname);
        }
        return values;
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
        const node = domain?.proxy_node_name ? ` · ${domain.proxy_node_name}` : '';
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

    public runtimeNginxText() {
        const summary = this.runtimeDomainSummary();
        if (!Number(summary.total || 0)) return '도메인 없음';
        return `${summary.nginx_configured || 0}/${summary.total || 0}개 적용`;
    }

    public latestOperation() {
        const rows = this.detail()?.operations || [];
        return rows.length ? rows[0] : null;
    }

    public operationLabel(type: string) {
        const labels: any = {
            'service.deploy': '서비스 적용',
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
        const labels: any = {
            ui_wizard: '화면에서 생성',
            server_compose_import: '서버 Compose 가져오기',
            server_compose_import_wizard: '서버 Compose 가져오기',
            template_catalog: '템플릿에서 생성',
        };
        return labels[source] || source || '-';
    }

    public statusLabel(status: string) {
        const labels: any = {
            draft: '준비 중',
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
        if (this.selectedTemplateRecord()) {
            return `${this.selectedTemplateRecord()?.name} 템플릿으로 Compose 초안을 채워서 시작합니다.`;
        }
        return this.serviceMode() === 'basic_web'
            ? '기본 웹 서비스 템플릿으로 Compose를 자동 생성합니다.'
            : 'Compose 초안을 직접 조정하면서 서비스 초안을 저장합니다.';
    }

    public templateCategoryBadgeClass(category: string) {
        const value = String(category || '').toLowerCase();
        if (['service', 'web'].includes(value)) {
            return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300';
        }
        if (['was', 'api'].includes(value)) {
            return 'border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-900/70 dark:bg-violet-950/40 dark:text-violet-300';
        }
        if (['db', 'database'].includes(value)) {
            return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        }
        if (['cache', 'queue'].includes(value)) {
            return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
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
