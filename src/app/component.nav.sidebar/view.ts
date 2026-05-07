import { OnInit } from '@angular/core';
import { HostListener } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

const DEFAULT_INTEGRATION_STATE = {
    harbor: true,
    gitlab: true,
    cloudflare: true
};

let sidebarSettingsCache: any = null;
let sidebarSettingsPromise: Promise<any> | null = null;

export class Component implements OnInit {
    public allMenuItems = [
        { link: '/dashboard', label: 'nav.dashboard', icon: 'fa-gauge-high' },
        { link: '/servers', label: 'nav.servers', icon: 'fa-server' },
        { link: '/services', label: 'nav.services', icon: 'fa-layer-group' },
        { link: '/macros', label: 'nav.macros', icon: 'fa-bolt' },
        { link: '/domains', label: 'nav.domains', icon: 'fa-globe' },
        { link: '/images', label: 'nav.images', icon: 'fa-cubes' },
        { link: '/templates', label: 'nav.templates', icon: 'fa-file-code' },
        { link: '/system', label: 'nav.system', icon: 'fa-gear' },
        { link: '/tools', label: 'nav.tools', icon: 'fa-toolbox' },
    ];
    public menuItems = this.allMenuItems;
    public integrationEnabled: any = { ...DEFAULT_INTEGRATION_STATE };

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
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

    public settingValue(settings: any[], key: string, fallback: any) {
        const found = settings.find((item: any) => item.key === key);
        if (!found) return fallback;
        return found.value;
    }

    private normalizeIntegrationState(settings: any[]) {
        return {
            harbor: this.settingValue(settings, 'integration.harbor.enabled', false) === true,
            gitlab: this.settingValue(settings, 'integration.gitlab.enabled', false) === true,
            cloudflare: this.settingValue(settings, 'integration.cloudflare.enabled', false) === true
        };
    }

    private async fetchSidebarSettings() {
        if (sidebarSettingsCache) return sidebarSettingsCache;
        if (!sidebarSettingsPromise) {
            sidebarSettingsPromise = (async () => {
                try {
                    const response = await fetch('/api/system/settings');
                    if (!response.ok) return { ...DEFAULT_INTEGRATION_STATE };
                    const payload = await response.json();
                    const settings = payload?.data?.settings || [];
                    return this.normalizeIntegrationState(settings);
                } catch (error) {
                    return { ...DEFAULT_INTEGRATION_STATE };
                }
            })();
        }
        sidebarSettingsCache = await sidebarSettingsPromise;
        return sidebarSettingsCache;
    }

    public async loadMenuState() {
        this.integrationEnabled = await this.fetchSidebarSettings();
        this.menuItems = this.allMenuItems;
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
