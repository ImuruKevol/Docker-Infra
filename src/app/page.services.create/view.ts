import { OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

type StepId = 1 | 2 | 3 | 4;

export class Component implements OnInit {
    public loading = signal<boolean>(true);
    public busy = signal<boolean>(false);
    public templateLoading = signal<boolean>(false);
    public preflightLoading = signal<boolean>(false);
    public error = signal<string>('');
    public step = signal<StepId>(1);
    public advancedSettings = signal<boolean>(false);
    public templateLocked = signal<boolean>(false);
    public importLoading = signal<boolean>(false);
    public aiBusy = signal<boolean>(false);
    public importSource = signal<any>(null);
    public importWarnings = signal<any[]>([]);
    public templates = signal<any[]>([]);
    public zones = signal<any[]>([]);
    public selectedTemplateId = signal<string>('');
    public baseContent = '';
    public generatedSecretKeys: string[] = [];
    public imageChecks: any = {};
    public preflight = signal<any>(null);
    public form: any = {
        name: '',
        description: '',
        domain_mode: 'none',
        zone_id: '',
        domain_prefix: '',
        domain_target_key: '',
        domain_target_port: 80,
    };
    public components: any[] = [];
    public aiForm: any = { intent: '', model_ref: 'auto' };
    public aiResult: any = null;
    public aiModelOptions = signal<any[]>([]);
    public aiDefaultModelRef = signal<string>('auto');
    public aiStreamEvents = signal<any[]>([]);
    public aiOutputTokenCount = signal<number>(0);

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.load();
        await this.loadAiModelOptions();
        if (!this.error()) await this.loadImportFromQuery();
    }

    public async load() {
        this.loading.set(true);
        const { code, data } = await wiz.call('load', {});
        if (code === 200) {
            this.templates.set(data.templates || []);
            this.zones.set(data.zones || []);
            this.baseContent = '';
            this.generatedSecretKeys = [];
            this.components = [];
            this.ensureDomainTarget();
        } else {
            this.error.set(data?.message || '서비스 생성 정보를 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
    }

    public async loadAiModelOptions() {
        const { code, data } = await wiz.call('ai_model_options', {});
        if (code === 200) {
            this.aiModelOptions.set(data.options || []);
            this.aiDefaultModelRef.set(data.default_model_ref || 'auto');
            this.aiForm.model_ref = data.default_model_ref || 'auto';
        }
    }

    private importQuery() {
        const params = new URLSearchParams(window.location.search || '');
        const nodeId = String(params.get('import_node_id') || '').trim();
        const path = String(params.get('import_path') || '').trim();
        if (!nodeId || !path) return null;
        return {
            node_id: nodeId,
            path,
            suggested_name: String(params.get('import_name') || '').trim(),
        };
    }

    public async loadImportFromQuery() {
        const query = this.importQuery();
        if (!query) return;
        this.importLoading.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('load_import', query);
        if (code === 200) {
            this.selectedTemplateId.set('');
            this.templateLocked.set(true);
            this.importSource.set(data.source_ref || null);
            this.importWarnings.set(data.warnings || []);
            this.baseContent = data.content || '';
            this.generatedSecretKeys = [];
            this.components = data.components || [];
            this.form.name = data.suggested_name || query.suggested_name || this.form.name;
            this.form.description = this.form.description || '서버에 있던 Compose 파일을 가져와 생성합니다.';
            this.imageChecks = {};
            this.preflight.set(null);
            this.ensureDomainTarget();
        } else {
            await this.alert(this.formatComposeError(data, 'Compose 파일을 서비스 생성 화면으로 가져올 수 없습니다.'));
        }
        this.importLoading.set(false);
        await this.service.render();
    }

    public steps() {
        return [
            { id: 1, title: '서비스 종류', description: '이름과 템플릿' },
            { id: 2, title: '구성 확인', description: '이미지, 연결 포트, 고급 설정' },
            { id: 3, title: '도메인', description: '접속 주소' },
            { id: 4, title: '확인', description: '저장 또는 배포' },
        ];
    }

    public templateSelectorItems() {
        return this.templates()
            .filter((item: any) => item?.enabled !== false)
            .map((item: any) => ({
                value: item.id,
                label: item.name,
                description: item.description || '설명 없음',
                badge: item?.metadata?.category || 'template',
                badgeClass: 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300',
            }));
    }

    public zoneSelectorItems() {
        return this.zones().map((zone: any) => {
            const summary = zone.certificate_summary || {};
            const hasCert = Number(summary.valid || 0) > 0;
            return {
                value: zone.id,
                label: zone.domain,
                description: hasCert ? '업로드된 SSL 인증서 사용' : '인증서는 배포 시 자동 발급 예정',
                badge: hasCert ? 'SSL' : 'certbot',
                badgeClass: hasCert
                    ? 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300'
                    : 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300',
            };
        });
    }

    public selectedZone() {
        return this.zones().find((zone: any) => zone.id === this.form.zone_id) || null;
    }

    public serviceAiInputRows() {
        return [
            { key: 'intent', value: '배포 요구사항' },
            { key: 'model', value: 'AI 설정에서 사용 가능한 모델' },
            { key: 'form', value: '서비스 이름, 설명, 도메인' },
            { key: 'components', value: '이미지, 포트, 환경변수, 볼륨' },
            { key: 'base_content', value: '선택 템플릿 Compose' },
        ];
    }

    public serviceAiOutputRows() {
        return [
            { key: 'form', value: '서비스 기본 정보와 도메인 대상' },
            { key: 'components', value: '컴포넌트별 실행 설정' },
            { key: 'warnings', value: '지원 불가 또는 확인 필요 항목' },
        ];
    }

    private resetAiStream() {
        this.aiStreamEvents.set([]);
        this.aiOutputTokenCount.set(0);
    }

    private pushAiEvent(event: any) {
        this.aiStreamEvents.set([...this.aiStreamEvents(), event].slice(-120));
        if (event?.type === 'delta') {
            this.aiOutputTokenCount.set(this.aiOutputTokenCount() + String(event.text || '').length);
        }
    }

    public aiStreamRows() {
        return this.compactAiStreamRows(this.aiStreamEvents());
    }

    private streamLines(value: any) {
        return String(value || '')
            .replace(/\r/g, '')
            .split('\n')
            .map((line: string) => line.replace(/\s+/g, ' ').trim())
            .filter((line: string) => !!line)
            .map((line: string) => line.length > 220 ? `${line.slice(0, 217)}...` : line);
    }

    private latestStreamLine(value: any) {
        const lines = this.streamLines(value);
        if (!lines.length) return '';
        const cleaned = lines[lines.length - 1]
            .replace(/^[\s"',:{}\[\]]+|[\s"',:{}\[\]]+$/g, '')
            .replace(/\\"/g, '"')
            .trim();
        if (!cleaned || /^[{}\[\],:"]+$/.test(cleaned)) return '';
        return cleaned.length > 120 ? `${cleaned.slice(0, 117)}...` : cleaned;
    }

    private streamProgressMessage(value: any) {
        const text = String(value || '');
        let stage = 'AI 응답 작성 중';
        if (text.includes('"README.md"')) stage = 'README 작성 중';
        else if (text.includes('"values.schema.json"')) stage = 'Schema 작성 중';
        else if (text.includes('"values.default.yaml"')) stage = '기본값 작성 중';
        else if (text.includes('"docker-compose.yaml"') || text.includes('"compose"')) stage = 'Compose 작성 중';
        else if (text.includes('"components"')) stage = '컴포넌트 설정 작성 중';
        else if (text.includes('"form"')) stage = '서비스 기본 정보 작성 중';
        else if (text.includes('"template"')) stage = '템플릿 메타데이터 작성 중';
        const latest = this.latestStreamLine(text);
        return latest ? `${stage} · ${latest}` : stage;
    }

    private compactAiStreamRows(events: any[]) {
        const rows: any[] = [];
        let thinkingBuffer = '';
        let deltaBuffer = '';
        let progressIndex = -1;
        const pushRow = (row: any) => {
            const message = row?.message || row?.text || row?.provider?.label;
            if (!message && row?.type !== 'provider') return;
            const last = rows[rows.length - 1];
            if (last?.type === row?.type && (last?.message || last?.text) === (row?.message || row?.text)) return;
            rows.push(row);
        };
        const upsertProgress = () => {
            if (!deltaBuffer) return;
            const row = { type: 'progress', label: '생각 중', message: this.streamProgressMessage(deltaBuffer) };
            if (progressIndex >= 0) rows[progressIndex] = row;
            else {
                progressIndex = rows.length;
                rows.push(row);
            }
        };
        const flushThinking = (force: boolean = false) => {
            if (!thinkingBuffer) return;
            const parts = thinkingBuffer.split('\n');
            thinkingBuffer = parts.pop() || '';
            for (const line of parts) {
                for (const text of this.streamLines(line)) {
                    pushRow({ type: 'thinking', message: text, text });
                }
            }
            if (force && thinkingBuffer.trim()) {
                const text = this.streamLines(thinkingBuffer).join(' ');
                if (text) pushRow({ type: 'thinking', message: text, text });
                thinkingBuffer = '';
            }
        };
        for (const event of events || []) {
            if (!['provider', 'status', 'thinking', 'error', 'delta'].includes(event?.type)) continue;
            if (event.type === 'delta') {
                deltaBuffer += String(event.text || '');
                upsertProgress();
                continue;
            }
            if (event.type === 'thinking') {
                thinkingBuffer += String(event.text || event.message || '');
                flushThinking(false);
                continue;
            }
            flushThinking(true);
            if (event.type === 'provider') {
                pushRow(event);
                continue;
            }
            for (const text of this.streamLines(event.message || event.text || '')) {
                pushRow({ ...event, message: text, text });
            }
        }
        flushThinking(true);
        return rows.slice(-8);
    }

    private async streamAi(functionName: string, payload: any, onDone: (data: any) => Promise<void>) {
        const formData = new FormData();
        formData.append('payload', JSON.stringify(payload || {}));
        const response = await fetch(`/wiz/api/page.services.create/${functionName}`, { method: 'POST', body: formData });
        if (!response.ok || !response.body) {
            throw new Error(`AI 스트림 요청 실패: HTTP ${response.status}`);
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const blocks = buffer.split('\n\n');
            buffer = blocks.pop() || '';
            for (const block of blocks) {
                const line = block.split('\n').find((item: string) => item.startsWith('data: '));
                if (!line) continue;
                const event = JSON.parse(line.slice(6));
                this.pushAiEvent(event);
                if (event.type === 'error') {
                    throw new Error(event.message || 'AI 스트림 처리 중 오류가 발생했습니다.');
                }
                if (event.type === 'done') {
                    await onDone(event.data);
                }
            }
            await this.service.render();
        }
    }

    public async selectTemplate(templateId: string) {
        if (this.step() !== 1 || this.templateLocked()) return;
        this.selectedTemplateId.set(templateId || '');
        if (!templateId) {
            this.generatedSecretKeys = [];
            return;
        }
        this.templateLoading.set(true);
        const { code, data } = await wiz.call('template_detail', { template_id: templateId });
        if (code === 200) {
            this.baseContent = data?.preview?.rendered_compose || data?.files?.['docker-compose.yaml'] || '';
            this.generatedSecretKeys = data?.generated_secret_keys || [];
            this.components = data.components || [];
            this.form.name = data?.template?.name || this.form.name;
            this.form.description = data?.template?.description || this.form.description;
            this.imageChecks = {};
            this.preflight.set(null);
            this.ensureDomainTarget();
        } else {
            this.generatedSecretKeys = [];
            await this.alert(data?.message || '템플릿을 불러올 수 없습니다.');
        }
        this.templateLoading.set(false);
        await this.service.render();
    }

    private applyAiServiceDraft(draft: any) {
        if (draft?.form) {
            this.form = {
                ...this.form,
                ...draft.form,
            };
        }
        if (Array.isArray(draft?.components) && draft.components.length) {
            this.components = draft.components;
        }
        this.ensureDomainTarget();
        this.syncDomain();
        this.preflight.set(null);
    }

    public async generateServiceWithAi() {
        const intent = String(this.aiForm.intent || '').trim();
        if (!intent) {
            await this.alert('AI 요청 내용을 입력해주세요.');
            return;
        }
        if (!this.importSource() && !this.selectedTemplateId()) {
            await this.alert('AI 자동 구성 전에 서비스 종류를 선택해주세요.');
            return;
        }
        if (!this.components.length) {
            await this.alert('서비스 구성을 먼저 불러와주세요.');
            return;
        }
        this.aiBusy.set(true);
        this.resetAiStream();
        try {
            await this.streamAi('stream_service_ai', {
                mode: 'service_create',
                intent,
                model_ref: this.aiForm.model_ref || this.aiDefaultModelRef() || 'auto',
                form: this.form,
                components: this.components,
                base_content: this.baseContent,
                template_id: this.selectedTemplateId(),
                templates: this.templates(),
                zones: this.zones(),
                service: {},
            }, async (data: any) => {
                this.aiResult = data;
                this.applyAiServiceDraft(data?.draft);
            });
            await this.alert(this.aiResult?.summary || 'AI 서비스 구성을 적용했습니다. 다음 단계에서 검토하세요.', 'success');
        } catch (error: any) {
            await this.alert(error?.message || 'AI 서비스 구성을 생성할 수 없습니다.');
        }
        this.aiBusy.set(false);
        await this.service.render();
    }

    public async setStep(step: StepId) {
        if (step <= this.step()) {
            this.step.set(step);
            return;
        }
        for (let index = 1; index < step; index += 1) {
            if (!(await this.validateStep(index as StepId))) {
                this.step.set(index as StepId);
                await this.service.render();
                return;
            }
        }
        if (step > 1) this.templateLocked.set(true);
        this.step.set(step);
        if (step === 4) await this.runPreflight(false);
        await this.service.render();
    }

    public async nextStep() {
        await this.setStep(Math.min(4, this.step() + 1) as StepId);
    }

    public previousStep() {
        this.step.set(Math.max(1, this.step() - 1) as StepId);
    }

    public async validateStep(step: StepId = this.step()) {
        if (step === 1 && !String(this.form.name || '').trim()) {
            await this.alert('서비스 이름을 입력해주세요.');
            return false;
        }
        if (step === 1 && !this.importSource() && !this.selectedTemplateId()) {
            await this.alert('만들 서비스의 종류를 선택해주세요.');
            return false;
        }
        if (step === 2) {
            if (!this.components.length) {
                await this.alert('서비스 구성을 불러오지 못했습니다. 서비스 종류를 다시 선택해주세요.');
                return false;
            }
            let connectablePorts = 0;
            for (const item of this.components) {
                if (!String(item.image_name || '').trim() || !String(item.image_tag || '').trim()) {
                    await this.alert('모든 구성의 이미지 이름과 버전을 입력해주세요.');
                    return false;
                }
                connectablePorts += this.ports(item).length;
            }
            if (connectablePorts < 1) {
                await this.alert('도메인이나 외부 접속에 연결할 포트가 하나 이상 필요합니다.');
                return false;
            }
        }
        if (step === 3 && this.form.domain_mode === 'registered') {
            this.syncDomain();
            if (!this.form.zone_id || !this.form.domain) {
                await this.alert('사용할 도메인을 선택해주세요.');
                return false;
            }
        }
        return true;
    }

    public imageRef(item: any) {
        const tag = String(item.image_tag || 'latest').trim();
        return tag.startsWith('sha256:') ? `${item.image_name}@${tag}` : `${item.image_name}:${tag}`;
    }

    public ports(item: any) {
        return (item.ports || []).filter((port: any) => Number(port.target || 0) > 0);
    }

    public addPort(item: any) {
        item.ports = item.ports || [];
        item.ports.push({ target: 80, protocol: 'tcp' });
        this.ensureDomainTarget();
    }

    public removePort(item: any, index: number) {
        item.ports.splice(index, 1);
        this.ensureDomainTarget();
    }

    public addEnv(item: any) {
        item.env_vars = item.env_vars || [];
        item.env_vars.push({ key: '', value: '' });
    }

    public removeEnv(item: any, index: number) {
        item.env_vars.splice(index, 1);
    }

    public addVolume(item: any) {
        item.volumes = item.volumes || [];
        item.volumes.push({ source: `${item.key}_data`, target: '/data' });
    }

    public removeVolume(item: any, index: number) {
        item.volumes.splice(index, 1);
    }

    public domainTargetOptions() {
        const options: any[] = [];
        for (const item of this.components) {
            for (const port of this.ports(item)) {
                const serviceLabel = item.label || item.key;
                const protocol = port.protocol || 'tcp';
                options.push({
                    key: `${item.key}:${port.target}`,
                    label: `${serviceLabel} · ${port.target}/${protocol}`,
                    service_label: serviceLabel,
                    service_key: item.key,
                    port: port.target,
                    protocol,
                    recommended: !!port.public_endpoint,
                });
            }
        }
        return options.sort((a: any, b: any) => Number(!!b.recommended) - Number(!!a.recommended));
    }

    public ensureDomainTarget() {
        const first = this.domainTargetOptions()[0];
        const current = this.domainTargetOptions().find((item: any) => item.key === this.form.domain_target_key);
        if ((!this.form.domain_target_key || !current) && first) {
            this.form.domain_target_key = first.key;
            this.form.domain_target_port = first.port;
        }
    }

    public selectDomainTarget(key: string) {
        const option = this.domainTargetOptions().find((item: any) => item.key === key);
        this.form.domain_target_key = key;
        this.form.domain_target_port = option?.port || 80;
    }

    public setDomainMode(mode: 'none' | 'registered') {
        this.form.domain_mode = mode;
        if (mode === 'registered' && !this.form.zone_id && this.zones()[0]) {
            this.form.zone_id = this.zones()[0].id;
        }
        this.syncDomain();
    }

    public selectZone(zoneId: string) {
        this.form.zone_id = zoneId || '';
        this.syncDomain();
    }

    public syncDomain() {
        if (this.form.domain_mode !== 'registered') {
            this.form.domain = '';
            return;
        }
        const zone = this.selectedZone();
        if (!zone?.domain) return;
        const prefix = String(this.form.domain_prefix || '').trim().replace(/^\.+|\.+$/g, '');
        this.form.domain = prefix ? `${prefix}.${zone.domain}` : zone.domain;
    }

    public domainPreview() {
        if (this.form.domain_mode !== 'registered') return '도메인 사용 안 함';
        const zone = this.selectedZone();
        const prefix = String(this.form.domain_prefix || '').trim().replace(/^\.+|\.+$/g, '');
        return zone?.domain ? (prefix ? `${prefix}.${zone.domain}` : zone.domain) : '도메인 선택 필요';
    }

    public async checkImage(item: any) {
        const ref = this.imageRef(item);
        this.imageChecks[ref] = { loading: true };
        await this.service.render();
        const { code, data } = await wiz.call('check_image', { image_ref: ref });
        this.imageChecks[ref] = code === 200 ? data : { exists: false, message: data?.message || '이미지를 확인할 수 없습니다.' };
        await this.service.render();
    }

    public imageCheck(item: any) {
        return this.imageChecks[this.imageRef(item)] || null;
    }

    public payload() {
        this.syncDomain();
        this.ensureDomainTarget();
        return {
            ...this.form,
            template_id: this.selectedTemplateId(),
            base_content: this.baseContent,
            generated_secret_keys: this.generatedSecretKeys,
            components: this.components,
            source: this.importSource() ? 'server_compose_import_wizard' : 'ui_wizard',
            import_source: this.importSource(),
            source_ref: this.importSource() || undefined,
        };
    }

    public importSourcePath() {
        return this.importSource()?.path || '';
    }

    public importWarningCount() {
        return this.importWarnings().length;
    }

    public preflightItems() {
        return this.preflight()?.items || [];
    }

    public preflightSummaryText() {
        const summary = this.preflight()?.summary;
        if (!summary) return '아직 자동 점검을 실행하지 않았습니다.';
        if (summary.blocking > 0) return `${summary.blocking}개 항목을 수정해야 합니다.`;
        if (summary.warnings > 0) return `${summary.warnings}개 항목은 자동 조정 또는 배포 중 확인됩니다.`;
        return '저장과 배포에 필요한 기본 점검을 통과했습니다.';
    }

    public preflightStatusLabel(status: string) {
        const labels: any = {
            ok: '통과',
            warning: '확인',
            adjusted: '자동 조정',
            error: '수정 필요',
            info: '정보',
        };
        return labels[status] || status || '-';
    }

    public preflightStatusClass(status: string) {
        if (status === 'ok') return 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300';
        if (status === 'adjusted') return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        if (status === 'warning') return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        if (status === 'error') return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }

    public preflightActionText(item: any) {
        const key = String(item?.key || '');
        if (key.includes('image')) return '조치: 이미지 이름과 버전을 확인하거나, 먼저 해당 이미지를 서버 또는 공개 저장소에 준비해주세요.';
        if (key.includes('ports')) return '조치: Docker Infra가 가능한 포트를 자동 조정합니다. 계속 문제가 나면 해당 서버에서 사용 중인 포트를 정리해주세요.';
        if (key.includes('domain')) return '조치: 도메인 관리에서 도메인과 인증서 상태를 확인하거나 도메인을 사용하지 않도록 선택해주세요.';
        if (key.includes('volume')) return '조치: 데이터 보관 경로는 /로 시작하는 컨테이너 내부 경로를 사용해주세요.';
        if (key.includes('namespace')) return '조치: 서비스 이름을 조금 다르게 입력한 뒤 다시 저장해주세요.';
        if (key.includes('placement')) return '조치: 서버 관리에서 실행 서버의 Docker와 SSH 상태를 먼저 확인해주세요.';
        if (key.includes('nginx')) return '조치: nginx 설치와 설정 경로는 Ubuntu 24.04 기본값으로 자동 확인됩니다. 설치 상태를 확인해주세요.';
        return '조치: 표시된 항목을 수정한 뒤 다시 점검해주세요.';
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

    private formatPreflightError(data: any) {
        const preflight = data?.preflight || data?.result?.preflight;
        const blocking = preflight?.blocking || [];
        if (blocking.length) {
            return [
                '서비스를 만들기 전에 아래 항목을 수정해야 합니다.',
                ...blocking.map((item: any) => `- 원인: ${item.title} - ${item.message}\n  ${this.preflightActionText(item)}`),
            ].join('\n');
        }
        return this.formatComposeError(data, data?.message || '자동 점검을 통과하지 못했습니다.');
    }

    public async runPreflight(showMessage: boolean = false) {
        this.preflightLoading.set(true);
        this.preflight.set(null);
        const { code, data } = await wiz.call('preflight', this.payload());
        this.preflightLoading.set(false);
        if (code === 200) {
            this.preflight.set(data.preflight || null);
            await this.service.render();
            if (!data.preflight?.ok && showMessage) {
                await this.alert(this.formatPreflightError(data));
            }
            return !!data.preflight?.ok;
        }
        if (showMessage) await this.alert(this.formatPreflightError(data));
        await this.service.render();
        return false;
    }

    public async save(deploy: boolean = false) {
        for (const item of [1, 2, 3] as StepId[]) {
            if (!(await this.validateStep(item))) {
                this.step.set(item);
                return;
            }
        }
        if (!(await this.runPreflight(true))) {
            this.step.set(4);
            return;
        }
        this.busy.set(true);
        const { code, data } = await wiz.call('create_service', this.payload());
        if (code !== 200) {
            this.busy.set(false);
            await this.alert(this.formatPreflightError(data));
            return;
        }
        const serviceId = data.result?.service?.id;
        if (deploy && serviceId) {
            const deployResult = await wiz.call('deploy_service_background', { service_id: serviceId });
            this.busy.set(false);
            if (![200, 202].includes(deployResult.code)) {
                await this.alert(deployResult.data?.message || '서비스 배포에 실패했습니다.');
                this.service.href(`/services?service_id=${encodeURIComponent(serviceId)}`);
                return;
            }
            await this.alert('서비스를 저장했고 배포는 백그라운드에서 시작했습니다. 서비스 화면에서 진행 상태를 확인할 수 있습니다.', 'success');
            this.service.href(`/services?service_id=${encodeURIComponent(serviceId)}`);
            return;
        }
        this.busy.set(false);
        await this.alert('서비스 초안을 저장했습니다.', 'success');
        this.service.href('/services');
    }

    public cancel() {
        this.service.href('/services');
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
}
