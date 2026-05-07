import { OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    public loading = signal<boolean>(true);
    public busy = signal<boolean>(false);
    public detailLoading = signal<boolean>(false);
    public templateLoading = signal<boolean>(false);
    public error = signal<string>('');
    public services = signal<any[]>([]);
    public templates = signal<any[]>([]);
    public selected = signal<any>(null);
    public detail = signal<any>(null);
    public serviceModalOpen = signal<boolean>(false);
    public serviceMode = signal<'basic_web' | 'direct_compose'>('basic_web');
    public advancedCompose = signal<boolean>(false);
    public validation = signal<any>(null);
    public lastCreated = signal<any>(null);
    public fileBrowserOpen = signal<boolean>(false);
    public fileBrowserBusy = signal<boolean>(false);
    public fileBrowserPath = signal<string>('.');
    public fileBrowserItems = signal<any[]>([]);
    public filePreviewOpen = signal<boolean>(false);
    public filePreviewBusy = signal<boolean>(false);
    public filePreviewTitle = signal<string>('');
    public filePreviewContent = signal<string>('');
    public selectedTemplateId = signal<string>('');
    public serviceForm: any = this.emptyForm();
    public compose: any = this.emptyCompose();

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        this.refreshCompose(true);
        await this.load();
    }

    private emptyForm() {
        return {
            name: '',
            namespace: '',
            domain: '',
            port: 80,
            image: 'nginx:alpine',
            service_name: 'web',
            proxy_type: 'nginx',
            ssl_mode: 'none',
        };
    }

    private emptyCompose() {
        return {
            namespace: '',
            filename: 'docker-compose.yaml',
            content: '',
        };
    }

    private applyDetail(data: any) {
        this.detail.set(data || null);
        this.selected.set(data?.service || null);
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

    public async load(selectedId: string = '') {
        this.loading.set(true);
        this.error.set('');
        const { code, data } = await wiz.call('load', {});
        if (code === 200) {
            const services = data.services || [];
            this.services.set(services);
            this.templates.set(data.templates || []);
            const next = services.find((item: any) => item.id === selectedId) || services[0] || null;
            if (next?.id) {
                await this.selectService(next, true);
            } else {
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
        this.detailLoading.set(true);
        const { code, data } = await wiz.call('detail_service', { service_id: service.id });
        if (code === 200) {
            this.applyDetail(data);
        } else if (!silent) {
            await this.alert(data?.message || '서비스 상세 정보를 불러올 수 없습니다.');
        }
        this.detailLoading.set(false);
        await this.service.render();
    }

    public openCreateModal(mode: 'basic_web' | 'direct_compose' = 'basic_web') {
        this.serviceMode.set(mode);
        this.serviceModalOpen.set(true);
        this.advancedCompose.set(mode === 'direct_compose');
        this.validation.set(null);
        this.lastCreated.set(null);
        this.selectedTemplateId.set('');
        this.templateLoading.set(false);
        this.serviceForm = this.emptyForm();
        this.compose = this.emptyCompose();
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
            this.serviceForm.namespace = String(values.namespace || data?.template?.namespace || this.serviceForm.namespace || '').trim();
            this.serviceForm.service_name = String(values.service_name || this.serviceForm.service_name || 'web').trim();
            this.serviceForm.image = String(values.image || data?.template?.metadata?.primary_image || this.serviceForm.image || 'nginx:alpine').trim();
            this.serviceForm.port = Number(values.service_port || this.serviceForm.port || 80);
            this.normalizeNamespace();
            this.compose.namespace = this.serviceForm.namespace || 'my_service';
            this.compose.filename = 'docker-compose.yaml';
            this.compose.content = data?.preview?.rendered_compose || data?.files?.['docker-compose.yaml'] || '';
            this.advancedCompose.set(true);
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
        this.advancedCompose.set(this.serviceMode() === 'direct_compose');
        this.validation.set(null);
        this.refreshCompose(true);
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
        const image = this.serviceForm.image || 'nginx:alpine';
        const port = Number(this.serviceForm.port || 80);
        this.compose.namespace = namespace;
        this.compose.filename = 'docker-compose.yaml';
        if (!force && this.advancedCompose() && this.compose.content) return;

        this.compose.content = [
            'services:',
            `  ${serviceName}:`,
            `    image: ${image}`,
            '    ports:',
            `      - "${port}:${port}"`,
            '    healthcheck:',
            `      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:${port}"]`,
            '      interval: 30s',
            '      timeout: 5s',
            '      retries: 3',
        ].join('\n');
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

    public async createService() {
        if (!this.serviceForm.name) {
            await this.alert('서비스 이름을 입력해주세요.');
            return;
        }
        if (!this.serviceForm.namespace) {
            await this.alert('서비스 ID를 입력해주세요.');
            return;
        }
        this.refreshCompose();
        this.busy.set(true);
        this.validation.set(null);
        const payload = {
            ...this.serviceForm,
            filename: this.compose.filename,
            content: this.compose.content,
            source: this.selectedTemplateId() ? 'template_catalog' : undefined,
            source_ref: this.selectedTemplateId() ? {
                template_id: this.selectedTemplateId(),
                template_namespace: this.selectedTemplateRecord()?.namespace || '',
            } : undefined,
        };
        const { code, data } = await wiz.call('create_service', payload);
        if (code === 200) {
            this.validation.set({ ok: true, validation: data.result?.validation });
            this.lastCreated.set(data.result || null);
            this.serviceModalOpen.set(false);
            await this.load(data.result?.service?.id || '');
            await this.alert('서비스 초안을 저장했습니다.', 'success');
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

    public async openFileBrowser() {
        if (!this.selected()?.id) return;
        this.fileBrowserOpen.set(true);
        this.filePreviewOpen.set(false);
        await this.browseFiles('.');
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

    public sourceLabel(service: any) {
        const source = service?.metadata?.source || '';
        const labels: any = {
            ui_wizard: '화면에서 생성',
            server_compose_import: '서버 Compose 가져오기',
            template_catalog: '템플릿에서 생성',
        };
        return labels[source] || source || '-';
    }

    public statusLabel(status: string) {
        const labels: any = {
            draft: '초안',
            pending: '대기',
            active: '정상',
            running: '실행 중',
            deployed: '배포됨',
            failed: '실패',
            canceled: '취소됨',
            succeeded: '완료',
        };
        return labels[status] || status || '-';
    }

    public statusClass(status: string) {
        if (['active', 'running', 'succeeded', 'deployed'].includes(status)) {
            return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300';
        }
        if (['draft', 'pending'].includes(status)) {
            return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        }
        if (['failed', 'canceled'].includes(status)) {
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
