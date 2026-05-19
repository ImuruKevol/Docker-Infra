import { OnDestroy, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import { AppearanceRuntime } from '@wiz/libs/portal/season/appearance';

const ASSET_KINDS = ['favicon', 'logo'];

export class Component implements OnInit, OnDestroy {
    public loading = signal<boolean>(true);
    public error = signal<string>('');
    public activeTab = signal<string>('general');
    public activeAiTab = signal<string>('codex');
    public savingGeneral = signal<boolean>(false);
    public savingPassword = signal<boolean>(false);
    public savingAi = signal<boolean>(false);
    public savingAiSection = signal<string>('');
    public savingBackupPolicy = signal<boolean>(false);
    public runningBackupPolicy = signal<boolean>(false);
    public cleanupBusy = signal<boolean>(false);
    public backupBusy = signal<boolean>(false);
    public backupNodeRegistryBusy = signal<boolean>(false);
    public refreshingAiProvider = signal<string>('');
    public refreshingAiResources = signal<boolean>(false);
    public refreshingCodexStatus = signal<boolean>(false);
    public testingCodex = signal<boolean>(false);
    public checkingCodexUpdate = signal<boolean>(false);
    public upgradingCodexCli = signal<boolean>(false);
    public codexDeviceLoginBusy = signal<boolean>(false);
    public codexDeviceLoginPolling = signal<boolean>(false);
    public codexDeviceLogin = signal<any>(null);
    public general: any = { browser_title: 'Docker Infra', favicon_url: AppearanceRuntime.assetRoute('favicon'), logo_url: AppearanceRuntime.assetRoute('logo') };
    public adminPassword: any = { current_password: '', new_password: '', confirm_password: '' };
    public aiSettings: any = this.defaultAiSettings();
    public aiTokens: any = { openai: {}, gemini: {} };
    public aiSecrets: any = { openai_api_token: '', gemini_api_token: '' };
    public aiModelCache: any = this.defaultAiModelCache();
    public aiResources: any = { nodes: [], checked_at: null, probe: false };
    public aiSources: any = {};
    public aiCodexStatus: any = {};
    public aiCodexTestResult: any = null;
    public codexUpdate: any = null;
    public codexUpdateOperation: any = null;
    public codexUpdateLog: string = '';
    public aiProviderErrors: any = {};
    public backupSystem: any = {};
    public backupPolicy: any = this.defaultBackupPolicy();
    public backupPolicyResult: any = null;
    public backupPolicyOperation: any = null;
    public backupPolicyLog: string = '';
    public backupPolicyTimer: any = null;
    public backupInstallOperation: any = null;
    public backupInstallLog: string = '';
    public backupInstallTimer: any = null;
    public codexDeviceLoginTimer: any = null;
    public codexUpdateTimer: any = null;
    public backupOperationPolling: boolean = false;
    public backupPolicyOperationPolling: boolean = false;
    public codexUpdateOperationPolling: boolean = false;
    public backupHealth: any = null;
    public backupNodeRegistryResult: any = null;
    public cleanupPlan: any = null;
    public uploading: any = { favicon: false, logo: false };
    public assetVersion: number = Date.now();
    public resetModalOpen = signal<boolean>(false);
    public resetConfirmText = signal<string>('');
    public resetDeleteData = signal<boolean>(true);
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
        this.stopBackupInstallPoll();
        this.stopBackupPolicyPoll();
        this.stopCodexUpdatePoll();
        this.stopCodexDeviceLoginPoll();
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

    public async confirm(message: string, action: string = '확인', status: string = 'warning') {
        return await this.service.modal.show({
            title: '',
            message,
            cancel: '취소',
            action,
            actionBtn: status,
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
            this.syncAiPayload(data.ai_settings || {});
            this.syncBackupPolicy();
        } else {
            this.error.set(data?.message || '시스템 설정을 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
    }

    public setActiveTab(tab: string) {
        this.activeTab.set(tab);
    }

    public setActiveAiTab(tab: string) {
        const allowed = this.aiSubTabItems().map((item: any) => item.key);
        this.activeAiTab.set(allowed.includes(tab) ? tab : 'codex');
    }

    public async saveAiSettings() {
        if (this.savingAi()) return;
        this.savingAi.set(true);
        await this.service.render();
        const payload = {
            ...this.aiSettings,
            openai_api_token: this.aiSecrets.openai_api_token,
            gemini_api_token: this.aiSecrets.gemini_api_token,
        };
        const { code, data } = await wiz.call('save_ai_settings', payload);
        this.savingAi.set(false);
        if (code === 200) {
            this.aiSecrets = { openai_api_token: '', gemini_api_token: '' };
            this.syncAiPayload(data.ai_settings || {});
            await this.alert('AI 설정을 저장했습니다.', 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || 'AI 설정을 저장할 수 없습니다.');
        await this.service.render();
    }

    public aiSectionBusy(section: string) {
        return this.savingAiSection() === section;
    }

    public async saveAiProvider(provider: string) {
        if (this.savingAiSection()) return;
        if (!['openai', 'gemini', 'ollama'].includes(provider)) return;
        this.savingAiSection.set(provider);
        await this.service.render();
        const payload: any = {
            section: provider,
            [provider]: { ...(this.aiSettings?.[provider] || {}) },
        };
        if (provider === 'openai') payload.openai_api_token = this.aiSecrets.openai_api_token;
        if (provider === 'gemini') payload.gemini_api_token = this.aiSecrets.gemini_api_token;
        const { code, data } = await wiz.call('save_ai_section', payload);
        this.savingAiSection.set('');
        if (code === 200) {
            if (provider === 'openai') this.aiSecrets.openai_api_token = '';
            if (provider === 'gemini') this.aiSecrets.gemini_api_token = '';
            this.syncAiPayload(data.ai_settings || {});
            await this.alert(`${this.aiProviderLabel(provider)} 설정을 저장했습니다.`, 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || `${this.aiProviderLabel(provider)} 설정을 저장할 수 없습니다.`);
        await this.service.render();
    }

    public async saveAiRuntime() {
        if (this.savingAiSection()) return;
        this.savingAiSection.set('runtime');
        await this.service.render();
        const runtime = {
            ...(this.aiSettings.runtime || {}),
            mode: this.aiSettings.runtime?.enabled ? 'registered_node' : 'cloud_api',
        };
        const { code, data } = await wiz.call('save_ai_section', { section: 'runtime', runtime });
        this.savingAiSection.set('');
        if (code === 200) {
            this.syncAiPayload(data.ai_settings || {});
            await this.alert('등록 노드 AI 실행 설정을 저장했습니다.', 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || '등록 노드 AI 실행 설정을 저장할 수 없습니다.');
        await this.service.render();
    }

    public async saveAiCodex() {
        if (this.savingAiSection()) return;
        this.savingAiSection.set('codex');
        await this.service.render();
        const codex = { ...(this.aiSettings.codex || {}), cli_mode: 'system' };
        const { code, data } = await wiz.call('save_ai_section', { section: 'codex', codex });
        this.savingAiSection.set('');
        if (code === 200) {
            this.syncAiPayload(data.ai_settings || {});
            await this.alert('Codex 로그인 실행 설정을 저장했습니다.', 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || 'Codex 로그인 실행 설정을 저장할 수 없습니다.');
        await this.service.render();
    }

    public async refreshAiCodexStatus() {
        if (this.refreshingCodexStatus()) return;
        this.refreshingCodexStatus.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('ai_codex_status', { codex: { ...(this.aiSettings.codex || {}), cli_mode: 'system' } });
        this.refreshingCodexStatus.set(false);
        if (code === 200) {
            this.aiCodexStatus = data.codex_status || {};
            await this.service.render();
            return;
        }
        await this.alert(data?.message || 'Codex 로그인 상태를 확인할 수 없습니다.');
        await this.service.render();
    }

    public async testAiCodexLogin() {
        if (this.testingCodex()) return;
        this.testingCodex.set(true);
        this.aiCodexTestResult = null;
        await this.service.render();
        const { code, data } = await wiz.call('ai_codex_test', {
            codex: { ...(this.aiSettings.codex || {}), cli_mode: 'system' },
            prompt: 'Docker Infra 시스템 설정에서 Codex 로그인 실행 테스트 중입니다.'
        });
        this.testingCodex.set(false);
        if (code === 200) {
            this.aiCodexTestResult = data.result || {};
            this.aiCodexStatus = this.aiCodexTestResult.status || this.aiCodexStatus;
            await this.alert('Codex 로그인 실행 테스트를 완료했습니다.', 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || 'Codex 로그인 실행 테스트에 실패했습니다.');
        await this.service.render();
    }

    public async checkCodexCliUpdate() {
        if (this.checkingCodexUpdate()) return;
        this.checkingCodexUpdate.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('ai_codex_cli_update_check', { codex: this.codexConfigPayload() });
        this.checkingCodexUpdate.set(false);
        if (code === 200) {
            this.syncCodexUpdate(data.update || null);
            await this.service.render();
            return;
        }
        await this.alert(data?.message || 'Codex CLI 최신 버전을 확인할 수 없습니다.');
        await this.service.render();
    }

    public async upgradeCodexCli() {
        if (this.upgradingCodexCli()) return;
        if (!this.codexUpdate?.latest_version) {
            await this.checkCodexCliUpdate();
            if (!this.codexUpdate?.latest_version) return;
        }
        const latest = this.codexUpdate?.latest_version || 'latest';
        const ok = await this.confirm(`npm install -g @openai/codex@latest 명령으로 Codex CLI를 ${latest} 버전으로 업그레이드합니다. 진행할까요?`, '업그레이드', 'warning');
        if (!ok) return;
        this.stopCodexUpdatePoll();
        this.upgradingCodexCli.set(true);
        this.codexUpdateOperation = null;
        this.codexUpdateLog = 'Codex CLI 업그레이드 요청을 시작합니다.\n';
        await this.service.render();
        const { code, data } = await wiz.call('ai_codex_cli_upgrade', { codex: this.codexConfigPayload() });
        if (code === 200) {
            this.syncCodexUpdate(data.update || this.codexUpdate);
            this.codexUpdateOperation = data.operation || null;
            this.codexUpdateLog = this.operationOutputText(this.codexUpdateOperation) || this.codexUpdateLog;
            if (this.codexUpdateOperation?.id) {
                this.pollCodexUpdateOperation(this.codexUpdateOperation.id);
            } else {
                this.upgradingCodexCli.set(false);
                this.codexUpdateLog += '업그레이드 작업 ID를 받지 못했습니다.\n';
            }
            await this.service.render();
            return;
        }
        this.upgradingCodexCli.set(false);
        await this.alert(data?.message || 'Codex CLI 업그레이드를 시작할 수 없습니다.');
        await this.service.render();
    }

    private syncCodexUpdate(update: any) {
        if (!update) return;
        this.codexUpdate = update;
        if (update.codex_status) this.aiCodexStatus = update.codex_status || this.aiCodexStatus;
    }

    private pollCodexUpdateOperation(operationId: string) {
        if (!operationId) return;
        this.stopCodexUpdatePoll();
        this.fetchCodexUpdateOperation(operationId);
        this.codexUpdateTimer = window.setInterval(() => this.fetchCodexUpdateOperation(operationId), 1500);
    }

    private stopCodexUpdatePoll() {
        if (!this.codexUpdateTimer) return;
        window.clearInterval(this.codexUpdateTimer);
        this.codexUpdateTimer = null;
    }

    private async fetchCodexUpdateOperation(operationId: string) {
        if (!operationId || this.codexUpdateOperationPolling) return;
        this.codexUpdateOperationPolling = true;
        const { code, data } = await wiz.call('ai_codex_cli_upgrade_status', { operation_id: operationId });
        this.codexUpdateOperationPolling = false;
        if (code !== 200) {
            this.codexUpdateLog += `업그레이드 상태를 확인할 수 없습니다: ${data?.message || 'unknown error'}\n`;
            this.upgradingCodexCli.set(false);
            this.stopCodexUpdatePoll();
            await this.service.render();
            return;
        }
        this.codexUpdateOperation = data.operation || this.codexUpdateOperation;
        this.codexUpdateLog = this.operationOutputText(this.codexUpdateOperation) || this.codexUpdateLog;
        if (this.codexUpdateDone()) {
            this.upgradingCodexCli.set(false);
            this.stopCodexUpdatePoll();
            const after = this.codexUpdateOperation?.result_payload?.after;
            if (after) this.syncCodexUpdate(after);
            if (this.codexUpdateOperation?.status === 'succeeded') {
                await this.alert('Codex CLI 업그레이드를 완료했습니다.', 'success');
            } else if (this.codexUpdateOperation?.status === 'failed') {
                await this.alert(this.codexUpdateOperation?.message || 'Codex CLI 업그레이드에 실패했습니다.');
            }
        }
        await this.service.render();
    }

    private codexConfigPayload() {
        return { ...(this.aiSettings.codex || {}), cli_mode: 'system' };
    }

    private syncCodexDeviceLogin(data: any) {
        if (data?.codex_status) this.aiCodexStatus = data.codex_status || {};
        if (data?.device_login) this.codexDeviceLogin.set(data.device_login);
        else if (!this.codexDeviceLoginActive()) this.codexDeviceLogin.set(null);
        if (this.codexDeviceLoginActive()) this.startCodexDeviceLoginPoll();
        else this.stopCodexDeviceLoginPoll();
    }

    public codexDeviceLoginActive() {
        const status = String(this.codexDeviceLogin()?.status || '');
        return ['starting', 'waiting_for_user'].includes(status);
    }

    public codexDeviceLoginStatusLabel() {
        const status = String(this.codexDeviceLogin()?.status || '');
        const labels: any = {
            starting: '시작 중',
            waiting_for_user: '로그인 대기',
            succeeded: '완료',
            failed: '종료됨',
            canceled: '취소됨',
        };
        return labels[status] || '대기';
    }

    public async startCodexDeviceLogin() {
        if (this.codexDeviceLoginBusy()) return;
        this.codexDeviceLoginBusy.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('ai_codex_device_login_start', { codex: this.codexConfigPayload() });
        this.codexDeviceLoginBusy.set(false);
        if (code === 200) {
            this.syncCodexDeviceLogin(data);
            await this.service.render();
            return;
        }
        await this.alert(data?.message || 'Codex 브라우저 로그인을 시작할 수 없습니다.');
        await this.service.render();
    }

    public async refreshCodexDeviceLoginStatus() {
        if (this.codexDeviceLoginPolling()) return;
        this.codexDeviceLoginPolling.set(true);
        const { code, data } = await wiz.call('ai_codex_device_login_status', { codex: this.codexConfigPayload() });
        this.codexDeviceLoginPolling.set(false);
        if (code === 200) {
            this.syncCodexDeviceLogin(data);
            await this.service.render();
            return;
        }
        this.stopCodexDeviceLoginPoll();
        await this.alert(data?.message || 'Codex 브라우저 로그인 상태를 확인할 수 없습니다.');
        await this.service.render();
    }

    public async cancelCodexDeviceLogin() {
        if (!this.codexDeviceLoginActive()) return;
        const { code, data } = await wiz.call('ai_codex_device_login_cancel', { codex: this.codexConfigPayload() });
        if (code === 200) {
            this.syncCodexDeviceLogin(data);
            await this.service.render();
            return;
        }
        await this.alert(data?.message || 'Codex 브라우저 로그인을 취소할 수 없습니다.');
        await this.service.render();
    }

    public async copyCodexDeviceCode() {
        const code = String(this.codexDeviceLogin()?.user_code || '').trim();
        if (!code) return;
        try {
            await navigator.clipboard.writeText(code);
            await this.alert('Codex one-time code를 복사했습니다.', 'success');
        } catch (error) {
            await this.alert('브라우저에서 클립보드 복사를 허용하지 않았습니다.');
        }
    }

    private startCodexDeviceLoginPoll() {
        if (this.codexDeviceLoginTimer) return;
        this.codexDeviceLoginTimer = setInterval(() => {
            this.refreshCodexDeviceLoginStatus();
        }, 2500);
    }

    private stopCodexDeviceLoginPoll() {
        if (!this.codexDeviceLoginTimer) return;
        clearInterval(this.codexDeviceLoginTimer);
        this.codexDeviceLoginTimer = null;
    }

    public async refreshAiModels(provider: string) {
        if (this.refreshingAiProvider()) return;
        this.refreshingAiProvider.set(provider);
        this.aiProviderErrors[provider] = '';
        await this.service.render();
        const payload = this.aiModelPayload(provider);
        const { code, data } = await wiz.call('ai_models', payload);
        this.refreshingAiProvider.set('');
        if (code === 200) {
            this.aiModelCache[provider] = data.result || this.aiModelCache[provider];
            await this.service.render();
            return;
        }
        this.aiProviderErrors[provider] = data?.message || '모델 목록을 불러올 수 없습니다.';
        await this.alert(this.aiProviderErrors[provider]);
        await this.service.render();
    }

    public async refreshAiResources() {
        if (this.refreshingAiResources()) return;
        this.refreshingAiResources.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('ai_resources', { port: this.aiSettings.runtime?.node_ollama_port || 11434 });
        this.refreshingAiResources.set(false);
        if (code === 200) {
            this.aiResources = data.resources || this.aiResources;
            await this.service.render();
            return;
        }
        await this.alert(data?.message || 'AI 실행 자원 정보를 갱신할 수 없습니다.');
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

    public async changeAdminPassword() {
        if (this.savingPassword()) return;
        if (!this.adminPassword.current_password) {
            await this.alert('현재 비밀번호를 입력해주세요.');
            return;
        }
        if (!this.adminPassword.new_password) {
            await this.alert('새 비밀번호를 입력해주세요.');
            return;
        }
        if (this.adminPassword.new_password !== this.adminPassword.confirm_password) {
            await this.alert('새 비밀번호 확인이 일치하지 않습니다.');
            return;
        }

        this.savingPassword.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('change_admin_password', {
            current_password: this.adminPassword.current_password,
            new_password: this.adminPassword.new_password,
            confirm_password: this.adminPassword.confirm_password
        });
        this.savingPassword.set(false);
        if (code === 200) {
            this.adminPassword = { current_password: '', new_password: '', confirm_password: '' };
            await this.alert('관리자 비밀번호를 변경했습니다.', 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || '관리자 비밀번호를 변경할 수 없습니다.');
        await this.service.render();
    }

    public async refreshBackupSystem() {
        if (this.backupBusy()) return;
        this.backupBusy.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('backup_status', {});
        this.backupBusy.set(false);
        if (code === 200) {
            this.backupSystem = data.backup_system || this.backupSystem;
            this.backupHealth = {
                status: this.backupSystem.status,
                checked_at: new Date().toISOString(),
                message: this.backupSystem.last_error || ''
            };
            this.syncBackupPolicy();
            await this.service.render();
            return;
        }
        await this.alert(data?.message || '백업 시스템 상태를 갱신할 수 없습니다.');
        await this.service.render();
    }

    public async installBackupSystem() {
        if (this.backupInstalling()) return;
        this.backupBusy.set(true);
        this.backupInstallOperation = null;
        this.backupInstallLog = '설치 요청을 시작합니다.\n';
        await this.service.render();
        const { code, data } = await wiz.call('start_backup_system', { background: true });
        this.backupBusy.set(false);
        if (code === 200) {
            this.backupSystem = data.backup_system || this.backupSystem;
            this.backupInstallOperation = data.operation || null;
            this.backupInstallLog = this.operationOutputText(this.backupInstallOperation) || this.backupInstallLog;
            this.pollBackupOperation(this.backupInstallOperation?.id);
            await this.service.render();
            return;
        }
        await this.alert(data?.message || '백업 시스템 설치를 시작할 수 없습니다.');
        await this.service.render();
    }

    public async runBackupAction(action: 'start' | 'stop' | 'restart' | 'disable') {
        if (this.backupBusy()) return;
        const labels: any = { start: '시작', stop: '정지', restart: '재시작', disable: '비활성화' };
        if (action === 'disable') {
            const ok = await this.confirm('서비스 백업 시스템을 사용 안 함으로 바꿉니다. 저장된 백업 데이터는 삭제하지 않습니다.', '비활성화', 'warning');
            if (!ok) return;
        }
        this.backupBusy.set(true);
        const { code, data } = await wiz.call(`${action}_backup_system`, {});
        this.backupBusy.set(false);
        if (code === 200) {
            this.backupSystem = data.backup_system || this.backupSystem;
            this.syncBackupPolicy();
            await this.alert(`백업 시스템 ${labels[action]} 요청을 완료했습니다.`, 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || `백업 시스템을 ${labels[action]}할 수 없습니다.`);
        await this.service.render();
    }

    public async applyBackupRegistryNodes() {
        if (this.backupNodeRegistryBusy()) return;
        const ok = await this.confirm('등록된 서버의 Docker daemon 설정을 갱신합니다. 설정 변경이 필요한 서버는 Docker가 재시작됩니다.', '노드 설정 적용', 'warning');
        if (!ok) return;
        this.backupNodeRegistryBusy.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('apply_backup_registry_nodes', {});
        this.backupNodeRegistryBusy.set(false);
        if (code === 200) {
            this.backupNodeRegistryResult = data;
            const summary = data.operation?.result_payload?.summary || {};
            const message = `노드 백업 설정 결과: 성공 ${summary.ok || 0}개, 건너뜀 ${summary.skipped || 0}개, 실패 ${summary.failed || 0}개`;
            await this.alert(message, summary.failed ? 'warning' : 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || '노드 백업 설정을 적용할 수 없습니다.');
        await this.service.render();
    }

    private pollBackupOperation(operationId: string) {
        if (!operationId) return;
        this.stopBackupInstallPoll();
        this.fetchBackupOperation(operationId);
        this.backupInstallTimer = window.setInterval(() => this.fetchBackupOperation(operationId), 1500);
    }

    private stopBackupInstallPoll() {
        if (!this.backupInstallTimer) return;
        window.clearInterval(this.backupInstallTimer);
        this.backupInstallTimer = null;
    }

    private async fetchBackupOperation(operationId: string) {
        if (!operationId || this.backupOperationPolling) return;
        this.backupOperationPolling = true;
        const { code, data } = await wiz.call('backup_operation_status', { operation_id: operationId });
        this.backupOperationPolling = false;
        if (code !== 200) {
            this.backupInstallLog += `설치 상태를 확인할 수 없습니다: ${data?.message || 'unknown error'}\n`;
            this.stopBackupInstallPoll();
            await this.service.render();
            return;
        }
        this.backupInstallOperation = data.operation || this.backupInstallOperation;
        this.backupInstallLog = this.operationOutputText(this.backupInstallOperation) || this.backupInstallLog;
        if (this.backupInstallDone()) {
            this.stopBackupInstallPoll();
            const status = await wiz.call('backup_status', {});
            if (status.code === 200) {
                this.backupSystem = status.data.backup_system || this.backupSystem;
                this.syncBackupPolicy();
            }
        }
        await this.service.render();
    }

    private pollBackupPolicyOperation(operationId: string) {
        if (!operationId) return;
        this.stopBackupPolicyPoll();
        this.fetchBackupPolicyOperation(operationId);
        this.backupPolicyTimer = window.setInterval(() => this.fetchBackupPolicyOperation(operationId), 1500);
    }

    private stopBackupPolicyPoll() {
        if (!this.backupPolicyTimer) return;
        window.clearInterval(this.backupPolicyTimer);
        this.backupPolicyTimer = null;
    }

    private async fetchBackupPolicyOperation(operationId: string) {
        if (!operationId || this.backupPolicyOperationPolling) return;
        this.backupPolicyOperationPolling = true;
        const { code, data } = await wiz.call('backup_operation_status', { operation_id: operationId });
        this.backupPolicyOperationPolling = false;
        if (code !== 200) {
            this.backupPolicyLog += `백업 상태를 확인할 수 없습니다: ${data?.message || 'unknown error'}\n`;
            this.runningBackupPolicy.set(false);
            this.stopBackupPolicyPoll();
            await this.service.render();
            return;
        }
        this.backupPolicyOperation = data.operation || this.backupPolicyOperation;
        this.backupPolicyLog = this.operationOutputText(this.backupPolicyOperation) || this.backupPolicyLog;
        if (this.backupPolicyProgressDone()) {
            this.runningBackupPolicy.set(false);
            this.stopBackupPolicyPoll();
            this.backupPolicyResult = this.backupPolicyOperation?.result_payload || this.backupPolicyResult;
            const status = await wiz.call('backup_status', {});
            if (status.code === 200) {
                this.backupSystem = status.data.backup_system || this.backupSystem;
                this.syncBackupPolicy();
            }
        }
        await this.service.render();
    }

    public openBackupResetModal() {
        this.resetConfirmText.set('');
        this.resetDeleteData.set(true);
        this.resetModalOpen.set(true);
    }

    public closeBackupResetModal() {
        if (this.backupBusy()) return;
        this.resetModalOpen.set(false);
    }

    public canResetBackupSystem() {
        return this.resetConfirmText().trim() === '초기화';
    }

    public async resetBackupSystem() {
        if (this.backupBusy() || !this.canResetBackupSystem()) return;
        this.backupBusy.set(true);
        const { code, data } = await wiz.call('reset_backup_system', {
            confirm: this.resetConfirmText(),
            delete_data: this.resetDeleteData()
        });
        this.backupBusy.set(false);
        if (code === 200) {
            this.backupSystem = data.backup_system || this.backupSystem;
            this.syncBackupPolicy();
            this.resetModalOpen.set(false);
            await this.alert('백업 시스템을 초기화했습니다.', 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || '백업 시스템을 초기화할 수 없습니다.');
        await this.service.render();
    }

    public async saveBackupPolicy() {
        if (this.savingBackupPolicy()) return;
        this.savingBackupPolicy.set(true);
        const payload = {
            ...this.backupPolicy,
            schedule_type: this.backupPolicy.schedule_type || 'weekly',
            schedule_weekday: Number(this.backupPolicy.schedule_weekday ?? 0),
            schedule_month_day: Number(this.backupPolicy.schedule_month_day ?? 1),
            schedule_time: this.backupPolicy.schedule_time || '02:00',
            window_start: '00:00',
            window_end: '00:00',
            snapshot_pause: true,
        };
        const { code, data } = await wiz.call('save_backup_policy', payload);
        this.savingBackupPolicy.set(false);
        if (code === 200) {
            this.backupSystem = data.backup_system || this.backupSystem;
            this.syncBackupPolicy();
            await this.alert('자동 백업 정책을 저장했습니다.', 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || '자동 백업 정책을 저장할 수 없습니다.');
        await this.service.render();
    }

    public async runBackupPolicyNow() {
        if (this.runningBackupPolicy()) return;
        const ok = await this.confirm('지금 백업 가능한 서비스 이미지와 실행 중인 컨테이너 스냅샷을 내부 백업 시스템에 저장합니다.\n\n스냅샷 대상 컨테이너는 파일 상태 저장을 위해 잠깐 일시 정지될 수 있습니다. 진행할까요?', '지금 백업', 'warning');
        if (!ok) return;
        this.stopBackupPolicyPoll();
        this.runningBackupPolicy.set(true);
        this.backupPolicyOperation = null;
        this.backupPolicyLog = '수동 백업 요청을 시작합니다.\n';
        await this.service.render();
        const { code, data } = await wiz.call('run_backup_policy_now', { include_snapshots: true, snapshot_pause: true, background: true });
        if (code === 200) {
            this.backupSystem = data.backup_system || this.backupSystem;
            this.backupPolicyOperation = data.operation || data.result?.operation || null;
            this.backupPolicyResult = data.result || this.backupPolicyResult;
            this.backupPolicyLog = this.operationOutputText(this.backupPolicyOperation) || this.backupPolicyLog;
            if (this.backupPolicyOperation?.id) {
                this.pollBackupPolicyOperation(this.backupPolicyOperation.id);
            } else {
                this.runningBackupPolicy.set(false);
                this.backupPolicyLog += '백업 작업 ID를 받지 못했습니다.\n';
            }
            await this.service.render();
            return;
        }
        this.runningBackupPolicy.set(false);
        await this.alert(data?.message || '서비스 이미지 백업을 실행할 수 없습니다.');
        await this.service.render();
    }

    public async previewBackupCleanup() {
        if (this.cleanupBusy()) return;
        this.cleanupBusy.set(true);
        const { code, data } = await wiz.call('backup_cleanup_plan', {
            retention_keep_per_service: this.backupPolicy.retention_keep_per_service,
            cleanup_unused_days: this.backupPolicy.cleanup_unused_days
        });
        this.cleanupBusy.set(false);
        if (code === 200) {
            this.cleanupPlan = data.cleanup || null;
            await this.service.render();
            return;
        }
        await this.alert(data?.message || '백업 정리 대상을 확인할 수 없습니다.');
        await this.service.render();
    }

    public async runBackupCleanup() {
        if (this.cleanupBusy()) return;
        const count = Number(this.cleanupPlan?.summary?.count || 0);
        if (count <= 0) {
            await this.previewBackupCleanup();
            if (Number(this.cleanupPlan?.summary?.count || 0) <= 0) return;
        }
        const ok = await this.confirm(`내부 백업 시스템에서 오래되었거나 미사용인 백업 이미지 ${this.cleanupPlan.summary.count}개를 삭제합니다.`, '백업 정리', 'warning');
        if (!ok) return;
        this.cleanupBusy.set(true);
        const { code, data } = await wiz.call('run_backup_cleanup', {
            retention_keep_per_service: this.backupPolicy.retention_keep_per_service,
            cleanup_unused_days: this.backupPolicy.cleanup_unused_days
        });
        this.cleanupBusy.set(false);
        if (code === 200) {
            this.cleanupPlan = data.cleanup || null;
            await this.alert(this.cleanupSummaryLabel(), 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || '백업 이미지를 정리할 수 없습니다.');
        await this.service.render();
    }

    public tabItems() {
        return [
            { key: 'general', label: 'General', icon: 'fa-sliders' },
            { key: 'backup', label: 'Backup', icon: 'fa-box-archive' },
            { key: 'ai', label: 'AI', icon: 'fa-wand-magic-sparkles' },
        ];
    }

    public aiSubTabItems() {
        return [
            { key: 'codex', label: 'Codex', icon: 'fa-terminal', enabled: this.aiSectionEnabled('codex'), summary: this.aiSectionSummary('codex') },
            { key: 'openai', label: 'OpenAI GPT', icon: 'fa-bolt', enabled: this.aiSectionEnabled('openai'), summary: this.aiSectionSummary('openai') },
            { key: 'gemini', label: 'Gemini', icon: 'fa-gem', enabled: this.aiSectionEnabled('gemini'), summary: this.aiSectionSummary('gemini') },
            { key: 'ollama', label: 'Ollama', icon: 'fa-server', enabled: this.aiSectionEnabled('ollama'), summary: this.aiSectionSummary('ollama') },
            { key: 'runtime', label: '등록 노드', icon: 'fa-microchip', enabled: this.aiSectionEnabled('runtime'), summary: this.aiSectionSummary('runtime') },
        ];
    }

    public aiSectionEnabled(section: string) {
        return Boolean(this.aiSettings?.[section]?.enabled);
    }

    public setAiSectionEnabled(section: string, value: boolean) {
        if (section === 'runtime') {
            this.setRuntimeEnabled(value);
            return;
        }
        if (!this.aiSettings?.[section]) return;
        this.aiSettings[section].enabled = Boolean(value);
    }

    public enabledAiSectionsCount() {
        return this.aiSubTabItems().filter((item: any) => item.enabled).length;
    }

    public aiSectionSummary(section: string) {
        if (!this.aiSectionEnabled(section)) return '사용 안 함';
        if (section === 'codex') return `${this.codexLoginStatus()} · ${this.aiSettings.codex?.model || '-'} / ${this.aiSettings.codex?.reasoning_effort || '-'}`;
        if (section === 'openai') return `${this.tokenStatus('openai')} · ${this.selectedModelLabel('openai')} · ${this.modelSortLabel(this.modelSortValue('openai'))}`;
        if (section === 'gemini') return `${this.tokenStatus('gemini')} · ${this.selectedModelLabel('gemini')} · ${this.modelSortLabel(this.modelSortValue('gemini'))}`;
        if (section === 'ollama') return `${this.aiSettings.ollama?.host || '-'}:${this.aiSettings.ollama?.port || '-'} · ${this.selectedModelLabel('ollama')}`;
        if (section === 'runtime') return `${this.selectedRuntimeNodeLabel()} · ${this.aiSettings.runtime?.selected_model || '모델 미선택'}`;
        return '';
    }

    public modelSortOptions() {
        return [
            { value: 'name_asc', label: '모델명 A-Z' },
            { value: 'name_desc', label: '모델명 Z-A' },
            { value: 'latest', label: '최근 생성/수정순' },
            { value: 'oldest', label: '오래된 생성/수정순' },
            { value: 'recommended', label: '권장 상태 우선' },
        ];
    }

    public modelSortLabel(value: string) {
        return this.modelSortOptions().find((item: any) => item.value === value)?.label || '모델명 A-Z';
    }

    public providerModels(provider: string) {
        return this.sortModels(this.aiModelCache?.[provider]?.models || [], this.modelSortValue(provider));
    }

    public modelLabel(model: any) {
        if (!model) return '';
        return model.label || model.id || model.name || '';
    }

    public modelSelectorItems(provider: string) {
        const empty = {
            value: '',
            label: '모델 선택 안 함',
            description: '설정 저장 시 모델을 고정하지 않습니다.',
            badge: '',
            badgeClass: ''
        };
        return [empty, ...this.providerModels(provider).map((model: any) => ({
            value: model.id,
            label: this.modelLabel(model),
            description: this.modelDescription(model),
            badge: this.modelBadge(model),
            badgeClass: this.modelBadgeClass(model),
        }))];
    }

    public selectAiModel(provider: string, value: string) {
        if (!this.aiSettings?.[provider]) return;
        this.aiSettings[provider].selected_model = value || '';
    }

    public selectedProviderModel(provider: string) {
        const selected = String(this.aiSettings?.[provider]?.selected_model || '').replace(/^models\//, '');
        if (!selected) return null;
        return this.providerModels(provider).find((model: any) => model?.id === selected || model?.full_name === selected || model?.full_name === `models/${selected}`) || null;
    }

    public selectedModelLabel(provider: string) {
        const model = this.selectedProviderModel(provider);
        if (model) return this.modelLabel(model);
        return this.aiSettings?.[provider]?.selected_model || '모델 미선택';
    }

    public modelDescription(model: any) {
        if (!model) return '';
        return [
            model.id || model.name,
            this.capabilitySummary(model),
            this.tokenProfileLabel(model),
            this.modelPricingLabel(model),
        ].filter(Boolean).join(' · ');
    }

    public modelBadge(model: any) {
        const state = model?.state || {};
        if (state.level === 'error') return '지원종료';
        if (state.level === 'warning') return '주의';
        return model?.efficiency?.label || '';
    }

    public modelBadgeClass(model: any) {
        const state = model?.state || {};
        if (state.level === 'error') return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        if (state.level === 'warning') return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-200';
        const level = model?.efficiency?.level || 'standard';
        if (level === 'efficient' || level === 'balanced') return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        if (level === 'performance') return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300';
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300';
    }

    public modelDetailRows(provider: string) {
        const model = this.selectedProviderModel(provider);
        if (!model) return [];
        const rows = [
            { label: '지원', value: this.capabilitySummary(model), source: '' },
            { label: '토큰', value: this.tokenProfileLabel(model), source: model?.token_profile?.source || '' },
            { label: '효율', value: this.efficiencyLabel(model), source: '' },
            { label: '요금', value: this.modelPricingLabel(model), source: model?.pricing?.source || '' },
        ];
        const state = model?.state || {};
        if (state.message) rows.push({ label: '상태', value: state.message, source: state.source || '' });
        return rows.filter((row: any) => row.value);
    }

    public capabilitySummary(model: any) {
        const labels = model?.capabilities?.labels || [];
        if (labels.length) return labels.join(', ');
        return '텍스트';
    }

    public tokenProfileLabel(model: any) {
        const token = model?.token_profile || {};
        const input = this.formatCount(token.input_limit);
        const output = this.formatCount(token.output_limit);
        if (input && output) return `입력 ${input} / 출력 ${output} tokens`;
        if (input) return `입력 ${input} tokens`;
        return token.label || '';
    }

    public efficiencyLabel(model: any) {
        const efficiency = model?.efficiency || {};
        return efficiency.note ? `${efficiency.label || '표준'} (${efficiency.note})` : (efficiency.label || '표준');
    }

    public modelPricingLabel(model: any) {
        return model?.pricing?.label || '';
    }

    public aiProviderBusy(provider: string) {
        return this.refreshingAiProvider() === provider;
    }

    public aiProviderLabel(provider: string) {
        const labels: any = { codex: 'Codex', openai: 'OpenAI', gemini: 'Gemini', ollama: 'Ollama' };
        return labels[provider] || provider;
    }

    public codexLoginStatus() {
        const login = this.aiCodexStatus?.login || {};
        if (login.logged_in) return '로그인됨';
        if (login.status === 'missing') return 'CLI 없음';
        if (login.status === 'error') return '확인 오류';
        return '미로그인';
    }

    public codexStatusClass() {
        const login = this.aiCodexStatus?.login || {};
        if (login.logged_in) return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        if (login.status === 'missing' || login.status === 'error') return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-200';
    }

    public codexActiveCliLabel() {
        const active = this.aiCodexStatus?.active || {};
        if (!active.available) return '실행 파일 없음';
        return '일반 Codex CLI';
    }

    public codexStatusRows() {
        const active = this.aiCodexStatus?.active || {};
        const login = this.aiCodexStatus?.login || {};
        return [
            { label: '활성 CLI', value: this.codexActiveCliLabel() },
            { label: '실행 파일', value: active.executable || '-' },
            { label: '버전', value: active.version || '-' },
            { label: '로그인', value: login.message || this.codexLoginStatus() },
        ];
    }

    public codexUpdateRows() {
        const update = this.codexUpdate || {};
        const npm = update.npm || {};
        return [
            { label: 'npm', value: npm.available ? `${npm.version || '-'} · ${npm.executable || '-'}` : 'npm 없음' },
            { label: '패키지', value: update.package_name || '@openai/codex' },
            { label: '현재', value: update.current_version || update.current_version_raw || '-' },
            { label: '최신', value: update.latest_version || '-' },
        ];
    }

    public codexUpdateStatusLabel() {
        if (!this.codexUpdate) return '아직 확인하지 않음';
        if (!this.codexUpdate?.npm?.available) return 'npm 없음';
        if (!this.codexUpdate?.current_version) return '설치 필요';
        if (this.codexUpdate?.update_available) return '업데이트 가능';
        return '최신 상태';
    }

    public codexUpdateStatusClass() {
        if (!this.codexUpdate) return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300';
        if (!this.codexUpdate?.npm?.available) return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        if (this.codexUpdate?.update_available || !this.codexUpdate?.current_version) return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-200';
        return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
    }

    public codexUpdateCheckedAt() {
        const value = this.codexUpdate?.checked_at;
        if (!value) return '없음';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '없음';
        return date.toLocaleString();
    }

    public codexUpdateVisible() {
        return Boolean(this.codexUpdate);
    }

    public codexUpdateCanUpgrade() {
        return Boolean(this.codexUpdate?.latest_version && (this.codexUpdate?.update_available || !this.codexUpdate?.current_version));
    }

    public codexUpdateDone() {
        return ['succeeded', 'failed', 'canceled'].includes(this.codexUpdateOperation?.status);
    }

    public codexUpdateOperationVisible() {
        return Boolean(this.codexUpdateOperation || this.codexUpdateLog);
    }

    public codexUpdateOperationStatusLabel() {
        const status = this.codexUpdateOperation?.status;
        if (status === 'succeeded') return '완료';
        if (status === 'failed') return '실패';
        if (status === 'canceled') return '취소됨';
        if (status === 'running') return '진행 중';
        if (status === 'pending') return '대기 중';
        return this.upgradingCodexCli() ? '준비 중' : '대기';
    }

    public codexUpdateOperationIcon() {
        const status = this.codexUpdateOperation?.status;
        if (status === 'succeeded') return 'fa-circle-check';
        if (status === 'failed' || status === 'canceled') return 'fa-triangle-exclamation';
        return 'fa-spinner fa-spin';
    }

    public codexUpdateOperationOutput() {
        const output = this.operationOutputText(this.codexUpdateOperation) || this.codexUpdateLog;
        return output || '업그레이드 로그를 기다리고 있습니다.\n';
    }

    public codexTestSummary() {
        const result = this.aiCodexTestResult || {};
        const metadata = result.metadata || {};
        const text = String(result.text || '').trim();
        if (!text && !metadata.model) return '';
        return [
            metadata.provider_label || 'Codex 로그인',
            metadata.model || this.aiSettings.codex?.model,
            metadata.reasoning_effort || this.aiSettings.codex?.reasoning_effort,
            text ? text.slice(0, 160) : '',
        ].filter(Boolean).join(' · ');
    }

    public aiProviderStatus(provider: string) {
        const error = this.aiProviderErrors[provider];
        if (error) return { level: 'error', message: error };
        const cache = this.aiModelCache?.[provider] || {};
        const validation = cache.validation || {};
        if (validation.message) return validation;
        if (cache.message) return { level: cache.status === 'ok' ? 'ok' : 'info', message: cache.message };
        return { level: 'info', message: '아직 모델 목록을 불러오지 않았습니다.' };
    }

    public aiStatusClass(status: any) {
        const level = status?.level || 'info';
        if (level === 'error') return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        if (level === 'warning') return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-200';
        if (level === 'ok') return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300';
    }

    public tokenStatus(provider: string) {
        return this.aiTokens?.[provider]?.configured ? '저장됨' : '미설정';
    }

    public aiNodeOptions() {
        const nodes = this.aiResources?.nodes || [];
        return nodes.map((item: any) => item.node).filter((node: any) => node?.id);
    }

    public runtimeNodeItems() {
        return this.aiResources?.nodes || [];
    }

    public selectedRuntimeNodeItem() {
        const nodeId = String(this.aiSettings.runtime?.target_node_id || '');
        if (!nodeId) return null;
        return this.runtimeNodeItems().find((item: any) => String(item.node?.id || '') === nodeId) || null;
    }

    public selectedRuntimeNodeLabel() {
        const item = this.selectedRuntimeNodeItem();
        if (!item) return '노드 미선택';
        return item.node?.name || item.node?.host || '노드 미선택';
    }

    public setRuntimeEnabled(value: boolean) {
        this.aiSettings.runtime.enabled = Boolean(value);
        this.aiSettings.runtime.mode = this.aiSettings.runtime.enabled ? 'registered_node' : 'cloud_api';
    }

    public selectRuntimeNodeById(nodeId: string) {
        const item = this.runtimeNodeItems().find((row: any) => String(row.node?.id || '') === String(nodeId || ''));
        if (!item) {
            this.aiSettings.runtime.target_node_id = '';
            this.aiSettings.runtime.selected_model = '';
            return;
        }
        this.selectRuntimeNode(item);
    }

    public selectRuntimeNode(item: any) {
        this.setRuntimeEnabled(true);
        this.aiSettings.runtime.target_node_id = item?.node?.id || '';
        this.aiSettings.runtime.node_ollama_port = item?.ollama?.port || this.aiSettings.runtime.node_ollama_port || 11434;
        const models = item?.ollama?.models || [];
        const current = this.aiSettings.runtime.selected_model;
        if (!models.find((model: any) => model?.id === current)) {
            this.aiSettings.runtime.selected_model = this.sortModels(models, this.modelSortValue('runtime'))[0]?.id || '';
        }
    }

    public selectRuntimeModel(value: string) {
        this.aiSettings.runtime.selected_model = value || '';
        if (value) this.setRuntimeEnabled(true);
    }

    public runtimeModelSelectorItems() {
        const empty = {
            value: '',
            label: '모델 선택 안 함',
            description: '선택한 노드의 Ollama 모델을 고정하지 않습니다.',
            badge: '',
            badgeClass: ''
        };
        const item = this.selectedRuntimeNodeItem();
        const models = this.sortModels(item?.ollama?.models || [], this.modelSortValue('runtime'));
        return [empty, ...models.map((model: any) => ({
            value: model.id,
            label: this.modelLabel(model),
            description: this.modelDescription(model),
            badge: this.modelBadge(model),
            badgeClass: this.modelBadgeClass(model),
        }))];
    }

    public runtimeNodeStatusLabel(item: any) {
        const status = item?.ollama?.status;
        if (status === 'ok') return 'Ollama 실행 중';
        if (status === 'warning') return 'API 미응답';
        if (status === 'missing') return 'Ollama 없음';
        if (status === 'error') return '스캔 오류';
        return '미스캔';
    }

    public runtimeNodeStatusClass(item: any) {
        const status = item?.ollama?.status;
        if (status === 'ok') return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        if (status === 'warning') return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-200';
        if (status === 'missing' || status === 'error') return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300';
    }

    public runtimeNodeModelSummary(item: any) {
        const count = Number(item?.ollama?.model_count || (item?.ollama?.models || []).length || 0);
        if (count <= 0) return '모델 없음';
        return `${count.toLocaleString()}개 모델`;
    }

    public resourcePayload(item: any) {
        return item?.resource?.payload || {};
    }

    public resourceStatusLabel(item: any) {
        const status = item?.resource?.status;
        if (status === 'ok') return '확인됨';
        if (status === 'error') return '오류';
        return '미확인';
    }

    public gpuSummary(item: any) {
        const payload = this.resourcePayload(item);
        const gpu = payload.gpu || {};
        const nvidiaCount = (gpu.nvidia?.gpus || []).length;
        const radeonCount = (gpu.radeon?.gpus || []).length;
        const pciCount = (gpu.devices || []).length;
        if (nvidiaCount || radeonCount) return `NVIDIA ${nvidiaCount} · Radeon ${radeonCount}`;
        if (pciCount) return `PCI GPU ${pciCount}`;
        return 'GPU 없음';
    }

    public driverLabel(item: any, driver: string) {
        const gpu = this.resourcePayload(item).gpu || {};
        const info = gpu[driver] || {};
        return info.driver_installed ? '설치됨' : '미설치';
    }

    public modelCacheCheckedAt(provider: string) {
        const value = this.aiModelCache?.[provider]?.checked_at;
        if (!value) return '없음';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '없음';
        return date.toLocaleString();
    }

    public backupStatusLabel() {
        return this.backupStatusText(this.backupSystem?.status || 'disabled');
    }

    public backupStatusText(status: string) {
        const labels: any = {
            disabled: '사용 안 함',
            pending_install: '설치 필요',
            running: '실행 중',
            stopped: '정지됨',
            failed: '오류',
        };
        return labels[status] || status;
    }

    public backupHealthLabel() {
        if (!this.backupHealth?.checked_at) return '아직 확인하지 않음';
        const status = this.backupStatusText(this.backupHealth.status || this.backupSystem?.status || 'disabled');
        const checkedAt = new Date(this.backupHealth.checked_at);
        const time = Number.isNaN(checkedAt.getTime()) ? '' : ` · ${checkedAt.toLocaleTimeString()}`;
        return `${status}${time}`;
    }

    public backupInstalling() {
        const status = this.backupInstallOperation?.status;
        return this.backupBusy() || status === 'running' || status === 'pending';
    }

    public backupInstallVisible() {
        return Boolean(this.backupInstallOperation || this.backupInstallLog);
    }

    public backupInstallDone() {
        return ['succeeded', 'failed', 'canceled'].includes(this.backupInstallOperation?.status);
    }

    public backupInstallStatusLabel() {
        const status = this.backupInstallOperation?.status;
        if (status === 'succeeded') return '완료';
        if (status === 'failed') return '실패';
        if (status === 'canceled') return '취소됨';
        if (status === 'running') return '진행 중';
        if (status === 'pending') return '대기 중';
        return this.backupBusy() ? '준비 중' : '대기';
    }

    public backupInstallOutput() {
        const output = this.operationOutputText(this.backupInstallOperation) || this.backupInstallLog;
        return output || '설치 로그를 기다리고 있습니다.\n';
    }

    public backupPolicyProgressVisible() {
        return Boolean(this.backupPolicyOperation || this.backupPolicyLog);
    }

    public backupPolicyProgressDone() {
        return ['succeeded', 'failed', 'canceled'].includes(this.backupPolicyOperation?.status);
    }

    public backupPolicyProgressStatusLabel() {
        const status = this.backupPolicyOperation?.status;
        if (status === 'succeeded') return '완료';
        if (status === 'failed') return '실패';
        if (status === 'canceled') return '취소됨';
        if (status === 'running') return '진행 중';
        if (status === 'pending') return '대기 중';
        return this.runningBackupPolicy() ? '준비 중' : '대기';
    }

    public backupPolicyProgressIcon() {
        const status = this.backupPolicyOperation?.status;
        if (status === 'succeeded') return 'fa-circle-check';
        if (status === 'failed' || status === 'canceled') return 'fa-triangle-exclamation';
        return 'fa-spinner fa-spin';
    }

    public backupPolicyProgressOutput() {
        const output = this.operationOutputText(this.backupPolicyOperation) || this.backupPolicyLog;
        return output || '백업 로그를 기다리고 있습니다.\n';
    }

    public operationOutputText(operation: any) {
        const output = operation?.output;
        if (!Array.isArray(output)) return '';
        return output.map((item: any) => String(item?.message || '')).join('');
    }

    public formatBytes(value: any) {
        const bytes = Number(value || 0);
        if (bytes <= 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
        const amount = bytes / Math.pow(1024, index);
        return `${amount.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
    }

    public formatCount(value: any) {
        const count = Number(value || 0);
        if (count <= 0) return '';
        return count.toLocaleString();
    }

    private modelSortValue(provider: string) {
        const value = String(this.aiSettings?.[provider]?.model_sort || 'name_asc');
        return this.modelSortOptions().some((item: any) => item.value === value) ? value : 'name_asc';
    }

    private sortModels(models: any[], sort: string) {
        const items = [...(models || [])];
        const name = (model: any) => this.modelSortName(model);
        const byNameAsc = (a: any, b: any) => name(a).localeCompare(name(b));
        if (sort === 'name_desc') return items.sort((a: any, b: any) => name(b).localeCompare(name(a)));
        if (sort === 'latest') return items.sort((a: any, b: any) => this.modelTimestamp(b) - this.modelTimestamp(a) || byNameAsc(a, b));
        if (sort === 'oldest') return items.sort((a: any, b: any) => this.modelTimestamp(a) - this.modelTimestamp(b) || byNameAsc(a, b));
        if (sort === 'recommended') {
            return items.sort((a: any, b: any) => {
                return this.modelStateRank(a) - this.modelStateRank(b)
                    || this.modelEfficiencyRank(a) - this.modelEfficiencyRank(b)
                    || byNameAsc(a, b);
            });
        }
        return items.sort(byNameAsc);
    }

    private modelSortName(model: any) {
        return String(model?.label || model?.id || model?.name || '').trim().toLowerCase();
    }

    private modelTimestamp(model: any) {
        const raw = model?.modified_at ?? model?.created ?? model?.updated_at ?? model?.created_at;
        if (typeof raw === 'number') return raw < 10000000000 ? raw * 1000 : raw;
        const parsed = Date.parse(String(raw || ''));
        return Number.isNaN(parsed) ? 0 : parsed;
    }

    private modelStateRank(model: any) {
        const level = model?.state?.level || 'ok';
        if (level === 'ok') return 0;
        if (level === 'warning') return 1;
        if (level === 'error') return 3;
        return 2;
    }

    private modelEfficiencyRank(model: any) {
        const level = model?.efficiency?.level || 'standard';
        const ranks: any = { efficient: 0, balanced: 1, standard: 2, performance: 3, specialized: 4 };
        return ranks[level] ?? 2;
    }

    public backupPolicyLastRunLabel() {
        const value = this.backupPolicy?.last_run_at;
        if (!value) return '없음';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '없음';
        return date.toLocaleString();
    }

    public backupScheduleTypes() {
        return [
            { key: 'weekly', label: '매주', icon: 'fa-calendar-week' },
            { key: 'monthly', label: '매월', icon: 'fa-calendar-days' },
        ];
    }

    public weekdayOptions() {
        return [
            { value: 0, label: '월' },
            { value: 1, label: '화' },
            { value: 2, label: '수' },
            { value: 3, label: '목' },
            { value: 4, label: '금' },
            { value: 5, label: '토' },
            { value: 6, label: '일' },
        ];
    }

    public setBackupScheduleType(type: string) {
        this.backupPolicy.schedule_type = type === 'monthly' ? 'monthly' : 'weekly';
    }

    public setBackupWeekday(day: number) {
        this.backupPolicy.schedule_weekday = Number(day);
    }

    public backupScheduleSummary() {
        if (!this.backupPolicy?.enabled) return '자동 백업이 꺼져 있습니다.';
        const time = this.backupPolicy.schedule_time || '02:00';
        if (this.backupPolicy.schedule_type === 'monthly') {
            const day = Math.max(1, Math.min(31, Number(this.backupPolicy.schedule_month_day || 1)));
            return `매월 ${day}일 ${time}에 실행`;
        }
        return `매주 ${this.backupWeekdayLabel(this.backupPolicy.schedule_weekday)}요일 ${time}에 실행`;
    }

    public backupRetentionSummary() {
        const keep = Number(this.backupPolicy?.retention_keep_per_service || 1);
        const snapshot = this.backupPolicy?.snapshot_enabled ? '컨테이너 상태 포함' : '이미지만 백업';
        return `서비스별 최근 ${keep}개 보존 · ${snapshot}`;
    }

    private backupWeekdayLabel(value: any) {
        const item = this.weekdayOptions().find((option: any) => option.value === Number(value));
        return item?.label || '월';
    }

    public backupPolicyResultLabel() {
        if (!this.backupPolicyResult && !this.backupPolicy?.last_result) return '아직 실행 결과가 없습니다.';
        const result = this.backupPolicyResult || this.backupPolicy?.last_result || {};
        const processed = Number(result.processed || 0);
        const succeeded = Number(result.succeeded || 0);
        const failed = Number(result.failed || 0);
        const snapshots = Number(result.snapshots || 0);
        if (processed === 0) return '백업할 서비스 이미지가 없습니다.';
        return `서비스 이미지 백업 ${processed}건 중 ${succeeded}건 완료, ${failed}건 실패 · 스냅샷 ${snapshots}건`;
    }

    public cleanupSummaryLabel() {
        const summary = this.cleanupPlan?.summary || {};
        const count = Number(summary.count ?? summary.deleted_count ?? 0);
        const deleted = Number(summary.deleted_count || 0);
        const failed = Number(summary.failed_count || 0);
        if (deleted > 0 || failed > 0) return `백업 이미지 ${deleted}개 삭제, ${failed}개 실패`;
        return count > 0 ? `정리 대상 ${count}개` : '정리할 백업 이미지가 없습니다.';
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

    private defaultAiSettings() {
        return {
            codex: { enabled: false, cli_mode: 'system', model: 'gpt-5.5', reasoning_effort: 'xhigh', codex_home: '' },
            openai: { enabled: false, base_url: 'https://api.openai.com/v1', selected_model: '', model_sort: 'name_asc' },
            gemini: { enabled: false, api_version: 'v1beta', selected_model: '', model_sort: 'name_asc' },
            ollama: { enabled: false, scheme: 'http', host: '127.0.0.1', port: 11434, selected_model: '', model_sort: 'name_asc' },
            runtime: { enabled: false, mode: 'cloud_api', target_node_id: '', node_ollama_port: 11434, prefer_gpu: true, selected_model: '', model_sort: 'name_asc' },
        };
    }

    private defaultAiModelCache() {
        return {
            openai: { status: 'not_checked', models: [], checked_at: null, message: '' },
            gemini: { status: 'not_checked', models: [], checked_at: null, message: '' },
            ollama: { status: 'not_checked', models: [], checked_at: null, message: '' },
        };
    }

    private syncAiPayload(payload: any) {
        const defaults = this.defaultAiSettings();
        const config = payload?.config || {};
        this.aiSettings = {
            codex: { ...defaults.codex, ...(config.codex || {}) },
            openai: { ...defaults.openai, ...(config.openai || {}) },
            gemini: { ...defaults.gemini, ...(config.gemini || {}) },
            ollama: { ...defaults.ollama, ...(config.ollama || {}) },
            runtime: { ...defaults.runtime, ...(config.runtime || {}) },
        };
        this.aiTokens = payload?.tokens || { openai: {}, gemini: {} };
        this.aiModelCache = { ...this.defaultAiModelCache(), ...(payload?.model_cache || {}) };
        this.aiResources = payload?.resources || this.aiResources;
        this.aiSources = payload?.sources || {};
        this.aiCodexStatus = payload?.codex_status || this.aiCodexStatus || {};
    }

    private aiModelPayload(provider: string) {
        if (provider === 'openai') {
            return {
                provider,
                ...this.aiSettings.openai,
                api_token: this.aiSecrets.openai_api_token,
            };
        }
        if (provider === 'gemini') {
            return {
                provider,
                ...this.aiSettings.gemini,
                api_token: this.aiSecrets.gemini_api_token,
            };
        }
        return {
            provider,
            ...this.aiSettings.ollama,
        };
    }

    private defaultBackupPolicy() {
        return {
            enabled: false,
            mode: 'manual',
            schedule_type: 'weekly',
            schedule_weekday: 0,
            schedule_month_day: 1,
            schedule_time: '02:00',
            interval_days: 7,
            window_start: '00:00',
            window_end: '00:00',
            max_items_per_run: 3,
            retention_keep_per_service: 10,
            cleanup_unused_days: 30,
            method: 'image_ref',
            snapshot_enabled: false,
            snapshot_pause: true,
            last_run_at: null,
            last_result: null
        };
    }

    private syncBackupPolicy() {
        this.backupPolicy = { ...this.defaultBackupPolicy(), ...(this.backupSystem?.backup_policy || {}) };
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
