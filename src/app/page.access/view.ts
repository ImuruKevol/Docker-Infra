import { HostListener, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import { AppearanceRuntime } from '@wiz/libs/portal/season/appearance';

export class Component implements OnInit {
    public loading = signal<boolean>(true);
    public setup = signal<any>(null);
    public appearance: any = {
        browser_title: 'Docker Infra',
        favicon_url: '',
        logo_url: ''
    };
    public data: any = {
        password: ''
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
        if (this.requiresSetup()) {
            await this.alert("설치 관리자에서 초기 설정을 먼저 완료해주세요.");
            return;
        }
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
        } else {
            this.setup.set({ requires_setup: true, database_configured: false });
        }
        this.loading.set(false);
        await this.service.render();
    }

    public requiresSetup() {
        const status = this.setup();
        if (!status) return true;
        return status.requires_setup !== false;
    }

    public setupStatusLabel() {
        const status = this.setup();
        if (!status) return '확인 중';
        if (status.database_configured === false) return '설치 필요';
        return this.requiresSetup() ? '초기 설정 필요' : '접속 가능';
    }

    public setupStatusMessage() {
        const status = this.setup();
        if (!status || status.database_configured === false) {
            return 'Docker Infra installer에서 DB 설치와 서비스 구성을 먼저 완료해야 합니다.';
        }
        return '관리자 비밀번호와 초기 시스템 설정은 Docker Infra installer에서 완료해야 합니다.';
    }

    public installerUrl() {
        const host = location.hostname || '127.0.0.1';
        return `http://${host}:8088`;
    }

    public openInstaller() {
        location.href = this.installerUrl();
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
