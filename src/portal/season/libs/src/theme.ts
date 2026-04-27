import Service from '../service';

export default class Theme {
    public dark: boolean = false;

    constructor(public service: Service) {
        this.dark = this.load();
        this.apply();
    }

    public async set(dark: boolean) {
        this.dark = dark;
        this.save();
        this.apply();
        if (this.service.event) await this.service.event.call('theme.change');
        await this.service.render();
    }

    public async toggle() {
        await this.set(!this.dark);
    }

    public isDark() {
        return this.dark;
    }

    private load() {
        if (typeof window === 'undefined') return false;
        const saved = window.localStorage.getItem('season-theme');
        if (saved === 'dark') return true;
        if (saved === 'light') return false;
        return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    }

    private save() {
        if (typeof window === 'undefined') return;
        window.localStorage.setItem('season-theme', this.dark ? 'dark' : 'light');
    }

    private apply() {
        if (typeof document === 'undefined') return;
        document.documentElement.classList.toggle('dark', this.dark);
        document.body.classList.toggle('dark', this.dark);
    }
}