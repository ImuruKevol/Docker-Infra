import { OnInit } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    public loading: boolean = false;
    public members: any[] = [];

    public search: any = {
        text: "",
        role: ""
    };

    public roles: string[] = ['admin', 'editor', 'viewer'];

    public showInviteModal: boolean = false;
    public inviteData: any = { email: '', role: 'viewer' };

    public showDetailModal: boolean = false;
    public detailMember: any = null;
    public detailLoading: boolean = false;

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.service.auth.allow("/access");
        await this.load();
    }

    public async load() {
        this.loading = true;
        await this.service.render();

        const { code, data } = await wiz.call("list", this.search);
        if (code === 200) {
            this.members = data || [];
        }

        this.loading = false;
        await this.service.render();
    }

    public async filterByRole(role: string) {
        this.search.role = this.search.role === role ? "" : role;
        await this.load();
    }

    public async openInvite() {
        this.inviteData = { email: '', role: 'viewer' };
        this.showInviteModal = true;
        await this.service.render();
    }

    public async invite() {
        if (!this.inviteData.email) {
            await this.service.modal.error("이메일을 입력해주세요.");
            return;
        }

        const { code, data } = await wiz.call("invite", this.inviteData);
        if (code === 200) {
            await this.service.modal.success("초대가 완료되었습니다.");
            this.showInviteModal = false;
            await this.load();
        } else {
            await this.service.modal.error(data || "초대에 실패했습니다.");
        }
    }

    public async removeMember(member: any) {
        let res = await this.service.modal.error(`${member.name}님을 멤버에서 제거하시겠습니까?`, "취소", "제거");
        if (!res) return;

        const { code } = await wiz.call("remove", { id: member.id });
        if (code === 200) {
            await this.load();
        }
    }

    public roleClass(role: string) {
        switch (role) {
            case 'admin': return 'bg-purple-100 text-purple-700';
            case 'editor': return 'bg-blue-100 text-blue-700';
            case 'viewer': return 'bg-gray-100 text-gray-600';
            default: return 'bg-gray-100 text-gray-600';
        }
    }

    public async openDetail(member: any) {
        this.detailMember = member;
        this.showDetailModal = true;
        this.detailLoading = true;
        await this.service.render();

        const { code, data } = await wiz.call("detail", { id: member.id });
        if (code === 200) {
            this.detailMember = data;
        }

        this.detailLoading = false;
        await this.service.render();
    }

    public closeDetail() {
        this.showDetailModal = false;
        this.detailMember = null;
        this.detailLoading = false;
    }
}
