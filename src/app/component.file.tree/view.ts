import { Input, OnChanges, OnInit, SimpleChanges } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit, OnChanges {
    @Input() title: string = '파일';
    @Input() description: string = '';
    @Input() scope: string = '';
    @Input() context: any = {};
    @Input() rootLabel: string = 'root';
    @Input() allowUpload: boolean = true;
    @Input() allowMutate: boolean = true;
    @Input() allowRead: boolean = true;

    public busy = false;
    public path = '';
    public parent = '';
    public pathInput = '';
    public showHidden = false;
    public items: any[] = [];
    public error = '';
    public previewOpen = false;
    public previewTitle = '';
    public previewContent = '';
    public dragged: any = null;
    private contextKey = '';

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.reload();
    }

    public async ngOnChanges(changes: SimpleChanges) {
        const nextKey = JSON.stringify({ scope: this.scope, context: this.context || {} });
        if (this.contextKey && nextKey !== this.contextKey) {
            this.path = '';
            await this.reload();
        }
        this.contextKey = nextKey;
    }

    private async render() {
        await this.service.render();
    }

    private async request(action: string, payload: any = {}) {
        const requestContext = { ...(this.context || {}), show_hidden: this.showHidden };
        const response = await fetch('/api/file-tree', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action,
                scope: this.scope,
                context: requestContext,
                ...payload,
            }),
        });
        const json = await response.json();
        const code = json?.code || response.status;
        const data = json?.data || json;
        if (code !== 200) throw new Error(data?.message || '파일 작업을 처리할 수 없습니다.');
        return data;
    }

    public async reload(path: string = this.path || '') {
        if (!this.scope) return;
        this.busy = true;
        this.error = '';
        await this.render();
        try {
            const data = await this.request('list', { path });
            this.path = data.path || '';
            this.parent = data.parent || '';
            this.pathInput = this.path;
            this.items = data.items || [];
        } catch (error: any) {
            this.error = error?.message || '파일 목록을 불러올 수 없습니다.';
        }
        this.busy = false;
        await this.render();
    }

    public async openItem(item: any) {
        if (item?.type === 'folder') {
            await this.reload(item.path);
            return;
        }
        if (!this.allowRead) return;
        this.busy = true;
        this.error = '';
        await this.render();
        try {
            const data = await this.request('read', { path: item.path });
            this.previewTitle = data.path || item.path;
            this.previewContent = data.content || '';
            this.previewOpen = true;
        } catch (error: any) {
            this.error = error?.message || '파일을 읽을 수 없습니다.';
        }
        this.busy = false;
        await this.render();
    }

    public async closePreview() {
        this.previewOpen = false;
        this.previewTitle = '';
        this.previewContent = '';
        await this.render();
    }

    public crumbs() {
        const current = this.path || (this.scope === 'node' ? '/' : '.');
        if (this.scope !== 'node') {
            if (current === '.') return [{ label: this.rootLabel || 'root', path: '.' }];
            const parts = current.split('/').filter(Boolean);
            let path = '';
            const result = [{ label: this.rootLabel || 'root', path: '.' }];
            for (const part of parts) {
                path = path ? `${path}/${part}` : part;
                result.push({ label: part, path });
            }
            return result;
        }
        const parts = current.split('/').filter(Boolean);
        let path = '';
        const result = [{ label: '/', path: '/' }];
        for (const part of parts) {
            path += `/${part}`;
            result.push({ label: part, path });
        }
        return result;
    }

    public async goParent() {
        if (!this.parent) return;
        await this.reload(this.parent);
    }

    public async jumpToPath(event?: Event) {
        event?.preventDefault();
        await this.reload(this.pathInput || '');
    }

    public async toggleHidden() {
        this.showHidden = !this.showHidden;
        await this.reload(this.path || '');
    }

    public itemMutatable(item: any) {
        return Boolean(this.allowMutate && !item?.protected);
    }

    public async createFolder() {
        if (!this.allowMutate) return;
        const name = window.prompt('새 폴더 이름');
        if (!name) return;
        const base = this.path || (this.scope === 'node' ? '' : '.');
        const path = !base || base === '.' ? name : `${base.replace(/\/$/, '')}/${name}`;
        await this.mutate('mkdir', path);
    }

    public async renameItem(item: any) {
        if (!this.itemMutatable(item)) return;
        const name = window.prompt('새 이름', item?.name || '');
        if (!name || name === item?.name) return;
        await this.mutate('rename', item.path, { new_name: name });
    }

    public async deleteItem(item: any) {
        if (!this.itemMutatable(item)) return;
        if (!window.confirm(`${item?.name || item?.path} 항목을 삭제합니다.`)) return;
        await this.mutate('delete', item.path);
    }

    public dragStart(item: any) {
        if (!this.itemMutatable(item)) return;
        this.dragged = item;
    }

    public async dropOn(item: any, event: DragEvent) {
        event.preventDefault();
        if (!this.allowMutate || !this.dragged || item?.type !== 'folder' || item?.protected) return;
        if (this.dragged.path === item.path) return;
        await this.mutate('move', this.dragged.path, { destination: item.path });
        this.dragged = null;
    }

    public allowDrop(event: DragEvent) {
        event.preventDefault();
    }

    private async mutate(action: string, path: string, extra: any = {}) {
        this.busy = true;
        this.error = '';
        await this.render();
        try {
            await this.request(action, { path, ...extra });
            await this.reload(this.path);
        } catch (error: any) {
            this.error = error?.message || '파일 작업을 처리할 수 없습니다.';
        }
        this.busy = false;
        await this.render();
    }

    public async uploadFiles(event: Event) {
        if (!this.allowUpload) return;
        const input = event.target as HTMLInputElement;
        const files = Array.from(input.files || []);
        if (!files.length) return;
        this.busy = true;
        this.error = '';
        await this.render();
        const fd = new FormData();
        fd.append('scope', this.scope);
        fd.append('context', JSON.stringify({ ...(this.context || {}), show_hidden: this.showHidden }));
        fd.append('destination', this.path || (this.scope === 'node' ? '' : '.'));
        for (const file of files) {
            const rel = (file as any).webkitRelativePath || file.name;
            fd.append('files', file, rel);
        }
        try {
            const response = await fetch('/api/file-tree/upload', { method: 'POST', body: fd });
            const json = await response.json();
            const code = json?.code || response.status;
            const data = json?.data || json;
            if (code !== 200) throw new Error(data?.message || '업로드할 수 없습니다.');
            await this.reload(this.path);
        } catch (error: any) {
            this.error = error?.message || '업로드할 수 없습니다.';
        }
        input.value = '';
        this.busy = false;
        await this.render();
    }

    public formatBytes(value: any) {
        const size = Number(value || 0);
        if (!size) return '-';
        const units = ['B', 'KB', 'MB', 'GB'];
        let next = size;
        let index = 0;
        while (next >= 1024 && index < units.length - 1) {
            next /= 1024;
            index += 1;
        }
        return `${next.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
    }
}
