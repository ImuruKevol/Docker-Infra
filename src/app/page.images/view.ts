import { OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

type ImageTab = 'harbor' | 'local';
type LocalUsageFilter = 'all' | 'used' | 'unused';
type LocalSortKey = 'last_used_desc' | 'last_used_asc' | 'size_desc' | 'size_asc';
type LocalImageConfirmMode = '' | 'prune' | 'delete';
type ImageOperationTone = 'info' | 'warning' | 'danger';

export class Component implements OnInit {
    public loading = signal<boolean>(true);
    public error = signal<string>('');
    public activeTab = signal<ImageTab>('local');
    public harborOverviewBusy = signal<boolean>(false);
    public harborBusy = signal<boolean>(false);
    public localBusy = signal<boolean>(false);
    public harbor = signal<any>({ enabled: false, configured: false, url: '', username: '' });
    public harborError = signal<string>('');
    public harborProjects = signal<any[]>([]);
    public harborSummary = signal<any>({ project_count: 0, tag_count: 0 });
    public selectedProject = signal<string>('');
    public harborDetail = signal<any>(null);
    public harborTags = signal<any[]>([]);
    public selectedRepository = signal<string>('');
    public harborSearch = signal<string>('');
    public selectedHarborRepositories = signal<string[]>([]);
    public selectedHarborItems = signal<string[]>([]);
    public harborTagsBusy = signal<boolean>(false);
    public showCreateProjectModal = signal<boolean>(false);
    public fileTreeOpen = signal<boolean>(false);
    public createProjectBusy = signal<boolean>(false);
    public newProjectName = signal<string>('');
    public newProjectPublic = signal<boolean>(false);
    public nodes = signal<any[]>([]);
    public localSummaryByNode = signal<Record<string, any>>({});
    public selectedNodeId = signal<string>('');
    public localDetail = signal<any>(null);
    public localLoadError = signal<string>('');
    public localSearch = signal<string>('');
    public localUsageFilter = signal<LocalUsageFilter>('all');
    public localSort = signal<LocalSortKey>('last_used_desc');
    public selectedLocalItems = signal<string[]>([]);
    public localDeleteEstimate = signal<any>(null);
    public localDeleteEstimateBusy = signal<boolean>(false);
    public localPruneBusy = signal<boolean>(false);
    public localPruneEstimateBusy = signal<boolean>(false);
    public localUploadBusy = signal<boolean>(false);
    public localUploadProgress = signal<number>(0);
    public localUploadPhase = signal<string>('');
    public localUploadFileName = signal<string>('');
    public showLocalImageConfirmModal = signal<boolean>(false);
    public localImageConfirmMode = signal<LocalImageConfirmMode>('');
    public localImageConfirmTitle = signal<string>('');
    public localImageConfirmMessage = signal<string>('');
    public localImageConfirmEstimate = signal<string>('');
    public localImageConfirmAction = signal<string>('확인');
    public localImageConfirmItems = signal<any[]>([]);
    public imageOperationBusy = signal<boolean>(false);
    public imageOperationTitle = signal<string>('');
    public imageOperationMessage = signal<string>('');
    public imageOperationTone = signal<ImageOperationTone>('info');
    private localImageConfirmResolve: ((confirmed: boolean) => void) | null = null;
    private localLoadRequestId = 0;
    private localDetailCache: Record<string, any> = {};

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.load();
    }

    public async alert(message: string, status: string = 'error') {
        return await this.service.modal.show({
            title: '',
            message,
            cancel: false,
            actionBtn: status,
            action: '확인',
            status,
        });
    }

    public async confirm(message: string, action: string = '삭제', status: string = 'warning') {
        return await this.service.modal.show({
            title: '',
            message,
            cancel: true,
            cancelLabel: '취소',
            actionBtn: status,
            action,
            status,
        });
    }

    private async startImageOperation(title: string, message: string, tone: ImageOperationTone = 'info') {
        this.imageOperationTitle.set(title);
        this.imageOperationMessage.set(message);
        this.imageOperationTone.set(tone);
        this.imageOperationBusy.set(true);
        await this.service.render();
    }

    private async finishImageOperation() {
        this.imageOperationBusy.set(false);
        this.imageOperationTitle.set('');
        this.imageOperationMessage.set('');
        await this.service.render();
    }

    private emptyLocalSummary() {
        return { image_count: 0, used_count: 0, unused_count: 0, total_size_bytes: 0 };
    }

    private routeImageTarget() {
        const segments = this.service.pathSegments();
        const mode = segments[1] || '';
        return {
            tab: mode === 'harbor' || mode === 'local' ? mode as ImageTab : '',
            nodeId: this.service.routeSegment('node_id') || this.service.queryParam('node_id'),
            projectName: this.service.routeSegment('project_name') || this.service.queryParam('project_name'),
            repositoryName: this.service.routeSegment('repository_name') || this.service.queryParam('repository_name'),
        };
    }

    private imageRoute() {
        if (this.activeTab() === 'local') {
            const nodeId = this.service.encodeRouteSegment(this.selectedNodeId());
            return nodeId ? `/images/local/${nodeId}` : '/images/local';
        }
        if (this.activeTab() === 'harbor') {
            const projectName = this.service.encodeRouteSegment(this.selectedProject());
            const repositoryName = this.service.encodeRouteSegment(this.selectedRepository());
            if (projectName && repositoryName) return `/images/harbor/${projectName}/${repositoryName}`;
            if (projectName) return `/images/harbor/${projectName}`;
            return '/images/harbor';
        }
        return '/images';
    }

    private async syncImageRoute(replace: boolean = false) {
        const target = this.imageRoute();
        if (this.service.currentPath() !== target) await this.service.routeTo(target, replace);
    }

    private localDetailCacheItem(nodeId: string) {
        return this.localDetailCache[String(nodeId || '').trim()] || null;
    }

    private applyLocalDetail(data: any, nodeId: string = this.selectedNodeId()) {
        const key = String(nodeId || '').trim();
        if (!key || !data) return;
        const summary = data.summary || this.emptyLocalSummary();
        this.localDetailCache = { ...this.localDetailCache, [key]: data };
        this.localSummaryByNode.set({
            ...this.localSummaryByNode(),
            [key]: summary,
        });
        if (this.selectedNodeId() === key) {
            this.localDetail.set(data);
            this.selectedLocalItems.set([]);
            this.localDeleteEstimate.set(null);
            this.localLoadError.set('');
        }
    }

    public async load() {
        const routeTarget = this.routeImageTarget();
        this.loading.set(true);
        this.error.set('');
        this.harborDetail.set(null);
        this.localDetail.set(null);
        this.localLoadError.set('');
        this.localDetailCache = {};
        this.localLoadRequestId += 1;
        await this.service.render();
        const { code, data } = await wiz.call('load', {});
        if (code !== 200) {
            this.error.set(data?.message || '이미지 정보를 불러올 수 없습니다.');
            this.loading.set(false);
            await this.service.render();
            return;
        }

        this.harbor.set(data.harbor || { enabled: false, configured: false, url: '', username: '' });
        this.harborError.set(data.harbor_error || '');
        this.harborProjects.set(data.harbor_projects || []);
        this.harborSummary.set(data.harbor_summary || { project_count: 0, tag_count: 0 });
        this.nodes.set(data.nodes || []);
        this.localSummaryByNode.set(data.local_summary_by_node || {});
        this.selectedProject.set(routeTarget.projectName || data.selected_project || '');
        this.harborTags.set([]);
        this.selectedRepository.set('');
        this.selectedHarborRepositories.set([]);
        this.selectedHarborItems.set([]);
        this.selectedLocalItems.set([]);
        this.localDeleteEstimate.set(null);
        this.closeLocalImageConfirm(false);
        this.selectedNodeId.set(routeTarget.tab === 'local' ? (routeTarget.nodeId || data.selected_node_id || '') : (data.selected_node_id || ''));
        this.activeTab.set(routeTarget.tab || (!this.selectedNodeId() && this.harbor().enabled ? 'harbor' : 'local'));
        this.loading.set(false);
        await this.service.render();

        if (this.activeTab() === 'local' && this.selectedNodeId()) {
            void this.loadLocalDetail(this.selectedNodeId(), true, false, true);
        } else if (this.activeTab() === 'harbor' && this.harbor().enabled) {
            void (async () => {
                await this.ensureHarborOverview(true);
                const projectName = routeTarget.projectName || this.selectedProject();
                if (projectName) await this.loadHarborDetail(projectName, true, routeTarget.repositoryName, true);
                else await this.syncImageRoute(true);
            })();
        }
    }

    public async setTab(tab: ImageTab) {
        if (tab === 'harbor' && !this.harbor().enabled) return;
        this.activeTab.set(tab);
        await this.syncImageRoute();
        await this.service.render();
        if (tab === 'harbor') {
            await this.ensureHarborOverview(true);
            if (this.selectedProject() && !this.harborDetail()) {
                await this.loadHarborDetail(this.selectedProject(), true);
            }
            return;
        }
        if (tab === 'local' && this.selectedNodeId() && !this.localDetail()) {
            await this.loadLocalDetail(this.selectedNodeId(), true);
        }
    }

    public async ensureHarborOverview(silent: boolean = false) {
        if (!this.harbor().enabled || this.harborProjects().length > 0 || this.harborOverviewBusy()) return;
        this.harborOverviewBusy.set(true);
        const { code, data } = await wiz.call('harbor_overview', {});
        if (code === 200) {
            this.harborProjects.set(data.projects || []);
            this.harborSummary.set({
                ...this.harborSummary(),
                ...(data.summary || {}),
                project_count: (data.projects || []).length,
            });
            const current = this.selectedProject();
            const projects = data.projects || [];
            this.selectedProject.set(projects.find((item: any) => item.name === current)?.name || data.selected_project || projects[0]?.name || '');
        } else if (!silent) {
            await this.alert(data?.message || '백업 저장소 프로젝트 목록을 불러올 수 없습니다.');
        } else {
            this.harborError.set(data?.message || '백업 저장소 프로젝트 목록을 불러올 수 없습니다.');
        }
        this.harborOverviewBusy.set(false);
        await this.service.render();
    }

    public async loadHarborDetail(projectName: string, silent: boolean = false, repositoryName: string = '', replaceRoute: boolean = false) {
        if (!projectName) return;
        this.harborBusy.set(true);
        this.activeTab.set('harbor');
        this.selectedProject.set(projectName);
        this.harborTags.set([]);
        this.selectedRepository.set('');
        this.selectedHarborRepositories.set([]);
        this.selectedHarborItems.set([]);
        const { code, data } = await wiz.call('harbor_detail', { project_name: projectName });
        if (code === 200) {
            this.harborDetail.set(data);
            const repositories = data.repositories || [];
            const requestedRepository = String(repositoryName || '').trim();
            const nextRepository = repositories.find((item: any) => item.name === requestedRepository)?.name || data.selected_repository || repositories[0]?.name || '';
            this.selectedRepository.set(nextRepository);
            this.harborSummary.set({
                ...this.harborSummary(),
                repository_count: data?.summary?.repository_count || repositories.length,
            });
            await this.syncImageRoute(replaceRoute);
            if (nextRepository) {
                await this.loadHarborTags(nextRepository, true, replaceRoute);
            }
        } else if (!silent) {
            await this.alert(data?.message || '백업 저장소를 불러올 수 없습니다.');
        } else {
            this.harborError.set(data?.message || '백업 저장소를 불러올 수 없습니다.');
        }
        this.harborBusy.set(false);
        await this.service.render();
    }

    public async loadHarborTags(repositoryName: string, silent: boolean = false, replaceRoute: boolean = false) {
        if (!this.selectedProject() || !repositoryName) return;
        this.harborTagsBusy.set(true);
        this.activeTab.set('harbor');
        this.selectedRepository.set(repositoryName);
        this.selectedHarborItems.set([]);
        await this.syncImageRoute(replaceRoute);
        const { code, data } = await wiz.call('harbor_tags', {
            project_name: this.selectedProject(),
            repository_name: repositoryName,
        });
        if (code === 200) {
            this.harborTags.set(data.tags || []);
        } else if (!silent) {
            await this.alert(data?.message || '백업 저장소 태그 목록을 불러올 수 없습니다.');
        } else {
            this.harborError.set(data?.message || '백업 저장소 태그 목록을 불러올 수 없습니다.');
        }
        this.harborTagsBusy.set(false);
        await this.service.render();
    }

    public async loadLocalDetail(nodeId: string, silent: boolean = false, force: boolean = false, replaceRoute: boolean = false) {
        if (!nodeId) return;
        const requestId = ++this.localLoadRequestId;
        const isNodeChange = this.selectedNodeId() !== nodeId;
        this.activeTab.set('local');
        this.selectedNodeId.set(nodeId);
        this.selectedLocalItems.set([]);
        this.localDeleteEstimate.set(null);
        this.localLoadError.set('');
        this.closeLocalImageConfirm(false);
        await this.syncImageRoute(replaceRoute);
        const cached = force ? null : this.localDetailCacheItem(nodeId);
        if (cached) {
            this.localBusy.set(false);
            this.applyLocalDetail(cached, nodeId);
            await this.service.render();
            return;
        }
        this.localBusy.set(true);
        if (isNodeChange || !this.localDetail()) {
            this.localDetail.set(null);
        }
        await this.service.render();
        const { code, data } = await wiz.call('local_detail', { node_id: nodeId });
        if (code === 200) {
            this.localDetailCache = { ...this.localDetailCache, [nodeId]: data };
            this.localSummaryByNode.set({
                ...this.localSummaryByNode(),
                [nodeId]: data.summary || this.emptyLocalSummary(),
            });
            if (requestId !== this.localLoadRequestId || this.selectedNodeId() !== nodeId) return;
            this.applyLocalDetail(data, nodeId);
        } else if (!silent) {
            if (requestId !== this.localLoadRequestId || this.selectedNodeId() !== nodeId) return;
            const message = data?.message || '서버 로컬 이미지를 불러올 수 없습니다.';
            this.localLoadError.set(message);
            await this.alert(message);
        } else {
            if (requestId !== this.localLoadRequestId || this.selectedNodeId() !== nodeId) return;
            this.localLoadError.set(data?.message || '서버 로컬 이미지를 불러올 수 없습니다.');
        }
        this.localBusy.set(false);
        await this.service.render();
    }

    public openFileTree() {
        if (!this.selectedNodeId()) return;
        this.fileTreeOpen.set(true);
    }

    public closeFileTree() {
        this.fileTreeOpen.set(false);
    }

    public openLocalImageUpload() {
        if (!this.selectedNodeId() || this.localUploadBusy()) return;
        (document.getElementById('local-image-upload-input') as HTMLInputElement | null)?.click();
    }

    private isLocalImageArchiveName(name: string) {
        const lower = String(name || '').trim().toLowerCase();
        return lower.endsWith('.tar') || lower.endsWith('.tar.gz') || lower.endsWith('.tgz');
    }

    private resetLocalUploadState() {
        this.localUploadBusy.set(false);
        this.localUploadProgress.set(0);
        this.localUploadPhase.set('');
        this.localUploadFileName.set('');
    }

    public localUploadPhaseLabel() {
        if (this.localUploadPhase() === 'importing') return '업로드 완료, Docker import 실행 중';
        if (this.localUploadPhase() === 'uploading') return '이미지 tar 업로드 중';
        return '업로드 준비 중';
    }

    public localUploadProgressLabel() {
        const progress = this.localUploadProgress();
        const normalized = Math.max(0, Math.min(100, Number(progress || 0)));
        return `${normalized.toFixed(normalized % 1 ? 1 : 0)}%`;
    }

    public localUploadProgressBarWidth() {
        if (this.localUploadPhase() === 'importing') return 100;
        const progress = Math.max(0, Math.min(100, Number(this.localUploadProgress() || 0)));
        return this.localUploadBusy() ? Math.max(2, progress) : progress;
    }

    private localImportResultText(result: any) {
        const refs = result?.load?.loaded_images || [];
        const ids = result?.load?.loaded_image_ids || [];
        const loaded = refs.length ? refs.join(', ') : (ids.length ? ids.join(', ') : this.localUploadFileName());
        return `${loaded || '이미지'} import를 완료했습니다.`;
    }

    public async uploadLocalImageArchive(event: Event) {
        const input = event.target as HTMLInputElement;
        const file = input?.files && input.files[0];
        if (input) input.value = '';
        if (!file) return;
        const nodeId = this.selectedNodeId();
        if (!nodeId) {
            await this.alert('먼저 서버를 선택해주세요.');
            return;
        }
        if (!this.isLocalImageArchiveName(file.name)) {
            await this.alert('Docker image archive tar 파일만 업로드할 수 있습니다.');
            return;
        }

        const fd = new FormData();
        fd.append('node_id', nodeId);
        fd.append('file', file, file.name);
        this.localUploadBusy.set(true);
        this.localUploadProgress.set(0);
        this.localUploadPhase.set('uploading');
        this.localUploadFileName.set(file.name);
        await this.service.render();

        const response: any = await this.service.file.upload(wiz.url('upload_local'), fd, async (percent: number) => {
            this.localUploadProgress.set(percent);
            if (percent >= 100) this.localUploadPhase.set('importing');
            await this.service.render();
        });
        const code = response?.code || 500;
        const data = response?.data || response;
        if (code === 200) {
            const message = this.localImportResultText(data.import_result);
            this.applyLocalDetail(data, nodeId);
            this.resetLocalUploadState();
            await this.alert(message, 'success');
            await this.service.render();
            return;
        }
        this.resetLocalUploadState();
        await this.alert(data?.message || response?.message || '이미지 tar를 import할 수 없습니다.');
        await this.service.render();
    }

    public imageFileTreeContext() {
        return { node_id: this.selectedNodeId() || '' };
    }

    public projectSummary() {
        const detail = this.harborDetail();
        return detail?.summary || {
            repository_count: this.harborDetail()?.repositories?.length || 0,
            artifact_count: 0,
            pull_count: 0,
        };
    }

    public harborProjectCount() {
        return this.harborProjects().length || this.harborSummary().project_count || 0;
    }

    public harborTagCount() {
        return this.harborTags().length || 0;
    }

    public selectedRepositoryLabel() {
        const selected = this.selectedRepository();
        const repository = this.harborRepositories().find((item: any) => item?.name === selected);
        return repository?.display_name || selected;
    }

    public shortDigest(value: any) {
        const text = String(value || '').replace(/^sha256:/, '').trim();
        if (!text) return '-';
        if (text.length <= 18) return text;
        return `${text.slice(0, 12)}...${text.slice(-6)}`;
    }

    public selectedNodeSummary() {
        const nodeId = this.selectedNodeId();
        const cached = this.localSummaryByNode()?.[nodeId] || { image_count: 0, used_count: 0, unused_count: 0, total_size_bytes: 0 };
        return this.localDetail()?.summary || cached;
    }

    public localImageCount() {
        return this.selectedNodeSummary().image_count || 0;
    }

    public localUsedCount() {
        return this.selectedNodeSummary().used_count || 0;
    }

    public localUnusedCount() {
        return this.selectedNodeSummary().unused_count || 0;
    }

    public localTotalImageSize() {
        return this.selectedNodeSummary().total_size_bytes || 0;
    }

    public localTotalImageCount() {
        return Object.values(this.localSummaryByNode() || {})
            .reduce((total: number, item: any) => total + Number(item?.image_count || 0), 0);
    }

    public nodeImageCount(node: any) {
        return Number(this.localSummaryByNode()?.[node?.id]?.image_count || 0);
    }

    public selectedNodeStorage() {
        return this.localDetail()?.storage || {};
    }

    public localStorageAvailable() {
        const storage = this.selectedNodeStorage();
        return storage?.available !== false && Number(storage?.total_bytes || 0) > 0;
    }

    public localStorageUsedPercent() {
        const storage = this.selectedNodeStorage();
        const total = Number(storage?.total_bytes || 0);
        if (!total) return 0;
        const used = Number(storage?.used_bytes || 0);
        return Math.max(0, Math.min(100, Number(storage?.used_percent ?? (used * 100 / total))));
    }

    public localStorageMessage() {
        return this.selectedNodeStorage()?.message || '저장소 용량을 확인할 수 없습니다.';
    }

    public localStoragePath() {
        return this.selectedNodeStorage()?.path || '-';
    }

    public harborRepositories() {
        return this.harborDetail()?.repositories || [];
    }

    public harborRepositoryKey(item: any) {
        return String(item?.name || '').trim();
    }

    public isHarborRepositorySelected(item: any) {
        return this.selectedHarborRepositories().includes(this.harborRepositoryKey(item));
    }

    public toggleHarborRepositorySelection(item: any, checked: boolean) {
        const key = this.harborRepositoryKey(item);
        const items = new Set(this.selectedHarborRepositories());
        if (checked) items.add(key);
        else items.delete(key);
        this.selectedHarborRepositories.set(Array.from(items));
    }

    public toggleAllHarborRepositories(checked: boolean) {
        if (!checked) {
            this.selectedHarborRepositories.set([]);
            return;
        }
        this.selectedHarborRepositories.set(this.harborRepositories().map((item: any) => this.harborRepositoryKey(item)).filter((item: string) => item));
    }

    public allVisibleHarborRepositoriesSelected() {
        const visible = this.harborRepositories();
        if (!visible.length) return false;
        const selected = new Set(this.selectedHarborRepositories());
        return visible.every((item: any) => selected.has(this.harborRepositoryKey(item)));
    }

    public selectedHarborRepositoryCount() {
        return this.selectedHarborRepositories().length;
    }

    public selectedHarborRepositoryItems() {
        const selected = new Set(this.selectedHarborRepositories());
        return this.harborRepositories()
            .filter((item: any) => selected.has(this.harborRepositoryKey(item)))
            .map((item: any) => ({ repository_name: item.name }));
    }

    public filteredHarborTags() {
        const query = String(this.harborSearch() || '').trim().toLowerCase();
        let items = [...this.harborTags()];
        if (!query) return items;
        return items.filter((item: any) => `${item.repository_name} ${item.tag} ${item.digest}`.toLowerCase().includes(query));
    }

    public harborTagKey(item: any) {
        return `${item.repository_name}@@${item.digest}`;
    }

    public isHarborTagSelected(item: any) {
        return this.selectedHarborItems().includes(this.harborTagKey(item));
    }

    public toggleHarborTagSelection(item: any, checked: boolean) {
        const key = this.harborTagKey(item);
        const items = new Set(this.selectedHarborItems());
        if (checked) items.add(key);
        else items.delete(key);
        this.selectedHarborItems.set(Array.from(items));
    }

    public toggleAllHarborTags(checked: boolean) {
        if (!checked) {
            this.selectedHarborItems.set([]);
            return;
        }
        this.selectedHarborItems.set(this.filteredHarborTags().map((item: any) => this.harborTagKey(item)));
    }

    public allVisibleHarborTagsSelected() {
        const visible = this.filteredHarborTags();
        if (!visible.length) return false;
        const selected = new Set(this.selectedHarborItems());
        return visible.every((item: any) => selected.has(this.harborTagKey(item)));
    }

    public selectedHarborTagCount() {
        return this.selectedHarborItems().length;
    }

    public selectedHarborDeleteItems() {
        const selected = new Set(this.selectedHarborItems());
        return this.harborTags()
            .filter((item: any) => selected.has(this.harborTagKey(item)))
            .map((item: any) => ({ repository_name: item.repository_name, digest: item.digest }));
    }

    public filteredLocalImages() {
        const detail = this.localDetail();
        const query = String(this.localSearch() || '').trim().toLowerCase();
        const usageFilter = this.localUsageFilter();
        let items = [...(detail?.images || [])];
        if (query) {
            items = items.filter((item: any) => `${item.repository} ${item.tag} ${item.digest} ${item.image_id}`.toLowerCase().includes(query));
        }
        if (usageFilter === 'used') {
            items = items.filter((item: any) => Boolean(item.in_use));
        } else if (usageFilter === 'unused') {
            items = items.filter((item: any) => !item.in_use);
        }
        return items.sort((a: any, b: any) => this.compareLocalImages(a, b));
    }

    public localImageKey(item: any) {
        return String(item?.remove_ref || item?.image_id || '').trim();
    }

    public localImageSelectable(item: any) {
        return Boolean(this.localImageKey(item)) && !item?.in_use;
    }

    public isLocalImageSelected(item: any) {
        return this.localImageSelectable(item) && this.selectedLocalItems().includes(this.localImageKey(item));
    }

    public toggleLocalImageSelection(item: any, checked: boolean) {
        const key = this.localImageKey(item);
        if (!key || (checked && !this.localImageSelectable(item))) return;
        const items = new Set(this.selectedLocalItems());
        if (checked) items.add(key);
        else items.delete(key);
        this.selectedLocalItems.set(Array.from(items));
        this.localDeleteEstimate.set(null);
    }

    public toggleAllLocalImages(checked: boolean) {
        if (!checked) {
            this.selectedLocalItems.set([]);
            this.localDeleteEstimate.set(null);
            return;
        }
        this.selectedLocalItems.set(
            this.filteredLocalImages()
                .filter((item: any) => this.localImageSelectable(item))
                .map((item: any) => this.localImageKey(item))
                .filter((item: string) => item)
        );
        this.localDeleteEstimate.set(null);
    }

    public allVisibleLocalImagesSelected() {
        const visible = this.filteredLocalImages().filter((item: any) => this.localImageSelectable(item));
        if (!visible.length) return false;
        const selected = new Set(this.selectedLocalItems());
        return visible.every((item: any) => selected.has(this.localImageKey(item)));
    }

    public selectedLocalImageCount() {
        return this.selectedLocalDeleteItems().length;
    }

    public selectedLocalDeleteItems() {
        const selected = new Set(this.selectedLocalItems());
        return this.selectedLocalDeleteImageRows()
            .map((item: any) => ({ image_ref: item.remove_ref }));
    }

    public selectedLocalDeleteImageRows() {
        const selected = new Set(this.selectedLocalItems());
        return (this.localDetail()?.images || [])
            .filter((item: any) => this.localImageSelectable(item) && selected.has(this.localImageKey(item)));
    }

    public localPruneCandidates() {
        return (this.localDetail()?.images || []).filter((item: any) => this.localImageSelectable(item));
    }

    private compareLocalImages(left: any, right: any) {
        switch (this.localSort()) {
            case 'size_asc':
                return this.numberValue(left.size_bytes) - this.numberValue(right.size_bytes);
            case 'size_desc':
                return this.numberValue(right.size_bytes) - this.numberValue(left.size_bytes);
            case 'last_used_asc':
                return this.dateValue(left.last_used_at) - this.dateValue(right.last_used_at);
            case 'last_used_desc':
            default:
                return this.dateValue(right.last_used_at) - this.dateValue(left.last_used_at);
        }
    }

    private numberValue(value: any) {
        return Number(value || 0);
    }

    private dateValue(value: any) {
        if (!value) return 0;
        const epoch = new Date(value).getTime();
        return Number.isNaN(epoch) ? 0 : epoch;
    }

    public setLocalUsageFilter(value: LocalUsageFilter) {
        this.localUsageFilter.set(value);
    }

    public setLocalSort(value: LocalSortKey) {
        this.localSort.set(value);
    }

    public localSortOptions() {
        return [
            { value: 'last_used_desc', label: '최근 사용 순' },
            { value: 'last_used_asc', label: '오래된 사용 순' },
            { value: 'size_desc', label: '용량 큰 순' },
            { value: 'size_asc', label: '용량 작은 순' },
        ];
    }

    public imageOperationToneClass() {
        if (this.imageOperationTone() === 'danger') {
            return 'border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900/70 dark:bg-rose-950/30 dark:text-rose-200';
        }
        if (this.imageOperationTone() === 'warning') {
            return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-200';
        }
        return 'border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-900/70 dark:bg-sky-950/30 dark:text-sky-200';
    }

    public imageOperationProgressClass() {
        if (this.imageOperationTone() === 'danger') {
            return 'bg-rose-100 text-rose-500 dark:bg-rose-950 dark:text-rose-400';
        }
        if (this.imageOperationTone() === 'warning') {
            return 'bg-amber-100 text-amber-500 dark:bg-amber-950 dark:text-amber-400';
        }
        return 'bg-sky-100 text-sky-500 dark:bg-sky-950 dark:text-sky-400';
    }

    public imageOperationIconClass() {
        if (this.imageOperationTone() === 'warning') return 'fa-broom';
        if (this.imageOperationTone() === 'danger') return 'fa-trash';
        return 'fa-spinner fa-spin';
    }

    public async deleteHarborTag(item: any) {
        const ok = await this.confirm(`${item.repository_name}:${item.tag} 태그를 백업 저장소에서 삭제합니다.`, '백업 저장소 삭제');
        if (!ok) return;
        this.harborBusy.set(true);
        await this.startImageOperation('이미지 삭제 중', `${item.repository_name}:${item.tag} 태그를 백업 저장소에서 삭제하고 있습니다.`, 'danger');
        const { code, data } = await wiz.call('delete_harbor', {
            project_name: this.selectedProject(),
            repository_name: item.repository_name,
            digest: item.digest,
        });
        if (code === 200) {
            this.harborTags.set(data.tags || []);
            this.selectedHarborItems.set([]);
            this.harborBusy.set(false);
            await this.finishImageOperation();
            await this.alert('백업 저장소 이미지를 삭제했습니다.', 'success');
        } else {
            this.harborBusy.set(false);
            await this.finishImageOperation();
            await this.alert(data?.message || '백업 저장소 이미지를 삭제할 수 없습니다.');
        }
        await this.service.render();
    }

    public async deleteSelectedHarborTags() {
        const items = this.selectedHarborDeleteItems();
        if (!items.length) return;
        const ok = await this.confirm(`선택한 백업 저장소 이미지 ${items.length}개를 삭제합니다.`, '백업 저장소 삭제');
        if (!ok) return;
        this.harborBusy.set(true);
        await this.startImageOperation('선택 이미지 삭제 중', `선택한 백업 저장소 이미지 ${items.length}개를 삭제하고 있습니다.`, 'danger');
        const { code, data } = await wiz.call('delete_harbor', {
            project_name: this.selectedProject(),
            repository_name: this.selectedRepository(),
            items,
        });
        if (code === 200) {
            this.harborTags.set(data.tags || []);
            this.selectedHarborItems.set([]);
            this.harborBusy.set(false);
            await this.finishImageOperation();
            await this.alert('선택한 백업 저장소 이미지를 삭제했습니다.', 'success');
        } else {
            this.harborBusy.set(false);
            await this.finishImageOperation();
            await this.alert(data?.message || '백업 저장소 이미지를 삭제할 수 없습니다.');
        }
        await this.service.render();
    }

    public async deleteHarborProject() {
        if (!this.selectedProject()) return;
        const ok = await this.confirm(`${this.selectedProject()} 백업 저장소 프로젝트를 통째로 삭제합니다.`, '프로젝트 삭제');
        if (!ok) return;
        this.harborBusy.set(true);
        await this.startImageOperation('프로젝트 삭제 중', `${this.selectedProject()} 백업 저장소 프로젝트와 포함된 이미지를 삭제하고 있습니다.`, 'danger');
        const { code, data } = await wiz.call('delete_harbor_project', {
            project_name: this.selectedProject(),
        });
        if (code === 200) {
            this.harborProjects.set(data.projects || []);
            this.harborSummary.set(data.summary || { project_count: 0, tag_count: 0 });
            this.selectedProject.set(data.selected_project || '');
            this.harborDetail.set(null);
            this.harborTags.set([]);
            this.selectedRepository.set('');
            this.selectedHarborRepositories.set([]);
            this.selectedHarborItems.set([]);
            this.harborBusy.set(false);
            await this.finishImageOperation();
            await this.alert('백업 저장소 프로젝트를 삭제했습니다.', 'success');
        } else {
            this.harborBusy.set(false);
            await this.finishImageOperation();
            await this.alert(data?.message || '백업 저장소 프로젝트를 삭제할 수 없습니다.');
        }
        await this.service.render();
    }

    public async deleteHarborRepository(item: any) {
        const repositoryName = this.harborRepositoryKey(item);
        if (!repositoryName) return;
        const ok = await this.confirm(`${repositoryName} 이미지를 백업 저장소 프로젝트에서 삭제합니다.`, '백업 저장소 삭제');
        if (!ok) return;
        this.harborBusy.set(true);
        await this.startImageOperation('저장소 이미지 삭제 중', `${repositoryName} 이미지를 백업 저장소 프로젝트에서 삭제하고 있습니다.`, 'danger');
        const { code, data } = await wiz.call('delete_harbor_repository', {
            project_name: this.selectedProject(),
            repository_name: repositoryName,
        });
        if (code === 200) {
            this.harborDetail.set(data);
            this.selectedHarborRepositories.set(this.selectedHarborRepositories().filter((itemKey: string) => itemKey !== repositoryName));
            if (this.selectedRepository() === repositoryName) {
                this.harborTags.set([]);
                const nextRepository = (data.repositories || [])[0]?.name || '';
                this.selectedRepository.set(nextRepository);
                if (nextRepository) {
                    await this.loadHarborTags(nextRepository, true);
                }
            }
            this.harborBusy.set(false);
            await this.finishImageOperation();
            await this.alert('백업 저장소 이미지를 삭제했습니다.', 'success');
        } else {
            this.harborBusy.set(false);
            await this.finishImageOperation();
            await this.alert(data?.message || '백업 저장소 이미지를 삭제할 수 없습니다.');
        }
        await this.service.render();
    }

    public async deleteSelectedHarborRepositories() {
        const items = this.selectedHarborRepositoryItems();
        if (!items.length) return;
        const ok = await this.confirm(`선택한 백업 저장소 이미지 ${items.length}개를 삭제합니다.`, '백업 저장소 삭제');
        if (!ok) return;
        this.harborBusy.set(true);
        await this.startImageOperation('선택 저장소 삭제 중', `선택한 백업 저장소 이미지 ${items.length}개를 삭제하고 있습니다.`, 'danger');
        const selectedRepository = this.selectedRepository();
        const { code, data } = await wiz.call('delete_harbor_repository', {
            project_name: this.selectedProject(),
            items,
        });
        if (code === 200) {
            this.harborDetail.set(data);
            this.selectedHarborRepositories.set([]);
            if (items.some((item: any) => item.repository_name === selectedRepository)) {
                this.harborTags.set([]);
                const nextRepository = (data.repositories || [])[0]?.name || '';
                this.selectedRepository.set(nextRepository);
                if (nextRepository) {
                    await this.loadHarborTags(nextRepository, true);
                }
            }
            this.harborBusy.set(false);
            await this.finishImageOperation();
            await this.alert('선택한 백업 저장소 이미지를 삭제했습니다.', 'success');
        } else {
            this.harborBusy.set(false);
            await this.finishImageOperation();
            await this.alert(data?.message || '백업 저장소 이미지를 삭제할 수 없습니다.');
        }
        await this.service.render();
    }

    public openCreateProjectModal() {
        this.newProjectName.set('');
        this.newProjectPublic.set(false);
        this.showCreateProjectModal.set(true);
    }

    public closeCreateProjectModal() {
        this.showCreateProjectModal.set(false);
        this.createProjectBusy.set(false);
    }

    public async createHarborProject() {
        const projectName = String(this.newProjectName() || '').trim();
        if (!projectName) {
            await this.alert('프로젝트 이름을 입력해주세요.');
            return;
        }
        this.createProjectBusy.set(true);
        const { code, data } = await wiz.call('create_harbor_project', {
            project_name: projectName,
            public: this.newProjectPublic(),
        });
        if (code === 200) {
            this.harborProjects.set(data.projects || []);
            this.harborSummary.set(data.summary || { project_count: 0, tag_count: 0 });
            this.showCreateProjectModal.set(false);
            await this.loadHarborDetail(projectName, true);
            await this.alert('백업 저장소 프로젝트를 생성했습니다.', 'success');
        } else {
            await this.alert(data?.message || '백업 저장소 프로젝트를 생성할 수 없습니다.');
        }
        this.createProjectBusy.set(false);
        await this.service.render();
    }

    private localDeleteEstimateText(estimate: any) {
        if (!estimate) return '예상 확보 용량을 계산하지 못했습니다.';
        const method = estimate.method === 'docker_system_df_verbose' ? 'Docker system df -v 기준 실제 확보 용량' : 'Docker 명령 기준';
        const displaySize = Number(estimate.removable_size_bytes || estimate.selected_size_bytes || 0);
        const displayText = displaySize > 0 ? ` / 표시 용량 ${this.formatBytes(displaySize)}` : '';
        const retained = Number(estimate.shared_or_retained_bytes || 0);
        const retainedText = retained > 0 ? ` / 공유·유지 레이어 ${this.formatBytes(retained)} 제외` : '';
        const blocked = Number(estimate.blocked_image_count || 0);
        const blockedText = blocked > 0 ? ` / 사용 중 제외 ${blocked}개` : '';
        const missing = Number(estimate.missing_unique_count || 0);
        const missingText = missing > 0 ? ` / 고유 용량 미확인 ${missing}개` : '';
        return `실제 확보 예상: ${this.formatBytes(estimate.reclaimable_bytes, '0 B')} (${method}${displayText}${retainedText}${blockedText}${missingText})`;
    }

    private async estimateSelectedLocalDelete(items: any[], nodeId: string = this.selectedNodeId()) {
        this.localDeleteEstimate.set(null);
        this.localDeleteEstimateBusy.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('local_delete_estimate', {
            node_id: nodeId,
            items,
        });
        this.localDeleteEstimateBusy.set(false);
        if (code === 200) {
            this.localDeleteEstimate.set(data.estimate || null);
            await this.service.render();
            return data.estimate || null;
        }
        await this.service.render();
        return null;
    }

    private pruneEstimateText(estimate: any) {
        if (!estimate) return '예상 확보 용량을 계산하지 못했습니다.';
        const total = Number(estimate.image_total_bytes || 0);
        const totalText = total > 0 ? ` / 이미지 표시 용량 ${this.formatBytes(total)}` : '';
        return `미사용 이미지 정리 예상 확보: ${this.formatBytes(estimate.reclaimable_bytes, '0 B')}${totalText} (Docker image prune 기준)`;
    }

    private pruneResultText(result: any) {
        if (!result) return '정리 작업을 완료했습니다.';
        const reclaimed = result.reclaimed || this.formatBytes(result.reclaimed_bytes, '0 B');
        return `정리 작업을 완료했습니다. 확보 용량: ${reclaimed || '0 B'}`;
    }

    private localImageDisplayLabel(item: any) {
        const repository = String(item?.repository || '').trim();
        const tag = String(item?.tag || '').trim();
        if (repository && repository !== '<none>' && tag && tag !== '<none>') return `${repository}:${tag}`;
        if (repository && repository !== '<none>') return repository;
        return String(item?.image_id || item?.remove_ref || '-');
    }

    private shortImageId(value: any) {
        const text = String(value || '').replace(/^sha256:/, '').trim();
        if (!text) return '';
        return text.length > 12 ? text.slice(0, 12) : text;
    }

    private localImageConfirmListItems(items: any[]) {
        return (items || []).map((item: any) => {
            const imageId = this.shortImageId(item?.image_id);
            const meta = [
                item?.size || '',
                imageId ? `ID ${imageId}` : '',
                item?.last_used_at ? `최근 사용 ${this.formatDate(item.last_used_at)}` : '',
            ].filter((value: string) => value);
            return {
                key: this.localImageKey(item) || this.localImageDisplayLabel(item),
                label: this.localImageDisplayLabel(item),
                meta: meta.join(' · '),
            };
        });
    }

    private async confirmLocalImageAction(config: any) {
        if (this.localImageConfirmResolve) {
            this.localImageConfirmResolve(false);
            this.localImageConfirmResolve = null;
        }
        this.localImageConfirmMode.set(config.mode || '');
        this.localImageConfirmTitle.set(config.title || '');
        this.localImageConfirmMessage.set(config.message || '');
        this.localImageConfirmEstimate.set(config.estimate || '');
        this.localImageConfirmAction.set(config.action || '확인');
        this.localImageConfirmItems.set(this.localImageConfirmListItems(config.items || []));
        this.showLocalImageConfirmModal.set(true);
        const confirmed = new Promise<boolean>((resolve) => {
            this.localImageConfirmResolve = resolve;
        });
        await this.service.render();
        return await confirmed;
    }

    public closeLocalImageConfirm(confirmed: boolean = false) {
        const resolve = this.localImageConfirmResolve;
        this.localImageConfirmResolve = null;
        this.showLocalImageConfirmModal.set(false);
        this.localImageConfirmMode.set('');
        this.localImageConfirmTitle.set('');
        this.localImageConfirmMessage.set('');
        this.localImageConfirmEstimate.set('');
        this.localImageConfirmAction.set('확인');
        this.localImageConfirmItems.set([]);
        if (resolve) resolve(confirmed);
    }

    private async estimateLocalPrune(nodeId: string = this.selectedNodeId()) {
        if (!nodeId) return null;
        this.localPruneEstimateBusy.set(true);
        await this.service.render();
        const { code, data } = await wiz.call('local_prune_estimate', {
            node_id: nodeId,
            action: 'image',
        });
        this.localPruneEstimateBusy.set(false);
        if (code === 200) {
            await this.service.render();
            return data.estimate || null;
        }
        await this.alert(data?.message || '미사용 이미지 정리 예상 확보 용량을 계산할 수 없습니다.');
        await this.service.render();
        return null;
    }

    private async applyLocalPruneResult(data: any, nodeId: string = this.selectedNodeId()) {
        this.applyLocalDetail(data, nodeId);
    }

    private async executeLocalPrune(nodeId: string = this.selectedNodeId(), nodeName: string = this.selectedNodeName()) {
        this.localPruneBusy.set(true);
        await this.startImageOperation('미사용 이미지 정리 중', `${nodeName} 서버에서 미사용 Docker 이미지를 정리하고 있습니다.`, 'warning');
        const { code, data } = await wiz.call('local_prune', {
            node_id: nodeId,
            action: 'image',
            confirmed: true,
        });
        if (code === 200) {
            await this.applyLocalPruneResult(data, nodeId);
            this.localPruneBusy.set(false);
            await this.finishImageOperation();
            await this.alert(this.pruneResultText(data.prune_result), 'success');
        } else {
            this.localPruneBusy.set(false);
            await this.finishImageOperation();
            await this.alert(data?.message || '미사용 이미지 정리를 실행할 수 없습니다.');
        }
        await this.service.render();
    }

    public async runImagePrune() {
        const nodeId = this.selectedNodeId();
        const nodeName = this.selectedNodeName();
        if (!nodeId) return;
        const estimate = await this.estimateLocalPrune(nodeId);
        const ok = await this.confirmLocalImageAction({
            mode: 'prune',
            title: '미사용 이미지 정리',
            message: '사용 중이지 않은 모든 Docker 이미지가 삭제됩니다. 이 작업은 되돌릴 수 없습니다.',
            estimate: `실행 명령: docker image prune -a -f\n${this.pruneEstimateText(estimate)}`,
            action: '미사용 이미지 정리',
            items: this.localPruneCandidates(),
        });
        if (!ok) return;
        await this.executeLocalPrune(nodeId, nodeName);
    }

    public async deleteLocalImage(item: any) {
        if (!this.localImageSelectable(item)) {
            await this.alert('사용 중인 이미지는 삭제할 수 없습니다.');
            return;
        }
        const label = item.repository && item.tag ? `${item.repository}:${item.tag}` : item.image_id;
        const nodeId = this.selectedNodeId();
        const nodeName = this.selectedNodeName();
        const ok = await this.confirm(`${label} 이미지를 이 서버 로컬 저장소에서 삭제합니다.`, '로컬 삭제');
        if (!ok || !nodeId) return;
        this.localBusy.set(true);
        await this.startImageOperation('로컬 이미지 삭제 중', `${label} 이미지를 ${nodeName} 서버 로컬 저장소에서 삭제하고 있습니다.`, 'danger');
        const { code, data } = await wiz.call('delete_local', {
            node_id: nodeId,
            image_ref: item.remove_ref,
        });
        if (code === 200) {
            this.applyLocalDetail(data, nodeId);
            if (this.selectedNodeId() === nodeId) {
                this.selectedLocalItems.set(this.selectedLocalItems().filter((itemKey: string) => itemKey !== this.localImageKey(item)));
                this.localDeleteEstimate.set(null);
            }
            this.localBusy.set(false);
            await this.finishImageOperation();
            await this.alert('로컬 이미지를 삭제했습니다.', 'success');
        } else {
            this.localBusy.set(false);
            await this.finishImageOperation();
            await this.alert(data?.message || '로컬 이미지를 삭제할 수 없습니다.');
        }
        await this.service.render();
    }

    public async deleteSelectedLocalImages() {
        const nodeId = this.selectedNodeId();
        const nodeName = this.selectedNodeName();
        const rows = this.selectedLocalDeleteImageRows();
        const items = rows.map((item: any) => ({ image_ref: item.remove_ref }));
        if (!nodeId || !items.length) return;
        const estimate = await this.estimateSelectedLocalDelete(items, nodeId);
        const ok = await this.confirmLocalImageAction({
            mode: 'delete',
            title: '선택 이미지 삭제',
            message: `선택한 로컬 이미지 ${items.length}개를 삭제합니다. 이 작업은 되돌릴 수 없습니다.`,
            estimate: this.localDeleteEstimateText(estimate),
            action: '선택 삭제',
            items: rows,
        });
        if (!ok) return;
        this.localBusy.set(true);
        await this.startImageOperation('선택 이미지 삭제 중', `선택한 로컬 이미지 ${items.length}개를 ${nodeName} 서버에서 삭제하고 있습니다.`, 'danger');
        const { code, data } = await wiz.call('delete_local', {
            node_id: nodeId,
            items,
        });
        if (code === 200) {
            this.applyLocalDetail(data, nodeId);
            this.localBusy.set(false);
            await this.finishImageOperation();
            await this.alert('선택한 로컬 이미지를 삭제했습니다.', 'success');
        } else {
            this.localBusy.set(false);
            await this.finishImageOperation();
            await this.alert(data?.message || '로컬 이미지를 삭제할 수 없습니다.');
        }
        await this.service.render();
    }

    public selectedNode() {
        return this.nodes().find((item: any) => item.id === this.selectedNodeId()) || null;
    }

    public selectedNodeName() {
        return this.selectedNode()?.name || '서버 선택';
    }

    public selectedNodeHost() {
        return this.selectedNode()?.host || '왼쪽에서 서버를 선택하세요.';
    }

    public isLocalDockerUnavailable() {
        return this.localDetail()?.docker_available === false;
    }

    public isLocalDockerAvailable() {
        return !this.isLocalDockerUnavailable();
    }

    public localDockerMessage() {
        return this.localDetail()?.message || '이 서버에서는 Docker 이미지를 조회할 수 없습니다.';
    }

    public displayImageField(value: any) {
        return value || '<none>';
    }

    public localUsageBadgeClass(item: any) {
        return item?.in_use ? this.statusClass('enabled') : this.statusClass('disabled');
    }

    public localUsageLabel(item: any) {
        return item?.in_use ? '사용 중' : '미사용';
    }

    public localRunningLabel(item: any) {
        const usage = Number(item?.usage_count || 0);
        const running = Number(item?.running_count || 0);
        if (!usage) return '연결된 컨테이너 없음';
        if (!running) return `중지 포함 ${usage}개`;
        if (running === usage) return `실행 ${running}개`;
        return `실행 ${running}개 / 전체 ${usage}개`;
    }

    public selectedLocalEstimateLabel() {
        const estimate = this.localDeleteEstimate();
        if (!estimate) return '';
        return this.localDeleteEstimateText(estimate);
    }

    public statusClass(status: any) {
        if (status === true || ['ok', 'active', 'enabled', 'configured'].includes(status)) {
            return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300';
        }
        if (['warning', 'pending'].includes(status)) {
            return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-300';
        }
        if (['error', 'failed', 'disabled'].includes(status) || status === false) {
            return 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-300';
        }
        return 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300';
    }

    public formatDate(value: any) {
        if (!value) return '-';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString();
    }

    public formatBytes(value: any, zeroLabel: string = '-') {
        const size = Number(value || 0);
        if (!size) return zeroLabel;
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let current = size;
        let index = 0;
        while (current >= 1024 && index < units.length - 1) {
            current /= 1024;
            index += 1;
        }
        return `${current >= 100 || index === 0 ? current.toFixed(0) : current.toFixed(1)} ${units[index]}`;
    }

    public repositoryOptions() {
        return (this.harborDetail()?.repositories || []).map((item: any) => ({ value: item.name, label: item.display_name || item.name }));
    }
}
