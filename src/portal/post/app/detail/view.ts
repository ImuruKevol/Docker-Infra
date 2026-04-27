import { OnInit, OnDestroy } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import { Router, NavigationEnd } from '@angular/router';

export class Component implements OnInit, OnDestroy {
    public id: string = '';
    public tab: string = 'view';
    public data: any = null;
    public saving: boolean = false;
    public editorOptions: any = {};

    public tabs: any[] = [
        { key: 'view', labelKey: 'post.detail.tabs.view', icon: '📄' },
        { key: 'edit', labelKey: 'post.detail.tabs.edit', icon: '✏️' },
        { key: 'settings', labelKey: 'post.detail.tabs.settings', icon: '⚙️' },
    ];

    public categories: any[] = [
        { value: '공지사항', labelKey: 'post.category.notice' },
        { value: '가이드', labelKey: 'post.category.guide' },
        { value: '기술 블로그', labelKey: 'post.category.tech' },
        { value: '회의록', labelKey: 'post.category.minutes' },
        { value: '자유게시판', labelKey: 'post.category.free' },
    ];

    public statuses: any[] = [
        { value: 'draft', labelKey: 'post.status.draft' },
        { value: 'published', labelKey: 'post.status.published' },
        { value: 'archived', labelKey: 'post.status.archived' },
    ];

    private basePath: string = '/posts';
    private routerSub: any;
    private themeChangeHandler: any;
    private fallbackText: any = {
        'post.detail.sampleContent': '# 새 글 작성 예시\n\nMonaco Editor로 Markdown 콘텐츠를 작성해보세요.\n\n- 다크 모드 전환\n- ko/en 다국어 라벨\n- Angular 21 WIZ NgModule scope 예시',
        'post.detail.validationTitle': '제목을 입력해주세요.',
        'post.detail.saveSuccess': '저장되었습니다.',
        'post.detail.saveFail': '저장에 실패했습니다.',
        'post.detail.deleteTitle': '게시물 삭제',
        'post.detail.deleteMessage': '정말 이 게시물을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.',
        'post.detail.deleteAction': '삭제',
        'post.detail.cancel': '취소'
    };

    constructor(public service: Service, private router: Router) {
        this.id = WizRoute.segment.id;
        this.tab = WizRoute.segment.tab || 'view';
        this.refreshEditorOptions();
    }

    public async ngOnInit() {
        await this.service.init();
        this.refreshEditorOptions();
        this.themeChangeHandler = async () => {
            this.refreshEditorOptions();
            await this.service.render();
        };
        this.service.event.bind('theme.change', this.themeChangeHandler);

        this.routerSub = this.router.events.subscribe(async (event) => {
            if (event instanceof NavigationEnd) {
                const newId = WizRoute.segment.id;
                const newTab = WizRoute.segment.tab || 'view';

                if (newId && newId !== this.id) {
                    this.id = newId;
                    this.tab = newTab;
                    await this.load();
                } else if (newTab !== this.tab) {
                    this.tab = newTab;
                    await this.service.render();
                }
            }
        });

        if (!WizRoute.segment.tab) {
            this.service.href(`${this.basePath}/${this.id}/view`);
            return;
        }

        await this.load();
    }

    public ngOnDestroy() {
        if (this.routerSub) this.routerSub.unsubscribe();
        if (this.themeChangeHandler) this.service.event.unbind('theme.change', this.themeChangeHandler);
    }

    public isNewPost() {
        return this.id === 'new';
    }

    public isDarkMode() {
        return this.service.theme && this.service.theme.isDark();
    }

    public async load() {
        if (this.isNewPost()) {
            this.data = {
                title: '',
                content: await this.translate('post.detail.sampleContent'),
                category: '',
                status: 'draft'
            };
            this.tab = 'edit';
            await this.service.render();
            return;
        }

        this.data = null;
        await this.service.render();

        const { code, data } = await wiz.call("get", { id: this.id });
        if (code !== 200) {
            this.service.href(this.basePath);
            return;
        }
        this.data = data;
        await this.service.render();
    }

    public async save() {
        if (!this.data.title) {
            await this.service.modal.error(await this.translate('post.detail.validationTitle'));
            return;
        }

        this.saving = true;
        await this.service.render();

        let payload = JSON.stringify(this.data);
        const { code, data } = await wiz.call("save", { data: payload });

        await this.service.sleep(800);
        this.saving = false;

        if (code === 200) {
            await this.service.modal.success(await this.translate('post.detail.saveSuccess'));
            if (this.isNewPost() && data.id) {
                this.id = data.id;
                this.service.href(`${this.basePath}/${this.id}/view`);
            }
        } else {
            await this.service.modal.error(data || await this.translate('post.detail.saveFail'));
        }

        await this.service.render();
    }

    public async remove() {
        let res = await this.service.modal.show({
            title: await this.translate('post.detail.deleteTitle'),
            message: await this.translate('post.detail.deleteMessage'),
            action: await this.translate('post.detail.deleteAction'),
            cancel: await this.translate('post.detail.cancel'),
            actionBtn: "error",
            status: "error"
        });
        if (!res) return;

        const { code } = await wiz.call("delete", { id: this.id });
        if (code === 200) {
            this.service.href(this.basePath);
        }
    }

    private refreshEditorOptions() {
        this.editorOptions = {
            language: 'markdown',
            theme: this.isDarkMode() ? 'vs-dark' : 'vs',
            automaticLayout: true,
            minimap: { enabled: false },
            wordWrap: 'on',
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            fontSize: 13,
            tabSize: 2,
            padding: { top: 12, bottom: 12 },
            renderWhitespace: 'selection'
        };
    }

    private async translate(key: string) {
        if (!this.service.lang) return this.fallbackText[key] || key;
        const value = await this.service.lang.translate(key);
        if (!value || value === key) return this.fallbackText[key] || key;
        return value;
    }
}
