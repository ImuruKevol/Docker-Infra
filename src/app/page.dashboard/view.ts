import { computed, OnInit, signal } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    public stats = signal<any[]>([]);
    public recentItems = signal<any[]>([]);
    public loading = signal<boolean>(true);
    public signalCount = signal<number>(3);
    public signalStep = signal<number>(2);

    public totalPosts = computed(() => {
        const target = this.stats().find((stat: any) => stat.label === '전체 게시물');
        return Number(target?.value || 0);
    });

    public publishedPosts = computed(() => {
        const target = this.stats().find((stat: any) => stat.label === '공개 게시물');
        return Number(target?.value || 0);
    });

    public publishedRate = computed(() => {
        const total = this.totalPosts();
        if (total <= 0) return 0;
        return Math.round(this.publishedPosts() / total * 100);
    });

    public signalTotal = computed(() => this.signalCount() * this.signalStep());

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.service.auth.allow("/access");
        await this.load();
    }

    public async load() {
        this.loading.set(true);
        await this.service.render();

        const { code, data } = await wiz.call("overview");
        if (code === 200) {
            this.stats.set(data.stats || []);
            this.recentItems.set(data.recent || []);
        }

        this.loading.set(false);
        await this.service.render();
    }

    public async increaseSignalCount() {
        this.signalCount.update((value) => value + 1);
        await this.service.render();
    }

    public async decreaseSignalCount() {
        this.signalCount.update((value) => Math.max(0, value - 1));
        await this.service.render();
    }

    public async increaseSignalStep() {
        this.signalStep.update((value) => value + 1);
        await this.service.render();
    }

    public async decreaseSignalStep() {
        this.signalStep.update((value) => Math.max(1, value - 1));
        await this.service.render();
    }
}
