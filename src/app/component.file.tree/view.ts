import { EventEmitter, Input, OnChanges, OnInit, Output, SimpleChanges } from '@angular/core';
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
    @Input() selectMode: boolean = false;
    @Input() embedded: boolean = false;
    @Input() maxHeight: string = '520px';
    @Input() selectedPath: string = '';
    @Input() density: string = 'normal';

    @Output() fileSelect = new EventEmitter<any>();

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
    public dropActive = false;
    private contextKey = '';
    private reloadSerial = 0;

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.reload();
    }

    public async ngOnChanges(changes: SimpleChanges) {
        const nextKey = JSON.stringify({ scope: this.scope, context: this.context || {} });
        if (this.contextKey && nextKey !== this.contextKey) {
            this.contextKey = nextKey;
            this.reloadSerial += 1;
            this.path = '';
            this.parent = '';
            this.items = [];
            this.error = '';
            await this.reload('');
            return;
        }
        this.contextKey = nextKey;
    }

    private async render() {
        await this.service.render();
    }

    private usesAbsolutePath() {
        return this.scope === 'node' || this.scope === 'container';
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
        const serial = ++this.reloadSerial;
        const requestKey = JSON.stringify({ scope: this.scope, context: this.context || {} });
        this.busy = true;
        this.error = '';
        await this.render();
        try {
            const data = await this.request('list', { path });
            if (!this.isActiveReload(serial, requestKey)) return;
            this.path = data.path || '';
            this.parent = data.parent || '';
            this.pathInput = this.path;
            this.items = data.items || [];
        } catch (error: any) {
            if (!this.isActiveReload(serial, requestKey)) return;
            this.error = error?.message || '파일 목록을 불러올 수 없습니다.';
        }
        if (!this.isActiveReload(serial, requestKey)) return;
        this.busy = false;
        await this.render();
    }

    private isActiveReload(serial: number, requestKey: string) {
        return serial === this.reloadSerial && requestKey === JSON.stringify({ scope: this.scope, context: this.context || {} });
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
            if (this.selectMode) {
                this.fileSelect.emit({ ...item, path: data.path || item.path, content: data.content || '', scope: this.scope, context: this.context || {} });
                this.busy = false;
                await this.render();
                return;
            }
            this.previewTitle = data.path || item.path;
            this.previewContent = data.content || '';
            this.previewOpen = true;
        } catch (error: any) {
            this.error = error?.message || '파일을 읽을 수 없습니다.';
        }
        this.busy = false;
        await this.render();
    }

    public shellClass() {
        if (this.embedded) return 'h-full bg-transparent';
        return 'rounded-md border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900';
    }

    public isCompact() {
        return this.density === 'compact';
    }

    public headerVisible() {
        return !this.embedded || Boolean(this.title) || Boolean(this.description && !this.isCompact());
    }

    public headerClass() {
        if (this.isCompact()) return 'flex items-center justify-between gap-2 border-b border-zinc-200 px-3 py-2 dark:border-zinc-800';
        return 'flex flex-col gap-3 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800 lg:flex-row lg:items-center lg:justify-between';
    }

    public bodyClass() {
        if (this.embedded && this.isCompact()) return 'space-y-2';
        if (this.embedded) return 'space-y-3 px-3 pb-3';
        return 'space-y-3 px-4 py-3';
    }

    public pathToolbarClass() {
        if (this.isCompact()) return 'flex items-center justify-between gap-2';
        return 'flex flex-col gap-2 lg:flex-row lg:items-center';
    }

    public crumbGroupClass() {
        if (this.isCompact()) return 'flex min-w-0 flex-1 items-center gap-1 overflow-hidden';
        return 'flex min-w-0 flex-wrap items-center gap-2';
    }

    public crumbButtonClass() {
        if (this.isCompact()) return 'inline-flex h-7 max-w-[128px] items-center rounded-md border border-zinc-300 px-2 text-[11px] font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800';
        return 'inline-flex h-8 max-w-[180px] items-center rounded-md border border-zinc-300 px-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800';
    }

    public parentButtonClass() {
        if (this.isCompact()) return 'inline-flex h-7 w-7 items-center justify-center rounded-md border border-zinc-300 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800';
        return 'inline-flex h-8 items-center gap-2 rounded-md border border-zinc-300 px-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800';
    }

    public refreshButtonClass() {
        if (this.isCompact()) return 'inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-zinc-300 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800';
        return 'inline-flex h-8 items-center gap-2 rounded-md border border-zinc-300 px-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800';
    }

    public toolbarClass() {
        if (this.isCompact()) return 'flex shrink-0 items-center gap-1';
        return 'flex flex-wrap items-center gap-2';
    }

    public toolbarButtonClass() {
        if (this.isCompact()) return 'inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-md border border-zinc-300 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800';
        return 'inline-flex h-8 cursor-pointer items-center gap-2 rounded-md border border-zinc-300 px-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800';
    }

    public toolbarToggleClass() {
        const active = this.showHidden
            ? 'border-sky-300 bg-sky-50 text-sky-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-sky-300'
            : 'border-zinc-300 text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800';
        if (this.isCompact()) return `inline-flex h-8 w-8 items-center justify-center rounded-md border text-xs font-semibold disabled:opacity-50 ${active}`;
        return `inline-flex h-8 items-center gap-2 rounded-md border px-2.5 text-xs font-semibold disabled:opacity-50 ${active}`;
    }

    public toolbarLabelClass() {
        return this.isCompact() ? 'sr-only' : '';
    }

    public listClass() {
        const active = this.dropActive ? ' ring-2 ring-sky-300 ring-offset-1 dark:ring-sky-700 dark:ring-offset-zinc-900' : '';
        if (this.isCompact()) return `overflow-auto rounded-md border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950/40${active}`;
        return `overflow-auto rounded-md border border-zinc-200 dark:border-zinc-800${active}`;
    }

    public listStyle() {
        return { maxHeight: this.maxHeight || '520px' };
    }

    public itemRowClass(item: any) {
        const selected = this.selectedPath && item?.path === this.selectedPath;
        if (selected) return 'border-sky-200 bg-sky-50 dark:border-sky-900/70 dark:bg-sky-950/30';
        return 'border-zinc-100 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800/60';
    }

    public itemRowDensityClass() {
        if (this.isCompact()) return 'px-2.5 py-2';
        return 'px-4 py-3';
    }

    public itemButtonClass() {
        if (this.isCompact()) return 'flex min-w-0 flex-1 items-center gap-2 text-left';
        return 'flex min-w-0 flex-1 items-center gap-3 text-left';
    }

    public itemIconClass(item: any) {
        const base = this.isCompact() ? 'text-sm' : 'text-base';
        const tone = item?.type === 'folder' ? 'fa-folder text-amber-500' : 'fa-file-lines text-sky-500';
        return `${base} ${tone}`;
    }

    public async closePreview() {
        this.previewOpen = false;
        this.previewTitle = '';
        this.previewContent = '';
        await this.render();
    }

    public crumbs() {
        const current = this.path || (this.usesAbsolutePath() ? '/' : '.');
        if (!this.usesAbsolutePath()) {
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
        const base = this.path || (this.usesAbsolutePath() ? '' : '.');
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
        event.stopPropagation();
        if (this.hasDroppedFiles(event) && item?.type === 'folder' && !item?.protected) {
            await this.uploadDroppedFiles(event, item.path);
            return;
        }
        if (!this.allowMutate || !this.dragged || item?.type !== 'folder' || item?.protected) return;
        if (this.dragged.path === item.path) return;
        await this.mutate('move', this.dragged.path, { destination: item.path });
        this.dragged = null;
    }

    public allowDrop(event: DragEvent) {
        event.preventDefault();
    }

    public allowTreeDrop(event: DragEvent) {
        if (!this.allowUpload && !this.dragged) return;
        event.preventDefault();
        if (event.dataTransfer) event.dataTransfer.dropEffect = this.hasDroppedFiles(event) ? 'copy' : 'move';
        this.dropActive = this.hasDroppedFiles(event);
    }

    public leaveTreeDrop(event: DragEvent) {
        event.preventDefault();
        this.dropActive = false;
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

    private uploadDestination() {
        return this.path || (this.usesAbsolutePath() ? '' : '.');
    }

    private async uploadEntries(entries: Array<{ file: File, path: string }>, destination: string = this.uploadDestination()) {
        if (!this.allowUpload) return;
        if (!entries.length) return;
        this.busy = true;
        this.error = '';
        await this.render();
        const fd = new FormData();
        fd.append('scope', this.scope);
        fd.append('context', JSON.stringify({ ...(this.context || {}), show_hidden: this.showHidden }));
        fd.append('destination', destination || this.uploadDestination());
        for (const entry of entries) {
            fd.append('files', entry.file, entry.path || entry.file.name);
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
        this.dropActive = false;
        this.busy = false;
        await this.render();
    }

    public async uploadFiles(event: Event) {
        if (!this.allowUpload) return;
        const input = event.target as HTMLInputElement;
        const files = Array.from(input.files || []);
        if (!files.length) return;
        const entries = files.map((file) => ({ file, path: (file as any).webkitRelativePath || file.name }));
        await this.uploadEntries(entries);
        input.value = '';
    }

    public async uploadDroppedFiles(event: DragEvent, destination: string = this.uploadDestination()) {
        event.preventDefault();
        event.stopPropagation();
        if (!this.allowUpload || !this.hasDroppedFiles(event)) {
            this.dropActive = false;
            return;
        }
        const entries = await this.collectDroppedFiles(event);
        await this.uploadEntries(entries, destination);
    }

    private hasDroppedFiles(event: DragEvent) {
        const transfer = event.dataTransfer;
        if (!transfer) return false;
        if (transfer.files && transfer.files.length > 0) return true;
        return Array.from(transfer.items || []).some((item: any) => item.kind === 'file');
    }

    private async collectDroppedFiles(event: DragEvent): Promise<Array<{ file: File, path: string }>> {
        const transfer = event.dataTransfer;
        if (!transfer) return [];
        const itemEntries = Array.from(transfer.items || [])
            .map((item: any) => typeof item.webkitGetAsEntry === 'function' ? item.webkitGetAsEntry() : null)
            .filter(Boolean);
        if (itemEntries.length) {
            const groups = await Promise.all(itemEntries.map((entry: any) => this.collectEntryFiles(entry, '')));
            return ([] as Array<{ file: File, path: string }>).concat(...groups);
        }
        return Array.from(transfer.files || []).map((file) => ({ file, path: (file as any).webkitRelativePath || file.name }));
    }

    private async collectEntryFiles(entry: any, prefix: string): Promise<Array<{ file: File, path: string }>> {
        if (entry?.isFile) {
            return new Promise((resolve) => {
                entry.file(
                    (file: File) => resolve([{ file, path: `${prefix}${file.name}` }]),
                    () => resolve([])
                );
            });
        }
        if (!entry?.isDirectory) return [];
        const reader = entry.createReader();
        const children: any[] = [];
        while (true) {
            const batch = await new Promise<any[]>((resolve) => {
                reader.readEntries((entries: any[]) => resolve(entries || []), () => resolve([]));
            });
            if (!batch.length) break;
            children.push(...batch);
        }
        const nextPrefix = `${prefix}${entry.name}/`;
        const groups = await Promise.all(children.map((child) => this.collectEntryFiles(child, nextPrefix)));
        return ([] as Array<{ file: File, path: string }>).concat(...groups);
    }

    public async downloadItem(item: any, event?: Event) {
        event?.preventDefault();
        event?.stopPropagation();
        if (!this.allowRead || item?.type !== 'file') return;
        this.busy = true;
        this.error = '';
        await this.render();
        try {
            const data = await this.request('download', { path: item.path });
            const blob = this.blobFromBase64(data.content_base64 || '');
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = data.name || item.name || this.downloadName(data.path || item.path);
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
        } catch (error: any) {
            this.error = error?.message || '다운로드할 수 없습니다.';
        }
        this.busy = false;
        await this.render();
    }

    private downloadName(path: string) {
        const parts = String(path || '').split('/').filter(Boolean);
        return parts[parts.length - 1] || 'download';
    }

    private blobFromBase64(value: string) {
        const binary = atob(value || '');
        const chunks: Uint8Array[] = [];
        for (let index = 0; index < binary.length; index += 8192) {
            const slice = binary.slice(index, index + 8192);
            const bytes = new Uint8Array(slice.length);
            for (let offset = 0; offset < slice.length; offset += 1) {
                bytes[offset] = slice.charCodeAt(offset);
            }
            chunks.push(bytes);
        }
        return new Blob(chunks, { type: 'application/octet-stream' });
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
