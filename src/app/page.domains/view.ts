import { OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

const RECORD_TYPES = ['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'SRV', 'NS'];
const RECORD_TYPE_HELP: any = {
    A: '도메인을 IPv4 주소로 연결합니다.',
    AAAA: '도메인을 IPv6 주소로 연결합니다.',
    CNAME: '도메인을 다른 도메인 이름으로 연결합니다.',
    MX: '메일 서버 우선순위를 지정합니다.',
    TXT: '검증 문자열이나 설명 텍스트를 저장합니다.',
    SRV: '서비스 포트와 대상을 지정합니다.',
    NS: '하위 영역 nameserver를 지정합니다.'
};
const DEFAULT_TTL_BY_TYPE: any = {
    A: 1,
    AAAA: 1,
    CNAME: 1,
    MX: 1,
    TXT: 1,
    SRV: 1,
    NS: 1
};

export class Component implements OnInit {
    public loading = signal<boolean>(true);
    public detailLoading = signal<boolean>(false);
    public syncLoading = signal<boolean>(false);
    public ddnsUpdateEndpointId = signal<string>('');
    public ddnsDispatcherBusy = signal<boolean>(false);
    public error = signal<string>('');
    public zones = signal<any[]>([]);
    public ddnsEndpoints = signal<any[]>([]);
    public ddnsDispatcher = signal<any>({});
    public ddnsWarning = signal<string>('');
    public selectedZoneId = signal<string>('');
    public detail = signal<any>(this.emptyDetail());
    public zoneModalOpen = signal<boolean>(false);
    public ddnsModalOpen = signal<boolean>(false);
    public recordModalOpen = signal<boolean>(false);
    public recordDetailModalOpen = signal<boolean>(false);
    public certificateModalOpen = signal<boolean>(false);
    public certificateBusy = signal<boolean>(false);
    public zoneForm: any = this.emptyZoneForm();
    public ddnsForm: any = this.emptyDdnsForm();
    public recordForm: any = this.emptyRecordForm();
    public recordDetail: any = null;
    public certificateForm: any = this.emptyCertificateForm();
    public recordFilters: any = { types: [], query: '', ipv4: '' };

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

    public async load(selectZoneId: string = '') {
        this.loading.set(true);
        this.error.set('');
        const { code, data } = await wiz.call('load', {});
        if (code === 200) {
            const zones = data.zones || [];
            const ddns = data.ddns || {};
            this.ddnsEndpoints.set(ddns.endpoints || []);
            this.ddnsDispatcher.set(ddns.dispatcher || {});
            this.ddnsWarning.set(ddns.available === false ? (ddns.message || 'DDNS 관리 서버 정보를 불러올 수 없습니다.') : '');
            this.zones.set(zones);
            const currentZoneId = this.selectedZoneId();
            const nextZoneId = selectZoneId || (zones.some((zone: any) => zone.id === currentZoneId) ? currentZoneId : '') || zones[0]?.id || '';
            this.selectedZoneId.set(nextZoneId);
            if (nextZoneId) await this.loadDetail(nextZoneId);
            else this.detail.set(this.emptyDetail());
        } else {
            this.error.set(data?.message || '도메인 정보를 불러올 수 없습니다.');
            this.ddnsWarning.set('');
            this.ddnsDispatcher.set({});
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
            await this.load(this.selectedZoneId());
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
            await this.load(this.selectedZoneId());
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
            await this.load(this.selectedZoneId());
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
            await this.load(this.selectedZoneId());
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

    public async loadDetail(zoneId: string) {
        if (!zoneId) return;
        this.detailLoading.set(true);
        this.selectedZoneId.set(zoneId);
        const { code, data } = await wiz.call('detail', { zone_id: zoneId });
        if (code === 200) {
            this.detail.set({ ...this.emptyDetail(), ...data });
            this.resetRecordFilters();
        } else {
            await this.alert(data?.message || '도메인 상세 정보를 불러올 수 없습니다.');
        }
        this.detailLoading.set(false);
        await this.service.render();
    }

    public selectedZone() {
        return this.detail()?.zone || null;
    }

    public openZoneModal(zone: any = null) {
        this.zoneForm = this.emptyZoneForm(zone || {});
        this.zoneModalOpen.set(true);
    }

    public closeZoneModal() {
        this.zoneModalOpen.set(false);
        this.zoneForm = this.emptyZoneForm();
    }

    public async saveZone() {
        const { code, data } = await wiz.call('save_zone', { ...this.zoneForm });
        if (code === 200) {
            this.closeZoneModal();
            await this.load(data.zone?.id || this.selectedZoneId());
            await this.alert('도메인 설정을 저장했습니다.', 'success');
            return;
        }
        await this.alert(data?.message || '도메인 설정을 저장할 수 없습니다.');
    }

    public async deleteZone(zone: any) {
        const ok = await this.confirm(`${zone.domain} 도메인 설정을 삭제합니다. 캐시된 DNS 레코드도 함께 제거됩니다.`, '삭제');
        if (!ok) return;
        const { code, data } = await wiz.call('delete_zone', { zone_id: zone.id });
        if (code === 200) {
            const next = this.zones().find((item: any) => item.id !== zone.id)?.id || '';
            await this.load(next);
            await this.alert('도메인 설정을 삭제했습니다.', 'success');
            return;
        }
        await this.alert(data?.message || '도메인 설정을 삭제할 수 없습니다.');
    }

    public async syncSelectedZone() {
        const zone = this.selectedZone();
        if (!zone) return;
        this.syncLoading.set(true);
        const { code, data } = await wiz.call('sync_zone', { zone_id: zone.id });
        this.syncLoading.set(false);
        if (code === 200) {
            this.detail.set({ ...this.emptyDetail(), ...data });
            await this.load(zone.id);
            await this.alert(`${zone.domain} 동기화를 완료했습니다.`, 'success');
            return;
        }
        await this.alert(data?.message || '동기화에 실패했습니다.');
    }

    public async syncAllZones() {
        this.syncLoading.set(true);
        const { code, data } = await wiz.call('sync_all', {});
        this.syncLoading.set(false);
        if (code === 200) {
            await this.load(this.selectedZoneId());
            const failed = data.failed || [];
            if (failed.length > 0) {
                await this.alert(['일부 도메인 동기화에 실패했습니다.', ...failed.map((item: any) => `${item.domain}: ${item.message}`)].join('\n'));
                return;
            }
            await this.alert('전체 도메인 동기화를 완료했습니다.', 'success');
            return;
        }
        await this.alert(data?.message || '전체 동기화에 실패했습니다.');
    }

    public openRecordModal(record: any = null) {
        const zone = this.selectedZone();
        if (!zone) return;
        this.recordForm = this.emptyRecordForm(record || {});
        this.recordForm.zone_id = zone.id;
        this.recordModalOpen.set(true);
    }

    public closeRecordModal() {
        this.recordModalOpen.set(false);
        this.recordForm = this.emptyRecordForm();
    }

    public async saveRecord() {
        const payload = {
            ...this.recordForm,
            record_name: String(this.recordForm.record_name || '').trim() || '@',
            proxied: false,
            ttl: this.defaultTtlForType(this.recordForm.record_type),
            priority: undefined
        };
        const { code, data } = await wiz.call('save_record', payload);
        if (code === 200) {
            this.recordModalOpen.set(false);
            this.detail.set({ ...this.emptyDetail(), ...data });
            await this.load(this.selectedZoneId());
            await this.alert('DNS 레코드를 저장했습니다.', 'success');
            return;
        }
        await this.alert(data?.message || 'DNS 레코드를 저장할 수 없습니다.');
    }

    public openRecordDetail(record: any) {
        this.recordDetail = record || null;
        this.recordDetailModalOpen.set(Boolean(record));
    }

    public closeRecordDetail() {
        this.recordDetailModalOpen.set(false);
        this.recordDetail = null;
    }

    public async deleteRecord(record: any) {
        const ok = await this.confirm(`${record.record_name} ${record.record_type} 레코드를 삭제합니다.`, '삭제');
        if (!ok) return;
        const { code, data } = await wiz.call('delete_record', { zone_id: this.selectedZoneId(), record_id: record.cloudflare_record_id });
        if (code === 200) {
            this.detail.set({ ...this.emptyDetail(), ...data });
            await this.load(this.selectedZoneId());
            await this.alert('DNS 레코드를 삭제했습니다.', 'success');
            return;
        }
        await this.alert(data?.message || 'DNS 레코드를 삭제할 수 없습니다.');
    }

    public openCertificateModal() {
        const zone = this.selectedZone();
        if (!zone) return;
        this.certificateForm = this.emptyCertificateForm({ label: `${zone.domain} 인증서` });
        this.certificateModalOpen.set(true);
    }

    public closeCertificateModal() {
        if (this.certificateBusy()) return;
        this.certificateModalOpen.set(false);
        this.certificateForm = this.emptyCertificateForm();
    }

    public openCertificateFilePicker(field: string) {
        (document.getElementById(`domain-certificate-${field}`) as HTMLInputElement | null)?.click();
    }

    public async selectCertificateFile(field: string, event: Event) {
        const input = event?.target as HTMLInputElement | null;
        const file = input?.files && input.files[0];
        if (!file) return;
        this.certificateForm[field] = file;
        this.certificateForm[`${field}_name`] = file.name;
        if (input) input.value = '';
        await this.service.render();
    }

    public async uploadCertificate() {
        const zone = this.selectedZone();
        if (!zone) return;
        if (!this.certificateForm.cert_file || !this.certificateForm.key_file) {
            await this.alert('인증서 파일과 키 파일을 모두 선택해주세요.');
            return;
        }
        this.certificateBusy.set(true);
        await this.service.render();
        const fd = new FormData();
        fd.append('zone_id', zone.id);
        fd.append('label', this.certificateForm.label || `${zone.domain} 인증서`);
        fd.append('cert_file', this.certificateForm.cert_file);
        fd.append('key_file', this.certificateForm.key_file);
        if (this.certificateForm.chain_file) fd.append('chain_file', this.certificateForm.chain_file);
        const response: any = await this.service.file.upload('/api/domain-certificates', fd);
        this.certificateBusy.set(false);
        if (response?.code === 200) {
            this.certificateModalOpen.set(false);
            this.certificateForm = this.emptyCertificateForm();
            this.detail.set({ ...this.emptyDetail(), ...(response?.data || {}) });
            await this.alert('SSL 인증서를 업로드했습니다.', 'success');
            await this.service.render();
            return;
        }
        await this.alert(response?.data?.message || response?.message || 'SSL 인증서를 업로드할 수 없습니다.');
        await this.service.render();
    }

    public async deleteCertificate(cert: any) {
        const zone = this.selectedZone();
        if (!zone || !cert?.id) return;
        const ok = await this.confirm(`${cert.label || cert.cert_path} 인증서를 삭제합니다.`, '삭제');
        if (!ok) return;
        const { code, data } = await wiz.call('delete_certificate', { zone_id: zone.id, certificate_id: cert.id });
        if (code === 200) {
            this.detail.set({ ...this.emptyDetail(), ...data });
            await this.alert('SSL 인증서를 삭제했습니다.', 'success');
            return;
        }
        await this.alert(data?.message || 'SSL 인증서를 삭제할 수 없습니다.');
    }

    public zoneStatusLabel(zone: any) {
        const labels: any = { active: '동기화됨', manual: '수동', pending: '대기', error: '오류', disabled: '사용 안 함' };
        return labels[zone?.status] || zone?.status || '-';
    }

    public toggleRecordType(type: string) {
        const current = [...this.recordFilters.types];
        const index = current.indexOf(type);
        if (index >= 0) current.splice(index, 1);
        else current.push(type);
        this.recordFilters.types = current;
    }

    public isRecordTypeActive(type: string) {
        return this.recordFilters.types.includes(type);
    }

    public visibleRecords() {
        const filters = this.recordFilters;
        const query = String(filters.query || '').trim().toLowerCase();
        const ipv4 = String(filters.ipv4 || '').trim();
        return (this.detail()?.records || []).filter((record: any) => {
            if (filters.types.length > 0 && !filters.types.includes(record.record_type)) return false;
            if (query) {
                const target = [
                    record.record_name,
                    record.content,
                    record.comment,
                    this.fqdn(record.record_name, this.selectedZone()?.domain)
                ].join(' ').toLowerCase();
                if (!target.includes(query)) return false;
            }
            if (ipv4 && !(record.record_type === 'A' && String(record.content || '') === ipv4)) return false;
            return true;
        });
    }

    public recordTypeOptions() {
        return Array.from(new Set((this.detail()?.records || []).map((item: any) => item.record_type).filter(Boolean))).sort();
    }

    public ipv4Options() {
        const buckets: any = {};
        for (const record of this.detail()?.records || []) {
            if (record.record_type !== 'A') continue;
            const ip = String(record.content || '').trim();
            if (!ip) continue;
            buckets[ip] = (buckets[ip] || 0) + 1;
        }
        return Object.keys(buckets).sort().map((ip) => ({ ip, count: buckets[ip] }));
    }

    public ipv4FilterItems() {
        return this.ipv4Options().map((item) => ({
            value: item.ip,
            label: item.ip,
            description: `A 레코드 ${item.count}개`,
            badge: `${item.count}개`,
            badgeClass: 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300'
        }));
    }

    public setIpv4Filter(value: any) {
        this.recordFilters.ipv4 = String(value || '');
    }

    public resetRecordFilters() {
        this.recordFilters = { types: [], query: '', ipv4: '' };
    }

    public hasIpv4Filter() {
        return this.ipv4Options().length > 0;
    }

    public sslSummaryItems() {
        const summary = this.detail()?.ssl_summary || {};
        return [
            { label: '유효', value: summary.valid || 0, status: 'active' },
            { label: '곧 만료', value: summary.expiring || 0, status: 'pending' },
            { label: '만료', value: summary.expired || 0, status: 'error' },
            { label: '오류/누락', value: (summary.error || 0) + (summary.missing || 0) + (summary.key_insecure || 0) + (summary.key_mismatch || 0), status: 'error' }
        ].filter((item) => item.value > 0);
    }

    public statusClass(status: any) {
        if (status === true || ['active', 'ok', 'issued', 'success', 'valid'].includes(status)) return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        if (['pending', 'manual', 'none', 'disabled', 'expiring'].includes(status)) return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        if (['failed', 'expired', 'error', 'missing'].includes(status)) return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }

    public certificateStatusLabel(status: string) {
        const labels: any = {
            valid: '유효',
            expiring: '곧 만료',
            expired: '만료',
            missing: '파일 없음',
            error: '분석 실패',
            key_insecure: '키 권한 확인 필요',
            key_mismatch: '키 불일치',
            disabled: '사용 안 함'
        };
        return labels[status] || status || '-';
    }

    public certificateKeyText(cert: any) {
        if (!cert?.key_exists) return 'KEY 없음';
        if (cert.key_matches === false) return 'KEY 불일치';
        if (cert.key_permission_secure === false) return `권한 확인 필요 (${cert.key_permission_mode || '-'})`;
        return `KEY 정상 (${cert.key_permission_mode || '0600'})`;
    }

    public serviceLinks() {
        return this.detail()?.service_links || [];
    }

    public serviceDetailHref(item: any) {
        const serviceId = String(item?.service_id || '').trim();
        return serviceId ? `/services?service_id=${encodeURIComponent(serviceId)}` : '/services';
    }

    public certificateAppliedServiceLinks() {
        return this.serviceLinks().filter((item: any) => item.certificate_applied === true);
    }

    public serviceCertificateLabel(item: any) {
        const labels: any = {
            existing: '업로드 인증서',
            upload: '업로드 인증서',
            certbot: '무료 인증서',
            self_signed: '테스트 인증서',
            none: 'SSL 없음',
        };
        return labels[item?.nginx_ssl_mode] || labels[item?.ssl_mode] || item?.nginx_ssl_mode || item?.ssl_mode || '-';
    }

    public formatDate(value: any) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString();
    }

    public recordTypes() {
        return RECORD_TYPES;
    }

    public setRecordType(type: string) {
        this.recordForm.record_type = type;
        this.recordForm.ttl = this.defaultTtlForType(type);
    }

    public defaultTtlForType(type: string) {
        return DEFAULT_TTL_BY_TYPE[String(type || '').toUpperCase()] || 1;
    }

    public recordTypeDescription(type: string) {
        return RECORD_TYPE_HELP[type] || '레코드 타입 설명';
    }

    public fqdn(name: string, domain: string) {
        const hostname = String(name || '').trim();
        const zoneDomain = String(domain || '').trim();
        if (!hostname || hostname === '@') return zoneDomain;
        if (hostname === '*') return `*.${zoneDomain}`;
        if (hostname.endsWith(`.${zoneDomain}`)) return hostname;
        return `${hostname}.${zoneDomain}`;
    }

    public aRecordHelper() {
        const zone = this.selectedZone();
        if (!zone || !['A', 'AAAA', 'CNAME'].includes(this.recordForm.record_type)) return '';
        const host = this.fqdn(this.recordForm.record_name, zone.domain);
        const content = this.recordForm.content || '(대상 미입력)';
        return this.recordForm.record_type === 'CNAME' ? `${host} 접속 시 ${content} 도메인으로 연결됩니다.` : `${host} 접속 시 ${content} 주소로 연결됩니다.`;
    }

    public recordNameHelper() {
        if (this.recordForm.record_type !== 'A') return '';
        return 'Name을 비우면 @와 동일하게 루트 도메인에 연결됩니다. @는 루트, *는 모든 하위 도메인, _ 접두어는 검증/SRV 같은 특수 레이블에 사용합니다.';
    }

    public isAddressRecord(record: any) {
        return ['A', 'AAAA'].includes(String(record?.record_type || '').toUpperCase());
    }

    public contentSummary(record: any) {
        if (!record?.content) return '-';
        if (this.isAddressRecord(record)) return String(record.content);
        return `${record.record_type || 'DNS'} 상세`;
    }

    public recordDetailRows() {
        const record = this.recordDetail || {};
        return [
            { label: 'Type', value: record.record_type || '-' },
            { label: 'Name', value: record.record_name || '-' },
            { label: 'FQDN', value: this.fqdn(record.record_name, this.selectedZone()?.domain) || '-' },
            { label: 'Content', value: record.content || '-' },
            { label: 'Comment', value: record.comment || '-' },
            { label: '동기화', value: this.formatDate(record.last_synced_at) }
        ];
    }

    private emptyDetail() {
        return { zone: null, records: [], ssl_certificates: [], ssl_summary: {}, service_links: [] };
    }

    private emptyZoneForm(zone: any = {}) {
        return {
            id: zone.id || '',
            domain: zone.domain || '',
            zone_id: zone.zone_id || '',
            api_token_value: zone.api_token_value || '',
            enabled: zone.enabled !== false,
            usable_for_service: zone.usable_for_service !== false,
            token_visible: false
        };
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

    private emptyRecordForm(record: any = {}) {
        return {
            zone_id: '',
            id: record.cloudflare_record_id || record.id || '',
            cloudflare_record_id: record.cloudflare_record_id || '',
            record_type: record.record_type || record.type || 'A',
            record_name: record.record_name || record.name || '@',
            content: record.content || '',
            proxied: false,
            ttl: record.ttl || this.defaultTtlForType(record.record_type || record.type || 'A'),
            priority: '',
            comment: record.comment || ''
        };
    }

    private emptyCertificateForm(seed: any = {}) {
        return {
            label: seed.label || '',
            cert_file: null,
            chain_file: null,
            key_file: null,
            cert_file_name: '',
            chain_file_name: '',
            key_file_name: ''
        };
    }
}
