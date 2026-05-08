import { HostListener, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import { AppearanceRuntime } from '@wiz/libs/portal/season/appearance';

export class Component implements OnInit {
    public loading = signal<boolean>(true);
    public setup = signal<any>(null);
    public advancedSetup = signal<boolean>(false);
    public appearance: any = {
        browser_title: 'Docker Infra',
        favicon_url: '',
        logo_url: ''
    };
    public data: any = {
        password: '',
        setup: {
            password: '',
            confirm_password: '',
            advertise_address: '',
            proxy_type: 'nginx',
            template_root: '.runtime/dev/templates',
            backup_system: {
                enabled: false,
                data_path: ''
            }
        }
    };

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        this.refreshAppearance();
        if (await this.redirectAuthenticated()) return;
        await this.loadSetupStatus();
    }

    private async redirectAuthenticated() {
        const { code, data } = await wiz.call("session", {});
        if (code === 200 && data.authenticated === true) {
            location.href = "/dashboard";
            return true;
        }
        return false;
    }

    public async alert(message: string, status: string = 'error') {
        return await this.service.modal.show({
            title: "",
            message: message,
            cancel: false,
            actionBtn: status,
            action: '확인',
            status: status
        });
    }

    public async login() {
        if (!this.data.password) {
            await this.alert("비밀번호를 입력해주세요.");
            return;
        }

        const { code, data } = await wiz.call("login", { password: this.data.password });
        if (code === 200) {
            location.href = "/dashboard";
            return;
        }
        await this.alert(data.message || "접속할 수 없습니다.", 'error');
    }

    public async loadSetupStatus() {
        this.loading.set(true);
        const { code, data } = await wiz.call("setup_status", {});
        if (code === 200) {
            this.setup.set(data.setup);
            const checks = data.setup?.checks || {};
            this.data.setup.advertise_address = data.setup?.settings?.advertise_address || checks.advertise_address || '';
            this.data.setup.template_root = data.setup?.settings?.template_root || '.runtime/dev/templates';
            this.data.setup.proxy_type = 'nginx';
            const backup = data.setup?.backup_system || {};
            this.data.setup.backup_system.enabled = backup.enabled === true;
            this.data.setup.backup_system.data_path = backup.data_path || '';
        }
        this.loading.set(false);
        await this.service.render();
    }

    public requiresSetup() {
        const status = this.setup();
        if (!status) return true;
        return status.requires_setup !== false;
    }

    public setupChecks() {
        const checks = this.setup()?.checks || {};
        const docker = checks.docker || {};
        const swarm = docker.swarm || {};
        const proxy = checks.proxy || {};
        return [
            { label: 'Docker', value: docker.daemon || 'unknown', ok: docker.daemon === 'ok' },
            { label: 'Swarm', value: swarm.manager ? 'manager' : (swarm.state || 'unknown'), ok: !!swarm.manager },
            { label: 'nginx', value: proxy.nginx?.status || 'unknown', ok: proxy.nginx?.status === 'ok' },
        ];
    }

    public backupStatus() {
        return this.setup()?.backup_system || {};
    }

    public backupPorts() {
        return this.backupStatus()?.required_ports || [];
    }

    public backupStorageText() {
        const storage = this.backupStatus()?.storage || {};
        return `${this.formatBytes(storage.available_bytes)} 남음 / 전체 ${this.formatBytes(storage.total_bytes)}`;
    }

    public backupStatusLabel() {
        const enabled = this.data.setup.backup_system.enabled;
        const status = this.backupStatus()?.status || 'disabled';
        if (!enabled) return '사용 안 함';
        if (status === 'running') return '실행 중';
        if (status === 'failed') return '설치 실패';
        return '설치 준비';
    }

    public formatBytes(value: any) {
        const bytes = Number(value || 0);
        if (bytes <= 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
        const amount = bytes / Math.pow(1024, index);
        return `${amount.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
    }

    public toggleAdvancedSetup() {
        this.advancedSetup.set(!this.advancedSetup());
    }

    public async completeSetup() {
        if (!this.data.setup.password) {
            await this.alert("관리자 비밀번호를 입력해주세요.");
            return;
        }
        if (this.data.setup.password !== this.data.setup.confirm_password) {
            await this.alert("비밀번호 확인이 일치하지 않습니다.");
            return;
        }

        const { code, data } = await wiz.call("setup", this.data.setup);
        if (code === 200) {
            if (data?.backup_error) {
                await this.alert(`서비스 백업 시스템은 나중에 시스템 설정에서 다시 시작할 수 있습니다.\n${data.backup_error.message || ''}`, 'warning');
            }
            location.href = "/dashboard";
            return;
        }
        await this.alert(data.message || "설치를 완료할 수 없습니다.", 'error');
    }

    public hasLogo() {
        return !!this.appearance?.logo_url;
    }

    public title() {
        return this.appearance?.browser_title || 'Docker Infra';
    }

    @HostListener('window:docker-infra:appearance-changed', ['$event'])
    public handleAppearanceChanged(event: any) {
        this.appearance = event?.detail || AppearanceRuntime.read();
    }

    private refreshAppearance() {
        this.appearance = AppearanceRuntime.read();
    }
}
