import { OnInit, Input, Output, EventEmitter, OnChanges } from '@angular/core';

export class Component implements OnInit, OnChanges {
    @Input() current: any = 1;
    @Input() start: any = 1;
    @Input() end: any = 1;
    @Input() maxlength: any = 10;
    @Output() pageMove = new EventEmitter<number>();

    public list: Array<number> = [];
    public currentPage = 1;
    public startPage = 1;
    public endPage = 1;
    public pageWindow = 10;

    public async ngOnInit() {
        this.Math = Math;
    }

    public async ngOnChanges() {
        this.build();
    }

    private numberValue(value: any, fallback: number) {
        const number = Number(value);
        if (!Number.isFinite(number) || number < 1) return fallback;
        return Math.floor(number);
    }

    private clamp(page: number) {
        return Math.min(Math.max(1, page), this.endPage);
    }

    private blockStart(page: number) {
        return Math.floor((Math.max(1, page) - 1) / this.pageWindow) * this.pageWindow + 1;
    }

    private build() {
        this.pageWindow = this.numberValue(this.maxlength, 10);
        this.endPage = Math.max(1, this.numberValue(this.end, 1));
        this.currentPage = this.clamp(this.numberValue(this.current, 1));
        const fallbackStart = this.blockStart(this.currentPage);
        this.startPage = Math.min(this.endPage, this.numberValue(this.start, fallbackStart));
        this.list = [];
        for (let i = 0; i < this.pageWindow; i++) {
            const page = this.startPage + i;
            if (page > this.endPage) break;
            this.list.push(page);
        }
    }

    public move(page: number) {
        this.pageMove.emit(this.clamp(Number(page || 1)));
    }
}
