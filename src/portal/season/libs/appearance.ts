export const DEFAULT_APPEARANCE = {
    browser_title: 'Docker Infra',
    favicon_url: '/api/system/assets/favicon',
    logo_url: ''
};

export const APPEARANCE_STORAGE_KEY = 'docker-infra-appearance';
export const APPEARANCE_EVENT_NAME = 'docker-infra:appearance-changed';
export const APPEARANCE_ROUTE = '/api/system/appearance';
export const APPEARANCE_ASSET_ROUTES: any = {
    favicon: '/api/system/assets/favicon',
    logo: '/api/system/assets/logo'
};

export class AppearanceRuntime {
    private static loadingPromise: Promise<any> | null = null;

    public static normalize(appearance: any = null) {
        return {
            browser_title: appearance?.browser_title || DEFAULT_APPEARANCE.browser_title,
            favicon_url: appearance?.favicon_url || DEFAULT_APPEARANCE.favicon_url,
            logo_url: appearance?.logo_url || DEFAULT_APPEARANCE.logo_url
        };
    }

    public static read() {
        try {
            const runtime = (window as any).__dockerInfraAppearance;
            if (runtime) return this.normalize(runtime);
            const raw = localStorage.getItem(APPEARANCE_STORAGE_KEY);
            if (!raw) return this.normalize();
            return this.normalize(JSON.parse(raw));
        } catch (error) {
            return this.normalize();
        }
    }

    public static apply(appearance: any) {
        const normalized = this.normalize(appearance);
        try {
            localStorage.setItem(APPEARANCE_STORAGE_KEY, JSON.stringify(normalized));
        } catch (error) { }
        document.title = normalized.browser_title || DEFAULT_APPEARANCE.browser_title;
        this.updateFavicon(normalized.favicon_url || '');
        (window as any).__dockerInfraAppearance = normalized;
        window.dispatchEvent(new CustomEvent(APPEARANCE_EVENT_NAME, { detail: normalized }));
        return normalized;
    }

    public static async load(force: boolean = false) {
        if (this.loadingPromise && force !== true) {
            return await this.loadingPromise;
        }
        this.apply(this.read());
        this.loadingPromise = this.fetchRemote().finally(() => {
            this.loadingPromise = null;
        });
        return await this.loadingPromise;
    }

    private static updateFavicon(url: string = '') {
        const faviconUrl = this.withCacheBust(url || '/assets/brand/icon.ico');
        const specs = [
            { rel: 'shortcut icon' },
            { rel: 'icon' },
            { rel: 'apple-touch-icon' }
        ];
        specs.forEach((spec) => {
            let node = document.querySelector(`link[rel="${spec.rel}"]`) as HTMLLinkElement | null;
            if (!node) {
                node = document.createElement('link');
                node.rel = spec.rel;
                document.head.appendChild(node);
            }
            node.href = faviconUrl;
            node.removeAttribute('type');
        });
    }

    public static assetRoute(kind: string) {
        return APPEARANCE_ASSET_ROUTES[kind] || '';
    }

    private static withCacheBust(url: string = '') {
        if (!url) return url;
        return `${url}${url.includes('?') ? '&' : '?'}v=${Date.now()}`;
    }

    private static async fetchRemote() {
        try {
            const response = await fetch(APPEARANCE_ROUTE, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            });
            const payload = await this.parseResponse(response);
            const appearance = payload?.data?.appearance || payload?.appearance || null;
            if (!response.ok || appearance === null) {
                return this.read();
            }
            return this.apply(appearance);
        } catch (error) {
            return this.read();
        }
    }

    private static async parseResponse(response: Response) {
        try {
            return await response.clone().json();
        } catch (error) {
            const text = await response.text();
            return { code: response.status, data: text || response.statusText };
        }
    }
}

export default AppearanceRuntime;
