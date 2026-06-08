import { Component, OnDestroy, OnInit, ChangeDetectorRef } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { Router, NavigationEnd } from '@angular/router';
import { Service } from '@wiz/libs/portal/season/service';
import { TranslateService } from '@ngx-translate/core';

interface AgentMessage {
    id: string;
    role: 'user' | 'assistant' | 'status' | 'error';
    content: string;
    at: string;
    provider?: string;
    duration_ms?: number;
    suggested_actions?: AgentSuggestedAction[];
    __agentProgressMode?: boolean;
    __agentProgressLines?: string[];
    __agentAnswerStarted?: boolean;
    __agentAnswerText?: string;
}

interface AgentSuggestedAction {
    label: string;
    prompt: string;
    reason?: string;
}

interface AgentHistoryItem {
    id: string;
    session_id?: string;
    provider_session_id?: string;
    session_title?: string;
    turn_index?: number;
    turn_count?: number;
    session_started_at?: string;
    session_last_at?: string;
    agent_type: string;
    agent_label: string;
    model: string;
    status: 'succeeded' | 'failed';
    request_message: string;
    response_answer: string;
    response_summary: string;
    error_code?: string;
    error_message?: string;
    created_at: string;
    ip?: string;
    browser_label?: string;
    platform?: string;
    route?: string;
    context_summary?: string;
    duration_ms?: number;
    metadata?: any;
    response_payload?: any;
    turns?: AgentHistoryItem[];
}

interface AgentApiOperation {
    operation_id: string;
    menu: string;
    method: string;
    path: string;
    safety: 'read' | 'write' | 'destructive';
    summary: string;
    required?: string[];
}

interface AgentTodoItem {
    id: string;
    title: string;
    prompt: string;
    reason?: string;
    status: 'queued' | 'running' | 'succeeded' | 'failed' | 'blocked';
    detail?: string;
}

@Component({
    selector: 'app-root',
    templateUrl: './app.component.html',
    styleUrls: ['./app.component.scss']
})
export class AppComponent implements OnInit, OnDestroy {
    public agentWidgetOpen = false;
    public agentStatusLoaded = false;
    public agentAvailable = false;
    public agentStatusMessage = '';
    public agentLabel = 'AI Agent';
    public agentInput = '';
    public agentSending = false;
    public agentStreamStatus = '';
    public agentDockWidth = 420;
    public agentMessages: AgentMessage[] = [];
    public agentPanelMode: 'chat' | 'history' = 'chat';
    public agentType = '';
    public agentSessionId = '';
    public agentTodos: AgentTodoItem[] = [];
    public agentTodoSummary = '';
    public agentContextSummary = '';
    public agentModalContext: any = { open: false };
    public agentRecommendations: string[] = [];
    public agentHistoryLoading = false;
    public agentHistoryDeleting = false;
    public agentHistoryItems: AgentHistoryItem[] = [];
    public agentHistorySelected: AgentHistoryItem | null = null;
    public agentHistoryTotal = 0;
    public agentHistoryPageSize = 20;
    public agentHistoryOffset = 0;
    public agentHistoryNotice = '';
    public agentHistoryCopiedActionIndex = -1;
    public agentHistoryFilters: any = {
        start_date: '',
        end_date: '',
        q: ''
    };
    public agentApiOperations: AgentApiOperation[] = [];

    private agentEvents: any[] = [];
    private agentRefCounter = 0;
    private routeSub: any = null;
    private mutationObserver: MutationObserver | null = null;
    private clickHandler: any = null;
    private inputHandler: any = null;
    private submitHandler: any = null;
    private focusHandler: any = null;
    private codeCopyHandler: any = null;
    private contextRefreshTimer: any = null;
    private resizeMoveHandler: any = null;
    private resizeEndHandler: any = null;
    private agentHistoryCopyTimer: any = null;
    private agentSelectionRenderTimer: any = null;
    private agentContextSignature = '';
    private agentSessionMap: Record<string, string> = {};
    private readonly agentDockWidthStorageKey = 'docker-infra.ai-agent.dock-width';

    constructor(
        public service: Service,
        public router: Router,
        public ref: ChangeDetectorRef,
        public translate: TranslateService,
        private sanitizer: DomSanitizer
    ) {
        window['MonacoEnvironment'] = {
            getWorkerUrl: function (moduleId: string, label: string) {
                return `/lib/vs/base/worker/workerMain.js`;
            }
        };
    }

    public async ngOnInit() {
        this.restoreAgentDockWidth();
        await this.service.init(this);
        this.setupAgentContextTrackers();
        this.routeSub = this.router.events.subscribe((event: any) => {
            if (event instanceof NavigationEnd) {
                this.recordAgentEvent('navigation', { url: event.urlAfterRedirects || event.url });
                this.refreshAgentContextView();
            }
        });
        await this.loadAgentStatus();
        this.refreshAgentContextView();
    }

    public ngOnDestroy() {
        if (this.routeSub) this.routeSub.unsubscribe();
        if (this.mutationObserver) this.mutationObserver.disconnect();
        if (this.clickHandler) document.removeEventListener('click', this.clickHandler, true);
        if (this.inputHandler) document.removeEventListener('input', this.inputHandler, true);
        if (this.submitHandler) document.removeEventListener('submit', this.submitHandler, true);
        if (this.focusHandler) document.removeEventListener('focusin', this.focusHandler, true);
        if (this.codeCopyHandler) document.removeEventListener('click', this.codeCopyHandler, true);
        if (this.contextRefreshTimer) window.clearTimeout(this.contextRefreshTimer);
        if (this.agentSelectionRenderTimer) window.clearTimeout(this.agentSelectionRenderTimer);
        this.resetAgentHistoryCopyState();
        this.stopAgentResize();
    }

    public agentVisible() {
        return true;
    }

    public agentReady() {
        return this.agentStatusLoaded && this.agentAvailable;
    }

    public agentHistoryDetailDockVisible() {
        return this.agentVisible() && this.agentWidgetOpen && this.agentPanelMode === 'history' && this.agentReady() && Boolean(this.agentHistorySelected);
    }

    public agentStatusLoading() {
        return !this.agentStatusLoaded;
    }

    public agentUnavailable() {
        return this.agentStatusLoaded && !this.agentAvailable;
    }

    public agentHeaderStatusLabel() {
        if (this.agentStatusLoading()) return '상태 확인 중';
        if (this.agentUnavailable()) return this.agentStatusMessage || '사용할 수 없음';
        return this.agentStatusMessage || '준비됨';
    }

    public agentSessionLabel() {
        const sessionId = this.ensureAgentSession();
        const suffix = sessionId ? sessionId.slice(0, 8) : '준비';
        const agent = this.agentType ? this.agentType.replace(/_/g, ' ') : 'agent';
        return `${agent} · ${suffix}`;
    }

    public agentStateTitle() {
        if (this.agentStatusLoading()) return 'AI Agent 상태를 확인하는 중입니다.';
        return 'AI Agent를 사용할 수 없습니다.';
    }

    public agentStateMessage() {
        if (this.agentStatusLoading()) return '필요한 설정과 실행 상태를 불러오고 있습니다.';
        return this.agentStatusMessage || '시스템 설정에서 AI Agent를 먼저 사용 설정하세요.';
    }

    public async toggleAgentWidget() {
        this.agentWidgetOpen = !this.agentWidgetOpen;
        this.refreshAgentContextView();
        if (this.agentWidgetOpen && this.agentPanelMode === 'history' && this.agentReady()) {
            await this.loadAgentHistory();
        }
        await this.renderAgentView();
        this.scrollAgentMessages();
    }

    public async closeAgentWidget() {
        this.agentWidgetOpen = false;
        await this.renderAgentView();
    }

    public async newAgentSession() {
        if (this.agentSending) return;
        const sessionId = this.createAgentSessionId();
        this.setAgentSession(this.activeAgentKey(), sessionId);
        this.agentMessages = [];
        this.agentInput = '';
        this.agentStreamStatus = '';
        this.agentTodos = [];
        this.agentTodoSummary = '';
        this.agentHistorySelected = null;
        this.resetAgentHistoryCopyState();
        await this.renderAgentView();
        this.focusAgentInput();
    }

    public async showAgentChat() {
        this.agentPanelMode = 'chat';
        this.refreshAgentContextView();
        await this.renderAgentView();
        this.scrollAgentMessages();
    }

    public async showAgentHistory() {
        if (!this.agentReady()) {
            this.agentPanelMode = 'chat';
            await this.renderAgentView();
            return;
        }
        this.agentPanelMode = 'history';
        await this.loadAgentHistory();
    }

    public agentMessageClass(message: AgentMessage) {
        return `ai-agent-message ai-agent-message-${message.role}`;
    }

    public trackAgentMessage(index: number, message: AgentMessage) {
        return message.id;
    }

    public agentMessageHtml(message: AgentMessage): SafeHtml {
        return this.trustAgentMarkdown(message?.content || '');
    }

    public agentMessageActions(message: AgentMessage) {
        return (message?.suggested_actions || []).filter((item) => item && item.label && item.prompt);
    }

    public agentMessageDurationLabel(message: AgentMessage) {
        if (!message || !['assistant', 'error'].includes(message.role)) return '';
        return this.agentDurationLabel(message.duration_ms);
    }

    public agentConversationEmpty() {
        return this.agentMessages.length === 0 && !this.agentSending;
    }

    public agentTodoVisible() {
        return this.agentReady() && this.agentPanelMode === 'chat' && this.agentTodos.length > 0;
    }

    public trackAgentTodo(index: number, todo: AgentTodoItem) {
        return todo.id || index;
    }

    public agentTodoIcon(todo: AgentTodoItem) {
        if (todo?.status === 'running') return 'fa-solid fa-circle-notch fa-spin';
        if (todo?.status === 'succeeded') return 'fa-solid fa-check';
        if (todo?.status === 'failed') return 'fa-solid fa-xmark';
        if (todo?.status === 'blocked') return 'fa-solid fa-lock';
        return 'fa-regular fa-circle';
    }

    public agentTodoStatusLabel(todo: AgentTodoItem) {
        const labels: any = {
            queued: '대기',
            running: '진행',
            succeeded: '완료',
            failed: '실패',
            blocked: '확인 필요',
        };
        return labels[todo?.status || 'queued'] || '대기';
    }

    public startAgentResize(event: MouseEvent) {
        event.preventDefault();
        event.stopPropagation();
        this.stopAgentResize();
        this.resizeMoveHandler = (moveEvent: MouseEvent) => {
            const nextWidth = window.innerWidth - moveEvent.clientX;
            this.agentDockWidth = this.clampAgentDockWidth(nextWidth);
            this.ref.detectChanges();
        };
        this.resizeEndHandler = () => this.stopAgentResize(true);
        document.addEventListener('mousemove', this.resizeMoveHandler);
        document.addEventListener('mouseup', this.resizeEndHandler, { once: true });
    }

    public async useAgentRecommendation(question: string) {
        await this.sendAgentMessage(question);
    }

    public async runAgentSuggestedAction(action: AgentSuggestedAction) {
        const prompt = this.suggestedActionPrompt(action);
        if (!prompt || this.agentSending) return;
        await this.sendAgentMessage(prompt);
    }

    public async stageAgentSuggestedAction(action: AgentSuggestedAction) {
        const prompt = this.suggestedActionPrompt(action);
        if (!prompt) return;
        this.agentInput = prompt;
        this.agentPanelMode = 'chat';
        await this.renderAgentView();
        this.focusAgentInput();
    }

