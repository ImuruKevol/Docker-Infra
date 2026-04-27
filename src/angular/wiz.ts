import { io } from "socket.io-client";

export default class Wiz {
    public namespace: any;
    public baseuri: any;

    constructor(baseuri: any) {
        this.baseuri = baseuri;
    }

    public app(namespace: any) {
        let instance = new Wiz(this.baseuri);
        instance.namespace = namespace;
        return instance;
    }

    private cookie(name: string) {
        const cookies: Array<string> = document.cookie.split(';');
        const cookieName = `${name}=`;

        for (let index: number = 0; index < cookies.length; index += 1) {
            const cookie: string = cookies[index].replace(/^\s+/g, '');
            if (cookie.indexOf(cookieName) == 0) {
                return cookie.substring(cookieName.length, cookie.length);
            }
        }
        return '';
    }

    public dev() {
        let isdev = this.cookie("season-wiz-devmode");
        if (isdev == 'true') return true;
        return false;
    }

    public project() {
        let project = this.cookie("season-wiz-project");
        if (project) return project;
        return "main";
    }

    public socket() {
        let socketns = this.baseuri + "/app/" + this.project();
        if (this.namespace)
            socketns = socketns + "/" + this.namespace;
        return io(socketns);
    };

    public url(function_name: string) {
        if (function_name[0] == "/") function_name = function_name.substring(1);
        return this.baseuri + "/api/" + this.namespace + "/" + function_name;
    }

    private async parseResponse(response: Response) {
        try {
            return await response.clone().json();
        } catch (error) {
            const data = await response.text();
            if (response.status !== 200) {
                return { code: response.status, data: data || response.statusText };
            }
            return { code: response.status, data };
        }
    }

    public async call(function_name: string, body: any = {}, options: RequestInit = {}) {
        const uri = this.url(function_name);

        try {
            if (body) {
                const headers = new Headers(options.headers || {});
                const requestOptions: RequestInit = {
                    ...options,
                    method: options.method || "POST"
                };

                if (body instanceof FormData || body instanceof URLSearchParams || body instanceof Blob) {
                    requestOptions.body = body;
                } else {
                    if (!headers.has('Content-Type')) {
                        headers.set('Content-Type', 'application/json');
                    }
                    requestOptions.body = JSON.stringify(body);
                }

                requestOptions.headers = headers;
                const response = await fetch(uri, requestOptions);
                return await this.parseResponse(response);
            }

            const response = await fetch(uri, options);
            return await this.parseResponse(response);
        } catch (error) {
            return { code: 500, data: error };
        }
    }
}
