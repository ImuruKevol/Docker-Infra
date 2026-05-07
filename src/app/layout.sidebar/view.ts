import { OnInit, signal } from '@angular/core';
import { HostListener } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    public authReady = signal<boolean>(false);

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.enforceSession();
    }

    private async enforceSession() {
        if (this.service.auth?.check?.() !== true) {
            location.href = '/access';
            return;
        }
        this.authReady.set(true);
        await this.service.render();
    }

    @HostListener('document:click')
    public clickout() {
        this.service.status.toggle('navbar', false);
    }
}