    public async loadAgentHistory(resetPage: boolean = false) {
        if (resetPage) this.agentHistoryOffset = 0;
        this.agentHistoryLoading = true;
        this.agentHistoryNotice = '';
        try {
            const payload = await this.agentApi('history/sessions', {
                ...this.agentHistoryRequestFilters(),
                limit: this.agentHistoryPageSize,
                offset: this.agentHistoryOffset
            });
            this.agentHistoryItems = Array.isArray(payload?.items) ? payload.items : [];
            this.agentHistoryTotal = Number(payload?.total || this.agentHistoryItems.length || 0);
            this.agentHistoryPageSize = Math.max(1, Number(payload?.limit || this.agentHistoryPageSize || 20));
            this.agentHistoryOffset = Math.max(0, Number(payload?.offset || this.agentHistoryOffset || 0));
            if (this.agentHistoryItems.length === 0 && this.agentHistoryTotal > 0 && this.agentHistoryOffset >= this.agentHistoryTotal) {
                this.agentHistoryOffset = Math.max(0, Math.floor((this.agentHistoryTotal - 1) / this.agentHistoryPageSize) * this.agentHistoryPageSize);
                await this.loadAgentHistory();
                return;
            }
            if (this.agentHistorySelected && !this.agentHistoryItems.some((item) => item.id === this.agentHistorySelected?.id)) {
                this.agentHistorySelected = null;
            }
        } catch (error: any) {
            this.agentHistoryNotice = error?.message || 'AI Agent 히스토리를 불러오지 못했습니다.';
        } finally {
            this.agentHistoryLoading = false;
            await this.renderAgentView();
        }
    }

    public agentHistoryRangeLabel() {
        if (this.agentHistoryTotal <= 0) return '0세션';
        const start = this.agentHistoryOffset + 1;
        const end = Math.min(this.agentHistoryOffset + this.agentHistoryItems.length, this.agentHistoryTotal);
        return `${start}-${end} / ${this.agentHistoryTotal}세션`;
    }

    public agentHistoryCurrentPage() {
        return Math.floor(this.agentHistoryOffset / this.agentHistoryPageSize) + 1;
    }

    public agentHistoryTotalPages() {
        return Math.max(1, Math.ceil(this.agentHistoryTotal / this.agentHistoryPageSize));
    }

    public agentHistoryHasPrevious() {
        return this.agentHistoryOffset > 0;
    }

    public agentHistoryHasNext() {
        return this.agentHistoryOffset + this.agentHistoryPageSize < this.agentHistoryTotal;
    }

    public async moveAgentHistoryPage(direction: -1 | 1) {
        if (this.agentHistoryLoading) return;
        const nextOffset = this.agentHistoryOffset + (direction * this.agentHistoryPageSize);
        if (nextOffset < 0 || nextOffset >= this.agentHistoryTotal) return;
        this.agentHistoryOffset = nextOffset;
        await this.loadAgentHistory();
    }

    public async selectAgentHistory(item: AgentHistoryItem) {
        this.agentHistorySelected = item;
        this.resetAgentHistoryCopyState();
        try {
            this.agentHistorySelected = await this.loadAgentHistorySession(item);
        } catch (error: any) {
            this.agentHistoryNotice = error?.message || '세션 히스토리 상세를 불러오지 못했습니다.';
        }
        await this.renderAgentView();
    }

    public async continueAgentHistory(item: AgentHistoryItem, event?: Event) {
        if (event) event.stopPropagation();
        if (!item || this.agentSending) return;
        this.agentHistoryNotice = '';
        try {
            const history = await this.loadAgentHistorySession(item);
            const sessionId = this.normalizeSessionId(history?.session_id || item?.session_id || item?.id);
            const messages = this.agentHistoryChatMessages(history);
            if (!sessionId || messages.length === 0) {
                this.agentHistoryNotice = '이어갈 세션 대화가 없습니다.';
                await this.renderAgentView();
                return;
            }
            this.setAgentSession(this.activeAgentKey(), sessionId);
            this.agentMessages = messages;
            this.agentInput = '';
            this.agentStreamStatus = '';
            this.agentTodos = [];
            this.agentTodoSummary = '';
            this.agentHistorySelected = null;
            this.resetAgentHistoryCopyState();
            this.agentPanelMode = 'chat';
            this.agentWidgetOpen = true;
            this.refreshAgentContextView();
            await this.renderAgentView();
            this.scrollAgentMessages();
            this.focusAgentInput();
        } catch (error: any) {
            this.agentHistoryNotice = error?.message || '세션 대화를 이어서 열지 못했습니다.';
            await this.renderAgentView();
        }
    }

    public closeAgentHistoryDetail(event?: Event) {
        if (event) event.stopPropagation();
        this.agentHistorySelected = null;
        this.resetAgentHistoryCopyState();
    }

    public async deleteAgentHistory(item: AgentHistoryItem, event?: Event) {
        if (event) event.stopPropagation();
        if (!item?.id || this.agentHistoryDeleting) return;
        if (!window.confirm('선택한 AI Agent 히스토리 1건을 삭제할까요?')) return;
        this.agentHistoryDeleting = true;
        this.agentHistoryNotice = '';
        try {
            const sessionId = this.normalizeText(item.session_id || item.id);
            const payload = await this.agentApi('history/session/delete', {
                session_id: sessionId,
                agent: item.agent_type || ''
            });
            this.agentHistoryItems = this.agentHistoryItems.filter((row) => row.id !== item.id);
            this.agentHistoryTotal = Math.max(0, this.agentHistoryTotal - 1);
            if (this.agentHistorySelected?.id === item.id) this.agentHistorySelected = null;
            this.agentHistoryNotice = `${Number(payload?.deleted_count || 0)}건의 세션 히스토리를 삭제했습니다.`;
        } catch (error: any) {
            this.agentHistoryNotice = error?.message || '히스토리를 삭제하지 못했습니다.';
        } finally {
            this.agentHistoryDeleting = false;
            await this.renderAgentView();
        }
    }

    public async deleteAgentHistoryRange() {
        if (this.agentHistoryDeleting) return;
        const filters = {
            start_date: this.normalizeText(this.agentHistoryFilters.start_date),
            end_date: this.normalizeText(this.agentHistoryFilters.end_date)
        };
        if (!filters.start_date && !filters.end_date) {
            this.agentHistoryNotice = '삭제할 시작일 또는 종료일을 입력하세요.';
            await this.renderAgentView();
            return;
        }
        const label = [filters.start_date || filters.end_date, filters.end_date || filters.start_date].filter(Boolean).join(' ~ ');
        if (!window.confirm(`${label} 기간의 AI Agent 히스토리를 삭제할까요?`)) return;
        this.agentHistoryDeleting = true;
        this.agentHistoryNotice = '';
        try {
            const payload = await this.agentApi('history/delete-range', filters);
            this.agentHistoryNotice = `${Number(payload?.deleted_count || 0)}건을 삭제했습니다.`;
            await this.loadAgentHistory(true);
        } catch (error: any) {
            this.agentHistoryNotice = error?.message || '기간 히스토리를 삭제하지 못했습니다.';
        } finally {
            this.agentHistoryDeleting = false;
            await this.renderAgentView();
        }
    }

    public async downloadAgentHistory(format: 'json' | 'csv' = 'json') {
        this.agentHistoryNotice = '';
        const params = new URLSearchParams();
        const filters = this.agentHistoryRequestFilters();
        for (const key of Object.keys(filters)) {
            const value = String(filters[key] || '').trim();
            if (value) params.set(key, value);
        }
        params.set('format', format);
        try {
            const response = await fetch(`/api/ai-agent/history/download?${params.toString()}`, {
                method: 'GET',
                credentials: 'same-origin'
            });
            if (!response.ok) throw new Error(`다운로드 요청 실패 (${response.status})`);
            const blob = await response.blob();
            const disposition = response.headers.get('Content-Disposition') || '';
            const filename = this.agentDownloadFilename(disposition, format);
            this.saveAgentBlob(blob, filename);
            this.agentHistoryNotice = '히스토리 다운로드를 시작했습니다.';
        } catch (error: any) {
            this.agentHistoryNotice = error?.message || '히스토리를 다운로드하지 못했습니다.';
        }
        await this.renderAgentView();
    }

    public agentHistoryStatusLabel(item: AgentHistoryItem) {
        return item?.status === 'failed' ? '실패' : '완료';
    }

    public agentHistoryStatusClass(item: AgentHistoryItem) {
        return item?.status === 'failed' ? 'ai-agent-history-status failed' : 'ai-agent-history-status succeeded';
    }

    public agentHistoryDate(value: string) {
        if (!value) return '';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleString('ko-KR', { hour12: false });
    }

    public agentHistoryPreview(item: AgentHistoryItem) {
        return this.normalizeText(item?.response_summary || item?.response_answer || item?.error_message || '').slice(0, 180);
    }

    public agentHistoryQuestion(item: AgentHistoryItem) {
        return this.normalizeText(item?.request_message || '').slice(0, 180);
    }

    public agentHistoryTitle(item: AgentHistoryItem) {
        return this.normalizeText(item?.session_title || '') || this.agentHistoryQuestion(item) || '제목 없음';
    }

    public agentHistoryMetaLine(item: AgentHistoryItem) {
        return [
            item?.agent_label || item?.agent_type || 'AI Agent',
            item?.model || '',
            item?.turn_count ? `${item.turn_count}턴` : '',
            item?.browser_label || '',
            item?.ip || '',
        ].filter(Boolean).join(' · ');
    }

    public agentHistoryRouteLine(item: AgentHistoryItem) {
        return [item?.context_summary || '', item?.route || ''].filter(Boolean).join(' · ');
    }

    public agentHistoryDurationLabel(item: AgentHistoryItem) {
        return this.agentDurationLabel(item?.duration_ms);
    }

    public agentHistoryResponseHtml(item: AgentHistoryItem): SafeHtml {
        return this.trustAgentMarkdown(this.agentHistoryResponseText(item));
    }

    public agentHistoryActions(item: AgentHistoryItem) {
        const payload = item?.response_payload || {};
        return this.normalizeAgentSuggestedActions(
            payload?.suggested_actions || payload?.next_actions || payload?.recommended_actions,
            payload?.follow_up
        );
    }

    public agentHistoryTurns(item: AgentHistoryItem) {
        const turns = Array.isArray(item?.turns) ? item.turns : [];
        return turns.length ? turns : (item ? [item] : []);
    }

    public agentHistoryActionCopied(index: number) {
        return this.agentHistoryCopiedActionIndex === index;
    }

    public async copyAgentHistoryAction(action: AgentSuggestedAction, index: number, event?: Event) {
        if (event) event.stopPropagation();
        const prompt = this.suggestedActionPrompt(action);
        if (!prompt) return;
        try {
            await this.copyAgentText(prompt);
            this.agentHistoryCopiedActionIndex = index;
            if (this.agentHistoryCopyTimer) window.clearTimeout(this.agentHistoryCopyTimer);
            this.agentHistoryCopyTimer = window.setTimeout(async () => {
                this.agentHistoryCopiedActionIndex = -1;
                this.agentHistoryCopyTimer = null;
                await this.renderAgentView();
            }, 1400);
            await this.renderAgentView();
        } catch (_error) {
            this.agentHistoryNotice = '다음 동작을 복사하지 못했습니다.';
            await this.renderAgentView();
        }
    }

    public async handleAgentEnter(event: KeyboardEvent) {
        if (event.shiftKey) return;
        event.preventDefault();
        await this.sendAgentMessage();
    }

    public async sendAgentMessage(forcedMessage?: string) {
        if (!this.agentReady()) {
            this.agentWidgetOpen = true;
            this.agentPanelMode = 'chat';
            await this.renderAgentView();
            return;
        }
        const message = String(forcedMessage || this.agentInput || '').trim();
        if (!message || this.agentSending) return;

        if (!forcedMessage) this.agentInput = '';
        this.agentSending = true;
        this.agentStreamStatus = '요청을 준비하는 중입니다.';
        const sessionId = this.ensureAgentSession();
        this.refreshAgentContextView();
        this.addAgentMessage('user', message);
        this.agentTodos = [];
        this.agentTodoSummary = '';
        await this.renderAgentView();
        this.scrollAgentMessages();

        try {
            const planPayload = this.buildAgentPayload(message, sessionId);
            const plan = await this.planAgentTodos(planPayload, message);
            this.agentTodoSummary = this.normalizeText(plan?.summary || '');
            this.agentTodos = this.normalizeAgentTodos(plan?.todos, message);
            await this.renderAgentView();

            for (const todo of this.agentTodos) {
                const ok = await this.runAgentTodo(todo, message, sessionId);
                if (!ok) break;
            }
        } catch (error: any) {
            this.addAgentMessage('error', error?.message || 'AI Agent 요청을 처리하지 못했습니다.');
        } finally {
            this.agentSending = false;
            this.agentStreamStatus = '';
            this.refreshAgentContextView();
            await this.renderAgentView();
            this.scrollAgentMessages();
        }
    }

