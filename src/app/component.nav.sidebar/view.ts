import { HostListener, OnDestroy, OnInit } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import { AppearanceRuntime } from '@wiz/libs/portal/season/appearance';

type NavMenuItem = { link: string; label: string; icon: string };
type NavMenuGroup = { label: string; items: NavMenuItem[] };

export class Component implements OnInit, OnDestroy {
    public allMenuGroups: NavMenuGroup[] = [
        {
            label: 'nav.primaryMenu',
            items: [
                { link: '/dashboard', label: 'nav.dashboard', icon: 'fa-gauge-high' },
                { link: '/services', label: 'nav.services', icon: 'fa-layer-group' },
                { link: '/domains', label: 'nav.domains', icon: 'fa-globe' },
            ]
        },
        {
            label: 'nav.advancedMenu',
            items: [
                { link: '/servers', label: 'nav.servers', icon: 'fa-server' },
                { link: '/images', label: 'nav.images', icon: 'fa-cubes' },
                { link: '/templates', label: 'nav.templates', icon: 'fa-layer-group' },
                { link: '/macros', label: 'nav.macros', icon: 'fa-bolt' },
                { link: '/operations', label: 'nav.operations', icon: 'fa-clock-rotate-left' },
                { link: '/system', label: 'nav.system', icon: 'fa-gear' },
            ]
        }
    ];
    public menuGroups = this.allMenuGroups;
    public appearance: any = {
        browser_title: 'Docker Infra',
        favicon_url: '',
        logo_url: ''
    };
    public session: any = null;
    public sessionPolicy: any = null;
    public sessionLoadedAt: number = 0;
    public sessionNow: number = Date.now();
    public sessionExtending: boolean = false;
    private sessionTimer: any = null;

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        this.refreshAppearance();
        await this.loadMenuState();
        await this.loadSessionState();
        this.startSessionTimer();
        await this.service.render();
    }

    public ngOnDestroy() {
        this.stopSessionTimer();
    }

    // @HostListener('document:click')
    // public clickout() {
    //     this.service.status.toggle('navbar', true);
    // }

    public isActive(link: string) {
        return location.pathname.indexOf(link) === 0;
    }

    public currentLanguage() {
        if (!this.service.lang) return 'ko';
        return this.service.lang.get() || 'ko';
    }

    public languageButtonClass(lang: string) {
        const active = this.currentLanguage() === lang;
        if (active) return 'bg-zinc-950 text-white shadow-sm dark:bg-zinc-100 dark:text-zinc-950';
        return 'text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white';
    }

    public async setLanguage(lang: string) {
        if (this.service.lang) await this.service.lang.set(lang);
        await this.service.render();
    }

    public isDarkMode() {
        return this.service.theme && this.service.theme.isDark();
    }

    public async toggleTheme() {
        if (this.service.theme) await this.service.theme.toggle();
    }

    public activeClass(link: string) {
        if (this.isActive(link)) {
            return "group flex gap-x-3 items-center rounded-lg bg-zinc-950 px-3 py-2.5 text-sm font-semibold text-white shadow-sm transition dark:bg-zinc-100 dark:text-zinc-950";
        }
        return "group flex gap-x-3 items-center rounded-lg px-3 py-2.5 text-sm font-semibold text-zinc-600 transition hover:bg-white hover:text-zinc-950 hover:shadow-sm dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-zinc-50";
    }

    public logoTitle() {
        return this.appearance?.browser_title || 'Docker Infra';
    }

    public hasLogo() {
        return !!this.appearance?.logo_url;
    }

    public async loadMenuState() {
        this.menuGroups = this.allMenuGroups;
    }

    public async loadSessionState() {
        try {
            const response = await fetch('/api/auth/session', {
                method: 'GET',
                headers: { 'content-type': 'application/json' }
            });
            const payload = await response.json();
            if (payload?.code === 200) {
                this.applySessionPayload(payload?.data || {});
            }
        } catch (error) {
            this.session = null;
            this.sessionPolicy = null;
        }
    }

    public sessionRemainingSeconds() {
        const baseSeconds = Number(this.session?.remaining_seconds);
        if (!Number.isFinite(baseSeconds) || baseSeconds <= 0 || !this.sessionLoadedAt) return 0;
        const elapsedSeconds = Math.floor((this.sessionNow - this.sessionLoadedAt) / 1000);
        return Math.max(0, baseSeconds - elapsedSeconds);
    }

    public sessionRemainingLabel() {
        const seconds = this.sessionRemainingSeconds();
        if (seconds <= 0) return '';
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        if (days > 0) return hours > 0 ? `${days}일 ${hours}시간 남음` : `${days}일 남음`;
        if (hours > 0) return minutes > 0 ? `${hours}시간 ${minutes}분 남음` : `${hours}시간 남음`;
        if (minutes > 0) return `${minutes}분 남음`;
        return '1분 미만 남음';
    }

    public async extendSession() {
        if (this.sessionExtending || !this.session) return;
        this.sessionExtending = true;
        await this.service.render();
        try {
            const response = await fetch('/api/auth/session', {
                method: 'POST',
                headers: { 'content-type': 'application/json' },
                body: '{}'
            });
            const payload = await response.json();
            if (payload?.code === 200 && payload?.data?.session) {
                this.applySessionPayload(payload.data);
            } else {
                await this.loadSessionState();
            }
        } catch (error) {
            await this.loadSessionState();
        }
        this.sessionExtending = false;
        await this.service.render();
    }

    private startSessionTimer() {
        this.stopSessionTimer();
        this.sessionTimer = window.setInterval(async () => {
            this.sessionNow = Date.now();
            if (this.session && this.sessionRemainingSeconds() <= 0) await this.loadSessionState();
            await this.service.render();
        }, 30000);
    }

    private stopSessionTimer() {
        if (!this.sessionTimer) return;
        window.clearInterval(this.sessionTimer);
        this.sessionTimer = null;
    }

    @HostListener('window:docker-infra:appearance-changed', ['$event'])
    public handleAppearanceChanged(event: any) {
        this.appearance = event?.detail || AppearanceRuntime.read();
    }

    @HostListener('window:docker-infra:session-updated', ['$event'])
    public handleSessionUpdated(event: any) {
        const detail = event?.detail || {};
        this.applySessionPayload(detail);
        void this.service.render();
    }

    private applySessionPayload(payload: any) {
        if ('session' in payload) this.session = payload.session || null;
        if (payload?.session_policy) this.sessionPolicy = payload.session_policy;
        this.sessionLoadedAt = Date.now();
        this.sessionNow = this.sessionLoadedAt;
    }

    private refreshAppearance() {
        this.appearance = AppearanceRuntime.read();
    }

    public async logout() {
        await fetch('/api/auth/logout', {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: '{}'
        }).catch(() => undefined);
        location.href = "/access";
    }
}
