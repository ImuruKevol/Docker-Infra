export default class Request {
    constructor() { }

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

    public async post(url: string, data: any = {}, options: RequestInit = {}) {
        try {
            const headers = new Headers(options.headers || {});
            const requestOptions: RequestInit = {
                ...options,
                method: options.method || "POST"
            };

            if (data instanceof FormData || data instanceof URLSearchParams || data instanceof Blob) {
                requestOptions.body = data;
            } else {
                if (!headers.has('Content-Type')) {
                    headers.set('Content-Type', 'application/json');
                }
                requestOptions.body = JSON.stringify(data || {});
            }

            requestOptions.headers = headers;
            const response = await fetch(url, requestOptions);
            return await this.parseResponse(response);
        } catch (error) {
            return { code: 500, data: error };
        }
    }

}
