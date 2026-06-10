import { HostListener, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    public authReady = signal<boolean>(false);
    private activeRouteComponent: any = null;

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.enforceSession();
    }

    public setActiveRouteComponent(component: any) {
        this.activeRouteComponent = component;
    }

    public clearActiveRouteComponent(component: any) {
        if (this.activeRouteComponent === component) this.activeRouteComponent = null;
    }

    private async enforceSession() {
        if (this.service.auth?.check?.() !== true) {
            location.href = '/access';
            return;
        }
        this.authReady.set(true);
        await this.service.render();
    }

    @HostListener('window:docker-infra-agent-refresh-current-view', ['$event'])
    public async handleAgentRefreshCurrentView(event: any) {
        const detail = event?.detail || {};
        const requestId = String(detail.request_id || '');
        if (!requestId) return;
        const requestedRoute = this.normalizeRoute(detail.route || '');
        const currentRoute = this.normalizeRoute(this.service.currentPath());
        if (requestedRoute && requestedRoute !== currentRoute) {
            this.publishAgentRefreshResult(requestId, {
                ok: false,
                message: '현재 화면이 변경되어 데이터를 갱신하지 않았습니다.',
            });
            return;
        }

        try {
            await this.refreshActiveRouteComponent();
            this.publishAgentRefreshResult(requestId, { ok: true });
        } catch (error: any) {
            this.publishAgentRefreshResult(requestId, {
                ok: false,
                message: error?.message || '현재 화면 데이터를 갱신하지 못했습니다.',
            });
        }
    }

    private async refreshActiveRouteComponent() {
        const page = this.activeRouteComponent;
        if (!page || typeof page.load !== 'function') {
            throw new Error('현재 화면의 새로고침 API를 찾을 수 없습니다.');
        }

        const path = this.normalizeRoute(this.service.currentPath());
        if (path.startsWith('/dashboard')) return await page.load(false);
        if (path.startsWith('/services/create')) return await page.load();
        if (path.startsWith('/services')) return await page.load(this.selectedEntityId(page), true);
        if (path.startsWith('/servers')) return await page.load(this.selectedEntityId(page), true);
        if (path.startsWith('/templates')) return await page.load(true, this.selectedEntityId(page), true);
        if (path.startsWith('/macros')) return await page.load(true);
        if (path.startsWith('/operations')) return await this.refreshOperationsPage(page);
        return await page.load();
    }

    private async refreshOperationsPage(page: any) {
        const pagination = this.readSignal(page.pagination) || {};
        await page.load(Math.max(1, Number(pagination.current || 1)), false);
        if (this.readSignal(page.detailOpen) && typeof page.refreshDetail === 'function') {
            await page.refreshDetail(false);
        }
    }

    private selectedEntityId(page: any) {
        const selected = this.readSignal(page.selected);
        if (selected?.id) return String(selected.id);
        const selectedId = this.readSignal(page.selectedId);
        if (selectedId) return String(selectedId);
        const selectedMacroId = this.readSignal(page.selectedMacroId);
        if (selectedMacroId) return String(selectedMacroId);
        const selectedNodeId = this.readSignal(page.selectedNodeId);
        if (selectedNodeId) return String(selectedNodeId);
        return '';
    }

    private readSignal(value: any) {
        if (typeof value !== 'function') return value;
        try {
            return value();
        } catch (_error) {
            return undefined;
        }
    }

    private publishAgentRefreshResult(requestId: string, detail: any) {
        if (typeof window === 'undefined') return;
        window.dispatchEvent(new CustomEvent('docker-infra-agent-refresh-result', {
            detail: {
                request_id: requestId,
                route: this.service.currentPath(),
                ...detail,
            },
        }));
    }

    private normalizeRoute(value: any) {
        return String(value || '').split('?')[0].replace(/\/+$/g, '') || '/';
    }

    @HostListener('document:click')
    public clickout() {
        this.service.status.toggle('navbar', false);
    }
}
