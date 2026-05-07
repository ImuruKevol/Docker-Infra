import { ElementRef, EventEmitter, HostListener, Input, Output } from '@angular/core';

export class Component {
    @Input() items: any[] = [];
    @Input() value: any = '';
    @Input() placeholder: string = '선택하세요';
    @Input() searchPlaceholder: string = '검색';
    @Input() emptyText: string = '표시할 항목이 없습니다.';
    @Input() disabled: boolean = false;
    @Input() valueKey: string = 'value';
    @Input() labelKey: string = 'label';
    @Input() descriptionKey: string = 'description';
    @Input() badgeKey: string = 'badge';
    @Input() badgeClassKey: string = 'badgeClass';
    @Input() disabledKey: string = 'disabled';

    @Output() valueChange = new EventEmitter<any>();

    public open = false;
    public query = '';

    constructor(private elementRef: ElementRef) { }

    @HostListener('document:click', ['$event'])
    public handleDocumentClick(event: MouseEvent) {
        if (!this.open) return;
        if (this.elementRef.nativeElement.contains(event.target as Node)) return;
        this.close();
    }

    public toggle(event?: Event) {
        if (event) event.stopPropagation();
        if (this.disabled) return;
        this.open = !this.open;
        if (this.open) {
            setTimeout(() => {
                const input = this.elementRef.nativeElement.querySelector('[data-search-select-input]');
                if (input && typeof input.focus === 'function') input.focus();
            }, 0);
        } else {
            this.query = '';
        }
    }

    public close() {
        this.open = false;
        this.query = '';
    }

    public selectedItem() {
        return this.items.find((item: any) => this.itemValue(item) === this.value) || null;
    }

    public filteredItems() {
        const query = String(this.query || '').trim().toLowerCase();
        if (!query) return this.items || [];
        return (this.items || []).filter((item: any) => {
            const target = [
                this.itemLabel(item),
                this.itemDescription(item),
                this.itemBadge(item),
            ].join(' ').toLowerCase();
            return target.includes(query);
        });
    }

    public selectItem(item: any) {
        if (this.itemDisabled(item)) return;
        this.valueChange.emit(this.itemValue(item));
        this.close();
    }

    public itemValue(item: any) {
        return item?.[this.valueKey];
    }

    public itemLabel(item: any) {
        return String(item?.[this.labelKey] || '').trim();
    }

    public itemDescription(item: any) {
        return String(item?.[this.descriptionKey] || '').trim();
    }

    public itemBadge(item: any) {
        return String(item?.[this.badgeKey] || '').trim();
    }

    public itemBadgeClass(item: any) {
        return String(item?.[this.badgeClassKey] || '').trim();
    }

    public itemDisabled(item: any) {
        return Boolean(item?.[this.disabledKey]);
    }
}
