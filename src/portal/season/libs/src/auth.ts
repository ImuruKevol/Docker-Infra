import Service from '../service';
import Request from '../util/request';
import { AppearanceRuntime } from '../appearance';

export default class Auth {
    public verified: string | null = null;
    public appearance: any = {
        browser_title: 'Docker Infra',
        favicon_url: '',
        logo_url: ''
    };

    public timestamp: number = 0;
    public status: any = null;
    public loading: any = null;
    public session: any = {};

    constructor(public service: Service) {
        this.request = new Request();
    }

    public async init() {
        this.appearance = AppearanceRuntime.read();
        AppearanceRuntime.apply(this.appearance);
        try {
            let { code, data } = await this.request.post('/auth/check');
            this.loading = true;
            if (code != 200)
                return this;
            let status = data?.status;
            let session = data?.session || {};
            this.verified = session?.verified || null;
            this.timestamp = new Date().getTime();
            this.session = session;
            this.status = status;
            this.appearance = AppearanceRuntime.read();
        } catch (e) {
            this.loading = true;
            this.appearance = AppearanceRuntime.read();
        }
        return this;
    }

    public async update() {
        while (this.loading === null) {
            await this.service.render(100);
        }

        let diff = new Date().getTime() - this.timestamp;
        if (diff > 1000 * 60) {
            this.loading = null;
            await this.init();
        }
    }

    public check: any = new Proxy(((root) => {
        let obj: any = () => {
            return this.status;
        }

        obj.root = root;
        return obj;
    })(this), {
        get(target, propKey) {
            let propValue: any = target.root.session[propKey];

            return (values: any = null) => {
                if (values === null) {
                    return true;
                }

                if (typeof values == 'boolean') {
                    if (values === propValue)
                        return true;
                    return false;
                }

                if (typeof values == 'string')
                    values = [values];

                if (values.indexOf(propValue) >= 0) {
                    return true;
                }

                return false;
            };
        }
    });

    public allow: any = new Proxy(((root) => {
        let obj: any = (redirect: any = null) => {
            if (root.check()) return true;
            if (redirect) location.href = redirect;
            return false;
        }

        obj.root = root;
        obj.check = root.check;
        return obj;
    })(this), {
        get(target, propKey) {
            return (values: any = null, redirect: any = null) => {
                if (target.check[propKey](values)) return true;
                if (redirect) location.href = redirect;
                return false;
            }
        }
    });

    public hash(password: string = '') {
        return this.service.crypto.SHA256(password).toString();
    }
}
