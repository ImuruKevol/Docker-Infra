import { OnDestroy, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import { AppearanceRuntime } from '@wiz/libs/portal/season/appearance';

const FIELD_LABELS: any = {
    harbor: {
        url: 'Harbor URL',
        username: '계정'
    }
};

const ASSET_KINDS = ['favicon', 'logo'];

export class Component implements OnInit, OnDestroy {
    public loading = signal<boolean>(true);
    public error = signal<string>('');
    public savingGeneral = signal<boolean>(false);
    public general: any = { browser_title: 'Docker Infra', favicon_url: AppearanceRuntime.assetRoute('favicon'), logo_url: AppearanceRuntime.assetRoute('logo') };
    public integrations: any[] = [];
    public uploading: any = { favicon: false, logo: false };
    public assetVersion: number = Date.now();
    public pendingAssets: any = {
        favicon: this.emptyAssetSelection(),
        logo: this.emptyAssetSelection()
    };

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

    public async load() {
        this.loading.set(true);
        this.error.set('');
        const { code, data } = await wiz.call('load', {});
        if (code === 200) {
            this.general = data.general || this.general;
            this.integrations = this.prepareIntegrations(data.integrations || []);
        } else {
            this.error.set(data?.message || '시스템 설정을 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
    }

    public prepareIntegrations(items: any[]) {
        return (items || [])
            .filter((integration: any) => String(integration?.key || '').trim() !== 'gitlab')
            .map((integration: any) => ({
                ...integration,
                secret_visible: false,
                fields: { ...(integration.fields || {}) },
                field_entries: Object.keys(integration.fields || {}).map((field) => ({
                    key: field,
                    label: FIELD_LABELS[integration.key]?.[field] || field
                }))
            }));
    }

    public integrationDescription(integration: any) {
        if (integration?.key === 'harbor') {
            return integration.enabled
                ? '운영 중인 서비스 이미지의 백업과 버전 보관용 저장소로만 사용합니다.'
                : '사용을 켜면 서비스 이미지 백업 저장소 연결 정보를 입력할 수 있습니다.';
        }
        return integration.enabled ? '연결 정보를 저장하고 연결 테스트를 수행할 수 있습니다.' : '현재 사용 안 함 상태입니다.';
    }

    public previewUrl(kind: string) {
        const pending = this.pendingAssets[kind];
        if (pending?.preview_url) return pending.preview_url;
        if (kind === 'favicon') return this.assetUrl(this.general.favicon_url || AppearanceRuntime.assetRoute('favicon'));
        if (kind === 'logo') return this.assetUrl(this.general.logo_url || AppearanceRuntime.assetRoute('logo'));
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

    public assetUrl(url: string) {
        if (!url) return url;
        return `${url}${url.includes('?') ? '&' : '?'}v=${this.assetVersion}`;
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
}