    private buildAgentPayload(message: string, sessionId: string, excludeMessage?: AgentMessage, extra: any = {}) {
        return {
            message,
            session_id: sessionId,
            client_session_id: sessionId,
            session_title: this.agentSessionTitle(message),
            history: this.agentMessages
                .filter((item) => item !== excludeMessage && String(item.content || '').trim())
                .map((item) => ({ role: item.role, content: item.content, at: item.at })),
            screen: this.collectAgentScreenContext(),
            events: this.agentEvents,
            selection: {},
            ...extra,
        };
    }

    private async planAgentTodos(payload: any, fallbackMessage: string) {
        this.agentStreamStatus = 'TODO를 정리하는 중입니다.';
        try {
            return await this.agentApi('plan', payload);
        } catch (_error) {
            return {
                summary: '요청을 하나의 실행 TODO로 정리했습니다.',
                todos: [{ title: fallbackMessage, prompt: fallbackMessage, reason: '' }],
            };
        }
    }

    private normalizeAgentTodos(value: any, fallbackMessage: string): AgentTodoItem[] {
        const source = Array.isArray(value) ? value : [];
        const todos = source.slice(0, 5).map((item: any, index: number) => {
            const data = typeof item === 'string' ? { title: item, prompt: item } : (item || {});
            const title = this.normalizeText(data.title || data.label || data.name || data.summary || data.prompt || fallbackMessage);
            const prompt = this.normalizeText(data.prompt || data.message || data.instruction || title || fallbackMessage);
            const reason = this.normalizeText(data.reason || data.description || '');
            if (!title && !prompt) return null;
            return {
                id: this.normalizeText(data.id) || `todo-${Date.now()}-${index}`,
                title: title || prompt,
                prompt: prompt || title,
                reason,
                status: 'queued' as AgentTodoItem['status'],
                detail: '',
            };
        }).filter((item: AgentTodoItem | null) => !!item) as AgentTodoItem[];

        if (todos.length > 0) return todos;
        return [{
            id: `todo-${Date.now()}-0`,
            title: fallbackMessage,
            prompt: fallbackMessage,
            reason: '',
            status: 'queued',
            detail: '',
        }];
    }

    private async runAgentTodo(todo: AgentTodoItem, originalMessage: string, sessionId: string) {
        this.updateAgentTodo(todo.id, { status: 'running', detail: 'AI Agent 요청 중' });
        this.agentStreamStatus = todo.title;
        const assistantMessage = this.addAgentMessage('assistant', '', this.agentLabel);
        const requestStartedAt = this.agentNow();
        const requestId = this.createAgentRequestId();
        const payload = this.buildAgentPayload(todo.prompt || todo.title || originalMessage, sessionId, assistantMessage, {
            request_id: requestId,
            parent_message: originalMessage,
            todo: {
                id: todo.id,
                title: todo.title,
                prompt: todo.prompt,
                reason: todo.reason || '',
            },
        });
        await this.renderAgentView();
        this.scrollAgentMessages();

        try {
            let done = await this.streamAgentChat(payload, async (event: any) => {
                await this.applyAgentStreamEvent(event, assistantMessage);
            });
            let fallbackApplied = false;
            if (!this.agentMessageHasAnswerContent(assistantMessage) && !done?.answer && !done?.stream_incomplete) {
                done = await this.completeAgentChatFallback(payload, assistantMessage, requestStartedAt);
                fallbackApplied = true;
            }
            if (!this.agentMessageHasAnswerContent(assistantMessage) && done?.answer) {
                this.appendAgentAnswerText(assistantMessage, String(done.answer || '').trim());
            }
            this.applyAgentDuration(done, assistantMessage, requestStartedAt);
            if (!fallbackApplied) this.applyAgentSuggestedActions(done, assistantMessage);
            if (!this.agentMessageHasAnswerContent(assistantMessage)) {
                throw new Error(done?.stream_incomplete ? 'AI Agent 응답 스트림이 완료되지 않았고 표시할 본문이 없습니다.' : 'AI Agent 응답 본문이 비어 있습니다.');
            }
            if (done?.stream_incomplete) {
                this.updateAgentTodo(todo.id, { detail: '응답 스트림 종료 신호가 지연되어 표시된 내용까지만 반영했습니다.' });
            }
            if (done?.needs_confirmation) {
                this.updateAgentTodo(todo.id, { status: 'blocked', detail: '실행 전 구체적인 확인이 필요합니다.' });
                return false;
            }
            const actionsOk = await this.executeAgentActions(done?.client_actions || [], todo.prompt || originalMessage, todo.id);
            if (!actionsOk) return false;
            this.updateAgentTodo(todo.id, { status: 'succeeded', detail: '완료' });
            return true;
        } catch (error: any) {
            if (!this.agentMessageHasAnswerContent(assistantMessage)) {
                assistantMessage.role = 'error';
                this.setAgentErrorContent(assistantMessage, error?.message || 'AI Agent 호출에 실패했습니다.');
            }
            this.applyAgentDuration({}, assistantMessage, requestStartedAt);
            this.updateAgentTodo(todo.id, { status: 'failed', detail: error?.message || '실패' });
            return false;
        }
    }

    private async loadAgentStatus() {
        try {
            const payload = await this.agentApi('status');
            this.agentStatusLoaded = true;
            this.agentAvailable = Boolean(payload?.enabled);
            this.agentType = this.normalizeText(payload?.default_agent || this.agentType);
            this.ensureAgentSession();
            this.agentLabel = payload?.agent_label || 'AI Agent';
            this.agentStatusMessage = payload?.message || '';
            this.setAgentApiOperations(payload?.capabilities?.operations);
        } catch (error: any) {
            this.agentStatusLoaded = true;
            this.agentAvailable = false;
            this.agentStatusMessage = error?.message || 'AI Agent 상태를 확인할 수 없습니다.';
        }
        await this.loadAgentCapabilities();
        if (!this.agentAvailable && this.agentPanelMode === 'history') {
            this.agentPanelMode = 'chat';
        }
        if (this.agentWidgetOpen && this.agentPanelMode === 'history' && this.agentAvailable) {
            await this.loadAgentHistory();
        }
        await this.renderAgentView();
    }

    private async loadAgentCapabilities() {
        try {
            const payload = await this.agentApi('capabilities');
            this.setAgentApiOperations(payload?.operations);
        } catch (_error) {
            return;
        }
    }

    private setAgentApiOperations(value: any) {
        const operations = Array.isArray(value) ? value : [];
        this.agentApiOperations = operations
            .map((item: any) => ({
                operation_id: this.normalizeText(item?.operation_id || item?.operationId),
                menu: this.normalizeText(item?.menu),
                method: this.normalizeText(item?.method || 'POST').toUpperCase(),
                path: this.normalizeText(item?.path),
                safety: this.normalizeAgentApiSafety(item?.safety),
                summary: this.normalizeText(item?.summary),
                required: Array.isArray(item?.required) ? item.required.map((key: any) => this.normalizeText(key)).filter(Boolean) : [],
            }))
            .filter((item: AgentApiOperation) => item.operation_id && item.path);
    }

    private normalizeAgentApiSafety(value: any): AgentApiOperation['safety'] {
        const safety = this.normalizeText(value).toLowerCase();
        if (safety === 'destructive') return 'destructive';
        if (safety === 'write') return 'write';
        return 'read';
    }

