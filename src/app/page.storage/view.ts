import { OnDestroy, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit, OnDestroy {
    public loading = signal<boolean>(true);
    public error = signal<string>('');
    public actionError = signal<string>('');
    public preflightBusy = signal<boolean>(false);
    public bootstrapBusy = signal<boolean>(false);
    public masterBootstrapBusy = signal<boolean>(false);
    public preflightModalOpen = signal<boolean>(false);
    public operationModalOpen = signal<boolean>(false);
    public overview = signal<any>({});
    public activeTab = signal<string>('overview');
    public preflight = signal<any>(null);
    public operationDetail = signal<any>(null);
    public osdWizardOpen = signal<boolean>(false);
    public osdBusy = signal<boolean>(false);
    public osdTarget = signal<any>(null);
    public osdPlan = signal<any>(null);
    public osdForm = signal<any>({ slot_size_gb: 128, slot_count: 0 });
    public slotSizeOptions = [64, 128, 256];
    private preflightPollTimer: any = null;
    private preflightPollToken = 0;

    public tabs = [
        { key: 'overview', label: '개요', icon: 'fa-chart-simple', enabled: true },
        { key: 'cluster', label: '클러스터', icon: 'fa-diagram-project', enabled: false },
        { key: 'osd', label: 'OSD 슬롯', icon: 'fa-hard-drive', enabled: false },
        { key: 'mounts', label: '서비스 저장소', icon: 'fa-folder-tree', enabled: false },
        { key: 'policy', label: '정책', icon: 'fa-shield-halved', enabled: false },
    ];

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.load();
    }

    public ngOnDestroy() {
        this.stopPreflightPolling();
    }

    public async setActiveTab(tab: any) {
        if (!tab?.enabled) return;
        this.activeTab.set(tab.key);
        await this.service.render();
    }

    public isActiveTab(key: string) {
        return this.activeTab() === key;
    }

    public async load() {
        this.loading.set(true);
        this.error.set('');
        await this.service.render();
        const { code, data } = await wiz.call('load', {});
        if (code === 200) {
            this.overview.set(data.overview || {});
        } else {
            this.error.set(data?.message || '스토리지 상태를 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
    }

    public async runPreflight() {
        this.stopPreflightPolling();
        const token = ++this.preflightPollToken;
        this.preflightModalOpen.set(true);
        this.preflight.set(null);
        this.operationDetail.set(null);
        this.preflightBusy.set(true);
        this.actionError.set('');
        await this.service.render();
        const { code, data } = await wiz.call('cluster_preflight', { slot_size_gb: 64 });
        if (token !== this.preflightPollToken) return;
        if (code === 200) {
            const operation = data.operation || null;
            this.operationDetail.set(operation);
            this.applyPreflightFromOperation(operation);
            if (!this.preflight() && data.summary) this.preflight.set(data);
            if (operation?.id && this.isActiveOperation(operation)) {
                this.schedulePreflightPoll(operation.id, token, 600);
            } else {
                this.preflightBusy.set(false);
            }
        } else {
            this.actionError.set(data?.message || 'Ceph 사전 점검을 실행할 수 없습니다.');
            this.preflightBusy.set(false);
        }
        await this.service.render();
    }

    public openPreflightModal() {
        this.preflightModalOpen.set(true);
    }

    public closePreflightModal() {
        if (this.preflightBusy()) return;
        this.preflightModalOpen.set(false);
    }

    public openOperationModal() {
        if (this.operationDetail()?.id) this.operationModalOpen.set(true);
    }

    public closeOperationModal() {
        this.operationModalOpen.set(false);
    }

    public async bootstrapCluster() {
        this.bootstrapBusy.set(true);
        this.actionError.set('');
        await this.service.render();
        const { code, data } = await wiz.call('cluster_bootstrap', { slot_size_gb: 64 });
        await this.applyBootstrapResult(data, code === 200 ? '' : 'Ceph bootstrap을 실행할 수 없습니다.');
        this.bootstrapBusy.set(false);
        await this.service.render();
    }

    public async bootstrapMaster() {
        this.masterBootstrapBusy.set(true);
        this.actionError.set('');
        await this.service.render();
        const { code, data } = await wiz.call('cluster_master_bootstrap', { slot_size_gb: 64 });
        await this.applyBootstrapResult(data, code === 200 ? '' : 'Ceph 마스터 노드를 구성할 수 없습니다.');
        this.masterBootstrapBusy.set(false);
        await this.service.render();
    }

    private async applyBootstrapResult(data: any, fallbackMessage: string = '') {
        if (data?.preflight) this.preflight.set(data.preflight);
        const operation = data?.operation || null;
        this.operationDetail.set(operation);
        if (operation?.id) this.operationModalOpen.set(true);
        const failed = String(operation?.status || '').toLowerCase() === 'failed' || Boolean(data?.message) || Boolean(fallbackMessage);
        if (failed) {
            this.actionError.set(data?.message || operation?.message || fallbackMessage || 'Ceph 작업이 실패했습니다.');
        }
        await this.load();
    }

    public async refreshOperation(render: boolean = true) {
        const operationId = this.operationDetail()?.id;
        if (!operationId) return null;
        const { code, data } = await wiz.call('operation_status', { operation_id: operationId });
        if (code === 200) {
            const operation = data.operation || null;
            this.operationDetail.set(operation);
            this.applyPreflightFromOperation(operation);
            if (render) await this.service.render();
            return operation;
        }
        if (render) await this.service.render();
        return null;
    }

    private isActiveOperation(operation: any) {
        return ['pending', 'running'].includes(String(operation?.status || '').toLowerCase());
    }

    private applyPreflightFromOperation(operation: any) {
        const payload = operation?.result_payload || {};
        const result = payload.preflight || (payload.summary ? payload : null);
        if (result?.status) this.preflight.set(result);
    }

    private schedulePreflightPoll(operationId: string, token: number, delayMs: number = 1000) {
        if (this.preflightPollTimer) clearTimeout(this.preflightPollTimer);
        this.preflightPollTimer = setTimeout(() => this.pollPreflightOperation(operationId, token), delayMs);
    }

    private async pollPreflightOperation(operationId: string, token: number) {
        if (token !== this.preflightPollToken) return;
        try {
            const operation = await this.refreshOperation(false);
            if (token !== this.preflightPollToken) return;
            if (operation && this.isActiveOperation(operation)) {
                this.schedulePreflightPoll(operationId, token);
            } else {
                this.preflightBusy.set(false);
                this.preflightPollTimer = null;
            }
        } catch (error) {
            if (token !== this.preflightPollToken) return;
            this.actionError.set('Ceph 사전 점검 진행 상태를 갱신할 수 없습니다.');
            this.preflightBusy.set(false);
            this.preflightPollTimer = null;
        }
        await this.service.render();
    }

    private stopPreflightPolling() {
        this.preflightPollToken += 1;
        if (this.preflightPollTimer) clearTimeout(this.preflightPollTimer);
        this.preflightPollTimer = null;
    }

    public async openOsdWizard(node: any) {
        if (!node?.osd_slot_candidate) return;
        this.osdTarget.set(node);
        this.osdPlan.set(null);
        this.osdForm.set({ slot_size_gb: 128, slot_count: 0 });
        this.osdWizardOpen.set(true);
        await this.service.render();
        await this.createOsdPlan();
    }

    public closeOsdWizard() {
        if (this.osdBusy()) return;
        this.osdWizardOpen.set(false);
    }

    public osdPayload() {
        const payload: any = {
            node_id: this.osdTarget()?.id,
            slot_size_gb: this.osdSlotSize(),
        };
        const count = this.osdSlotCount();
        if (count > 0) payload.slot_count = count;
        return payload;
    }

    public osdSlotSize() {
        const size = Number(this.osdForm()?.slot_size_gb || 128);
        return this.slotSizeOptions.includes(size) ? size : 128;
    }

    public async selectOsdSize(size: any) {
        const value = this.slotSizeOptions.includes(Number(size)) ? Number(size) : 128;
        this.osdForm.set({ ...this.osdForm(), slot_size_gb: value, slot_count: 0 });
        this.osdPlan.set(null);
        await this.service.render();
        await this.createOsdPlan();
    }

    public osdMaxSlotCount() {
        const plan = this.osdPlan() || {};
        const capacity = plan.capacity || {};
        return Math.max(0, this.numberValue(capacity.max_slot_count || capacity.auto_slot_count || plan.slot_count));
    }

    public osdSlotCount() {
        const selected = this.numberValue(this.osdForm()?.slot_count);
        const max = this.osdMaxSlotCount();
        if (max <= 0) return Math.max(0, selected);
        if (selected <= 0) return max;
        return Math.max(1, Math.min(selected, max));
    }

    public async changeOsdSlotCount(delta: any) {
        const max = this.osdMaxSlotCount();
        if (max <= 0) return;
        await this.setOsdSlotCount(this.osdSlotCount() + Number(delta || 0));
    }

    public async setOsdSlotCount(value: any) {
        const max = this.osdMaxSlotCount();
        const raw = this.numberValue(value);
        const next = max > 0 ? Math.max(1, Math.min(raw || 1, max)) : Math.max(0, raw);
        this.osdForm.set({ ...this.osdForm(), slot_count: next });
        this.osdPlan.set(null);
        await this.service.render();
        await this.createOsdPlan();
    }

    public async createOsdPlan() {
        if (!this.osdTarget()) return;
        this.osdBusy.set(true);
        this.actionError.set('');
        await this.service.render();
        const { code, data } = await wiz.call('osd_slot_plan', this.osdPayload());
        if (code === 200) {
            const plan = data.plan || data;
            this.osdPlan.set(plan);
            this.osdForm.set({ ...this.osdForm(), slot_count: this.numberValue(plan?.slot_count) });
        } else {
            this.actionError.set(data?.message || 'OSD 슬롯 plan을 만들 수 없습니다.');
        }
        this.osdBusy.set(false);
        await this.service.render();
    }

    public async createOsdSlot() {
        if (!this.osdTarget()) return;
        this.osdBusy.set(true);
        this.actionError.set('');
        await this.service.render();
        const { code, data } = await wiz.call('osd_slot_create', this.osdPayload());
        if (code === 200) {
            this.operationDetail.set(data.operation || null);
            if (data.operation?.id) this.operationModalOpen.set(true);
            this.osdPlan.set(data.plan || this.osdPlan());
            await this.load();
            this.osdWizardOpen.set(false);
        } else {
            this.actionError.set(data?.message || 'OSD 슬롯을 생성할 수 없습니다.');
        }
        this.osdBusy.set(false);
        await this.service.render();
    }

    public async openServers() {
        await this.service.routeTo('/servers');
    }

    public async fixPreflightIssue(issue: any) {
        const action = issue?.auto_fix || {};
        if (!action.available) return;
        if (action.type === 'route' && action.route) {
            await this.service.routeTo(action.route);
            return;
        }
        if (action.type === 'rerun') {
            await this.runPreflight();
        }
    }

    public cluster() {
        return this.overview()?.cluster || {};
    }

    public health() {
        return this.overview()?.health || {};
    }

    public capacity() {
        return this.overview()?.capacity || {};
    }

    public daemons() {
        return this.overview()?.daemons || {};
    }

    public master() {
        return this.overview()?.master || {};
    }

    public showMasterBootstrap() {
        return this.master()?.configured !== true && this.cluster()?.schema_ready !== false;
    }

    public warnings() {
        return this.overview()?.warnings || [];
    }

    public storage() {
        return this.overview()?.storage || {};
    }

    public nodes() {
        return this.overview()?.nodes || { total: 0, swarm: 0, independent: 0, rows: [] };
    }

    public dashboardMetrics() {
        const capacity = this.capacity();
        const nodes = this.nodes();
        const daemons = this.daemons();
        const osd = daemons.osd || {};
        return [
            {
                key: 'health',
                label: 'Health',
                value: this.healthLabel(),
                caption: this.healthCaption(),
                icon: 'fa-heart-pulse',
                status: this.health()?.status || this.cluster()?.status || 'unknown',
            },
            {
                key: 'osd',
                label: 'OSD',
                value: `${this.numberValue(osd.up)}/${this.numberValue(osd.total)}`,
                caption: `${this.numberValue(osd.in)} in · ${this.osdPlacementSummary().active} active slots`,
                icon: 'fa-hard-drive',
                status: this.daemonStatus(osd.up, osd.total),
            },
            {
                key: 'capacity',
                label: 'Raw',
                value: this.formatBytes(capacity.raw_bytes),
                caption: `${this.formatBytes(capacity.used_bytes)} used · ${this.capacityUsagePercent()}%`,
                icon: 'fa-database',
                status: this.numberValue(capacity.raw_bytes) > 0 ? 'ready' : 'unknown',
            },
            {
                key: 'hosts',
                label: 'Hosts',
                value: `${this.numberValue(nodes.total)}`,
                caption: `${this.numberValue(nodes.ceph_registered)} Ceph · ${this.numberValue(nodes.ready_for_osd)} OSD 후보`,
                icon: 'fa-server',
                status: this.numberValue(nodes.total) > 0 ? 'ready' : 'unknown',
            },
        ];
    }

    public osdPlacementSummary() {
        const nodes = this.nodes();
        const storage = this.storage();
        const slots = nodes.osd_slots || storage.osd_slots || {};
        return {
            total: this.numberValue(slots.total),
            active: this.numberValue(slots.active),
            prepared: this.numberValue(slots.prepared),
            allocated: this.numberValue(slots.allocated),
            failed: this.numberValue(slots.failed),
            raw_bytes: this.numberValue(slots.raw_bytes),
        };
    }

    public nodeOsdSummary(node: any) {
        const slots = node?.osd_slots || {};
        return {
            total: this.numberValue(slots.total),
            active: this.numberValue(slots.active),
            prepared: this.numberValue(slots.prepared),
            allocated: this.numberValue(slots.allocated),
            failed: this.numberValue(slots.failed),
            raw_bytes: this.numberValue(slots.raw_bytes),
        };
    }

    public nodeOsdRows(node: any) {
        return node?.osd_slots?.rows || [];
    }

    public nodeOsdState(node: any) {
        const summary = this.nodeOsdSummary(node);
        if (summary.failed > 0) return 'failed';
        if (summary.total > 0 && summary.active === summary.total) return 'ready';
        if (summary.active > 0) return 'warning';
        if (summary.total > 0) return 'pending';
        return 'unknown';
    }

    public nodeOsdStateLabel(node: any) {
        const summary = this.nodeOsdSummary(node);
        if (summary.failed > 0) return `failed ${summary.failed}`;
        if (summary.total > 0) return `${summary.active}/${summary.total} active`;
        return 'empty';
    }

    public slotOsdLabel(slot: any) {
        const osdId = slot?.osd_id;
        if (osdId !== null && osdId !== undefined && String(osdId) !== '') return `osd.${osdId}`;
        return slot?.slot_name || 'slot';
    }

    public backingLabel(slot: any) {
        const type = String(slot?.backing_type || '');
        if (type === 'managed_loop') return 'managed loop';
        if (type === 'gpt_partition') return 'block device';
        if (type === 'lvm_lv') return 'LVM LV';
        return type || '-';
    }

    public clusterStatusLabel() {
        const status = String(this.cluster()?.status || '').toLowerCase();
        if (status === 'not_configured') return '클러스터 미구성';
        if (status === 'running') return '운영 중';
        if (status === 'warning') return '확인 필요';
        if (status === 'error') return '오류';
        return '상태 미확인';
    }

    public healthLabel() {
        return this.health()?.value || this.cluster()?.health || 'HEALTH_UNKNOWN';
    }

    public healthCaption() {
        if (this.health()?.placeholder) return 'health placeholder';
        return this.health()?.message || '최근 health 확인 결과';
    }

    public capacityItems() {
        const capacity = this.capacity();
        return [
            { key: 'raw', label: 'Raw 용량', value: capacity.raw_bytes, description: 'OSD slot 원본 합산', tone: 'sky' },
            { key: 'usable', label: 'Replica 후 예상', value: capacity.usable_bytes, description: '3 replica 기준 추정', tone: 'emerald' },
            { key: 'recommended', label: '운영 권장 사용 가능', value: capacity.recommended_bytes, description: 'nearfull 여유 제외', tone: 'amber' },
            { key: 'used', label: '사용 중', value: capacity.used_bytes, description: 'CephFS 사용량', tone: 'zinc' },
        ];
    }

    public storageItems() {
        const storage = this.storage();
        const osd = storage.osd_slots || {};
        const mounts = storage.mounts || {};
        const snapshots = storage.snapshots || {};
        const policies = storage.policies || {};
        const unknown = storage.schema_ready === false;
        return [
            { key: 'osd', label: 'OSD 슬롯', value: this.numberValue(osd.total), description: `active ${this.numberValue(osd.active)} · failed ${this.numberValue(osd.failed)}`, icon: 'fa-hard-drive', status: unknown ? 'unknown' : (osd.failed ? 'failed' : 'ready') },
            { key: 'mounts', label: '서비스 저장소', value: this.numberValue(mounts.total), description: `active ${this.numberValue(mounts.active)} · failed ${this.numberValue(mounts.failed)}`, icon: 'fa-folder-tree', status: unknown ? 'unknown' : (mounts.failed ? 'failed' : 'ready') },
            { key: 'snapshots', label: '스냅샷', value: this.numberValue(snapshots.total), description: `ready ${this.numberValue(snapshots.ready)} · failed ${this.numberValue(snapshots.failed)}`, icon: 'fa-clock-rotate-left', status: unknown ? 'unknown' : (snapshots.failed ? 'failed' : 'ready') },
            { key: 'policies', label: '정책', value: this.numberValue(policies.total), description: `enabled ${this.numberValue(policies.enabled)}`, icon: 'fa-shield-halved', status: unknown ? 'unknown' : 'ready' },
        ];
    }

    public daemonItems() {
        const daemons = this.daemons();
        const mon = daemons.mon || {};
        const mgr = daemons.mgr || {};
        const mds = daemons.mds || {};
        const osd = daemons.osd || {};
        return [
            {
                key: 'mon',
                label: 'MON',
                value: `${this.numberValue(mon.ready)}/${this.numberValue(mon.wanted)}`,
                description: 'quorum',
                status: this.daemonStatus(mon.ready, mon.wanted),
            },
            {
                key: 'mgr',
                label: 'MGR',
                value: `${this.numberValue(mgr.active)} active + ${this.numberValue(mgr.standby)} standby`,
                description: 'manager',
                status: this.daemonStatus(mgr.active, 1),
            },
            {
                key: 'mds',
                label: 'MDS',
                value: `${this.numberValue(mds.active)} active + ${this.numberValue(mds.standby)} standby`,
                description: 'CephFS metadata',
                status: this.daemonStatus(mds.active, 1),
            },
            {
                key: 'osd',
                label: 'OSD',
                value: `${this.numberValue(osd.up)} up / ${this.numberValue(osd.in)} in`,
                description: `total ${this.numberValue(osd.total)}`,
                status: this.daemonStatus(osd.up, osd.total),
            },
        ];
    }

    private daemonStatus(ready: any, wanted: any) {
        if (!this.cluster()?.configured) return 'unknown';
        const readyCount = this.numberValue(ready);
        const wantedCount = this.numberValue(wanted);
        if (wantedCount > 0 && readyCount >= wantedCount) return 'ready';
        if (readyCount > 0) return 'warning';
        return 'error';
    }

    public storageNodeRows() {
        return this.nodes()?.rows || [];
    }

    public preflightSummary() {
        return this.preflight()?.summary || {};
    }

    public preflightChecks() {
        return this.preflight()?.checks || [];
    }

    public preflightNodeRows() {
        return this.preflight()?.nodes || [];
    }

    public preflightAllowed() {
        return this.preflight()?.bootstrap_allowed === true;
    }

    public preflightIssueRows() {
        const rows: any[] = [];
        for (const check of this.preflightChecks()) {
            if (this.isIssueStatus(check.status)) rows.push({ scope: '공통 조건', ...check });
        }
        for (const node of this.preflightNodeRows()) {
            for (const check of node.checks || []) {
                if (!this.isIssueStatus(check.status)) continue;
                rows.push({
                    scope: node.label || node.name || node.host || 'node',
                    node,
                    ...check,
                });
            }
        }
        return rows;
    }

    public isIssueStatus(status: string) {
        return ['warning', 'error', 'failed'].includes(String(status || '').toLowerCase());
    }

    public autoFixLabel(issue: any) {
        return issue?.auto_fix?.label || '보정 열기';
    }

    public operationOutput() {
        return this.operationDetail()?.output || [];
    }

    public actionBusy() {
        return this.preflightBusy() || this.bootstrapBusy() || this.masterBootstrapBusy() || this.osdBusy();
    }

    public osdWizardTitle() {
        const node = this.osdTarget();
        return node?.name || node?.host || 'Swarm 서버';
    }

    public osdPlanRows() {
        const plan = this.osdPlan() || {};
        const capacity = plan.capacity || {};
        return [
            { label: '대상 서버', value: plan.node_name || this.osdWizardTitle() },
            { label: '구성 슬롯', value: `${this.numberValue(plan.slot_count)}개 / 최대 ${this.numberValue(capacity.max_slot_count || capacity.auto_slot_count || plan.slot_count)}개` },
            { label: '슬롯 크기', value: `${this.numberValue(plan.slot_size_gb || plan.size_gb)}GB` },
            { label: '총 구성 용량', value: this.formatBytes(capacity.planned_raw_bytes) },
            { label: '구성 후 남은 용량', value: this.formatBytes(capacity.remaining_after_bytes) },
            { label: 'backing', value: plan.backing_label || '자동 구성' },
            { label: '자동 대상', value: this.osdTargetPath() },
        ];
    }

    public osdTargetPath() {
        const plan = this.osdPlan() || {};
        return plan.target_path || plan.data_device || plan.managed_path || '마법사 생성 예정';
    }

    public osdCapacityItems() {
        const capacity = this.osdPlan()?.capacity || {};
        return [
            { label: '총 용량', value: capacity.total_bytes, icon: 'fa-database' },
            { label: '남은 용량', value: capacity.available_bytes, icon: 'fa-gauge-high' },
            { label: '구성 예정', value: capacity.planned_raw_bytes, icon: 'fa-hard-drive' },
            { label: '구성 후 남음', value: capacity.remaining_after_bytes, icon: 'fa-circle-nodes' },
        ];
    }

    public osdCreateDisabled() {
        const plan = this.osdPlan();
        return this.osdBusy() || !plan || plan.eligible !== true || this.numberValue(plan.slot_count) <= 0;
    }

    public warningIcon(level: string) {
        if (level === 'error') return 'fa-circle-xmark';
        if (level === 'warning') return 'fa-triangle-exclamation';
        return 'fa-circle-info';
    }

    public warningClass(level: string) {
        if (level === 'error') return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        if (level === 'warning') return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300';
    }

    public statusClass(status: string) {
        const value = String(status || '').toLowerCase();
        if (['ok', 'ready', 'active', 'running', 'health_ok', 'passed', 'succeeded'].includes(value)) {
            return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        }
        if (['warning', 'degraded', 'not_configured', 'unknown', 'health_warn', 'passed_with_warnings', 'pending'].includes(value)) {
            return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        }
        if (['error', 'failed', 'health_err'].includes(value)) {
            return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        }
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }

    public metricToneClass(tone: string) {
        const tones: any = {
            sky: 'bg-sky-50 text-sky-700 dark:bg-sky-950/50 dark:text-sky-300',
            emerald: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300',
            amber: 'bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300',
            zinc: 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200',
        };
        return tones[tone] || tones.zinc;
    }

    public capacityPercent(item: any) {
        const raw = this.numberValue(this.capacity()?.raw_bytes);
        if (!raw) return 0;
        return Math.max(0, Math.min(100, this.numberValue(item?.value) * 100 / raw));
    }

    public capacityUsagePercent() {
        const raw = this.numberValue(this.capacity()?.raw_bytes);
        if (!raw) return 0;
        return Math.round(Math.max(0, Math.min(100, this.numberValue(this.capacity()?.used_bytes) * 100 / raw)));
    }

    public formatBytes(value: any, zeroLabel: string = '0 B') {
        const num = Number(value || 0);
        if (!Number.isFinite(num) || num <= 0) return zeroLabel;
        const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
        let size = num;
        let index = 0;
        while (size >= 1024 && index < units.length - 1) {
            size = size / 1024;
            index += 1;
        }
        return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
    }

    private numberValue(value: any) {
        const numeric = Number(value || 0);
        return Number.isFinite(numeric) ? numeric : 0;
    }
}
