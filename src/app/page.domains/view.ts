import { OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    public loading = signal<boolean>(true);
    public error = signal<string>('');
    public ddnsEndpoints = signal<any[]>([]);
    public ddnsRegistrations = signal<any[]>([]);
    public ddnsEndpointPagination = signal<any>({ current: 1, start: 1, end: 1, total: 0, limit: 20 });
    public ddnsRegistrationPagination = signal<any>({ current: 1, start: 1, end: 1, total: 0, limit: 20 });
    public ddnsSummary = signal<any>({});
    public ddnsDispatcher = signal<any>({});
    public ddnsWarning = signal<string>('');
    public ddnsModalOpen = signal<boolean>(false);
    public ddnsUpdateEndpointId = signal<string>('');
    public ddnsDispatcherBusy = signal<boolean>(false);
    public ddnsRegistrationEndpointFilter = signal<string>('');
    public pageSize = 20;
    public ddnsForm: any = this.emptyDdnsForm();

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.load();
    }

    public async alert(message: string, status: string = 'error') {
        return await this.service.modal.show({ title: '', message, cancel: false, actionBtn: status, action: '확인', status });
    }

    public async confirm(message: string, action: string = '삭제', status: string = 'error') {
        return await this.service.modal.show({ title: '', message, cancel: true, cancelLabel: '취소', actionBtn: status, action, status });
    }

    public async load() {
        this.loading.set(true);
        this.error.set('');
        await this.service.render();
        const { code, data } = await wiz.call('load', {});
        if (code === 200) {
            const ddns = data.ddns || {};
            this.ddnsEndpoints.set(ddns.endpoints || []);
            this.ddnsRegistrations.set(ddns.registrations || []);
            this.ensureDdnsRegistrationFilter();
            this.ddnsEndpointPagination.set(this.paginationFor(this.ddnsEndpoints().length, this.ddnsEndpointPagination().current));
            this.ddnsRegistrationPagination.set(this.paginationFor(this.filteredDdnsRegistrations().length, this.ddnsRegistrationPagination().current));
            this.ddnsSummary.set(ddns.summary || {});
            this.ddnsDispatcher.set(ddns.dispatcher || {});
            this.ddnsWarning.set(ddns.available === false ? (ddns.message || 'DDNS 관리 서버 정보를 불러올 수 없습니다.') : '');
        } else {
            this.error.set(data?.message || '도메인 정보를 불러올 수 없습니다.');
            this.ddnsEndpoints.set([]);
            this.ddnsRegistrations.set([]);
            this.ddnsEndpointPagination.set(this.paginationFor(0, 1));
            this.ddnsRegistrationPagination.set(this.paginationFor(0, 1));
            this.ddnsRegistrationEndpointFilter.set('');
            this.ddnsSummary.set({});
            this.ddnsDispatcher.set({});
            this.ddnsWarning.set('');
        }
        this.loading.set(false);
        await this.service.render();
    }

    public openDdnsModal(endpoint: any = null) {
        this.ddnsForm = this.emptyDdnsForm(endpoint || {});
        this.ddnsModalOpen.set(true);
    }

    public closeDdnsModal() {
        this.ddnsModalOpen.set(false);
        this.ddnsForm = this.emptyDdnsForm();
    }

    public async saveDdnsEndpoint() {
        const { code, data } = await wiz.call('save_ddns_endpoint', { ...this.ddnsForm });
        if (code === 200) {
            this.closeDdnsModal();
            await this.load();
            await this.alert('DDNS 관리 서버 설정을 저장했습니다.', 'success');
            return;
        }
        await this.alert(data?.message || 'DDNS 관리 서버 설정을 저장할 수 없습니다.');
    }

    public async deleteDdnsEndpoint(endpoint: any) {
        const ok = await this.confirm(`${endpoint.domain_suffix} DDNS 관리 서버 설정을 삭제합니다. 등록 이력도 함께 제거됩니다.`, '삭제');
        if (!ok) return;
        const { code, data } = await wiz.call('delete_ddns_endpoint', { endpoint_id: endpoint.id });
        if (code === 200) {
            await this.load();
            await this.alert('DDNS 관리 서버 설정을 삭제했습니다.', 'success');
            return;
        }
        await this.alert(data?.message || 'DDNS 관리 서버 설정을 삭제할 수 없습니다.');
    }

    public async forceUpdateDdnsEndpoint(endpoint: any) {
        if (!endpoint?.id) return;
        this.ddnsUpdateEndpointId.set(endpoint.id);
        await this.service.render();
        let response: any = {};
        try {
            response = await wiz.call('force_update_ddns_endpoint', { endpoint_id: endpoint.id });
        } finally {
            this.ddnsUpdateEndpointId.set('');
        }
        const { code, data } = response;
        if (code === 200) {
            await this.load();
            await this.alert(data?.message || 'DDNS API 호출을 완료했습니다.', 'success');
            return;
        }
        await this.service.render();
        await this.alert(data?.message || 'DDNS API를 호출할 수 없습니다.');
    }

    public async ensureDdnsDispatcher() {
        if (this.ddnsDispatcherBusy()) return;
        this.ddnsDispatcherBusy.set(true);
        await this.service.render();
        let response: any = {};
        try {
            response = await wiz.call('ensure_ddns_dispatcher', {});
        } finally {
            this.ddnsDispatcherBusy.set(false);
        }
        const { code, data } = response;
        if (code === 200) {
            await this.load();
            await this.alert('NetworkManager dispatcher를 등록했습니다.', 'success');
            return;
        }
        await this.service.render();
        await this.alert(data?.message || 'NetworkManager dispatcher를 등록할 수 없습니다.');
    }

    public ddnsDispatcherLabel() {
        const dispatcher = this.ddnsDispatcher() || {};
        if (dispatcher.registered === true) return 'Dispatcher 등록됨';
        if (dispatcher.status === 'partial') return 'Dispatcher 확인 필요';
        return 'Dispatcher 미등록';
    }

    public ddnsDispatcherBadgeClass() {
        const dispatcher = this.ddnsDispatcher() || {};
        if (dispatcher.registered === true) return this.statusClass('active');
        if (dispatcher.status === 'partial') return this.statusClass('pending');
        return this.statusClass('missing');
    }

    public ddnsStatusLabel(endpoint: any) {
        const labels: any = { active: '사용 중', pending: '등록됨', error: '오류', disabled: '사용 안 함' };
        return labels[endpoint?.status] || endpoint?.status || '-';
    }

    public registrationStatusLabel(item: any) {
        const labels: any = { registered: '등록됨', updated: '갱신됨', failed: '실패', pending: '대기', skipped: '건너뜀' };
        return labels[item?.status] || item?.status || '-';
    }

    public endpointRegistrationCount(endpoint: any) {
        const count = Number(endpoint?.registration_count || 0);
        if (count > 0) return count;
        const endpointId = String(endpoint?.id || '');
        return this.ddnsRegistrations().filter((item: any) => String(item.endpoint_id || '') === endpointId).length;
    }

    private paginationStart(page: number) {
        return Math.floor((Math.max(1, Number(page || 1)) - 1) / 10) * 10 + 1;
    }

    private paginationFor(total: number, page: number = 1) {
        const limit = this.pageSize;
        const end = Math.max(1, Math.ceil(Number(total || 0) / limit));
        const current = Math.min(Math.max(1, Number(page || 1)), end);
        return {
            current,
            start: this.paginationStart(current),
            end,
            total: Number(total || 0),
            limit,
        };
    }

    private pageRows(rows: any[], pagination: any) {
        const limit = Number(pagination?.limit || this.pageSize);
        const start = (Number(pagination?.current || 1) - 1) * limit;
        return (rows || []).slice(start, start + limit);
    }

    public pagedDdnsEndpoints() {
        return this.pageRows(this.ddnsEndpoints(), this.ddnsEndpointPagination());
    }

    public pagedDdnsRegistrations() {
        return this.pageRows(this.filteredDdnsRegistrations(), this.ddnsRegistrationPagination());
    }

    public async moveDdnsEndpointPage(page: number) {
        this.ddnsEndpointPagination.set(this.paginationFor(this.ddnsEndpoints().length, page));
        await this.service.render();
    }

    public async moveDdnsRegistrationPage(page: number) {
        this.ddnsRegistrationPagination.set(this.paginationFor(this.filteredDdnsRegistrations().length, page));
        await this.service.render();
    }

    public filteredDdnsRegistrations() {
        const endpointId = String(this.ddnsRegistrationEndpointFilter() || '').trim();
        if (!endpointId) return this.ddnsRegistrations();
        return this.ddnsRegistrations().filter((item: any) => String(item?.endpoint_id || '') === endpointId);
    }

    public async setDdnsRegistrationFilter(endpointId: any) {
        this.ddnsRegistrationEndpointFilter.set(String(endpointId || '').trim());
        this.ddnsRegistrationPagination.set(this.paginationFor(this.filteredDdnsRegistrations().length, 1));
        await this.service.render();
    }

    public ddnsRegistrationFilterClass(endpointId: any) {
        const active = String(endpointId || '').trim() === String(this.ddnsRegistrationEndpointFilter() || '').trim();
        if (active) return 'border-zinc-950 bg-zinc-950 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-950';
        return 'border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800';
    }

    private ensureDdnsRegistrationFilter() {
        const endpointId = String(this.ddnsRegistrationEndpointFilter() || '').trim();
        if (!endpointId) return;
        const exists = this.ddnsEndpoints().some((endpoint: any) => String(endpoint?.id || '') === endpointId);
        if (!exists) this.ddnsRegistrationEndpointFilter.set('');
    }

    public registrationEndpointLabel(item: any) {
        return item?.endpoint_name || item?.domain_suffix || this.ddnsEndpoints().find((endpoint: any) => String(endpoint.id) === String(item?.endpoint_id))?.name || '-';
    }

    public hasLinkedService(item: any) {
        return Boolean(String(item?.service_id || '').trim());
    }

    public serviceDetailLink(item: any) {
        const serviceId = String(item?.service_id || '').trim();
        if (!serviceId) return '/services';
        return `/services/${this.service.encodeRouteSegment(serviceId)}`;
    }

    public registrationHostnameHref(item: any) {
        const hostname = String(item?.domain || '').trim();
        if (!hostname) return '#';
        if (/^https?:\/\//i.test(hostname)) return hostname;
        return `https://${hostname}`;
    }

    public hasTargetDetail(item: any) {
        return Boolean(this.registrationTargetNodeId(item));
    }

    public targetDetailLink(item: any) {
        const nodeId = this.registrationTargetNodeId(item);
        if (!nodeId) return '/servers';
        return `/servers/${this.service.encodeRouteSegment(nodeId)}`;
    }

    public registrationServiceLabel(item: any) {
        return item?.service_name || item?.service_namespace || '-';
    }

    public registrationServiceSubtitle(item: any) {
        const namespace = String(item?.service_namespace || '').trim();
        const serviceName = String(item?.service_name || '').trim();
        if (namespace && namespace !== serviceName) return namespace;
        return '';
    }

    public registrationTargetTitle(item: any) {
        const metadata = this.registrationMetadata(item);
        return this.firstText(
            item?.target_node_label,
            item?.target_node_name,
            metadata.proxy_node_display_name,
            metadata.proxy_registered_node_name,
            metadata.proxy_node_name,
            metadata.proxy_swarm_node_name,
            metadata.proxy_node_id,
            metadata.proxy_host,
        ) || '-';
    }

    public registrationTargetSubtitle(item: any) {
        const metadata = this.registrationMetadata(item);
        const title = this.registrationTargetTitle(item);
        const host = this.firstText(
            item?.target_node_host,
            metadata.proxy_registered_node_private_host,
            metadata.proxy_registered_node_host,
            metadata.proxy_swarm_addr,
            metadata.proxy_host,
        );
        if (!host || host === title) return '';
        return host;
    }

    public formatDate(value: any) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString();
    }

    public statusClass(status: any) {
        if (status === true || ['active', 'ok', 'issued', 'success', 'valid', 'registered', 'updated'].includes(status)) return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        if (['pending', 'manual', 'none', 'disabled', 'expiring', 'skipped'].includes(status)) return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        if (['failed', 'expired', 'error', 'missing'].includes(status)) return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }

    private registrationMetadata(item: any) {
        return {
            ...this.objectValue(item?.metadata),
            ...this.objectValue(item?.service_domain_metadata),
        };
    }

    private registrationTargetNodeId(item: any) {
        const metadata = this.registrationMetadata(item);
        return this.firstText(item?.target_node_id, metadata.proxy_node_id, metadata.proxy_registered_node_id);
    }

    private objectValue(value: any) {
        if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
        return value;
    }

    private firstText(...values: any[]) {
        for (const value of values) {
            const text = String(value ?? '').trim();
            if (text && text !== '0') return text;
        }
        return '';
    }

    private emptyDdnsForm(endpoint: any = {}) {
        const apiBaseUrl = String(endpoint.api_base_url || '').replace(/\/+$/, '');
        const registrationPath = String(endpoint.registration_path || '/api/ddns/update');
        const apiUrl = endpoint.api_url || (apiBaseUrl ? `${apiBaseUrl}${registrationPath.startsWith('/') ? registrationPath : `/${registrationPath}`}` : '');
        return {
            id: endpoint.id || '',
            name: endpoint.name || '',
            domain_suffix: endpoint.domain_suffix || '',
            api_url: apiUrl,
            token_value: '',
            tls_verify: endpoint.tls_verify !== false,
            token_visible: false,
        };
    }
}
