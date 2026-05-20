import { ChangeDetectorRef, ElementRef, EventEmitter, HostListener, Input, OnDestroy, Output } from '@angular/core';

export class Component implements OnDestroy {
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
    public dropdownPanelStyle: any = {};
    public dropdownListMaxHeight = 288;

    private readonly dropdownGap = 8;
    private readonly viewportPadding = 12;
    private readonly preferredPanelHeight = 360;
    private readonly panelHeaderHeight = 66;
    private scrollListenerBound = false;
    private readonly scrollListener = () => {
        if (this.open) this.updateDropdownPosition();
    };

    constructor(private elementRef: ElementRef, private cdr: ChangeDetectorRef) { }

    public ngOnDestroy() {
        this.unbindScrollListener();
    }

    @HostListener('document:click', ['$event'])
    public handleDocumentClick(event: MouseEvent) {
        if (!this.open) return;
        if (this.elementRef.nativeElement.contains(event.target as Node)) return;
        this.close();
    }

    @HostListener('window:resize')
    public handleWindowResize() {
        if (!this.open) return;
        this.updateDropdownPosition();
    }

    public stopEvent(event?: Event, preventDefault: boolean = false) {
        if (!event) return;
        if (preventDefault) event.preventDefault();
        event.stopPropagation();
        const nativeEvent: any = event;
        if (typeof nativeEvent.stopImmediatePropagation === 'function') nativeEvent.stopImmediatePropagation();
    }

    public toggle(event?: Event) {
        this.stopEvent(event);
        if (this.disabled) return;
        this.open = !this.open;
        if (this.open) {
            this.updateDropdownPosition();
            this.bindScrollListener();
            setTimeout(() => {
                this.updateDropdownPosition();
                const input = this.elementRef.nativeElement.querySelector('[data-search-select-input]');
                if (input && typeof input.focus === 'function') input.focus();
                this.cdr.detectChanges();
            }, 0);
        } else {
            this.close();
        }
    }

    public close() {
        this.open = false;
        this.query = '';
        this.dropdownPanelStyle = {};
        this.dropdownListMaxHeight = 288;
        this.unbindScrollListener();
    }

    private bindScrollListener() {
        if (this.scrollListenerBound || typeof document === 'undefined') return;
        document.addEventListener('scroll', this.scrollListener, true);
        this.scrollListenerBound = true;
    }

    private unbindScrollListener() {
        if (!this.scrollListenerBound || typeof document === 'undefined') return;
        document.removeEventListener('scroll', this.scrollListener, true);
        this.scrollListenerBound = false;
    }

    public updateDropdownPosition() {
        if (typeof window === 'undefined') return;
        const hostRect = this.elementRef.nativeElement.getBoundingClientRect();
        const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 800;
        const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 1024;
        const maxWidth = Math.max(160, viewportWidth - (this.viewportPadding * 2));
        const width = Math.min(Math.max(hostRect.width, 160), maxWidth);
        const left = Math.min(
            Math.max(hostRect.left, this.viewportPadding),
            viewportWidth - this.viewportPadding - width,
        );
        const spaceBelow = viewportHeight - hostRect.bottom - this.viewportPadding - this.dropdownGap;
        const spaceAbove = hostRect.top - this.viewportPadding - this.dropdownGap;
        const openUp = spaceBelow < 260 && spaceAbove > spaceBelow;
        const availableSpace = Math.max(0, openUp ? spaceAbove : spaceBelow);
        const panelMaxHeight = Math.max(180, Math.min(this.preferredPanelHeight, availableSpace || this.preferredPanelHeight));
        const top = openUp
            ? Math.max(this.viewportPadding, hostRect.top - this.dropdownGap - panelMaxHeight)
            : Math.min(hostRect.bottom + this.dropdownGap, viewportHeight - this.viewportPadding - panelMaxHeight);

        this.dropdownPanelStyle = {
            position: 'fixed',
            left: `${Math.max(this.viewportPadding, left)}px`,
            top: `${Math.max(this.viewportPadding, top)}px`,
            width: `${width}px`,
            maxHeight: `${panelMaxHeight}px`,
            zIndex: '80',
        };
        this.dropdownListMaxHeight = Math.max(112, panelMaxHeight - this.panelHeaderHeight);
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

    public selectItem(item: any, event?: Event) {
        this.stopEvent(event, true);
        if (this.itemDisabled(item)) return;
        this.value = this.itemValue(item);
        this.valueChange.emit(this.value);
        this.close();
        this.cdr.detectChanges();
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
