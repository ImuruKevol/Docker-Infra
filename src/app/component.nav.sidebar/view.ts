import { OnInit } from '@angular/core';
import { HostListener } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import { AppearanceRuntime } from '@wiz/libs/portal/season/appearance';

type NavMenuItem = { link: string; label: string; icon: string };
type NavMenuGroup = { label: string; items: NavMenuItem[] };

export class Component implements OnInit {
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
