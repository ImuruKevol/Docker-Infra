import { OnDestroy, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import { AppearanceRuntime } from '@wiz/libs/portal/season/appearance';

const FIELD_LABELS: any = {
    harbor: {
        url: 'Harbor URL',
        username: '계정'
    },
    gitlab: {
        url: 'GitLab URL'
    }
};

const ASSET_KINDS = ['favicon', 'logo'];

export class Component implements OnInit, OnDestroy {
    public loading = signal<boolean>(true);
    public error = signal<string>('');
    public savingGeneral = signal<boolean>(false);
    public general: any = { browser_title: 'Docker Infra', favicon_url: AppearanceRuntime.assetRoute('favicon'), logo_url: '' };
    public integrations: any[] = [];
    public webserver = signal<any>(this.emptyWebserver());
    public uploading: any = { favicon: false, logo: false };
    public assetVersion: number = Date.now();
    public pendingAssets: any = {
        favicon: this.emptyAssetSelection(),
        logo: this.emptyAssetSelection()
    };
    public certificateModalOpen = signal<boolean>(false);
    public certificateForm: any = this.emptyCertificate();
    public pathPickerOpen = signal<boolean>(false);
    public pathPickerBusy = signal<boolean>(false);
    public pathPickerPath = signal<string>('');
    public pathPickerInput = signal<string>('');
    public pathPickerShowHidden = signal<boolean>(false);
    public pathPickerItems = signal<any[]>([]);
    public pathPickerMode = signal<string>('file');
    public pathPickerTitle = signal<string>('경로 선택');
    public pathPickerDescription = signal<string>('');
    private pathPickerTarget: any = null;

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.load();
    }

    public ngOnDestroy() {
        for (const kind of ASSET_KINDS) this.releasePendingAsset(kind);
    }

    public async alert(message: string, status: string = 'error') {
        return await this.service.modal.show({
            title: '',
            message,
            cancel: false,
            actionBtn: status,
            action: '확인',
            status
        });
    }

    public async confirm(message: string, action: string = '삭제', status: string = 'error') {
        return await this.service.modal.show({
            title: '',
            message,
            cancel: true,
            cancelLabel: '취소',
            actionBtn: status,
            action,
            status
        });
    }

    public async load() {
        this.loading.set(true);
        this.error.set('');
        const { code, data } = await wiz.call('load', {});
        if (code === 200) {
            this.general = data.general || this.general;
            this.integrations = this.prepareIntegrations(data.integrations || []);
            this.webserver.set(data.webserver || this.emptyWebserver());
        } else {
            this.error.set(data?.message || '시스템 설정을 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
    }

    public prepareIntegrations(items: any[]) {
        return items.map((integration: any) => ({
            ...integration,
            secret_visible: false,
            fields: { ...(integration.fields || {}) },
            field_entries: Object.keys(integration.fields || {}).map((field) => ({
                key: field,
                label: FIELD_LABELS[integration.key]?.[field] || field
            }))
        }));
    }

    public previewUrl(kind: string) {
        const pending = this.pendingAssets[kind];
        if (pending?.preview_url) return pending.preview_url;
        if (kind === 'favicon') return this.assetUrl(this.general.favicon_url || AppearanceRuntime.assetRoute('favicon'));
        if (kind === 'logo') return this.assetUrl(this.general.logo_url || '');
        return '';
    }

    public pendingAssetName(kind: string) {
        return String(this.pendingAssets[kind]?.name || '').trim();
    }

    public hasPendingAsset(kind: string) {
        return Boolean(this.pendingAssets[kind]?.file);
    }

    public async saveGeneral() {
        if (this.savingGeneral()) return;
        this.savingGeneral.set(true);
        await this.service.render();
        const nextGeneral = { ...this.general };
        for (const kind of ASSET_KINDS) {
            const asset = await this.uploadPendingAsset(kind);
            if (asset === false) {
                this.savingGeneral.set(false);
                await this.service.render();
                return;
            }
            if (asset?.url) nextGeneral[`${kind}_url`] = asset.url;
        }
        const { code, data } = await wiz.call('save_general', nextGeneral);
        this.savingGeneral.set(false);
        if (code === 200) {
            this.general = data.general || nextGeneral;
            for (const kind of ASSET_KINDS) this.clearPendingAsset(kind);
            this.bumpAssetVersion();
            AppearanceRuntime.apply(this.general);
            await this.alert('일반 설정을 저장했습니다.', 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || '일반 설정을 저장할 수 없습니다.');
        await this.service.render();
    }

    public async saveIntegration(integration: any) {
        const payload = { key: integration.key, enabled: integration.enabled, fields: integration.fields, secret_value: integration.secret_value };
        const { code, data } = await wiz.call('save_integration', payload);
        if (code === 200) {
            this.integrations = this.prepareIntegrations(data.integrations || this.integrations);
            await this.alert(`${integration.label} 설정을 저장했습니다.`, 'success');
            return;
        }
        await this.alert(data?.message || `${integration.label} 설정을 저장할 수 없습니다.`);
    }

    public async testIntegration(integration: any) {
        const payload = { key: integration.key, fields: integration.fields, secret_value: integration.secret_value };
        const { code, data } = await wiz.call('test_integration', payload);
        if (code === 200) {
            const lines = Object.keys(data.summary || {}).map((key) => `${key}: ${data.summary[key]}`);
            await this.alert([data.message || '연결 성공', ...lines].join('\n'), 'success');
            return;
        }
        await this.alert(data?.message || `${integration.label} 연결을 확인할 수 없습니다.`);
    }

    public toggleSecret(integration: any) {
        integration.secret_visible = !integration.secret_visible;
    }

    public secretInputType(integration: any) {
        return integration.secret_visible ? 'text' : 'password';
    }

    public openAssetPicker(elementId: string) {
        (document.getElementById(elementId) as HTMLInputElement | null)?.click();
    }

    public async selectAsset(kind: string, event: Event) {
        const input = event?.target as HTMLInputElement | null;
        const file = input?.files && input.files[0];
        if (!file) return;
        this.releasePendingAsset(kind);
        this.pendingAssets[kind] = {
            file,
            name: file.name,
            preview_url: URL.createObjectURL(file),
            uploaded_asset: null
        };
        if (input) input.value = '';
        await this.service.render();
    }

    public async clearSelectedAsset(kind: string) {
        this.clearPendingAsset(kind);
        await this.service.render();
    }

    public visibleServerEntries() {
        const servers = Object.values(this.webserver()?.servers || {});
        const running = servers.find((server: any) => server?.daemon_status === 'active');
        if (running) return [running];
        const active = this.webserver()?.active_server;
        if (active && active !== 'none' && this.webserver()?.servers?.[active]) return [this.webserver().servers[active]];
        const installed = servers.filter((server: any) => server?.installed);
        return installed.length > 0 ? installed : servers;
    }

    public activeServerLabel() {
        const active = this.webserver()?.active_server;
        if (active === 'nginx') return 'Nginx 사용 중';
        if (active === 'apache2') return 'Apache2(httpd) 사용 중';
        return '사용 중인 웹서버 없음';
    }

    public serverStatusLabel(server: any) {
        if (!server?.installed) return '미설치';
        if (server?.daemon_status === 'active') return '실행 중';
        if (server?.daemon_status === 'inactive') return '설치됨';
        return server?.daemon_status || '확인 불가';
    }

    public certificateSummaryItems() {
        const summary = this.webserver()?.certificate_summary || {};
        return [
            { label: '유효', value: summary.valid || 0, tone: 'success' },
            { label: '곧 만료', value: summary.expiring || 0, tone: 'warning' },
            { label: '만료', value: summary.expired || 0, tone: 'error' },
            { label: '오류/누락', value: (summary.error || 0) + (summary.missing || 0), tone: 'error' },
        ];
    }

    public openCertificateModal(item: any = null) {
        this.certificateForm = this.emptyCertificate(item || {});
        this.certificateModalOpen.set(true);
    }

    public closeCertificateModal() {
        this.certificateModalOpen.set(false);
        this.certificateForm = this.emptyCertificate();
    }

    public async saveCertificate() {
        const runtime = this.webserver();
        const certificates = [...(runtime.certificates || [])];
        if (!this.certificateForm.id) this.certificateForm.id = this.createDraftId('cert');
        const index = certificates.findIndex((item: any) => item.id === this.certificateForm.id);
        const next = { ...this.certificateForm };
        if (index >= 0) certificates[index] = next;
        else certificates.push(next);
        this.webserver.set({ ...runtime, certificates });
        this.closeCertificateModal();
        await this.saveWebserver('SSL 인증서 경로를 저장했습니다.');
    }

    public async deleteCertificate(item: any) {
        const ok = await this.confirm(`${item.label || item.cert_path} 인증서 설정을 삭제합니다.`, '삭제');
        if (!ok) return;
        const runtime = this.webserver();
        this.webserver.set({ ...runtime, certificates: (runtime.certificates || []).filter((cert: any) => cert.id !== item.id) });
        await this.saveWebserver('SSL 인증서 경로를 삭제했습니다.');
    }

    public async openServerPathPicker(serverKey: string, field: string, mode: string) {
        const server = this.webserver()?.servers?.[serverKey];
        if (!server) return;
        const title = field === 'config_path' ? `${server.label} 메인 설정 파일 선택` : `${server.label} 사이트 설정 디렉토리 선택`;
        const description = field === 'config_path' ? '실제로 사용하는 설정 파일을 선택하세요.' : 'Virtual host 또는 site 설정 파일이 위치한 디렉토리를 선택하세요.';
        await this.openPathPicker({ type: 'server', serverKey, field }, mode, title, description, server.settings?.[field] || '');
    }

    public async openCertificatePathPicker(field: string) {
        const title = field === 'cert_path' ? '인증서 파일 선택' : '키 파일 선택';
        const description = field === 'cert_path' ? 'PEM/CRT 인증서 파일을 선택하세요.' : '인증서와 짝이 맞는 private key 파일을 선택하세요.';
        await this.openPathPicker({ type: 'certificate', field }, 'file', title, description, this.certificateForm[field] || '');
    }

    public async openPathPicker(target: any, mode: string, title: string, description: string, currentValue: string = '') {
        this.pathPickerTarget = target;
        this.pathPickerMode.set(mode);
        this.pathPickerTitle.set(title);
        this.pathPickerDescription.set(description);
        this.pathPickerOpen.set(true);
        this.pathPickerPath.set('');
        this.pathPickerInput.set(currentValue || '');
        this.pathPickerShowHidden.set(false);
        this.pathPickerItems.set([]);
        await this.browseLocalFiles(currentValue || '');
    }

    public closePathPicker() {
        if (this.pathPickerBusy()) return;
        this.pathPickerOpen.set(false);
        this.pathPickerBusy.set(false);
        this.pathPickerPath.set('');
        this.pathPickerInput.set('');
        this.pathPickerShowHidden.set(false);
        this.pathPickerItems.set([]);
        this.pathPickerMode.set('file');
        this.pathPickerTitle.set('경로 선택');
        this.pathPickerDescription.set('');
        this.pathPickerTarget = null;
    }

    public async browseLocalFiles(path: string = '') {
        this.pathPickerBusy.set(true);
        const { code, data } = await wiz.call('browse_local_files', {
            path,
            show_hidden: this.pathPickerShowHidden(),
        });
        if (code === 200) {
            this.pathPickerPath.set(data.path || '');
            this.pathPickerInput.set(data.path || '');
            this.pathPickerItems.set(data.items || []);
        } else {
            await this.alert(data?.message || '파일 목록을 불러올 수 없습니다.');
        }
        this.pathPickerBusy.set(false);
        await this.service.render();
    }

    public async jumpToPathPickerPath() {
        await this.browseLocalFiles(this.normalizedPathPickerInput());
    }

    public async togglePathPickerHidden() {
        this.pathPickerShowHidden.set(!this.pathPickerShowHidden());
        await this.browseLocalFiles(this.pathPickerPath() || '');
    }

    public async browsePathPickerParent() {
        const current = this.pathPickerPath();
        if (!current || current === '/') return;
        const parent = this.pathPickerParent();
        if (parent) await this.browseLocalFiles(parent);
    }

    public pathPickerCanSelect(item: any) {
        return this.pathPickerMode() === 'directory' ? item?.type === 'folder' : item?.type === 'file';
    }

    public pathPickerActionLabel(item: any) {
        if (this.pathPickerMode() === 'directory' && item?.type === 'folder') return '이 폴더 선택';
        return '선택';
    }

    public async selectPathItem(item: any) {
        if (!this.pathPickerCanSelect(item)) return;
        await this.applyPathPickerSelection(item.path);
    }

    public async selectCurrentDirectory() {
        if (this.pathPickerMode() !== 'directory' || !this.pathPickerPath()) return;
        await this.applyPathPickerSelection(this.pathPickerPath());
    }

    public async saveWebserver(successMessage: string = '웹서버 및 SSL 설정을 저장했습니다.') {
        const runtime = this.webserver();
        const payload = {
            nginx: runtime?.servers?.nginx?.settings || {},
            apache2: runtime?.servers?.apache2?.settings || {},
            certificates: (runtime?.certificates || []).map((item: any) => ({
                id: item.id,
                label: item.label,
                cert_path: item.cert_path,
                key_path: item.key_path,
                enabled: item.enabled !== false
            }))
        };
        const { code, data } = await wiz.call('save_webserver', payload);
        if (code === 200) {
            this.webserver.set(data.webserver || this.emptyWebserver());
            await this.alert(successMessage, 'success');
            return;
        }
        await this.alert(data?.message || '웹서버 및 SSL 설정을 저장할 수 없습니다.');
    }

    public assetUrl(url: string) {
        if (!url) return url;
        return `${url}${url.includes('?') ? '&' : '?'}v=${this.assetVersion}`;
    }

    public statusClass(status: any) {
        if (status === true || ['ok', 'active', 'configured', 'success', 'valid'].includes(status)) return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        if (['degraded', 'pending', 'manual', 'inactive', 'expiring'].includes(status)) return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        if (['error', 'failed', 'expired', 'missing'].includes(status)) return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }

    public formatDate(value: any) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString();
    }

    public normalizedPathPickerInput() {
        const raw = String(this.pathPickerInput() || '').trim();
        if (!raw) return '';
        if (raw.startsWith('/') || raw.startsWith('~')) return raw;
        const current = this.pathPickerPath();
        const base = current && current !== '/' ? current.replace(/\/+$/, '') : '';
        return `${base}/${raw}`.replace(/\/{2,}/g, '/');
    }

    public pathPickerParent() {
        const current = this.pathPickerPath();
        if (!current || current === '/') return '';
        const parts = current.split('/').filter(Boolean);
        if (parts.length <= 1) return '/';
        return `/${parts.slice(0, -1).join('/')}`;
    }

    public pathPickerCrumbs() {
        const current = this.pathPickerPath();
        if (!current) return [];
        const parts = current.split('/').filter(Boolean);
        const crumbs = [{ label: '/', path: '/' }];
        let currentPath = '';
        for (const part of parts) {
            currentPath += `/${part}`;
            crumbs.push({ label: part, path: currentPath });
        }
        return crumbs;
    }

    private async uploadPendingAsset(kind: string) {
        const pending = this.pendingAssets[kind];
        if (!pending?.file) return null;
        if (pending.uploaded_asset) return pending.uploaded_asset;
        this.uploading[kind] = true;
        await this.service.render();
        const fd = new FormData();
        fd.append('kind', kind);
        fd.append('file', pending.file);
        const response: any = await this.service.file.upload('/api/system/assets', fd);
        this.uploading[kind] = false;
        if (response?.code === 200) {
            pending.uploaded_asset = response?.data?.asset || null;
            await this.service.render();
            return pending.uploaded_asset;
        }
        await this.alert(response?.data?.message || response?.message || '이미지를 업로드할 수 없습니다.');
        await this.service.render();
        return false;
    }

    private async applyPathPickerSelection(path: string) {
        if (!this.pathPickerTarget) return;
        if (this.pathPickerTarget.type === 'server') {
            this.updateServerSetting(this.pathPickerTarget.serverKey, this.pathPickerTarget.field, path);
        }
        if (this.pathPickerTarget.type === 'certificate') {
            this.certificateForm = { ...this.certificateForm, [this.pathPickerTarget.field]: path };
        }
        this.closePathPicker();
        await this.service.render();
    }

    private updateServerSetting(serverKey: string, field: string, value: string) {
        const runtime = this.webserver();
        const server = runtime?.servers?.[serverKey];
        if (!server) return;
        this.webserver.set({
            ...runtime,
            servers: {
                ...(runtime.servers || {}),
                [serverKey]: {
                    ...server,
                    settings: {
                        ...(server.settings || {}),
                        [field]: value
                    }
                }
            }
        });
    }

    private bumpAssetVersion() {
        this.assetVersion = Date.now();
    }

    private emptyAssetSelection() {
        return { file: null, name: '', preview_url: '', uploaded_asset: null };
    }

    private clearPendingAsset(kind: string) {
        this.releasePendingAsset(kind);
        this.pendingAssets[kind] = this.emptyAssetSelection();
    }

    private releasePendingAsset(kind: string) {
        const previewUrl = this.pendingAssets[kind]?.preview_url;
        if (previewUrl) URL.revokeObjectURL(previewUrl);
    }

    private emptyCertificate(item: any = {}) {
        return {
            id: item.id || '',
            label: item.label || '',
            cert_path: item.cert_path || '',
            key_path: item.key_path || '',
            enabled: item.enabled !== false
        };
    }

    private emptyWebserver() {
        return {
            active_server: 'none',
            servers: {
                nginx: { key: 'nginx', label: 'Nginx', installed: false, daemon_status: 'missing', settings: { config_path: '/etc/nginx/nginx.conf', site_path: '/etc/nginx/sites-enabled' } },
                apache2: { key: 'apache2', label: 'Apache2(httpd)', installed: false, daemon_status: 'missing', settings: { config_path: '/etc/apache2/apache2.conf', site_path: '/etc/apache2/sites-enabled' } }
            },
            certificates: [],
            certificate_summary: {}
        };
    }

    private createDraftId(prefix: string) {
        const cryptoApi = (globalThis as any)?.crypto;
        if (typeof cryptoApi?.randomUUID === 'function') return cryptoApi.randomUUID();
        const seed = `${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
        return `${prefix}-${seed}`;
    }
}