    private async agentApi(path: string, payload?: any) {
        const options: RequestInit = { method: payload ? 'POST' : 'GET', credentials: 'same-origin' };
        if (payload) {
            const body = new URLSearchParams();
            for (const key of Object.keys(payload)) {
                const value = payload[key];
                body.set(key, typeof value === 'string' ? value : JSON.stringify(value));
            }
            options.headers = { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' };
            options.body = body.toString();
        }
        const response = await fetch(`/api/ai-agent/${path}`, options);
        const raw = await response.json().catch(() => ({}));
        const data = raw?.data || {};
        const code = Number(raw?.code || response.status || 500);
        if (!response.ok || code >= 400) {
            throw new Error(data?.message || raw?.message || `AI Agent API 오류 (${code})`);
        }
        return data;
    }

    private async completeAgentChatFallback(payload: any, assistantMessage: AgentMessage, requestStartedAt?: number) {
        this.agentStreamStatus = '스트림 응답을 동기 호출로 다시 확인하는 중입니다.';
        this.appendAgentProgressLine(assistantMessage, this.agentStreamStatus);
        await this.renderAgentView();
        const fallback = await this.agentApi('chat', payload);
        const answer = String(fallback?.answer || fallback?.message || '').trim();
        if (!answer) throw new Error('AI Agent 응답 본문이 비어 있습니다.');
        assistantMessage.role = 'assistant';
        assistantMessage.provider = 'AI Agent';
        this.appendAgentAnswerText(assistantMessage, answer);
        this.applyAgentSuggestedActions(fallback, assistantMessage);
        this.applyAgentDuration(fallback, assistantMessage, requestStartedAt);
        return fallback;
    }

    private async streamAgentChat(payload: any, onEvent: (event: any) => Promise<void>) {
        const body = new URLSearchParams();
        for (const key of Object.keys(payload || {})) {
            const value = payload[key];
            body.set(key, typeof value === 'string' ? value : JSON.stringify(value));
        }
        const response = await fetch('/api/ai-agent/stream', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
            body: body.toString()
        });
        if (!response.ok || !response.body) {
            throw new Error(`AI Agent 스트림 요청 실패 (${response.status})`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let donePayload: any = null;
        let sawDelta = false;
        let sawProgress = false;
        const startedAt = Date.now();
        let lastEventAt = Date.now();
        const timeoutLimitMs = 10 * 60 * 1000;
        const idleLimitMs = timeoutLimitMs;
        const maxDurationMs = timeoutLimitMs;
        let readPromise = reader.read().then((result) => ({ result }));

        const readWithTick = async () => {
            const timeout = new Promise((resolve) => setTimeout(() => resolve({ tick: true }), 1000));
            const next = await Promise.race([readPromise, timeout]) as any;
            if (!next.tick) {
                readPromise = reader.read().then((result) => ({ result }));
            }
            return next;
        };

        const handleBlock = async (block: string) => {
            const line = block.split('\n').find((item: string) => item.startsWith('data: '));
            if (!line) return;
            const event = JSON.parse(line.slice(6));
            lastEventAt = Date.now();
            if (event.type === 'delta') sawDelta = true;
            if (['provider', 'status', 'heartbeat', 'thinking', 'progress', 'phase'].includes(String(event.type || ''))) sawProgress = true;
            await onEvent(event);
            if (event.type === 'error') {
                throw new Error(event.message || 'AI Agent 스트림 처리 중 오류가 발생했습니다.');
            }
            if (event.type === 'complete' || event.type === 'done') {
                donePayload = event.data || donePayload || {};
            }
        };

        while (true) {
            const next = await readWithTick();
            if (next.tick) {
                const idleMs = Date.now() - lastEventAt;
                const elapsedSeconds = Math.max(1, Math.floor((Date.now() - startedAt) / 1000));
                if (Date.now() - startedAt > maxDurationMs) {
                    if (sawDelta) return { ...(donePayload || {}), stream_incomplete: true };
                    throw new Error('AI Agent 응답 시간이 초과되었습니다.');
                }
                if (idleMs > idleLimitMs) {
                    if (sawDelta) return { ...(donePayload || {}), stream_incomplete: true };
                    throw new Error('AI Agent 응답이 10분 이상 갱신되지 않았습니다.');
                }
                this.agentStreamStatus = `응답을 기다리는 중입니다. (${elapsedSeconds}초 경과)`;
                await this.renderAgentView();
                continue;
            }

            const { done, value } = next.result;
            if (done) {
                if (buffer.trim()) await handleBlock(buffer);
                break;
            }
            buffer += decoder.decode(value, { stream: true });
            const blocks = buffer.split('\n\n');
            buffer = blocks.pop() || '';
            for (const block of blocks) {
                await handleBlock(block);
            }
            await this.renderAgentView();
            this.scrollAgentMessages();
        }
        if (!donePayload && sawDelta) return { stream_incomplete: true };
        if (!donePayload && sawProgress) return { stream_incomplete: true, missing_terminal_event: true };
        return donePayload || {};
    }

    private async applyAgentStreamEvent(event: any, assistantMessage: AgentMessage) {
        if (!event) return;
        if (event.type === 'provider') {
            assistantMessage.provider = 'AI Agent';
            return;
        }
        if (event.type === 'status') {
            this.agentStreamStatus = event.message || event.label || '응답을 기다리는 중입니다.';
            this.appendAgentProgressLine(assistantMessage, this.agentStreamStatus);
            return;
        }
        if (event.type === 'thinking' || event.type === 'progress' || event.type === 'phase') {
            const progressText = event.message || event.text || event.summary || event.label || 'AI Agent가 요청을 처리하는 중입니다.';
            this.agentStreamStatus = progressText;
            this.appendAgentProgressLine(assistantMessage, progressText);
            return;
        }
        if (event.type === 'heartbeat') {
            this.agentStreamStatus = event.message || event.progress_message || event.label || '응답을 기다리는 중입니다.';
            return;
        }
        if (event.type === 'delta') {
            this.appendAgentAnswerText(assistantMessage, String(event.text || ''));
            this.agentStreamStatus = '';
            return;
        }
        if (event.type === 'complete') {
            const data = event.data || {};
            if (data.answer && !this.agentMessageHasAnswerContent(assistantMessage)) {
                this.appendAgentAnswerText(assistantMessage, String(data.answer || '').trim());
            }
            this.applyAgentSuggestedActions(data, assistantMessage);
            this.applyAgentDuration(data, assistantMessage);
            if (event.provider) {
                assistantMessage.provider = 'AI Agent';
            }
            this.agentStreamStatus = '';
        }
    }

    private appendAgentProgressLine(assistantMessage: AgentMessage, value: string) {
        const text = this.normalizeText(value);
        if (!text) return;
        const state = assistantMessage as any;
        const lines = Array.isArray(state.__agentProgressLines) ? state.__agentProgressLines : [];
        if (lines.includes(text)) return;
        lines.push(text);
        state.__agentProgressLines = lines.slice(-8);
        state.__agentProgressMode = true;
        if (state.__agentAnswerStarted) return;
        assistantMessage.content = state.__agentProgressLines.map((line: string) => `- ${line}`).join('\n');
    }

    private prepareAgentAnswerAfterProgress(assistantMessage: AgentMessage) {
        const state = assistantMessage as any;
        if (!state.__agentProgressMode || state.__agentAnswerStarted) return;
        assistantMessage.content = `${assistantMessage.content.trim()}\n\n`;
        state.__agentAnswerStarted = true;
    }

    private appendAgentAnswerText(assistantMessage: AgentMessage, value: string) {
        const text = String(value || '');
        if (!text) return;
        this.prepareAgentAnswerAfterProgress(assistantMessage);
        const state = assistantMessage as any;
        state.__agentAnswerText = `${state.__agentAnswerText || ''}${text}`;
        if (!state.__agentProgressMode) {
            state.__agentAnswerStarted = true;
        }
        assistantMessage.content += text;
    }

    private agentMessageHasAnswerContent(assistantMessage: AgentMessage) {
        const state = assistantMessage as any;
        if (state.__agentProgressMode) {
            return Boolean(this.normalizeText(state.__agentAnswerText || ''));
        }
        return Boolean(String(assistantMessage?.content || '').trim());
    }

    private setAgentErrorContent(assistantMessage: AgentMessage, value: string) {
        const text = this.normalizeText(value) || 'AI Agent 호출에 실패했습니다.';
        const current = String(assistantMessage.content || '').trim();
        assistantMessage.content = current ? `${current}\n\n${text}` : text;
        const state = assistantMessage as any;
        state.__agentAnswerStarted = true;
        state.__agentAnswerText = text;
    }

    private trustAgentMarkdown(value: string): SafeHtml {
        return this.sanitizer.bypassSecurityTrustHtml(this.renderAgentMarkdown(value));
    }

    private renderAgentMarkdown(value: string) {
        const lines = String(value || '').replace(/\r\n/g, '\n').split('\n');
        const html: string[] = [];
        let paragraph: string[] = [];
        let listType = '';
        let listItems: string[] = [];
        let inCode = false;
        let codeLines: string[] = [];

        const flushParagraph = () => {
            if (paragraph.length === 0) return;
            html.push(`<p>${this.renderAgentInlineMarkdown(paragraph.join('\n')).replace(/\n/g, '<br>')}</p>`);
            paragraph = [];
        };
        const flushList = () => {
            if (!listType || listItems.length === 0) return;
            const items = listItems.map((item) => `<li>${this.renderAgentInlineMarkdown(item)}</li>`).join('');
            html.push(`<${listType}>${items}</${listType}>`);
            listType = '';
            listItems = [];
        };
        const flushCode = () => {
            html.push(this.renderAgentCodeBlock(codeLines));
            codeLines = [];
        };

        for (let index = 0; index < lines.length; index++) {
            const line = lines[index];
            if (line.trim().startsWith('```')) {
                if (inCode) {
                    flushCode();
                    inCode = false;
                } else {
                    flushParagraph();
                    flushList();
                    inCode = true;
                    codeLines = [];
                }
                continue;
            }
            if (inCode) {
                codeLines.push(line);
                continue;
            }

            if (!line.trim()) {
                flushParagraph();
                flushList();
                continue;
            }

            if (this.isAgentMarkdownTableStart(lines, index)) {
                flushParagraph();
                flushList();
                const tableLines: string[] = [];
                while (index < lines.length && this.isAgentMarkdownTableRow(lines[index])) {
                    tableLines.push(lines[index]);
                    index += 1;
                }
                index -= 1;
                html.push(this.renderAgentMarkdownTable(tableLines));
                continue;
            }

            if (this.isAgentCodeLine(line)) {
                flushParagraph();
                flushList();
                const detectedCodeLines: string[] = [];
                while (index < lines.length && this.isAgentCodeLine(lines[index])) {
                    detectedCodeLines.push(lines[index]);
                    index += 1;
                }
                index -= 1;
                html.push(this.renderAgentCodeBlock(detectedCodeLines));
                continue;
            }

            const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
            const unordered = line.match(/^\s*[-*]\s+(.+)$/);
            const heading = line.match(/^\s{0,3}(#{1,6})\s+(.+)$/);
            if (heading) {
                flushParagraph();
                flushList();
                const level = Math.min(6, heading[1].length + 3);
                html.push(`<h${level}>${this.renderAgentInlineMarkdown(heading[2])}</h${level}>`);
                continue;
            }
            if (ordered || unordered) {
                flushParagraph();
                const nextType = ordered ? 'ol' : 'ul';
                if (listType && listType !== nextType) flushList();
                listType = nextType;
                listItems.push((ordered || unordered || [])[1]);
                continue;
            }

            flushList();
            paragraph.push(line.replace(/\s+$/, ''));
        }

        flushParagraph();
        flushList();
        if (inCode) flushCode();
        return html.join('');
    }

    private renderAgentInlineMarkdown(value: string) {
        const codeSpans: string[] = [];
        let html = this.escapeAgentHtml(value).replace(/`([^`]+)`/g, (_match: string, code: string) => {
            const token = `@@AGENT_CODE_${codeSpans.length}@@`;
            codeSpans.push(`<code>${code}</code>`);
            return token;
        });
        html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/__([^_]+)__/g, '<strong>$1</strong>');
        html = html.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
        codeSpans.forEach((code, index) => {
            html = html.replace(new RegExp(`@@AGENT_CODE_${index}@@`, 'g'), code);
        });
        return html;
    }

    private isAgentMarkdownTableStart(lines: string[], index: number) {
        return this.isAgentMarkdownTableRow(lines[index]) && this.isAgentMarkdownTableSeparator(lines[index + 1] || '');
    }

    private isAgentMarkdownTableRow(line: string) {
        const trimmed = String(line || '').trim();
        return trimmed.startsWith('|') && trimmed.endsWith('|') && this.agentMarkdownTableCells(trimmed).length >= 2;
    }

    private isAgentMarkdownTableSeparator(line: string) {
        if (!this.isAgentMarkdownTableRow(line)) return false;
        return this.agentMarkdownTableCells(line).every((cell) => /^:?-{3,}:?$/.test(cell.replace(/\s+/g, '')));
    }

    private agentMarkdownTableCells(line: string) {
        let text = String(line || '').trim();
        if (text.startsWith('|')) text = text.slice(1);
        if (text.endsWith('|')) text = text.slice(0, -1);
        return text.split('|').map((cell) => cell.trim());
    }

    private renderAgentMarkdownTable(lines: string[]) {
        const header = this.agentMarkdownTableCells(lines[0] || '').slice(0, 8);
        const body = lines.slice(2, 18).map((line) => this.agentMarkdownTableCells(line).slice(0, header.length));
        const headHtml = header.map((cell) => `<th>${this.renderAgentInlineMarkdown(cell)}</th>`).join('');
        const bodyHtml = body.map((row) => {
            const cells = header.map((_cell, index) => `<td>${this.renderAgentInlineMarkdown(row[index] || '')}</td>`).join('');
            return `<tr>${cells}</tr>`;
        }).join('');
        return `<div class="ai-agent-markdown-table-wrap"><table><thead><tr>${headHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></div>`;
    }

    private renderAgentCodeBlock(lines: string[]) {
        const code = this.escapeAgentHtml((lines || []).join('\n'));
        return [
            '<div class="ai-agent-code-block">',
            '<div class="ai-agent-code-toolbar">',
            '<span>코드</span>',
            '<button type="button" class="ai-agent-code-copy" data-ai-agent-copy-code="true" aria-label="코드 복사" title="코드 복사">',
            '<i class="fa-solid fa-copy"></i><span>복사</span>',
            '</button>',
            '</div>',
            `<pre><code>${code}</code></pre>`,
            '</div>'
        ].join('');
    }

    private isAgentCodeLine(line: string) {
        const trimmed = String(line || '').trim();
        if (!trimmed) return false;
        if (trimmed.startsWith('#!/')) return true;
        if (/^[A-Z_][A-Z0-9_]*=.*/.test(trimmed)) return true;
        if (/^(if|then|else|fi|for|while|do|done)\b/.test(trimmed)) return true;
        return /^(sudo\s+)?(docker|kubectl|helm|curl|wget|ssh|scp|rsync|find|grep|awk|sed|cat|tail|head|journalctl|systemctl|apt|apt-get|yum|dnf|apk|npm|node|python|python3|pip|pip3|git|openssl|nginx|certbot|truncate|chmod|chown|mkdir|rmdir|rm|cp|mv|echo|export|source)\b/.test(trimmed);
    }

    private escapeAgentHtml(value: string) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    private applyAgentSuggestedActions(payload: any, assistantMessage: AgentMessage) {
        const actions = this.normalizeAgentSuggestedActions(
            payload?.suggested_actions || payload?.next_actions || payload?.recommended_actions,
            payload?.follow_up
        );
        assistantMessage.suggested_actions = actions;
    }

    private applyAgentDuration(payload: any, assistantMessage: AgentMessage, requestStartedAt?: number) {
        const payloadDuration = this.coerceAgentDuration(payload?.duration_ms);
        if (payloadDuration !== null) {
            assistantMessage.duration_ms = payloadDuration;
            return;
        }
        if (assistantMessage.duration_ms || !requestStartedAt) return;
        const elapsed = Math.max(1, Math.round(this.agentNow() - requestStartedAt));
        assistantMessage.duration_ms = elapsed;
    }

    private agentHistoryResponseText(item: AgentHistoryItem) {
        return String(item?.response_answer || item?.response_summary || item?.error_message || '').trim() || '응답 내용 없음';
    }

    private agentDurationLabel(value: any) {
        const duration = this.coerceAgentDuration(value);
        if (duration === null) return '';
        if (duration < 1000) return `응답 시간 ${duration}ms`;
        const seconds = duration / 1000;
        return `응답 시간 ${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds).toString()}초`;
    }

    private coerceAgentDuration(value: any) {
        const number = Number(value);
        if (!Number.isFinite(number) || number <= 0) return null;
        return Math.max(1, Math.round(number));
    }

    private agentNow() {
        if (typeof performance !== 'undefined' && performance.now) return performance.now();
        return Date.now();
    }

    private normalizeAgentSuggestedActions(value: any, followUp?: string) {
        const source = Array.isArray(value) ? value : [];
        const actions: AgentSuggestedAction[] = [];
        for (const item of source.slice(0, 4)) {
            const data = typeof item === 'string' ? { label: item, prompt: item } : (item || {});
            const prompt = this.normalizeText(data.prompt || data.message || data.query || data.instruction || data.label || data.title);
            if (!prompt) continue;
            actions.push({
                label: this.agentSuggestedActionLabel(data.label || data.title || prompt),
                prompt: prompt.slice(0, 500),
                reason: this.normalizeText(data.reason || data.description).slice(0, 200)
            });
        }
        const fallback = this.normalizeText(followUp);
        if (actions.length === 0 && fallback) {
            actions.push({ label: this.agentSuggestedActionLabel(fallback), prompt: fallback.slice(0, 500) });
        }
        return actions;
    }

    private agentSuggestedActionLabel(value: string) {
        const label = this.normalizeText(value) || '다음 동작 실행';
        return label.length > 34 ? `${label.slice(0, 33)}...` : label;
    }

    private suggestedActionPrompt(action: AgentSuggestedAction) {
        return this.normalizeText(action?.prompt || action?.label || '').slice(0, 500);
    }

    private async copyAgentText(text: string) {
        const value = String(text || '');
        if (!value) return;
        const clipboard = typeof navigator !== 'undefined' ? (navigator as any).clipboard : null;
        if (clipboard?.writeText) {
            await clipboard.writeText(value);
            return;
        }
        const textarea = document.createElement('textarea');
        textarea.value = value;
        textarea.setAttribute('readonly', 'readonly');
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        const copied = document.execCommand('copy');
        textarea.remove();
        if (!copied) throw new Error('copy failed');
    }

    private resetAgentHistoryCopyState() {
        if (this.agentHistoryCopyTimer) window.clearTimeout(this.agentHistoryCopyTimer);
        this.agentHistoryCopyTimer = null;
        this.agentHistoryCopiedActionIndex = -1;
    }

    private async loadAgentHistorySession(item: AgentHistoryItem) {
        const sessionId = this.normalizeText(item?.session_id || item?.id);
        if (!sessionId) throw new Error('세션 ID가 비어 있습니다.');
        if (this.agentHistorySelected?.id === item.id && Array.isArray(this.agentHistorySelected?.turns) && this.agentHistorySelected.turns.length > 0) {
            return this.agentHistorySelected;
        }
        const detail = await this.agentApi('history/session', {
            session_id: sessionId,
            agent: item?.agent_type || ''
        });
        return { ...item, ...(detail || {}) };
    }

    private agentHistoryChatMessages(item: AgentHistoryItem) {
        const turns = this.agentHistoryTurns(item);
        const messages: AgentMessage[] = [];
        turns.forEach((turn, index) => {
            const id = this.normalizeText(turn?.id || `${turn?.session_id || item?.session_id || 'history'}-${index}`);
            const at = turn?.created_at || item?.created_at || new Date().toISOString();
            const question = String(turn?.request_message || '').trim();
            const answer = String(turn?.response_answer || turn?.response_summary || turn?.error_message || '').trim();
            if (question) {
                messages.push({
                    id: `${id}-user`,
                    role: 'user',
                    content: question,
                    at,
                });
            }
            if (answer) {
                messages.push({
                    id: `${id}-assistant`,
                    role: turn?.status === 'failed' ? 'error' : 'assistant',
                    content: answer,
                    at,
                    provider: turn?.agent_label || item?.agent_label || this.agentLabel,
                    duration_ms: turn?.duration_ms,
                    suggested_actions: this.agentHistoryActions(turn),
                });
            }
        });
        return messages;
    }

    private async renderAgentView() {
        if (this.agentTextSelectionActive()) {
            this.scheduleAgentRenderAfterSelection();
            return;
        }
        await this.service.render();
    }

    private agentTextSelectionActive() {
        if (typeof window === 'undefined' || !window.getSelection) return false;
        const selection = window.getSelection();
        if (!selection || selection.isCollapsed || selection.rangeCount === 0) return false;
        return [selection.anchorNode, selection.focusNode].some((node) => Boolean(node && this.isAgentMutationNode(node)));
    }

    private scheduleAgentRenderAfterSelection() {
        if (typeof window === 'undefined' || this.agentSelectionRenderTimer) return;
        this.agentSelectionRenderTimer = window.setTimeout(async () => {
            this.agentSelectionRenderTimer = null;
            await this.renderAgentView();
        }, 350);
    }

    private activeAgentKey() {
        return (this.normalizeText(this.agentType).replace(/-/g, '_') || 'default').slice(0, 80);
    }

    private ensureAgentSession() {
        const key = this.activeAgentKey();
        const sessions = this.loadAgentSessionMap();
        let sessionId = this.normalizeSessionId(sessions[key]);
        if (!sessionId) {
            sessionId = this.createAgentSessionId();
            sessions[key] = sessionId;
            this.saveAgentSessionMap(sessions);
        }
        this.agentSessionId = sessionId;
        return sessionId;
    }

    private setAgentSession(agentKey: string, sessionId: string) {
        const key = this.normalizeText(agentKey) || this.activeAgentKey();
        const sessions = this.loadAgentSessionMap();
        sessions[key] = this.normalizeSessionId(sessionId) || this.createAgentSessionId();
        this.saveAgentSessionMap(sessions);
        this.agentSessionId = sessions[key];
    }

    private loadAgentSessionMap() {
        return { ...this.agentSessionMap };
    }

    private saveAgentSessionMap(sessions: any) {
        this.agentSessionMap = { ...(sessions || {}) };
    }

    private createAgentSessionId() {
        const cryptoApi = typeof crypto !== 'undefined' ? crypto : null;
        if (cryptoApi?.randomUUID) return cryptoApi.randomUUID();
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
            const random = Math.floor(Math.random() * 16);
            const value = char === 'x' ? random : ((random & 0x3) | 0x8);
            return value.toString(16);
        });
    }

    private createAgentRequestId() {
        const cryptoApi = typeof crypto !== 'undefined' ? crypto : null;
        if (cryptoApi?.randomUUID) return cryptoApi.randomUUID();
        return `req-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
    }

    private normalizeSessionId(value: any) {
        return String(value || '').replace(/[^A-Za-z0-9_.:-]/g, '').slice(0, 160);
    }

    private agentSessionTitle(message?: string) {
        const firstUserMessage = this.agentMessages.find((item) => item.role === 'user' && this.normalizeText(item.content));
        return this.normalizeText(firstUserMessage?.content || message || 'AI Agent 세션').slice(0, 160);
    }

    private focusAgentInput() {
        setTimeout(() => {
            const input = document.querySelector('textarea[name="agentInput"]') as HTMLTextAreaElement | null;
            if (input) input.focus();
        }, 0);
    }

    private agentHistoryRequestFilters() {
        return {
            start_date: this.normalizeText(this.agentHistoryFilters.start_date),
            end_date: this.normalizeText(this.agentHistoryFilters.end_date),
            q: this.normalizeText(this.agentHistoryFilters.q)
        };
    }

    private agentDownloadFilename(disposition: string, format: string) {
        const match = String(disposition || '').match(/filename="?([^"]+)"?/i);
        if (match?.[1]) return match[1];
        const date = new Date().toISOString().slice(0, 10);
        return `ai-agent-history-${date}.${format}`;
    }

    private saveAgentBlob(blob: Blob, filename: string) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    }

    private stopAgentResize(persistWidth: boolean = false) {
        if (this.resizeMoveHandler) document.removeEventListener('mousemove', this.resizeMoveHandler);
        if (this.resizeEndHandler) document.removeEventListener('mouseup', this.resizeEndHandler);
        this.resizeMoveHandler = null;
        this.resizeEndHandler = null;
        if (persistWidth) this.saveAgentDockWidth();
    }

    private agentDockMaxWidth() {
        if (typeof window === 'undefined') return 760;
        return Math.min(760, Math.max(360, window.innerWidth - 360));
    }

    private clampAgentDockWidth(value: any) {
        const numeric = Number(value);
        const nextWidth = Number.isFinite(numeric) ? Math.round(numeric) : 420;
        return Math.max(340, Math.min(this.agentDockMaxWidth(), nextWidth));
    }

    private restoreAgentDockWidth() {
        if (typeof window === 'undefined') return;
        try {
            const value = window.localStorage?.getItem(this.agentDockWidthStorageKey);
            if (!value) return;
            this.agentDockWidth = this.clampAgentDockWidth(value);
        } catch { }
    }

    private saveAgentDockWidth() {
        if (typeof window === 'undefined') return;
        try {
            this.agentDockWidth = this.clampAgentDockWidth(this.agentDockWidth);
            window.localStorage?.setItem(this.agentDockWidthStorageKey, String(this.agentDockWidth));
        } catch { }
    }

    private setupAgentContextTrackers() {
        if (typeof document === 'undefined') return;
        this.clickHandler = (event: Event) => this.captureInteractionEvent('click', event);
        this.inputHandler = (event: Event) => this.captureInteractionEvent('input', event);
        this.submitHandler = (event: Event) => this.captureInteractionEvent('submit', event);
        this.focusHandler = (event: Event) => this.captureInteractionEvent('focus', event);
        this.codeCopyHandler = (event: Event) => this.handleAgentCodeCopy(event);
        document.addEventListener('click', this.clickHandler, true);
        document.addEventListener('input', this.inputHandler, true);
        document.addEventListener('submit', this.submitHandler, true);
        document.addEventListener('focusin', this.focusHandler, true);
        document.addEventListener('click', this.codeCopyHandler, true);
        this.mutationObserver = new MutationObserver((mutations) => {
            if (this.shouldIgnoreAgentContextMutations(mutations)) return;
            this.scheduleAgentContextRefresh();
        });
        this.mutationObserver.observe(document.body, { childList: true, subtree: true, characterData: true });
    }

    private shouldIgnoreAgentContextMutations(mutations: MutationRecord[]) {
        return !mutations.some((mutation) => {
            if (this.isAgentMutationNode(mutation.target)) return false;
            const nodes = [...Array.from(mutation.addedNodes), ...Array.from(mutation.removedNodes)]
                .filter((node) => node.nodeType === Node.ELEMENT_NODE || node.nodeType === Node.TEXT_NODE);
            if (nodes.length > 0) return nodes.some((node) => !this.isAgentMutationNode(node));
            return !this.isAgentMutationNode(mutation.target);
        });
    }

    private isAgentMutationNode(node: Node) {
        if (node instanceof HTMLElement) return Boolean(node.closest('.ai-agent-surface'));
        const parent = node.parentElement;
        return Boolean(parent?.closest('.ai-agent-surface'));
    }

    private async handleAgentCodeCopy(event: Event) {
        const target = event.target;
        if (!(target instanceof Element)) return;
        const button = target.closest('[data-ai-agent-copy-code="true"]') as HTMLButtonElement | null;
        if (!button) return;
        event.preventDefault();
        event.stopPropagation();

        const block = button.closest('.ai-agent-code-block') as HTMLElement | null;
        const code = block?.querySelector('pre code')?.textContent || '';
        try {
            await this.copyAgentText(code);
            this.setAgentCodeCopyState(button, 'copied');
            window.setTimeout(() => this.setAgentCodeCopyState(button, 'ready'), 1200);
        } catch (_error) {
            this.setAgentCodeCopyState(button, 'failed');
            window.setTimeout(() => this.setAgentCodeCopyState(button, 'ready'), 1200);
        }
    }

    private setAgentCodeCopyState(button: HTMLButtonElement, state: 'ready' | 'copied' | 'failed') {
        if (!button.isConnected) return;
        const copied = state === 'copied';
        const failed = state === 'failed';
        const label = copied ? '복사됨' : failed ? '실패' : '복사';
        const icon = copied ? 'fa-check' : failed ? 'fa-triangle-exclamation' : 'fa-copy';
        button.classList.toggle('copied', copied);
        button.classList.toggle('failed', failed);
        button.setAttribute('aria-label', state === 'ready' ? '코드 복사' : label);
        button.setAttribute('title', state === 'ready' ? '코드 복사' : label);
        button.innerHTML = `<i class="fa-solid ${icon}"></i><span>${label}</span>`;
    }

    private captureInteractionEvent(type: string, event: Event) {
        const target = this.closestInteractiveElement(event.target);
        if (!target || this.isAgentSurfaceElement(target)) return;
        const ref = this.ensureAgentRef(target);
        const detail: any = {
            ref,
            label: this.elementLabel(target),
            tag: target.tagName.toLowerCase(),
            route: this.currentRoutePath()
        };
        if (type === 'input') detail.value = this.safeFieldValue(target);
        this.recordAgentEvent(type, detail);
        this.scheduleAgentContextRefresh();
    }

    private recordAgentEvent(type: string, detail: any) {
        this.agentEvents.push({ type, detail, at: new Date().toISOString() });
        if (this.agentEvents.length > 30) this.agentEvents = this.agentEvents.slice(-30);
    }

    private scheduleAgentContextRefresh() {
        if (!this.agentWidgetOpen) return;
        if (this.contextRefreshTimer) window.clearTimeout(this.contextRefreshTimer);
        this.contextRefreshTimer = window.setTimeout(async () => {
            this.contextRefreshTimer = null;
            const changed = this.refreshAgentContextView();
            if (changed) await this.renderAgentView();
        }, 250);
    }

    private refreshAgentContextView() {
        if (typeof document === 'undefined') return false;
        const screen = this.collectAgentScreenContext();
        const headings = screen.headings || [];
        const modalContext = screen.modal || { open: false };
        const contextSummary = this.agentReadableContextSummary(screen);
        const recommendations = this.recommendedQuestions(screen.route, headings[0] || screen.title || '');
        const signature = JSON.stringify({ modalContext, contextSummary, recommendations });
        if (signature === this.agentContextSignature) return false;
        this.agentModalContext = modalContext;
        this.agentContextSummary = contextSummary;
        this.agentRecommendations = recommendations;
        this.agentContextSignature = signature;
        return true;
    }

    private agentReadableContextSummary(screen: any) {
        const route = String(screen?.route || '').split('?')[0];
        const title = (screen?.headings || [])[0] || screen?.title || '';
        const visibleText = String(screen?.visible_text || '');
        if (route.startsWith('/images/local')) {
            return ['이미지 관리', '서버 로컬 저장소', this.extractLocalServerName(visibleText)].filter(Boolean).join(' . ');
        }
        if (route.startsWith('/images/harbor/')) return ['이미지 관리', 'Harbor 저장소', this.extractContextEntityName(visibleText, title, '저장소 상세')].filter(Boolean).join(' . ');
        if (route.startsWith('/images')) return '이미지 관리';
        if (route.startsWith('/services/create')) return '서비스 생성';
        if (route.startsWith('/services/')) return ['서비스 관리', this.extractContextEntityName(visibleText, title, '서비스 상세')].filter(Boolean).join(' . ');
        if (route.startsWith('/services')) return '서비스 관리';
        if (route.startsWith('/servers/')) return ['서버 관리', this.extractLocalServerName(visibleText) || this.extractContextEntityName(visibleText, title, '서버 상세')].filter(Boolean).join(' . ');
        if (route.startsWith('/servers')) return '서버 관리';
        if (route.startsWith('/domains/')) return ['도메인 관리', this.extractDomainContextName(visibleText, title)].filter(Boolean).join(' . ');
        if (route.startsWith('/domains')) return '도메인 관리';
        if (route.startsWith('/templates/')) return ['Compose 템플릿', this.extractContextEntityName(visibleText, title, '템플릿 상세')].filter(Boolean).join(' . ');
        if (route.startsWith('/templates')) return 'Compose 템플릿';
        if (route.startsWith('/system')) return '시스템 설정';
        if (route.startsWith('/dashboard')) return '대시보드';
        return this.normalizeText(title) || '현재 화면';
    }

    private extractLocalServerName(text: string) {
        const normalized = this.normalizeText(text);
        const direct = normalized.match(/\b(local-master|local-[a-z0-9_.-]+|[a-z0-9_.-]+-master)\b/i);
        if (direct) return direct[1];
        const server = normalized.match(/서버\s*([a-z0-9_.-]{3,})/i);
        if (server) return server[1];
        return '로컬 서버';
    }

    private extractDomainContextName(text: string, title: string) {
        const normalized = this.normalizeText(`${title} ${text}`);
        const domain = normalized.match(/\b([a-z0-9-]+(?:\.[a-z0-9-]+)+)\b/i);
        return domain ? domain[1] : '도메인 상세';
    }

    private extractContextEntityName(text: string, title: string, fallback: string) {
        const normalizedTitle = this.normalizeText(title);
        if (normalizedTitle && !/docker infra|ai agent|서비스 관리|서버 관리|도메인 관리|이미지 관리|compose 템플릿/i.test(normalizedTitle)) return normalizedTitle;
        const normalized = this.normalizeText(text);
        const entity = normalized.match(/\b([a-z0-9][a-z0-9_.-]{2,})\s+(서비스|컨테이너|템플릿|저장소)\b/i);
        if (entity) return entity[1];
        const domain = normalized.match(/\b([a-z0-9-]+(?:\.[a-z0-9-]+)+)\b/i);
        if (domain) return domain[1];
        return fallback;
    }

    private recommendedQuestions(route: string, title: string) {
        const cleanRoute = String(route || '').split('?')[0];
        const shared = ['이 화면에서 다음에 확인할 일을 알려줘', '현재 열린 화면 기준으로 이상 징후를 찾아줘'];
        if (cleanRoute.startsWith('/system')) {
            return ['Hermes Agent 설정 적용 상태를 확인해줘', '현재 기본 AI Agent로 테스트 요청을 보내줘', '시스템 설정에서 저장되지 않은 항목이 있는지 봐줘', ...shared].slice(0, 5);
        }
        if (cleanRoute.startsWith('/services/create')) {
            return ['현재 입력값으로 서비스 생성 위험을 점검해줘', 'Compose 설정에서 빠진 값을 채워줘', '도메인과 포트 구성이 맞는지 확인해줘', ...shared].slice(0, 5);
        }
        if (cleanRoute.startsWith('/services')) {
            return ['서비스 상태와 최근 배포 이슈를 요약해줘', '선택한 서비스의 로그에서 원인을 찾아줘', '롤백이나 재배포가 필요한지 판단해줘', ...shared].slice(0, 5);
        }
        if (cleanRoute.startsWith('/servers')) {
            return ['서버별 리소스와 컨테이너 상태를 요약해줘', '응답 없는 노드가 있는지 확인해줘', '포트 충돌 가능성을 점검해줘', ...shared].slice(0, 5);
        }
        if (cleanRoute.startsWith('/domains')) {
            return ['도메인과 인증서 상태를 점검해줘', 'DNS 연결 문제 가능성을 확인해줘', '서비스에 연결할 도메인을 추천해줘', ...shared].slice(0, 5);
        }
        if (cleanRoute.startsWith('/images')) {
            return ['이미지 태그와 레지스트리 상태를 점검해줘', '오래된 이미지 정리 대상을 찾아줘', '배포에 사용할 이미지 위험을 확인해줘', ...shared].slice(0, 5);
        }
        if (cleanRoute.startsWith('/templates')) {
            return ['이 템플릿으로 만들 수 있는 서비스를 설명해줘', '템플릿 변수에서 누락된 값을 찾아줘', '보안상 조정할 값을 추천해줘', ...shared].slice(0, 5);
        }
        if (cleanRoute.startsWith('/dashboard')) {
            return ['대시보드 수치에서 우선 확인할 문제를 골라줘', '최근 운영 이벤트를 기준으로 위험을 요약해줘', '지금 바로 점검할 서비스를 추천해줘', ...shared].slice(0, 5);
        }
        return [title ? `${title} 화면에서 할 수 있는 작업을 알려줘` : '현재 화면을 요약해줘', ...shared, '이 화면에서 대신 조작할 수 있는 항목을 알려줘'].slice(0, 5);
    }

    private collectAgentScreenContext() {
        const screen: any = {
            url: location.href,
            route: this.currentRoutePath(),
            title: document.title,
            wiz_route: (window as any).WizRoute || {},
            viewport: { width: window.innerWidth, height: window.innerHeight },
            focused_element: this.describeElement(document.activeElement as HTMLElement),
            headings: this.collectTextFrom('h1,h2,h3,[data-page-title]', 20),
            modal: this.collectModalContext(),
            interactive_elements: this.collectInteractiveElements(),
            visible_text: this.collectVisibleText()
        };
        screen.context_summary = this.agentReadableContextSummary(screen);
        return screen;
    }

    private collectInteractiveElements() {
        const selector = 'button,a,input,textarea,select,[role="button"],[tabindex]';
        return Array.from(document.querySelectorAll(selector))
            .filter((item) => item instanceof HTMLElement)
            .map((item) => item as HTMLElement)
            .filter((item) => !this.isAgentSurfaceElement(item) && this.isVisibleElement(item))
            .slice(0, 90)
            .map((item) => ({
                ref: this.ensureAgentRef(item),
                tag: item.tagName.toLowerCase(),
                type: item.getAttribute('type') || item.getAttribute('role') || '',
                label: this.elementLabel(item),
                value: this.safeFieldValue(item),
                href: item.getAttribute('href') || '',
                disabled: Boolean((item as HTMLButtonElement).disabled || item.getAttribute('aria-disabled') === 'true')
            }));
    }

    private collectModalContext() {
        const candidates = Array.from(document.querySelectorAll('[role="dialog"], .modal, wiz-portal-season-modal, .fixed.inset-0'))
            .filter((item) => item instanceof HTMLElement)
            .map((item) => item as HTMLElement)
            .filter((item) => !this.isAgentSurfaceElement(item) && this.isVisibleElement(item));
        const modal = candidates.find((item) => String(item.innerText || '').trim());
        if (!modal) return { open: false };
        const text = this.normalizeText(modal.innerText).slice(0, 1800);
        const title = this.normalizeText((modal.querySelector('h1,h2,h3,[class*="title"]') as HTMLElement)?.innerText || '').slice(0, 160);
        return { open: true, title, text };
    }

    private collectTextFrom(selector: string, limit: number) {
        return Array.from(document.querySelectorAll(selector))
            .filter((item) => item instanceof HTMLElement)
            .map((item) => item as HTMLElement)
            .filter((item) => !this.isAgentSurfaceElement(item) && this.isVisibleElement(item))
            .map((item) => this.normalizeText(item.innerText))
            .filter(Boolean)
            .slice(0, limit);
    }

    private collectVisibleText() {
        const clone = document.body.cloneNode(true) as HTMLElement;
        clone.querySelectorAll('.ai-agent-surface, script, style, noscript, template').forEach((item) => item.remove());
        return this.normalizeText(clone.textContent || '').slice(0, 6000);
    }

    private async executeAgentActions(actions: any[], requestMessage: string = '', todoId: string = '') {
        if (!Array.isArray(actions) || actions.length === 0) return true;
        const todoItems = this.buildAgentActionTodoList(actions, requestMessage);
        const meaningfulItems = todoItems.filter((item) => item.executable);
        const executableItems = meaningfulItems.filter((item) => !item.blocked);
        if (meaningfulItems.length > 0 && executableItems.length === 0) {
            this.updateAgentTodo(todoId, { status: 'blocked', detail: '되돌리기 어려운 동작은 구체적인 확인이 필요합니다.' });
            return false;
        }
        if (executableItems.length === 0) return true;
        let stepIndex = 0;
        const actionContext: any = {};
        for (const item of todoItems) {
            if (!item.executable) continue;
            if (item.blocked) {
                this.updateAgentTodo(todoId, { status: 'blocked', detail: '되돌리기 어려운 동작은 구체적인 확인이 필요합니다.' });
                return false;
            }
            stepIndex += 1;
            this.updateAgentTodo(todoId, { status: 'running', detail: `${stepIndex}/${executableItems.length} ${item.label}` });
            await this.renderAgentView();
            try {
                const action = this.resolveAgentActionReferences(item.action, actionContext);
                const result = await this.executeAgentAction(action);
                if (!result) {
                    this.updateAgentTodo(todoId, { status: 'failed', detail: `${item.label} 실패` });
                    return false;
                }
                this.storeAgentActionResult(action, result, actionContext);
            } catch (error: any) {
                this.updateAgentTodo(todoId, { status: 'failed', detail: error?.message || `${item.label} 실패` });
                return false;
            }
        }
        return true;
    }

    private buildAgentActionTodoList(actions: any[], requestMessage: string = '') {
        return (actions || []).slice(0, 6).map((action) => {
            const executable = Boolean(
                action
                && !action.requires_confirmation
                && this.isMeaningfulAgentAction(action, requestMessage)
            );
            const blocked = executable && this.isBlockedAgentAction(action, requestMessage);
            return {
                action,
                executable,
                blocked,
                label: this.normalizeText(action?.reason || this.agentActionLabel(action)) || '화면 조작',
            };
        });
    }

    private updateAgentTodo(todoId: string, updates: Partial<AgentTodoItem>) {
        if (!todoId) return;
        this.agentTodos = this.agentTodos.map((todo) => todo.id === todoId ? { ...todo, ...updates } : todo);
    }

    private isMeaningfulAgentAction(action: any, requestMessage: string) {
        const type = String(action?.type || '').toLowerCase();
        const text = this.normalizeText(requestMessage).toLowerCase();
        const operationIntent = /(이동|열어|화면|페이지|탭|메뉴|클릭|눌러|선택|입력|채워|수정|변경|저장|실행|추가|만들|생성|등록|적용|닫|취소|새로고침|갱신|해줘|해 줘|navigate|open|click|press|select|fill|type|edit|save|run|add|create|register|apply|close|cancel|refresh|reload)/i;
        if (!type || type === 'noop') return false;
        if (type === 'navigate') {
            const target = String(action.target || '').split('?')[0];
            return Boolean(target && target !== this.currentRoutePath() && operationIntent.test(text));
        }
        if (type === 'click') return Boolean((action.ref || action.target) && operationIntent.test(text));
        if (type === 'fill') return Boolean((action.ref || action.target) && action.value !== undefined && operationIntent.test(text));
        if (type === 'focus') return Boolean((action.ref || action.target) && /(포커스|커서|focus)/i.test(text));
        if (type === 'close_modal') return /(닫|취소|모달|close|cancel|escape)/i.test(text);
        if (type === 'refresh') return /(새로고침|갱신|refresh|reload)/i.test(text);
        if (type === 'wait') return true;
        if (type === 'app_event') return Boolean(action.target && operationIntent.test(text));
        if (type === 'api_request') {
            const operation = this.findAgentApiOperation(action);
            if (!operation) return false;
            const readIntent = /(확인|조회|요약|점검|분석|찾아|알려|상태|목록|새로고침|갱신|check|inspect|list|summary|status|refresh|reload)/i;
            if (operation.safety === 'read') return readIntent.test(text) || operationIntent.test(text);
            return operationIntent.test(text);
        }
        return false;
    }

    private isBlockedAgentAction(action: any, requestMessage: string = '') {
        const operation = String(action?.type || '').toLowerCase() === 'api_request' ? this.findAgentApiOperation(action) : null;
        if (operation?.safety === 'destructive') return !this.hasExplicitDestructiveConfirmation(action, requestMessage, operation);
        const target = this.normalizeText(`${action?.target || ''} ${action?.reason || ''} ${action?.value || ''}`).toLowerCase();
        if (!/(삭제|제거|초기화|폐기|종료|전원|재부팅|delete|remove|destroy|reset|wipe|shutdown|poweroff|reboot)/i.test(target)) {
            return false;
        }
        return !this.hasExplicitDestructiveConfirmation(action, requestMessage, operation);
    }

    private hasExplicitDestructiveConfirmation(action: any, requestMessage: string = '', operation: AgentApiOperation | null = null) {
        if (action?.requires_confirmation) return false;
        const text = this.normalizeText(requestMessage).toLowerCase();
        if (!text) return false;
        const destructiveIntent = /(삭제|제거|초기화|폐기|영구|되돌릴 수|확정|확인|승인|진행|실행|delete|remove|destroy|reset|wipe|confirm|confirmed|proceed)/i.test(text);
        if (!destructiveIntent) return false;

        const payload = this.agentActionObject(action?.body || action?.payload);
        const params = this.agentActionObject(action?.params);
        const identifiers = [
            operation?.operation_id,
            operation?.summary,
            action?.target,
            action?.operation_id,
            action?.operationId,
            ...Object.values({ ...params, ...payload }),
        ]
            .map((value) => this.normalizeText(value).toLowerCase())
            .filter((value) => value.length >= 3 && !['true', 'false', 'null', 'undefined'].includes(value));

        if (identifiers.some((value) => text.includes(value))) return true;
        const summary = this.normalizeText(operation?.summary || action?.reason || action?.target).toLowerCase();
        return Boolean(summary && /(삭제|제거|초기화|delete|remove|destroy|reset|wipe)/i.test(summary) && destructiveIntent);
    }

    private agentActionLabel(action: any) {
        const type = String(action?.type || '').toLowerCase();
        if (type === 'navigate') return `이동: ${action.target || ''}`;
        if (type === 'click') return '클릭';
        if (type === 'fill') return '입력값 반영';
        if (type === 'focus') return '포커스 이동';
        if (type === 'close_modal') return '모달 닫기';
        if (type === 'refresh') return '새로고침';
        if (type === 'wait') return '대기';
        if (type === 'app_event') return `화면 명령: ${action.target || ''}`;
        if (type === 'api_request') return `API 작업: ${action.operation_id || action.target || ''}`;
        return '화면 조작';
    }

    private async executeAgentAction(action: any) {
        const type = String(action.type || '').toLowerCase();
        if (type === 'navigate' && action.target) {
            this.service.href(String(action.target));
            await this.waitForAgentRoute(String(action.target));
            await this.waitForAgentSettled(250);
            return true;
        }
        if (type === 'refresh') {
            location.reload();
            return true;
        }
        if (type === 'close_modal') {
            const closed = this.closeVisibleModal();
            await this.waitForAgentSettled();
            return closed;
        }
        if (type === 'wait') {
            await this.waitForAgentSettled(Number(action.value || 400));
            return true;
        }
        if (type === 'api_request') {
            const result = await this.executeAgentApiRequest(action);
            await this.waitForAgentSettled(250);
            return result || { ok: true };
        }
        if (type === 'app_event') {
            await this.dispatchAgentAppEvent(action);
            await this.waitForAgentSettled(250);
            return true;
        }
        const element = await this.waitForAgentElement(action);
        if (!element) return false;
        if (type === 'focus') {
            element.focus();
            await this.waitForAgentSettled();
            return true;
        }
        if (type === 'fill') {
            this.fillElement(element, action.value || '');
            await this.waitForAgentSettled();
            return true;
        }
        if (type === 'click') {
            element.click();
            await this.waitForAgentSettled(300);
            return true;
        }
        return false;
    }

    private resolveAgentActionReferences(value: any, context: any, depth: number = 0): any {
        if (depth > 8) return value;
        if (Array.isArray(value)) {
            return value.map((item) => this.resolveAgentActionReferences(item, context, depth + 1));
        }
        if (value && typeof value === 'object') {
            const resolved: any = {};
            Object.keys(value).forEach((key) => {
                resolved[key] = this.resolveAgentActionReferences(value[key], context, depth + 1);
            });
            return resolved;
        }
        if (typeof value !== 'string') return value;
        return this.resolveAgentActionReferenceText(value, context);
    }

    private resolveAgentActionReferenceText(value: string, context: any) {
        const text = String(value || '');
        const exact = text.match(/^{{\s*([A-Za-z0-9_.:-]+)\s*}}$/);
        if (exact) {
            const resolved = this.agentActionContextValue(context, exact[1]);
            return resolved === undefined ? value : resolved;
        }
        return text.replace(/{{\s*([A-Za-z0-9_.:-]+)\s*}}/g, (_match, path) => {
            const resolved = this.agentActionContextValue(context, path);
            if (resolved === undefined) return _match;
            if (resolved === null) return '';
            if (typeof resolved === 'object') return JSON.stringify(resolved);
            return String(resolved);
        });
    }

    private agentActionContextValue(context: any, path: string) {
        const parts = String(path || '').split('.').filter(Boolean);
        let current = context;
        for (const part of parts) {
            if (!current || typeof current !== 'object' || !(part in current)) return undefined;
            current = current[part];
        }
        return current;
    }

    private storeAgentActionResult(action: any, result: any, context: any) {
        if (!context || result === undefined) return;
        context.last = result;
        const alias = this.normalizeAgentActionAlias(action?.save_as || action?.result_key);
        if (alias) context[alias] = result;
        const operationAlias = this.normalizeAgentActionAlias(action?.operation_id || action?.operationId || action?.target);
        if (operationAlias && !context[operationAlias]) context[operationAlias] = result;
    }

    private normalizeAgentActionAlias(value: any) {
        return this.normalizeText(value)
            .replace(/[^A-Za-z0-9_:-]+/g, '_')
            .replace(/^_+|_+$/g, '')
            .slice(0, 80);
    }

    private async waitForAgentSettled(ms: number = 120) {
        await this.sleep(ms);
        await this.renderAgentView();
    }

    private async waitForAgentRoute(target: string) {
        const expected = String(target || '').split('?')[0];
        if (!expected || /^https?:\/\//i.test(expected)) {
            await this.sleep(500);
            return;
        }
        for (let index = 0; index < 40; index++) {
            if (this.currentRoutePath() === expected) return;
            await this.sleep(100);
        }
    }

    private async waitForAgentElement(action: any) {
        for (let index = 0; index < 30; index++) {
            const element = this.findAgentElement(action.ref || action.target, action);
            if (element) return element;
            await this.sleep(100);
        }
        return null;
    }

    private async dispatchAgentAppEvent(action: any) {
        const target = this.normalizeText(action?.target);
        if (!target) throw new Error('AI Agent 화면 명령 대상이 비어 있습니다.');
        const requestId = `agent-action-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        const payload = action?.payload && typeof action.payload === 'object' ? action.payload : {};

        await new Promise<void>((resolve, reject) => {
            let timer: any = null;
            const finish = (event: Event) => {
                const detail = (event as CustomEvent)?.detail || {};
                if (detail.request_id !== requestId) return;
                if (timer) window.clearTimeout(timer);
                window.removeEventListener('docker-infra-agent-action-result', finish as EventListener);
                if (detail.ok === false) {
                    reject(new Error(detail.message || 'AI Agent 화면 명령을 실행하지 못했습니다.'));
                    return;
                }
                resolve();
            };
            window.addEventListener('docker-infra-agent-action-result', finish as EventListener);
            timer = window.setTimeout(() => {
                window.removeEventListener('docker-infra-agent-action-result', finish as EventListener);
                reject(new Error(`AI Agent 화면 명령 응답 시간이 초과되었습니다: ${target}`));
            }, 15000);
            window.dispatchEvent(new CustomEvent('docker-infra-agent-action', {
                detail: {
                    request_id: requestId,
                    target,
                    payload,
                    reason: action?.reason || ''
                }
            }));
        });
    }

    private async executeAgentApiRequest(action: any) {
        const operation = this.findAgentApiOperation(action);
        if (!operation) {
            throw new Error(`AI Agent API 작업을 찾을 수 없습니다: ${action?.operation_id || action?.target || ''}`);
        }
        const body = this.agentActionObject(action?.body || action?.payload);
        const params = this.agentActionObject(action?.params);
        const payload = await this.resolveAgentApiEntityPayload(operation, { ...params, ...body });
        const path = this.interpolateAgentApiPath(operation.path, payload);
        const method = operation.method || 'POST';
        const request: RequestInit = { method, credentials: 'same-origin' };
        let url = path;

        if (method === 'GET') {
            const query = this.agentApiSearchParams(payload);
            if (query.toString()) url += `${url.includes('?') ? '&' : '?'}${query.toString()}`;
        } else {
            request.headers = { 'Content-Type': 'application/json' };
            request.body = JSON.stringify(payload || {});
        }

        const response = await fetch(url, request);
        const data = await response.json().catch(() => ({}));
        const code = Number(data?.code || response.status || 500);
        if (!response.ok || code >= 400) {
            throw new Error(data?.data?.message || data?.message || `${operation.summary || operation.operation_id} 실패 (${code})`);
        }
        return data?.data || data || {};
    }

    private async resolveAgentApiEntityPayload(operation: AgentApiOperation, payload: any) {
        const next = { ...(payload || {}) };
        if (this.agentOperationNeedsServiceId(operation.operation_id) && !this.normalizeText(next.service_id)) {
            const serviceName = this.normalizeText(next.service_name || next.service || next.name || next.namespace);
            if (serviceName) {
                next.service_id = await this.resolveAgentServiceIdByName(serviceName);
            }
        }
        return next;
    }

    private agentOperationNeedsServiceId(operationId: string) {
        return [
            'services.deploy',
            'services.deploy_sync',
            'services.delete',
            'services.refresh_status',
            'services.detail',
            'services.logs',
            'services.extras',
            'services.backups',
            'services.advanced',
            'services.save_nginx',
            'services.save_compose',
            'services.update',
            'services.rollback_plan',
            'services.rollback',
            'services.runtime_ai_repair',
            'services.runtime_ai_verify',
            'services.backup_image',
            'services.snapshot_image',
            'services.refresh_image_records',
            'services_create.deploy',
            'services_create.deploy_background',
        ].includes(this.normalizeText(operationId));
    }

    private async resolveAgentServiceIdByName(serviceName: string) {
        const target = this.normalizeComparableText(serviceName);
        if (!target) throw new Error('서비스 이름이 비어 있어 service_id를 확인할 수 없습니다.');
        const response = await fetch('/wiz/api/page.services/load', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: '{}',
        });
        const raw = await response.json().catch(() => ({}));
        const code = Number(raw?.code || response.status || 500);
        if (!response.ok || code >= 400) {
            throw new Error(raw?.data?.message || raw?.message || `서비스 목록 조회 실패 (${code})`);
        }
        const data = raw?.data || {};
        const rows = Array.isArray(data.services) ? data.services : (Array.isArray(data.items) ? data.items : []);
        const matches = rows.filter((item: any) => {
            const values = [item?.id, item?.name, item?.namespace, item?.stack_name].map((value) => this.normalizeComparableText(value));
            return values.includes(target);
        });
        const partial = matches.length ? matches : rows.filter((item: any) => {
            const values = [item?.name, item?.namespace, item?.stack_name].map((value) => this.normalizeComparableText(value));
            return values.some((value) => value && (value.includes(target) || target.includes(value)));
        });
        if (partial.length === 1 && partial[0]?.id) return String(partial[0].id);
        if (partial.length > 1) throw new Error(`서비스 이름이 여러 항목과 일치합니다: ${serviceName}`);
        throw new Error(`서비스를 찾을 수 없습니다: ${serviceName}`);
    }

    private normalizeComparableText(value: any) {
        return this.normalizeText(value).toLowerCase();
    }

    private findAgentApiOperation(action: any) {
        const operationId = this.normalizeText(action?.operation_id || action?.operationId || action?.target);
        if (operationId) {
            const byId = this.agentApiOperations.find((item) => item.operation_id === operationId);
            if (byId) return byId;
        }
        const path = this.normalizeText(action?.path);
        const method = this.normalizeText(action?.method || 'POST').toUpperCase();
        if (!path) return null;
        return this.agentApiOperations.find((item) => item.path === path && item.method === method) || null;
    }

    private agentActionObject(value: any) {
        return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    }

    private interpolateAgentApiPath(path: string, payload: any) {
        return String(path || '').replace(/\{([^}]+)\}/g, (_match, key) => {
            const value = payload?.[key];
            if (value === undefined || value === null || value === '') {
                throw new Error(`API 경로 파라미터가 비어 있습니다: ${key}`);
            }
            return encodeURIComponent(String(value));
        });
    }

    private agentApiSearchParams(payload: any) {
        const form = new URLSearchParams();
        Object.keys(payload || {}).forEach((key) => {
            const value = payload[key];
            if (value === undefined || value === null) return;
            form.set(key, typeof value === 'string' ? value : JSON.stringify(value));
        });
        return form;
    }

    private closeVisibleModal() {
        const buttons = Array.from(document.querySelectorAll('button'))
            .filter((item) => item instanceof HTMLElement)
            .map((item) => item as HTMLElement)
            .filter((item) => this.isVisibleElement(item));
        const closeButton = buttons.find((item) => /닫기|취소|close|cancel/i.test(this.elementLabel(item)));
        if (closeButton) {
            closeButton.click();
            return true;
        }
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        return true;
    }

    private fillElement(element: HTMLElement, value: string) {
        if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement) {
            element.focus();
            element.value = String(value || '');
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    private findAgentElement(ref: string, action?: any) {
        const safeRef = String(ref || '').replace(/"/g, '\\"');
        if (safeRef) {
            const byRef = document.querySelector(`[data-ai-agent-ref="${safeRef}"]`) as HTMLElement | null;
            if (byRef && this.isVisibleElement(byRef)) return byRef;
        }
        return this.findAgentElementByLabel(action?.target || ref, action?.type);
    }

    private findAgentElementByLabel(label: string, actionType?: string) {
        const query = this.normalizeText(label).toLowerCase();
        if (!query) return null;
        const selector = 'button,a,input,textarea,select,[role="button"],[tabindex]';
        const candidates = Array.from(document.querySelectorAll(selector))
            .filter((item) => item instanceof HTMLElement)
            .map((item) => item as HTMLElement)
            .filter((item) => !this.isAgentSurfaceElement(item) && this.isVisibleElement(item));

        const normalizedLabel = (item: HTMLElement) => this.elementLabel(item).toLowerCase();
        const exact = candidates.find((item) => normalizedLabel(item) === query);
        if (exact) return exact;

        const contains = candidates.find((item) => normalizedLabel(item).includes(query));
        if (contains) return contains;

        if (String(actionType || '').toLowerCase() === 'fill') {
            const field = candidates.find((item) => {
                const element = item as HTMLInputElement;
                const parts = [
                    element.name || '',
                    element.id || '',
                    element.getAttribute('placeholder') || '',
                    element.getAttribute('aria-label') || '',
                    this.associatedLabelText(item),
                ].map((value) => this.normalizeText(value).toLowerCase());
                return parts.some((part) => part === query || part.includes(query));
            });
            if (field) return field;
        }

        return null;
    }

    private closestInteractiveElement(target: EventTarget | null) {
        if (!(target instanceof Element)) return null;
        return target.closest('button,a,input,textarea,select,[role="button"],[tabindex]') as HTMLElement | null;
    }

    private describeElement(element: HTMLElement | null) {
        if (!element || this.isAgentSurfaceElement(element) || !this.isVisibleElement(element)) return null;
        return {
            ref: this.ensureAgentRef(element),
            tag: element.tagName.toLowerCase(),
            type: element.getAttribute('type') || element.getAttribute('role') || '',
            label: this.elementLabel(element),
            value: this.safeFieldValue(element)
        };
    }

    private ensureAgentRef(element: HTMLElement) {
        let ref = element.getAttribute('data-ai-agent-ref');
        if (!ref) {
            this.agentRefCounter += 1;
            ref = `ai-ref-${this.agentRefCounter}`;
            element.setAttribute('data-ai-agent-ref', ref);
        }
        return ref;
    }

    private elementLabel(element: HTMLElement) {
        const text = [
            element.getAttribute('aria-label') || '',
            element.getAttribute('title') || '',
            this.associatedLabelText(element),
            element.getAttribute('placeholder') || '',
            element.innerText || '',
            (element as HTMLInputElement).value || '',
            element.getAttribute('name') || '',
            element.getAttribute('id') || '',
        ].filter(Boolean).join(' · ');
        return this.normalizeText(text).slice(0, 240);
    }

    private associatedLabelText(element: HTMLElement) {
        const id = element.getAttribute('id') || '';
        if (id) {
            const explicit = document.querySelector(`label[for="${id.replace(/"/g, '\\"')}"]`) as HTMLElement | null;
            if (explicit) return explicit.innerText || '';
        }
        const label = element.closest('label') as HTMLElement | null;
        if (label) return label.innerText || '';
        return '';
    }

    private safeFieldValue(element: HTMLElement) {
        const input = element as HTMLInputElement;
        const type = String(input.type || '').toLowerCase();
        const name = `${input.name || ''} ${input.id || ''} ${input.getAttribute('autocomplete') || ''}`;
        if (!('value' in input)) return '';
        if (type === 'password' || /(password|secret|token|key|auth|credential)/i.test(name)) return '********';
        if (type === 'checkbox' || type === 'radio') return input.checked ? 'checked' : 'unchecked';
        return String(input.value || '').slice(0, 240);
    }

    private isVisibleElement(element: HTMLElement) {
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
    }

    private isAgentSurfaceElement(element: HTMLElement) {
        return Boolean(element.closest('.ai-agent-surface'));
    }

    private currentRoutePath() {
        return String(this.router.url || location.pathname || '').split('?')[0];
    }

    private normalizeText(value: any) {
        return String(value || '').replace(/\s+/g, ' ').trim();
    }

    private sleep(ms: number) {
        return new Promise((resolve) => window.setTimeout(resolve, Math.max(0, ms || 0)));
    }

    private addAgentMessage(role: AgentMessage['role'], content: string, provider?: string) {
        const message = {
            id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
            role,
            content,
            provider,
            at: new Date().toISOString()
        };
        this.agentMessages.push(message);
        if (this.agentMessages.length > 40) this.agentMessages = this.agentMessages.slice(-40);
        return message;
    }

    private scrollAgentMessages() {
        setTimeout(() => {
            const container = document.querySelector('.ai-agent-messages') as HTMLElement | null;
            if (container) container.scrollTop = container.scrollHeight;
        }, 0);
    }
}
