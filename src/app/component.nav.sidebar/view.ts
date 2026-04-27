import { OnInit } from '@angular/core';
import { HostListener } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        this.service.render();
    }

    @HostListener('document:click')
    public clickout() {
        this.service.status.toggle('navbar', true);
    }

    public isActive(link: string) {
        return location.pathname.indexOf(link) === 0
    }

    public currentLanguage() {
        if (!this.service.lang) return 'en';
        return this.service.lang.get() || 'en';
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
            return "group flex gap-x-2 items-center rounded-md bg-gray-100 px-2 py-1.5 text-[13px] font-medium text-indigo-600 dark:bg-zinc-800 dark:text-indigo-300";
        }
        return "group flex gap-x-2 items-center rounded-md px-2 py-1.5 text-[13px] font-medium text-gray-600 hover:bg-gray-50 hover:text-indigo-600 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-indigo-300";
    }
}