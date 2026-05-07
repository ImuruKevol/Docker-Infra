import { OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    public loading = signal<boolean>(true);
    public setup = signal<any>(null);
    public advancedSetup = signal<boolean>(false);
    public data: any = {
        password: '',
        setup: {
            password: '',
            confirm_password: '',
            advertise_address: '',
            proxy_type: 'auto',
            template_root: '.runtime/dev/templates'
        }
    };

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
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
            this.data.setup.proxy_type = data.setup?.settings?.default_proxy || 'auto';
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
            { label: 'apache2', value: proxy.apache2?.status || 'unknown', ok: proxy.apache2?.status === 'ok' },
        ];
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
            location.href = "/dashboard";
            return;
        }
        await this.alert(data.message || "설치를 완료할 수 없습니다.", 'error');
    }
}
