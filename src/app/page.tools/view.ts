import { OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    public loading = signal<boolean>(true);
    public error = signal<string>('');
    public commands = signal<any[]>([]);
    public backups = signal<any[]>([]);
    public health = signal<any>({});
    public runningDiagnostic = signal<string>('');
    public diagnosticResults = signal<any>({});
    public diagnostics = [
        {
            id: 'docker',
            title: 'Docker 상태 확인',
            description: 'Docker daemon이 응답하는지 확인합니다.',
            icon: 'fa-cube',
            command_id: 'docker.info'
        },
        {
            id: 'swarm',
            title: 'Swarm 연결 확인',
            description: '현재 서버가 Swarm manager로 동작하는지 확인합니다.',
            icon: 'fa-network-wired',
            command_id: 'swarm.info'
        },
        {
            id: 'nodes',
            title: '서버 목록 확인',
            description: 'Swarm에 연결된 서버 목록을 조회합니다.',
            icon: 'fa-server',
            command_id: 'swarm.nodes'
        },
        {
            id: 'proxy',
            title: 'Proxy 설정 검사',
            description: 'nginx/apache2 설정 파일이 reload 가능한 상태인지 검사합니다.',
            icon: 'fa-shield-halved',
            command_id: 'proxy.nginx.configtest',
            fallback_command_id: 'proxy.apachectl.configtest'
        }
    ];

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.load();
    }

    public async load() {
        this.loading.set(true);
        this.error.set('');
        const { code, data } = await wiz.call("load", {});
        if (code === 200) {
            this.commands.set(data.commands || []);
            this.backups.set(data.backups || []);
            this.health.set(data.health || {});
        } else {
            this.error.set(data?.message || '도구 정보를 불러올 수 없습니다.');
        }
        this.loading.set(false);
        await this.service.render();
    }

    public async runDiagnostic(item: any) {
        this.runningDiagnostic.set(item.id);
        const result = await this.executeDiagnosticCommand(item.command_id);
        let finalResult = result;
        if (result.status !== 'ok' && item.fallback_command_id) {
            const fallback = await this.executeDiagnosticCommand(item.fallback_command_id);
            finalResult = fallback.status === 'ok' ? fallback : result;
        }
        const next = { ...this.diagnosticResults() };
        next[item.id] = finalResult;
        this.diagnosticResults.set(next);
        this.runningDiagnostic.set('');
        await this.service.render();
    }

    private async executeDiagnosticCommand(command_id: string) {
        const { code, data } = await wiz.call("run_command", { command_id });
        if (code === 200) return data.result;
        return { status: 'error', stderr: data?.message, error_code: data?.error_code, command_id };
    }

    public diagnosticStatus(item: any) {
        return this.diagnosticResults()[item.id]?.status || 'pending';
    }

    public diagnosticMessage(item: any) {
        const result = this.diagnosticResults()[item.id];
        if (!result) return '아직 실행하지 않음';
        if (result.status === 'ok') return '정상';
        if (result.status === 'missing') return '명령을 찾을 수 없음';
        if (result.status === 'timeout') return '응답 지연';
        return result.error_code || '확인 필요';
    }

    public diagnosticDetail(item: any) {
        const result = this.diagnosticResults()[item.id];
        if (!result) return '';
        const text = result.stdout || result.stderr || '';
        if (!text) return '';
        return text.length > 400 ? `${text.slice(0, 400)}...` : text;
    }

    public statusClass(status: string) {
        if (['ok', 'active', 'succeeded'].includes(status)) {
            return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        }
        if (['running', 'timeout', 'missing'].includes(status)) {
            return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        }
        if (['failed', 'error'].includes(status)) {
            return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
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
