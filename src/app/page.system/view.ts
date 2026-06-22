import { OnDestroy, OnInit, signal } from '@angular/core';
import { Router, NavigationEnd } from '@angular/router';
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
    public savingAiDefault = signal<boolean>(false);
    public savingAiSection = signal<string>('');
    public savingBackupPolicy = signal<boolean>(false);
    public runningBackupPolicy = signal<boolean>(false);
    public cleanupBusy = signal<boolean>(false);
    public backupBusy = signal<boolean>(false);
    public refreshingAiProvider = signal<string>('');
    public testingAgent = signal<string>('');
    public refreshingCodexStatus = signal<boolean>(false);
    public testingCodex = signal<boolean>(false);
    public checkingCodexUpdate = signal<boolean>(false);
    public checkingAgentUpdate = signal<string>('');
    public loadingAgentModels = signal<string>('');
    public upgradingCodexCli = signal<boolean>(false);
    public installingAgent = signal<string>('');
    public codexDeviceLoginBusy = signal<boolean>(false);
    public codexDeviceLoginPolling = signal<boolean>(false);
    public codexDeviceLogin = signal<any>(null);
    public claudeLoginBusy = signal<boolean>(false);
    public claudeLoginPolling = signal<boolean>(false);
    public claudeLogin = signal<any>(null);
    public claudeLoginCode: string = '';
    public general: any = { browser_title: 'Docker Infra', favicon_url: AppearanceRuntime.assetRoute('favicon'), logo_url: AppearanceRuntime.assetRoute('logo') };
    public adminPassword: any = { current_password: '', new_password: '', confirm_password: '' };
    public aiSettings: any = this.defaultAiSettings();
    public aiCodexStatus: any = {};
    public aiAgentStatuses: any = {};
    public aiCodexTestResult: any = null;
    public aiAgentTestResult: any = {};
    public codexUpdate: any = null;
    public agentUpdates: any = {};
    public agentModelCatalogs: any = {};
    public codexUpdateOperation: any = null;
    public codexUpdateLog: string = '';
    public agentInstallOperation: any = null;
    public agentInstallLog: string = '';
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
    public claudeLoginTimer: any = null;
    public codexUpdateTimer: any = null;
    public agentInstallTimer: any = null;
    public backupOperationPolling: boolean = false;
    public backupPolicyOperationPolling: boolean = false;
    public codexUpdateOperationPolling: boolean = false;
    public agentInstallOperationPolling: boolean = false;
    public backupHealth: any = null;
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
    private routeSub: any = null;

    constructor(public service: Service, private router: Router) { }

    public async ngOnInit() {
        await this.service.init();
        this.applyRouteSelection();
        await this.syncSystemRoute(true);
        await this.load();
        this.routeSub = this.router.events.subscribe((event: any) => {
            if (event instanceof NavigationEnd) void this.handleRouteNavigation();
        });
    }

    public ngOnDestroy() {
        if (this.routeSub) this.routeSub.unsubscribe();
        for (const kind of ASSET_KINDS) this.releasePendingAsset(kind);
        this.stopBackupInstallPoll();
        this.stopBackupPolicyPoll();
        this.stopCodexUpdatePoll();
        this.stopAgentInstallPoll();
        this.stopCodexDeviceLoginPoll();
        this.stopClaudeLoginPoll();
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
        await this.service.render();
        const section = this.activeTab();
        const { code, data } = await wiz.call('load', { section });
        if (code === 200) {
            this.general = data.general || this.general;
            if (data.backup_system) {
                this.backupSystem = data.backup_system || {};
                this.syncBackupPolicy();
            }
            this.syncAiPayload(data.ai_settings || {});
        } else {
            this.error.set(data?.message || '시스템 설정을 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
        if (code === 200 && this.activeTab() === 'ai') this.refreshVisibleAiStatus();
    }

    private systemTabKeys() {
        return ['general', 'backup', 'ai'];
    }

    private systemSubTabKeys() {
        return ['codex', 'claude_code', 'hermes'];
    }

    private applyRouteSelection() {
        const section = this.service.routeSegment('section');
        const subsection = this.service.routeSegment('subsection');
        const nextSection = this.systemTabKeys().includes(section) ? section : 'general';
        this.activeTab.set(nextSection);
        if (nextSection === 'ai') {
            this.activeAiTab.set(this.systemSubTabKeys().includes(subsection) ? subsection : 'codex');
        }
    }

    private async handleRouteNavigation() {
        const previousTab = this.activeTab();
        const previousAiTab = this.activeAiTab();
        this.applyRouteSelection();
        const currentAiTab = this.activeAiTab();
        if (this.activeTab() === previousTab && currentAiTab === previousAiTab) return;
        if (this.activeTab() === 'ai') {
            if (!this.agentModelCatalogs?.[currentAiTab]) this.refreshAgentModels(currentAiTab);
            this.refreshVisibleAiStatus();
        }
        await this.service.render();
    }

    private systemRoute() {
        const tab = this.activeTab();
        if (tab === 'ai') return `/system/ai/${this.service.encodeRouteSegment(this.activeAiTab() || 'codex')}`;
        if (this.systemTabKeys().includes(tab)) return `/system/${this.service.encodeRouteSegment(tab)}`;
        return '/system/general';
    }

    private async syncSystemRoute(replace: boolean = false) {
        const target = this.systemRoute();
        if (this.service.currentPath() !== target) await this.service.routeTo(target, replace);
    }

    public async setActiveTab(tab: string) {
        if (!this.systemTabKeys().includes(tab)) return;
        this.activeTab.set(tab);
        await this.syncSystemRoute();
        if (tab === 'backup') void this.load();
        if (tab === 'ai') this.refreshVisibleAiStatus();
    }

    public async setActiveAiTab(tab: string) {
        const allowed = this.aiSubTabItems().map((item: any) => item.key);
        const nextTab = allowed.includes(tab) ? tab : 'codex';
        this.activeAiTab.set(nextTab);
        await this.syncSystemRoute();
        if (!this.agentModelCatalogs?.[nextTab]) this.refreshAgentModels(nextTab);
        this.refreshVisibleAiStatus();
    }

    private refreshVisibleAiStatus() {
        const tab = this.activeAiTab();
        if (tab === 'codex') {
            void this.refreshAiCodexStatus();
            return;
        }
        if (this.systemSubTabKeys().includes(tab)) void this.refreshAgentStatus(tab);
    }

    public async saveAiSettings() {
        if (this.savingAi()) return;
        this.savingAi.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('save_ai_settings', { ...this.aiSettings });
        this.savingAi.set(false);
        if (code === 200) {
            this.syncAiPayload(data.ai_settings || {});
            await this.alert('AI 설정을 저장했습니다.', 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || 'AI 설정을 저장할 수 없습니다.');
        await this.service.render();
    }

    public async saveAiDefaultAgent() {
        if (this.savingAiDefault()) return;
        const agent = this.aiSettings?.default_agent || this.enabledAiAgentKeys()[0] || '';
        if (!agent) return;
        this.savingAiDefault.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('save_ai_default_agent', { default_agent: agent });
        this.savingAiDefault.set(false);
        if (code === 200) {
            this.syncAiPayload(data.ai_settings || {});
            await this.alert('기본 AI Agent를 저장했습니다.', 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || '기본 AI Agent를 저장할 수 없습니다.');
        await this.service.render();
    }

    public aiSectionBusy(section: string) {
        return this.savingAiSection() === section;
    }

    public async saveAiProvider(provider: string) {
        if (this.savingAiSection()) return;
        if (!this.agentKeys().includes(provider)) return;
        if (provider === 'hermes') {
            await this.applyHermesSettings();
            return;
        }
        this.savingAiSection.set(provider);
        await this.service.render();
        const payload: any = {
            section: provider,
            [provider]: this.agentConfigPayload(provider),
        };
        const { code, data } = await wiz.call('save_ai_section', payload);
        this.savingAiSection.set('');
        if (code === 200) {
            this.syncAiPayload(data.ai_settings || {});
            await this.alert(`${this.aiProviderLabel(provider)} 설정을 저장했습니다.`, 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || `${this.aiProviderLabel(provider)} 설정을 저장할 수 없습니다.`);
        await this.service.render();
    }

    public async applyHermesSettings() {
        if (this.savingAiSection()) return;
        this.savingAiSection.set('hermes');
        await this.service.render();
        const payload: any = {
            hermes: this.agentConfigPayload('hermes'),
            api_key: String(this.aiSettings?.hermes?.api_key || '').trim(),
        };
        const { code, data } = await wiz.call('ai_hermes_apply_settings', payload);
        this.savingAiSection.set('');
        if (code === 200) {
            this.aiSettings.hermes.api_key = '';
            this.syncAiPayload(data.ai_settings || {});
            if (data?.result?.agent_status) {
                this.aiAgentStatuses = { ...(this.aiAgentStatuses || {}), hermes: data.result.agent_status };
            }
            await this.alert('헤르메스 에이전트 설정을 저장했습니다.', 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || '헤르메스 에이전트 설정을 저장할 수 없습니다.');
        await this.service.render();
    }

    public async saveAiCodex() {
        if (this.savingAiSection()) return;
        this.savingAiSection.set('codex');
        await this.service.render();
        const codex = this.codexConfigPayload();
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
        const { code, data } = await wiz.call('ai_codex_status', { codex: this.codexConfigPayload() });
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
            codex: this.codexConfigPayload(),
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
        const ok = await this.confirm('Node.js/npm이 없으면 먼저 설치하고, @openai/codex@latest를 global 설치/업데이트합니다. 진행할까요?', '설치 실행', 'warning');
        if (!ok) return;
        this.stopCodexUpdatePoll();
        this.upgradingCodexCli.set(true);
        this.codexUpdateOperation = null;
        this.codexUpdateLog = 'Codex CLI 설치/업데이트 요청을 시작합니다.\n';
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
                this.codexUpdateLog += '설치 작업 ID를 받지 못했습니다.\n';
            }
            await this.service.render();
            return;
        }
        this.upgradingCodexCli.set(false);
        await this.alert(data?.message || 'Codex CLI 설치/업데이트를 시작할 수 없습니다.');
        await this.service.render();
    }

    private syncCodexUpdate(update: any) {
        if (!update) return;
        this.codexUpdate = update;
        this.agentUpdates = { ...(this.agentUpdates || {}), codex: update };
        if (update.codex_status) this.aiCodexStatus = update.codex_status || this.aiCodexStatus;
    }

    private syncAgentUpdate(agent: string, update: any) {
        if (!agent || !update) return;
        if (agent === 'codex') {
            this.syncCodexUpdate(update);
            return;
        }
        this.agentUpdates = { ...(this.agentUpdates || {}), [agent]: update };
        if (update.agent_status) {
            this.aiAgentStatuses = { ...(this.aiAgentStatuses || {}), [agent]: update.agent_status };
        }
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
        this.syncCodexUpdate(data.update || null);
        this.codexUpdateLog = this.operationOutputText(this.codexUpdateOperation) || this.codexUpdateLog;
        if (this.codexUpdateDone()) {
            this.upgradingCodexCli.set(false);
            this.stopCodexUpdatePoll();
            const after = this.codexUpdateOperation?.result_payload?.after;
            if (after) this.syncCodexUpdate(after);
            if (this.codexUpdateOperation?.status === 'succeeded') {
                await this.alert('Codex CLI 설치/업데이트를 완료했습니다.', 'success');
            } else if (this.codexUpdateOperation?.status === 'failed') {
                await this.alert(this.codexUpdateOperation?.message || 'Codex CLI 설치/업데이트에 실패했습니다.');
            }
        }
        await this.service.render();
    }

    public async installAiAgent(agent: string) {
        if (!agent || this.installingAgent()) return;
        const label = this.aiProviderLabel(agent);
        const ok = await this.confirm(this.agentInstallConfirmMessage(agent), '설치 실행', 'warning');
        if (!ok) return;
        this.stopAgentInstallPoll();
        this.installingAgent.set(agent);
        this.agentInstallOperation = null;
        this.agentInstallLog = `${label} 설치/업데이트 요청을 시작합니다.\n`;
        await this.service.render();
        const payload: any = { agent };
        payload[agent] = this.agentConfigPayload(agent);
        const { code, data } = await wiz.call('ai_agent_install', payload);
        if (code === 200) {
            this.syncAgentUpdate(agent, data.update || null);
            this.agentInstallOperation = data.operation || null;
            this.agentInstallLog = this.operationOutputText(this.agentInstallOperation) || this.agentInstallLog;
            if (this.agentInstallOperation?.id) {
                this.pollAgentInstallOperation(this.agentInstallOperation.id);
            } else {
                this.installingAgent.set('');
                this.agentInstallLog += '설치 작업 ID를 받지 못했습니다.\n';
            }
            await this.service.render();
            return;
        }
        this.installingAgent.set('');
        await this.alert(data?.message || `${label} 설치/업데이트를 시작할 수 없습니다.`);
        await this.service.render();
    }

    private agentInstallConfirmMessage(agent: string) {
        const label = this.aiProviderLabel(agent);
        return `${label} 설치/업데이트 스크립트를 서버에서 실행합니다. 진행할까요?`;
    }

    private agentConfigPayload(agent: string) {
        if (agent === 'codex') return this.codexConfigPayload();
        const config = this.aiSettings?.[agent] || {};
        const payload: any = {
            enabled: Boolean(config.enabled),
            model: config.model || '',
        };
        if (agent === 'hermes') {
            payload.provider = config.provider || 'openrouter';
            payload.terminal_backend = config.terminal_backend || 'local';
            payload.terminal_timeout = Number(config.terminal_timeout || 180);
        }
        return payload;
    }

    private pollAgentInstallOperation(operationId: string) {
        if (!operationId) return;
        this.stopAgentInstallPoll();
        this.fetchAgentInstallOperation(operationId);
        this.agentInstallTimer = window.setInterval(() => this.fetchAgentInstallOperation(operationId), 1500);
    }

    private stopAgentInstallPoll() {
        if (!this.agentInstallTimer) return;
        window.clearInterval(this.agentInstallTimer);
        this.agentInstallTimer = null;
    }

    private async fetchAgentInstallOperation(operationId: string) {
        if (!operationId || this.agentInstallOperationPolling) return;
        this.agentInstallOperationPolling = true;
        const { code, data } = await wiz.call('ai_agent_install_status', { operation_id: operationId });
        this.agentInstallOperationPolling = false;
        if (code !== 200) {
            this.agentInstallLog += `설치 상태를 확인할 수 없습니다: ${data?.message || 'unknown error'}\n`;
            this.installingAgent.set('');
            this.stopAgentInstallPoll();
            await this.service.render();
            return;
        }
        this.agentInstallOperation = data.operation || this.agentInstallOperation;
        const operationAgent = this.agentInstallOperation?.target_id || this.installingAgent();
        this.syncAgentUpdate(operationAgent, data.update || this.agentInstallOperation?.result_payload?.after_update || null);
        this.agentInstallLog = this.operationOutputText(this.agentInstallOperation) || this.agentInstallLog;
        if (this.agentInstallDone()) {
            const agent = this.agentInstallOperation?.target_id || this.installingAgent();
            this.installingAgent.set('');
            this.stopAgentInstallPoll();
            if (agent) await this.refreshAgentStatus(agent);
        }
        await this.service.render();
    }

    public async checkAgentUpdate(agent: string) {
        if (!agent || this.checkingAgentUpdate()) return;
        this.checkingAgentUpdate.set(agent);
        await this.service.render();
        const payload: any = { agent };
        payload[agent] = this.agentConfigPayload(agent);
        const { code, data } = await wiz.call('ai_agent_update_check', payload);
        this.checkingAgentUpdate.set('');
        if (code === 200) {
            this.syncAgentUpdate(agent, data.update || null);
            await this.service.render();
            return;
        }
        await this.alert(data?.message || `${this.aiProviderLabel(agent)} 최신 버전을 확인할 수 없습니다.`);
        await this.service.render();
    }

    public agentModelsBusy(agent: string) {
        return this.loadingAgentModels() === agent;
    }

    public agentModelItems(agent: string) {
        const catalog = this.agentModelCatalogs?.[agent] || {};
        const items = Array.isArray(catalog.items) ? catalog.items : [];
        if (items.length) return items;
        const current = this.aiSettings?.[agent]?.model || '';
        if (!current) return [];
        return [{
            value: current,
            label: `${current} (현재 설정)`,
            description: '현재 저장된 모델입니다.',
            badge: '현재',
            badgeClass: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300',
        }];
    }

    public agentModelCatalogLabel(agent: string) {
        const catalog = this.agentModelCatalogs?.[agent] || {};
        if (!catalog.checked_at) return '모델 목록 미확인';
        const source = catalog?.source?.label || '공식 출처';
        const date = new Date(catalog.checked_at);
        const checkedAt = Number.isNaN(date.getTime()) ? '방금' : date.toLocaleString();
        return catalog.fallback ? `${source} 기본 목록 · ${checkedAt}` : `${source} 공식 목록 · ${checkedAt}`;
    }

    public async refreshAgentModels(agent: string) {
        if (!agent || this.loadingAgentModels()) return;
        this.loadingAgentModels.set(agent);
        await this.service.render();
        const payload: any = { agent };
        payload[agent] = this.agentConfigPayload(agent);
        const { code, data } = await wiz.call('ai_agent_model_catalog', payload);
        this.loadingAgentModels.set('');
        if (code === 200) {
            this.agentModelCatalogs = { ...(this.agentModelCatalogs || {}), [agent]: data.catalog || {} };
            await this.service.render();
            return;
        }
        await this.alert(data?.message || `${this.aiProviderLabel(agent)} 모델 목록을 가져올 수 없습니다.`);
        await this.service.render();
    }

    private codexConfigPayload() {
        const config = this.aiSettings.codex || {};
        return {
            enabled: Boolean(config.enabled),
            cli_mode: 'system',
            model: config.model || '',
            reasoning_effort: config.reasoning_effort || 'xhigh',
        };
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

    private syncClaudeLogin(data: any) {
        if (data?.agent_status) {
            this.aiAgentStatuses = { ...(this.aiAgentStatuses || {}), claude_code: data.agent_status };
        }
        if (data?.claude_login) this.claudeLogin.set(data.claude_login);
        else if (!this.claudeLoginActive()) this.claudeLogin.set(null);
        if (this.claudeLoginActive()) this.startClaudeLoginPoll();
        else this.stopClaudeLoginPoll();
    }

    public claudeLoginActive() {
        const status = String(this.claudeLogin()?.status || '');
        return ['starting', 'waiting_for_user', 'waiting_for_code', 'verifying'].includes(status);
    }

    public claudeLoginStatusLabel() {
        const status = String(this.claudeLogin()?.status || '');
        const labels: any = {
            starting: '시작 중',
            waiting_for_user: '로그인 대기',
            waiting_for_code: '코드 입력',
            verifying: '확인 중',
            succeeded: '완료',
            failed: '종료됨',
            canceled: '취소됨',
        };
        return labels[status] || '대기';
    }

    public async startClaudeLogin() {
        if (this.claudeLoginBusy()) return;
        this.claudeLoginBusy.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('ai_claude_code_login_start', { claude_code: this.agentConfigPayload('claude_code') });
        this.claudeLoginBusy.set(false);
        if (code === 200) {
            this.syncClaudeLogin(data);
            await this.service.render();
            return;
        }
        await this.alert(data?.message || 'Claude Code 브라우저 로그인을 시작할 수 없습니다.');
        await this.service.render();
    }

    public async refreshClaudeLoginStatus() {
        if (this.claudeLoginPolling()) return;
        this.claudeLoginPolling.set(true);
        const { code, data } = await wiz.call('ai_claude_code_login_status', { claude_code: this.agentConfigPayload('claude_code') });
        this.claudeLoginPolling.set(false);
        if (code === 200) {
            this.syncClaudeLogin(data);
            await this.service.render();
            return;
        }
        this.stopClaudeLoginPoll();
        await this.alert(data?.message || 'Claude Code 브라우저 로그인 상태를 확인할 수 없습니다.');
        await this.service.render();
    }

    public async submitClaudeLoginCode() {
        if (!this.claudeLoginActive()) return;
        const value = String(this.claudeLoginCode || '').trim();
        if (!value) {
            await this.alert('Claude Code 로그인 코드를 입력하세요.');
            return;
        }
        const { code, data } = await wiz.call('ai_claude_code_login_submit', {
            claude_code: this.agentConfigPayload('claude_code'),
            code: value,
        });
        if (code === 200) {
            this.claudeLoginCode = '';
            this.syncClaudeLogin(data);
            await this.service.render();
            return;
        }
        await this.alert(data?.message || 'Claude Code 로그인 코드를 전달할 수 없습니다.');
        await this.service.render();
    }

    public async cancelClaudeLogin() {
        if (!this.claudeLoginActive()) return;
        const { code, data } = await wiz.call('ai_claude_code_login_cancel', { claude_code: this.agentConfigPayload('claude_code') });
        if (code === 200) {
            this.syncClaudeLogin(data);
            await this.service.render();
            return;
        }
        await this.alert(data?.message || 'Claude Code 브라우저 로그인을 취소할 수 없습니다.');
        await this.service.render();
    }

    private startClaudeLoginPoll() {
        if (this.claudeLoginTimer) return;
        this.claudeLoginTimer = setInterval(() => {
            this.refreshClaudeLoginStatus();
        }, 2500);
    }

    private stopClaudeLoginPoll() {
        if (!this.claudeLoginTimer) return;
        clearInterval(this.claudeLoginTimer);
        this.claudeLoginTimer = null;
    }

    public async refreshAgentStatus(provider: string) {
        if (this.refreshingAiProvider()) return;
        this.refreshingAiProvider.set(provider);
        this.aiProviderErrors[provider] = '';
        await this.service.render();
        const { code, data } = await wiz.call('ai_agent_status', {
            agent: provider,
            [provider]: this.agentConfigPayload(provider),
        });
        this.refreshingAiProvider.set('');
        if (code === 200) {
            this.aiAgentStatuses[provider] = data.agent_status || {};
            if (provider === 'codex') this.aiCodexStatus = data.agent_status || this.aiCodexStatus;
            await this.service.render();
            return;
        }
        this.aiProviderErrors[provider] = data?.message || 'Agent 상태를 확인할 수 없습니다.';
        await this.alert(this.aiProviderErrors[provider]);
        await this.service.render();
    }

    public async testAiAgent(provider: string) {
        if (this.testingAgent()) return;
        this.testingAgent.set(provider);
        this.aiAgentTestResult[provider] = null;
        await this.service.render();
        const { code, data } = await wiz.call('ai_agent_test', {
            agent: provider,
            [provider]: this.agentConfigPayload(provider),
            prompt: 'Docker Infra 시스템 설정에서 AI Agent 실행 테스트 중입니다.'
        });
        this.testingAgent.set('');
        if (code === 200) {
            this.aiAgentTestResult[provider] = data.result || {};
            this.aiAgentStatuses[provider] = this.aiAgentTestResult[provider]?.status || this.aiAgentStatuses[provider] || {};
            await this.alert(`${this.aiProviderLabel(provider)} 실행 테스트를 완료했습니다.`, 'success');
            await this.service.render();
            return;
        }
        await this.alert(data?.message || `${this.aiProviderLabel(provider)} 실행 테스트에 실패했습니다.`);
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
            method: 'container_snapshot',
            snapshot_enabled: true,
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
        const ok = await this.confirm('지금 실행 중인 컨테이너 상태 스냅샷을 내부 백업 시스템에 저장합니다.\n\n스냅샷 대상 컨테이너는 파일 상태 저장을 위해 잠깐 일시 정지될 수 있습니다. 진행할까요?', '지금 백업', 'warning');
        if (!ok) return;
        this.stopBackupPolicyPoll();
        this.runningBackupPolicy.set(true);
        this.backupPolicyOperation = null;
        this.backupPolicyLog = '수동 백업 요청을 시작합니다.\n';
        await this.service.render();
        const { code, data } = await wiz.call('run_backup_policy_now', { snapshot_pause: true, background: true });
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
        await this.alert(data?.message || '서비스 상태 백업을 실행할 수 없습니다.');
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
            { key: 'claude_code', label: 'Claude Code', icon: 'fa-code', enabled: this.aiSectionEnabled('claude_code'), summary: this.aiSectionSummary('claude_code') },
            { key: 'hermes', label: '헤르메스', icon: 'fa-network-wired', enabled: this.aiSectionEnabled('hermes'), summary: this.aiSectionSummary('hermes') },
        ];
    }

    public agentKeys() {
        return ['codex', 'claude_code', 'hermes'];
    }

    public aiSectionEnabled(section: string) {
        return Boolean(this.aiSettings?.[section]?.enabled);
    }

    public setAiSectionEnabled(section: string, value: boolean) {
        if (!this.aiSettings?.[section]) return;
        this.aiSettings[section].enabled = Boolean(value);
        this.ensureDefaultAiAgent();
    }

    public enabledAiSectionsCount() {
        return this.aiSubTabItems().filter((item: any) => item.enabled).length;
    }

    public enabledAiAgentKeys() {
        return this.agentKeys().filter((agent: string) => this.aiSectionEnabled(agent));
    }

    public defaultAiAgentVisible() {
        return this.enabledAiAgentKeys().length > 1;
    }

    public defaultAgentOptions() {
        return this.aiSubTabItems()
            .filter((item: any) => item.enabled)
            .map((item: any) => ({
                value: item.key,
                label: item.label,
                description: item.summary,
                badge: '기본 후보',
                badgeClass: item.key === this.aiSettings?.default_agent
                    ? 'border-zinc-950 bg-zinc-950 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-950'
                    : 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300',
            }));
    }

    public setDefaultAiAgent(agent: string) {
        if (!this.aiSettings) return;
        if (!this.enabledAiAgentKeys().includes(agent)) return;
        this.aiSettings.default_agent = agent;
    }

    public aiSectionSummary(section: string) {
        if (!this.aiSectionEnabled(section)) return '사용 안 함';
        if (section === 'codex') return `${this.codexLoginStatus()} · ${this.aiSettings.codex?.model || '-'} / ${this.aiSettings.codex?.reasoning_effort || '-'}`;
        if (section === 'claude_code' || section === 'hermes') return `${this.agentStatusLabel(section)} · ${this.aiSettings[section]?.model || '-'}`;
        return '';
    }

    public aiProviderBusy(provider: string) {
        return this.refreshingAiProvider() === provider;
    }

    public aiProviderLabel(provider: string) {
        const labels: any = { codex: 'Codex', claude_code: 'Claude Code', hermes: '헤르메스 에이전트' };
        return labels[provider] || provider;
    }

    public agentStatus(provider: string) {
        if (provider === 'codex') return this.aiCodexStatus || {};
        return this.aiAgentStatuses?.[provider] || {};
    }

    public agentStatusLabel(provider: string) {
        const status = this.agentStatus(provider);
        const login = status?.login || {};
        const active = status?.active || {};
        if (provider === 'claude_code') {
            if (login.logged_in) return '로그인됨';
            if (active.available) return '미로그인';
            if (login.status === 'missing') return 'CLI 없음';
            if (login.status === 'error') return '확인 오류';
            return '미확인';
        }
        if (login.logged_in || active.available) return '사용 가능';
        if (login.status === 'missing') return 'CLI 없음';
        if (login.status === 'error') return '확인 오류';
        return '미확인';
    }

    public agentStatusClass(provider: string) {
        const status = this.agentStatus(provider);
        const login = status?.login || {};
        const active = status?.active || {};
        if (provider === 'claude_code' && active.available && !login.logged_in) {
            return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-200';
        }
        if (login.logged_in || active.available) return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        if (login.status === 'missing' || login.status === 'error') return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-200';
    }

    public agentStatusRows(provider: string) {
        const status = this.agentStatus(provider);
        const login = status?.login || {};
        return [
            { label: 'Agent', value: this.aiProviderLabel(provider) },
            { label: '모델', value: this.aiSettings?.[provider]?.model || status?.model || '-' },
            { label: '버전', value: this.agentVersionLabel(provider) },
            { label: '상태', value: login.message || this.agentStatusLabel(provider) },
        ];
    }

    public agentVersionLabel(provider: string) {
        const active = this.agentStatus(provider)?.active || {};
        return active.version || this.agentUpdate(provider)?.current_version || this.agentUpdate(provider)?.current_version_raw || '-';
    }

    public agentUpdate(provider: string) {
        if (provider === 'codex') return this.codexUpdate || this.agentUpdates?.codex || null;
        return this.agentUpdates?.[provider] || null;
    }

    public agentInstallMethod(provider: string) {
        const update = this.agentUpdate(provider);
        if (update?.install_method) return String(update.install_method);
        if (provider === 'claude_code' || provider === 'hermes') return 'script';
        return 'npm';
    }

    public agentInstallButtonLabel(provider: string) {
        if (this.agentInstallBusy(provider)) return '진행 중';
        if (this.agentInstalled(provider) && this.agentUpgradePolicy(provider) === 'manual') return '업그레이드';
        return '설치 스크립트 실행';
    }

    public agentInstalled(provider: string) {
        const active = this.agentStatus(provider)?.active || {};
        const update = this.agentUpdate(provider) || {};
        return Boolean(active.available || update.current_version || update.current_version_raw);
    }

    public agentUpgradePolicy(provider: string) {
        const update = this.agentUpdate(provider) || {};
        if (update.upgrade_policy) return String(update.upgrade_policy);
        if (provider === 'claude_code') return 'automatic';
        return 'manual';
    }

    public agentInstallActionVisible(provider: string) {
        if (!this.agentInstalled(provider)) return true;
        return this.agentUpgradePolicy(provider) === 'manual';
    }

    public agentUpgradeNotice(provider: string) {
        if (provider === 'claude_code' && this.agentInstalled(provider) && this.agentUpgradePolicy(provider) === 'automatic') {
            return '설치된 Claude Code는 실행 중 백그라운드로 자동 업데이트됩니다.';
        }
        return '';
    }

    public checkingAgentUpdateFor(provider: string) {
        return this.checkingAgentUpdate() === provider;
    }

    public agentUpdateCheckVisible(provider: string) {
        return provider !== 'claude_code';
    }

    public agentLatestVersionLabel(provider: string) {
        const update = this.agentUpdate(provider);
        if (this.agentInstallMethod(provider) === 'script') {
            const mode = this.agentUpgradePolicy(provider) === 'automatic' ? '자동 업데이트' : '수동 업그레이드';
            return `${mode} · 마지막 확인 ${this.agentUpdateCheckedAt(provider)}`;
        }
        if (!update) return `최신 버전 확인 전 · 마지막 확인 ${this.agentUpdateCheckedAt(provider)}`;
        const latest = update?.latest_version || '-';
        return `최신 ${latest} · 마지막 확인 ${this.agentUpdateCheckedAt(provider)}`;
    }

    public agentUpdateCheckedAt(provider: string) {
        const value = this.agentUpdate(provider)?.checked_at;
        if (!value) return '없음';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '없음';
        return date.toLocaleString();
    }

    public agentUpdateStatusLabel(provider: string) {
        const update = this.agentUpdate(provider);
        if (!update) return '아직 확인하지 않음';
        if (this.agentInstallMethod(provider) === 'script') {
            if (!update?.current_version) return '설치 필요';
            return '설치됨';
        }
        if (!update?.npm?.available) return 'npm 없음';
        if (!update?.current_version) return '설치 필요';
        if (update?.update_available) return '업데이트 가능';
        return '최신 상태';
    }

    public agentUpdateStatusClass(provider: string) {
        const update = this.agentUpdate(provider);
        if (!update) return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300';
        if (this.agentInstallMethod(provider) === 'script') {
            if (!update?.current_version) return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-200';
            return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        }
        if (!update?.npm?.available) return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        if (update?.update_available || !update?.current_version) return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-200';
        return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
    }

    public agentUpdateCanUpgrade(provider: string) {
        const update = this.agentUpdate(provider);
        if (this.agentInstallMethod(provider) === 'script') {
            if (!this.agentInstalled(provider)) return true;
            return this.agentUpgradePolicy(provider) === 'manual';
        }
        if (!update) return true;
        if (!update?.npm?.available) return true;
        return Boolean(!update?.current_version || update?.update_available);
    }

    public agentTestSummary(provider: string) {
        const result = this.aiAgentTestResult?.[provider] || {};
        const metadata = result.metadata || {};
        const text = String(result.text || '').trim();
        if (!text && !metadata.model) return '';
        return [
            metadata.provider_label || this.aiProviderLabel(provider),
            metadata.model || this.aiSettings?.[provider]?.model,
            text ? text.slice(0, 160) : '',
        ].filter(Boolean).join(' · ');
    }

    public hermesProviderOptions() {
        return [
            { value: 'openrouter', label: 'OpenRouter' },
            { value: 'anthropic', label: 'Anthropic' },
            { value: 'openai-api', label: 'OpenAI API' },
            { value: 'gemini', label: 'Gemini' },
            { value: 'xai', label: 'xAI' },
            { value: 'deepseek', label: 'DeepSeek' },
            { value: 'novita', label: 'NovitaAI' },
        ];
    }

    public hermesTerminalBackendOptions() {
        return [
            { value: 'local', label: 'local' },
            { value: 'docker', label: 'docker' },
            { value: 'ssh', label: 'ssh' },
            { value: 'modal', label: 'modal' },
            { value: 'daytona', label: 'daytona' },
            { value: 'singularity', label: 'singularity' },
        ];
    }

    public async setHermesProvider(provider: string) {
        if (!this.aiSettings?.hermes) return;
        this.aiSettings.hermes.provider = provider || 'openrouter';
        this.agentModelCatalogs = { ...(this.agentModelCatalogs || {}), hermes: null };
        await this.refreshAgentModels('hermes');
    }

    public hermesConfigStatusLabel() {
        const config = this.agentStatus('hermes')?.hermes_config || {};
        if (config.api_key_configured) return 'API Key 저장됨';
        return 'API Key 미설정';
    }

    public codexLoginStatus() {
        const login = this.aiCodexStatus?.login || {};
        if (login.logged_in) return '로그인됨';
        if (login.status === 'missing') return 'CLI 없음';
        if (login.status === 'error') return '확인 오류';
        return '미로그인';
    }

    public codexStatusClass() {
        return this.agentStatusClass('codex');
    }

    public codexActiveCliLabel() {
        const active = this.aiCodexStatus?.active || {};
        if (!active.available) return 'CLI 없음';
        return 'Codex CLI';
    }

    public codexStatusRows() {
        const active = this.aiCodexStatus?.active || {};
        const login = this.aiCodexStatus?.login || {};
        return [
            { label: '현재 모델', value: this.aiSettings.codex?.model || '-' },
            { label: 'Reasoning', value: this.aiSettings.codex?.reasoning_effort || '-' },
            { label: '버전', value: this.codexVersionLabel() },
            { label: '로그인', value: login.message || this.codexLoginStatus() },
        ];
    }

    public codexVersionLabel() {
        const active = this.aiCodexStatus?.active || {};
        return active.version || this.codexUpdate?.current_version || this.codexUpdate?.current_version_raw || '-';
    }

    public codexLatestVersionLabel() {
        if (!this.codexUpdate) return `최신 버전 확인 전 · 마지막 확인 ${this.codexUpdateCheckedAt()}`;
        const latest = this.codexUpdate?.latest_version || '-';
        return `최신 ${latest} · 마지막 확인 ${this.codexUpdateCheckedAt()}`;
    }

    public codexUpdateRows() {
        const update = this.codexUpdate || {};
        const npm = update.npm || {};
        return [
            { label: 'npm', value: npm.available ? `${npm.version || '-'}` : 'npm 없음' },
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
        if (!this.codexUpdate) return true;
        if (!this.codexUpdate?.npm?.available) return true;
        return Boolean(!this.codexUpdate?.current_version || this.codexUpdate?.update_available);
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
        return output || '설치/업데이트 로그를 기다리고 있습니다.\n';
    }

    public closeCodexUpdateOperation() {
        if (!this.codexUpdateDone()) return;
        this.codexUpdateOperation = null;
        this.codexUpdateLog = '';
    }

    public agentInstallVisible(agent?: string) {
        if (!this.agentInstallOperation && !this.agentInstallLog) return false;
        if (!agent) return true;
        const target = this.agentInstallOperation?.target_id || this.installingAgent();
        return !target || target === agent;
    }

    public agentInstallBusy(agent: string) {
        const status = this.agentInstallOperation?.status;
        const target = this.agentInstallOperation?.target_id || this.installingAgent();
        return this.installingAgent() === agent || (target === agent && ['pending', 'running'].includes(status));
    }

    public agentInstallDone() {
        return ['succeeded', 'failed', 'canceled'].includes(this.agentInstallOperation?.status);
    }

    public agentInstallStatusLabel() {
        const status = this.agentInstallOperation?.status;
        if (status === 'succeeded') return '완료';
        if (status === 'failed') return '실패';
        if (status === 'canceled') return '취소됨';
        if (status === 'running') return '진행 중';
        if (status === 'pending') return '대기 중';
        return this.installingAgent() ? '준비 중' : '대기';
    }

    public agentInstallOperationIcon() {
        const status = this.agentInstallOperation?.status;
        if (status === 'succeeded') return 'fa-circle-check';
        if (status === 'failed' || status === 'canceled') return 'fa-triangle-exclamation';
        return 'fa-spinner fa-spin';
    }

    public agentInstallOutput() {
        const output = this.operationOutputText(this.agentInstallOperation) || this.agentInstallLog;
        return output || '설치/업데이트 로그를 기다리고 있습니다.\n';
    }

    public closeAgentInstallOperation() {
        if (!this.agentInstallDone()) return;
        this.agentInstallOperation = null;
        this.agentInstallLog = '';
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
        return `서비스별 최근 ${keep}개 보존 · 컨테이너 상태 스냅샷`;
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
        if (processed === 0) return '백업할 서비스 상태 스냅샷이 없습니다.';
        return `서비스 상태 백업 ${processed}건 중 ${succeeded}건 완료, ${failed}건 실패 · 스냅샷 ${snapshots}건`;
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
            default_agent: '',
            codex: { enabled: false, cli_mode: 'system', model: 'gpt-5.5', reasoning_effort: 'xhigh' },
            claude_code: { enabled: false, model: 'sonnet' },
            hermes: {
                enabled: false,
                model: 'default',
                provider: 'openrouter',
                api_key: '',
                terminal_backend: 'local',
                terminal_timeout: 180,
            },
        };
    }

    private syncAiPayload(payload: any) {
        const defaults = this.defaultAiSettings();
        const config = payload?.config || {};
        this.aiSettings = {
            default_agent: config.default_agent || defaults.default_agent,
            codex: { ...defaults.codex, ...(config.codex || {}) },
            claude_code: { ...defaults.claude_code, ...(config.claude_code || {}) },
            hermes: { ...defaults.hermes, ...(config.hermes || {}) },
        };
        this.ensureDefaultAiAgent();
        this.aiCodexStatus = payload?.codex_status || this.aiCodexStatus || {};
        this.aiAgentStatuses = payload?.agent_statuses || payload?.resources?.agents || this.aiAgentStatuses || {};
        this.agentUpdates = payload?.agent_updates || this.agentUpdates || {};
        this.codexUpdate = this.agentUpdates?.codex || this.codexUpdate || null;
    }

    private ensureDefaultAiAgent() {
        if (!this.aiSettings) return;
        const enabled = this.enabledAiAgentKeys();
        if (!enabled.length) {
            this.aiSettings.default_agent = '';
            return;
        }
        if (!enabled.includes(this.aiSettings.default_agent)) {
            this.aiSettings.default_agent = enabled[0];
        }
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
            method: 'container_snapshot',
            snapshot_enabled: true,
            snapshot_pause: true,
            last_run_at: null,
            last_result: null
        };
    }

    private syncBackupPolicy() {
        this.backupPolicy = {
            ...this.defaultBackupPolicy(),
            ...(this.backupSystem?.backup_policy || {}),
            method: 'container_snapshot',
            snapshot_enabled: true,
            snapshot_pause: true
        };
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
