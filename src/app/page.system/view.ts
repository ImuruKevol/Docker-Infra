import { OnDestroy, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import { AppearanceRuntime } from '@wiz/libs/portal/season/appearance';

const ASSET_KINDS = ['favicon', 'logo'];

export class Component implements OnInit, OnDestroy {
    public loading = signal<boolean>(true);
    public error = signal<string>('');
    public savingGeneral = signal<boolean>(false);
    public backupBusy = signal<boolean>(false);
    public general: any = { browser_title: 'Docker Infra', favicon_url: AppearanceRuntime.assetRoute('favicon'), logo_url: AppearanceRuntime.assetRoute('logo') };
    public backupSystem: any = {};
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
            this.backupSystem = data.backup_system || {};
        } else {
            this.error.set(data?.message || '시스템 설정을 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
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

    public async refreshBackupSystem() {
        if (this.backupBusy()) return;
        this.backupBusy.set(true);
        const { code, data } = await wiz.call('backup_status', {});
        this.backupBusy.set(false);
        if (code === 200) {
            this.backupSystem = data.backup_system || this.backupSystem;
            await this.service.render();
            return;
        }
        await this.alert(data?.message || '백업 시스템 상태를 갱신할 수 없습니다.');
        await this.service.render();
    }

    public async runBackupAction(action: 'start' | 'stop' | 'restart') {
        if (this.backupBusy()) return;
        const labels: any = { start: '시작', stop: '정지', restart: '재시작' };
        this.backupBusy.set(true);
        const { code, data } = await wiz.call(`${action}_backup_system`, {});
        this.backupBusy.set(false);
        if (code === 200) {
            this.backupSystem = data.backup_system || this.backupSystem;
            await this.alert(`백업 시스템 ${labels[action]} 요청을 완료했습니다.`, 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || `백업 시스템을 ${labels[action]}할 수 없습니다.`);
        await this.service.render();
    }

    public backupStatusLabel() {
        const status = this.backupSystem?.status || 'disabled';
        const labels: any = {
            disabled: '사용 안 함',
            pending_install: '설치 필요',
            running: '실행 중',
            stopped: '정지됨',
            failed: '오류',
        };
        return labels[status] || status;
    }

    public formatBytes(value: any) {
        const bytes = Number(value || 0);
        if (bytes <= 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
        const amount = bytes / Math.pow(1024, index);
        return `${amount.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
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
