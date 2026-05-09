import { OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

type ImageTab = 'harbor' | 'local';
type LocalUsageFilter = 'all' | 'used' | 'unused';
type LocalSortKey = 'last_used_desc' | 'last_used_asc' | 'size_desc' | 'size_asc' | 'created_desc' | 'created_asc';

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
    public localSearch = signal<string>('');
    public localUsageFilter = signal<LocalUsageFilter>('all');
    public localSort = signal<LocalSortKey>('last_used_desc');
    public selectedLocalItems = signal<string[]>([]);

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

    public async load() {
        this.loading.set(true);
        this.error.set('');
        this.harborDetail.set(null);
        this.localDetail.set(null);
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
        this.selectedProject.set(data.selected_project || '');
        this.harborTags.set([]);
        this.selectedRepository.set('');
        this.selectedHarborRepositories.set([]);
        this.selectedHarborItems.set([]);
        this.selectedLocalItems.set([]);
        this.selectedNodeId.set(data.selected_node_id || '');
        this.activeTab.set(this.selectedNodeId() ? 'local' : 'harbor');
        this.loading.set(false);
        await this.service.render();

        if (this.selectedNodeId()) {
            void this.loadLocalDetail(this.selectedNodeId(), true);
        } else if (this.activeTab() === 'harbor' && this.harbor().enabled) {
            void this.ensureHarborOverview(true);
        }
    }

    public async setTab(tab: ImageTab) {
        this.activeTab.set(tab);
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
            await this.alert(data?.message || 'Harbor 프로젝트 목록을 불러올 수 없습니다.');
        } else {
            this.harborError.set(data?.message || 'Harbor 프로젝트 목록을 불러올 수 없습니다.');
        }
        this.harborOverviewBusy.set(false);
        await this.service.render();
    }

    public async loadHarborDetail(projectName: string, silent: boolean = false) {
        if (!projectName) return;
        this.harborBusy.set(true);
        this.selectedProject.set(projectName);
        this.harborTags.set([]);
        this.selectedRepository.set('');
        this.selectedHarborRepositories.set([]);
        this.selectedHarborItems.set([]);
        const { code, data } = await wiz.call('harbor_detail', { project_name: projectName });
        if (code === 200) {
            this.harborDetail.set(data);
            const repositories = data.repositories || [];
            const nextRepository = data.selected_repository || repositories[0]?.name || '';
            this.selectedRepository.set(nextRepository);
            this.harborSummary.set({
                ...this.harborSummary(),
                repository_count: data?.summary?.repository_count || repositories.length,
            });
            if (nextRepository) {
                await this.loadHarborTags(nextRepository, true);
            }
        } else if (!silent) {
            await this.alert(data?.message || 'Harbor 저장소를 불러올 수 없습니다.');
        } else {
            this.harborError.set(data?.message || 'Harbor 저장소를 불러올 수 없습니다.');
        }
        this.harborBusy.set(false);
        await this.service.render();
    }

    public async loadHarborTags(repositoryName: string, silent: boolean = false) {
        if (!this.selectedProject() || !repositoryName) return;
        this.harborTagsBusy.set(true);
        this.selectedRepository.set(repositoryName);
        this.selectedHarborItems.set([]);
        const { code, data } = await wiz.call('harbor_tags', {
            project_name: this.selectedProject(),
            repository_name: repositoryName,
        });
        if (code === 200) {
            this.harborTags.set(data.tags || []);
        } else if (!silent) {
            await this.alert(data?.message || 'Harbor 태그 목록을 불러올 수 없습니다.');
        } else {
            this.harborError.set(data?.message || 'Harbor 태그 목록을 불러올 수 없습니다.');
        }
        this.harborTagsBusy.set(false);
        await this.service.render();
    }

    public async loadLocalDetail(nodeId: string, silent: boolean = false) {
        if (!nodeId) return;
        this.localBusy.set(true);
        this.selectedNodeId.set(nodeId);
        this.selectedLocalItems.set([]);
        const { code, data } = await wiz.call('local_detail', { node_id: nodeId });
        if (code === 200) {
            this.localDetail.set(data);
            this.localSummaryByNode.set({
                ...this.localSummaryByNode(),
                [nodeId]: data.summary || { image_count: 0, used_count: 0, unused_count: 0 },
            });
        } else if (!silent) {
            await this.alert(data?.message || '서버 로컬 이미지를 불러올 수 없습니다.');
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

    public selectedNodeSummary() {
        const nodeId = this.selectedNodeId();
        const cached = this.localSummaryByNode()?.[nodeId] || { image_count: 0, used_count: 0, unused_count: 0 };
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

    public isLocalImageSelected(item: any) {
        return this.selectedLocalItems().includes(this.localImageKey(item));
    }

    public toggleLocalImageSelection(item: any, checked: boolean) {
        const key = this.localImageKey(item);
        const items = new Set(this.selectedLocalItems());
        if (checked) items.add(key);
        else items.delete(key);
        this.selectedLocalItems.set(Array.from(items));
    }

    public toggleAllLocalImages(checked: boolean) {
        if (!checked) {
            this.selectedLocalItems.set([]);
            return;
        }
        this.selectedLocalItems.set(this.filteredLocalImages().map((item: any) => this.localImageKey(item)).filter((item: string) => item));
    }

    public allVisibleLocalImagesSelected() {
        const visible = this.filteredLocalImages();
        if (!visible.length) return false;
        const selected = new Set(this.selectedLocalItems());
        return visible.every((item: any) => selected.has(this.localImageKey(item)));
    }

    public selectedLocalImageCount() {
        return this.selectedLocalItems().length;
    }

    public selectedLocalDeleteItems() {
        const selected = new Set(this.selectedLocalItems());
        return (this.localDetail()?.images || [])
            .filter((item: any) => selected.has(this.localImageKey(item)))
            .map((item: any) => ({ image_ref: item.remove_ref }));
    }

    private compareLocalImages(left: any, right: any) {
        switch (this.localSort()) {
            case 'size_asc':
                return this.numberValue(left.size_bytes) - this.numberValue(right.size_bytes);
            case 'size_desc':
                return this.numberValue(right.size_bytes) - this.numberValue(left.size_bytes);
            case 'created_asc':
                return this.dateValue(left.created_at) - this.dateValue(right.created_at);
            case 'created_desc':
                return this.dateValue(right.created_at) - this.dateValue(left.created_at);
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
            { value: 'created_desc', label: '생성 최신 순' },
            { value: 'created_asc', label: '생성 오래된 순' },
        ];
    }

    public async deleteHarborTag(item: any) {
        const ok = await this.confirm(`${item.repository_name}:${item.tag} 태그를 Harbor에서 삭제합니다.`, 'Harbor 삭제');
        if (!ok) return;
        this.harborBusy.set(true);
        const { code, data } = await wiz.call('delete_harbor', {
            project_name: this.selectedProject(),
            repository_name: item.repository_name,
            digest: item.digest,
        });
        if (code === 200) {
            this.harborTags.set(data.tags || []);
            this.selectedHarborItems.set([]);
            await this.alert('Harbor 이미지를 삭제했습니다.', 'success');
        } else {
            await this.alert(data?.message || 'Harbor 이미지를 삭제할 수 없습니다.');
        }
        this.harborBusy.set(false);
        await this.service.render();
    }

    public async deleteSelectedHarborTags() {
        const items = this.selectedHarborDeleteItems();
        if (!items.length) return;
        const ok = await this.confirm(`선택한 Harbor 이미지 ${items.length}개를 삭제합니다.`, 'Harbor 삭제');
        if (!ok) return;
        this.harborBusy.set(true);
        const { code, data } = await wiz.call('delete_harbor', {
            project_name: this.selectedProject(),
            repository_name: this.selectedRepository(),
            items,
        });
        if (code === 200) {
            this.harborTags.set(data.tags || []);
            this.selectedHarborItems.set([]);
            await this.alert('선택한 Harbor 이미지를 삭제했습니다.', 'success');
        } else {
            await this.alert(data?.message || 'Harbor 이미지를 삭제할 수 없습니다.');
        }
        this.harborBusy.set(false);
        await this.service.render();
    }

    public async deleteHarborProject() {
        if (!this.selectedProject()) return;
        const ok = await this.confirm(`${this.selectedProject()} Harbor 프로젝트를 통째로 삭제합니다.`, '프로젝트 삭제');
        if (!ok) return;
        this.harborBusy.set(true);
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
            await this.alert('Harbor 프로젝트를 삭제했습니다.', 'success');
        } else {
            await this.alert(data?.message || 'Harbor 프로젝트를 삭제할 수 없습니다.');
        }
        this.harborBusy.set(false);
        await this.service.render();
    }

    public async deleteHarborRepository(item: any) {
        const repositoryName = this.harborRepositoryKey(item);
        if (!repositoryName) return;
        const ok = await this.confirm(`${repositoryName} 이미지를 Harbor 프로젝트에서 삭제합니다.`, 'Harbor 삭제');
        if (!ok) return;
        this.harborBusy.set(true);
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
            await this.alert('Harbor 이미지를 삭제했습니다.', 'success');
        } else {
            await this.alert(data?.message || 'Harbor 이미지를 삭제할 수 없습니다.');
        }
        this.harborBusy.set(false);
        await this.service.render();
    }

    public async deleteSelectedHarborRepositories() {
        const items = this.selectedHarborRepositoryItems();
        if (!items.length) return;
        const ok = await this.confirm(`선택한 Harbor 이미지 ${items.length}개를 삭제합니다.`, 'Harbor 삭제');
        if (!ok) return;
        this.harborBusy.set(true);
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
            await this.alert('선택한 Harbor 이미지를 삭제했습니다.', 'success');
        } else {
            await this.alert(data?.message || 'Harbor 이미지를 삭제할 수 없습니다.');
        }
        this.harborBusy.set(false);
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
            await this.alert('Harbor 프로젝트를 생성했습니다.', 'success');
        } else {
            await this.alert(data?.message || 'Harbor 프로젝트를 생성할 수 없습니다.');
        }
        this.createProjectBusy.set(false);
        await this.service.render();
    }

    public async deleteLocalImage(item: any) {
        const label = item.repository && item.tag ? `${item.repository}:${item.tag}` : item.image_id;
        const ok = await this.confirm(`${label} 이미지를 이 서버 로컬 저장소에서 삭제합니다.`, '로컬 삭제');
        if (!ok) return;
        this.localBusy.set(true);
        const { code, data } = await wiz.call('delete_local', {
            node_id: this.selectedNodeId(),
            image_ref: item.remove_ref,
        });
        if (code === 200) {
            this.localDetail.set(data);
            this.localSummaryByNode.set({
                ...this.localSummaryByNode(),
                [this.selectedNodeId()]: data.summary || { image_count: 0, used_count: 0, unused_count: 0 },
            });
            this.selectedLocalItems.set(this.selectedLocalItems().filter((itemKey: string) => itemKey !== this.localImageKey(item)));
            await this.alert('로컬 이미지를 삭제했습니다.', 'success');
        } else {
            await this.alert(data?.message || '로컬 이미지를 삭제할 수 없습니다.');
        }
        this.localBusy.set(false);
        await this.service.render();
    }

    public async deleteSelectedLocalImages() {
        const items = this.selectedLocalDeleteItems();
        if (!items.length) return;
        const ok = await this.confirm(`선택한 로컬 이미지 ${items.length}개를 삭제합니다.`, '로컬 삭제');
        if (!ok) return;
        this.localBusy.set(true);
        const { code, data } = await wiz.call('delete_local', {
            node_id: this.selectedNodeId(),
            items,
        });
        if (code === 200) {
            this.localDetail.set(data);
            this.localSummaryByNode.set({
                ...this.localSummaryByNode(),
                [this.selectedNodeId()]: data.summary || { image_count: 0, used_count: 0, unused_count: 0 },
            });
            this.selectedLocalItems.set([]);
            await this.alert('선택한 로컬 이미지를 삭제했습니다.', 'success');
        } else {
            await this.alert(data?.message || '로컬 이미지를 삭제할 수 없습니다.');
        }
        this.localBusy.set(false);
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

    public formatBytes(value: any) {
        const size = Number(value || 0);
        if (!size) return '-';
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
