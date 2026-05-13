import { OnInit } from '@angular/core';
import { HostListener } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import { AppearanceRuntime } from '@wiz/libs/portal/season/appearance';

export class Component implements OnInit {
    public allMenuItems = [
        { link: '/dashboard', label: 'nav.dashboard', icon: 'fa-gauge-high' },
        { link: '/servers', label: 'nav.servers', icon: 'fa-server' },
        { link: '/services', label: 'nav.services', icon: 'fa-layer-group' },
        { link: '/macros', label: 'nav.macros', icon: 'fa-bolt' },
        { link: '/domains', label: 'nav.domains', icon: 'fa-globe' },
        { link: '/operations', label: '작업 로그', icon: 'fa-clock-rotate-left' },
        { link: '/images', label: 'nav.images', icon: 'fa-cubes' },
        { link: '/system', label: 'nav.system', icon: 'fa-gear' },
        { link: '/tools', label: 'nav.tools', icon: 'fa-toolbox' },
    ];
    public menuItems = this.allMenuItems;
    public appearance: any = {
        browser_title: 'Docker Infra',
        favicon_url: '',
        logo_url: ''
    };

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        this.refreshAppearance();
        await this.loadMenuState();
        await this.service.render();
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
        if (active) return 'bg-white text-gray-900 shadow-sm dark:bg-zinc-700 dark:text-white';
        return 'text-gray-500 hover:text-gray-900 dark:text-zinc-400 dark:hover:text-white';
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
            return "group flex gap-x-2 items-center rounded-md bg-zinc-100 px-2.5 py-2 text-[13px] font-semibold text-zinc-950 dark:bg-zinc-800 dark:text-zinc-50";
        }
        return "group flex gap-x-2 items-center rounded-md px-2.5 py-2 text-[13px] font-medium text-zinc-600 hover:bg-zinc-50 hover:text-zinc-950 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-50";
    }

    public logoTitle() {
        return this.appearance?.browser_title || 'Docker Infra';
    }

    public hasLogo() {
        return !!this.appearance?.logo_url;
    }

    public async loadMenuState() {
        this.menuItems = this.allMenuItems;
    }

    @HostListener('window:docker-infra:appearance-changed', ['$event'])
    public handleAppearanceChanged(event: any) {
        this.appearance = event?.detail || AppearanceRuntime.read();
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
