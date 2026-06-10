import { expect, test } from '@playwright/test';
import { loginOrSkipIfAuthPending } from '../helpers/auth';
import { e2eEnv, skipWithoutBaseURL } from '../helpers/env';

const answerText = '검증 결과: 이 문장은 AI Agent 응답 본문을 마우스로 드래그해서 복사할 때 선택 블록이 유지되는지 확인하기 위한 긴 테스트 문장입니다. 렌더 예약이 발생해도 선택 문자열은 사라지면 안 됩니다.';
const historyAnswerText = '히스토리 결과: 목록에서 긴 제목이나 요청 내용을 드래그해서 복사할 수 있어야 합니다. 버튼 내부 텍스트이면 선택이 바로 해제될 수 있습니다.';

test.describe('AI Agent selection behavior', () => {
  test.beforeEach(() => {
    skipWithoutBaseURL();
  });

  test('keeps assistant response text selected while context render is deferred', async ({ page, context }) => {
    const base = new URL(e2eEnv.baseURL);
    await context.addCookies([
      { name: 'season-wiz-project', value: 'main', domain: base.hostname, path: '/' },
      { name: 'season-wiz-devmode', value: 'true', domain: base.hostname, path: '/' },
    ]);

    const json = (data: unknown) => ({
      status: 200,
      contentType: 'application/json; charset=utf-8',
      body: JSON.stringify({ code: 200, data }),
    });

    await page.route('**/api/ai-agent/status', (route) => route.fulfill(json({
      enabled: true,
      default_agent: 'codex',
      agent_label: 'Codex Agent',
      message: 'ready',
      capabilities: { operations: [] },
    })));
    await page.route('**/api/ai-agent/capabilities', (route) => route.fulfill(json({ operations: [] })));
    await page.route('**/api/ai-agent/plan', (route) => route.fulfill(json({
      summary: '선택 유지 검증',
      todos: [{ title: '응답 선택 유지 확인', prompt: '응답 선택 유지 확인', reason: '' }],
    })));
    await page.route('**/api/ai-agent/stream', (route) => route.fulfill({
      status: 200,
      contentType: 'text/event-stream; charset=utf-8',
      body: [
        `data: ${JSON.stringify({ type: 'provider' })}\n\n`,
        `data: ${JSON.stringify({ type: 'thinking', message: '응답 선택 유지 테스트를 준비합니다.' })}\n\n`,
        `data: ${JSON.stringify({ type: 'delta', text: answerText })}\n\n`,
        `data: ${JSON.stringify({ type: 'complete', data: { duration_ms: 1200, suggested_actions: [] }, provider: 'Codex Agent' })}\n\n`,
      ].join(''),
    }));

    await loginOrSkipIfAuthPending(page);
    await page.getByLabel('AI Agent 열기').click();
    await page.locator('textarea[name="agentInput"]').fill('응답 선택 유지 테스트');
    await page.locator('button.ai-agent-send').click();

    const answerBlock = page.locator('.ai-agent-message-assistant .ai-agent-markdown').last();
    await expect(answerBlock).toContainText('검증 결과:');

    const paragraph = answerBlock.locator('p').first();
    await paragraph.scrollIntoViewIfNeeded();
    const selectedNow = await paragraph.evaluate((element) => {
      const text = Array.from(element.childNodes).find((node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim());
      if (!text || !text.textContent) return '';
      const range = document.createRange();
      range.setStart(text, 0);
      range.setEnd(text, Math.min(70, text.textContent.length));
      const selection = window.getSelection();
      selection?.removeAllRanges();
      selection?.addRange(range);
      return selection?.toString() || '';
    });
    expect(selectedNow.trim().length).toBeGreaterThan(0);

    await page.evaluate(() => {
      const marker = document.createElement('div');
      marker.id = 'selection-render-marker';
      marker.textContent = 'selection render marker';
      document.body.appendChild(marker);
      window.setTimeout(() => marker.remove(), 20);
    });
    await page.waitForTimeout(1600);

    const selectedAfter = await page.evaluate(() => window.getSelection()?.toString() || '');
    expect(selectedAfter.trim().length).toBeGreaterThan(0);
  });

  test('keeps history list text selectable without opening the detail on drag', async ({ page, context }) => {
    const base = new URL(e2eEnv.baseURL);
    await context.addCookies([
      { name: 'season-wiz-project', value: 'main', domain: base.hostname, path: '/' },
      { name: 'season-wiz-devmode', value: 'true', domain: base.hostname, path: '/' },
    ]);

    const json = (data: unknown) => ({
      status: 200,
      contentType: 'application/json; charset=utf-8',
      body: JSON.stringify({ code: 200, data }),
    });

    const historyItem = {
      id: 'hist-1',
      session_id: 'session-1',
      agent_type: 'codex',
      agent_label: 'Codex Agent',
      status: 'succeeded',
      created_at: '2026-06-08T08:30:00Z',
      session_title: '히스토리 목록 선택 유지 테스트 긴 제목입니다',
      request_message: '히스토리 목록 카드의 텍스트를 복사하려고 드래그합니다',
      response_summary: historyAnswerText,
      duration_ms: 1200,
      turn_count: 1,
    };

    await page.route('**/api/ai-agent/status', (route) => route.fulfill(json({
      enabled: true,
      default_agent: 'codex',
      agent_label: 'Codex Agent',
      message: 'ready',
      capabilities: { operations: [] },
    })));
    await page.route('**/api/ai-agent/capabilities', (route) => route.fulfill(json({ operations: [] })));
    await page.route('**/api/ai-agent/history/sessions', (route) => route.fulfill(json({
      total: 1,
      limit: 20,
      offset: 0,
      items: [historyItem],
    })));
    await page.route('**/api/ai-agent/history/session', (route) => route.fulfill(json({
      ...historyItem,
      turns: [{
        id: 'turn-1',
        session_id: 'session-1',
        turn_index: 1,
        created_at: '2026-06-08T08:30:00Z',
        request_message: historyItem.request_message,
        response_answer: historyAnswerText,
        status: 'succeeded',
        duration_ms: 1200,
      }],
    })));

    await loginOrSkipIfAuthPending(page);
    await page.getByLabel('AI Agent 열기').click();
    await page.getByLabel('히스토리').click();

    const title = page.locator('.ai-agent-history-main strong').first();
    await expect(title).toContainText('히스토리 목록 선택 유지');
    const box = await title.boundingBox();
    expect(box).not.toBeNull();
    if (!box) return;

    await page.mouse.move(box.x + 2, box.y + (box.height / 2));
    await page.mouse.down();
    await page.mouse.move(box.x + Math.min(box.width - 2, 320), box.y + (box.height / 2), { steps: 14 });
    await page.mouse.up();

    const selectedNow = await page.evaluate(() => window.getSelection()?.toString() || '');
    expect(selectedNow.trim().length).toBeGreaterThan(0);
    await expect(page.locator('.ai-agent-history-detail-dock')).toHaveCount(0);
  });

  test('keeps history turn card text selectable while context render is deferred', async ({ page, context }) => {
    const base = new URL(e2eEnv.baseURL);
    await context.addCookies([
      { name: 'season-wiz-project', value: 'main', domain: base.hostname, path: '/' },
      { name: 'season-wiz-devmode', value: 'true', domain: base.hostname, path: '/' },
    ]);

    const json = (data: unknown) => ({
      status: 200,
      contentType: 'application/json; charset=utf-8',
      body: JSON.stringify({ code: 200, data }),
    });

    const historyItem = {
      id: 'hist-1',
      session_id: 'session-1',
      agent_type: 'codex',
      agent_label: 'Codex Agent',
      status: 'succeeded',
      created_at: '2026-06-08T08:30:00Z',
      session_title: '히스토리 turn 카드 선택 유지 테스트',
      request_message: '히스토리 turn 카드의 응답 텍스트를 복사하려고 드래그합니다',
      response_summary: historyAnswerText,
      duration_ms: 1200,
      turn_count: 1,
    };

    await page.route('**/api/ai-agent/status', (route) => route.fulfill(json({
      enabled: true,
      default_agent: 'codex',
      agent_label: 'Codex Agent',
      message: 'ready',
      capabilities: { operations: [] },
    })));
    await page.route('**/api/ai-agent/capabilities', (route) => route.fulfill(json({ operations: [] })));
    await page.route('**/api/ai-agent/history/sessions', (route) => route.fulfill(json({
      total: 1,
      limit: 20,
      offset: 0,
      items: [historyItem],
    })));
    await page.route('**/api/ai-agent/history/session', (route) => route.fulfill(json({
      ...historyItem,
      turns: [{
        id: 'turn-1',
        session_id: 'session-1',
        turn_index: 1,
        created_at: '2026-06-08T08:30:00Z',
        request_message: historyItem.request_message,
        response_answer: historyAnswerText,
        status: 'succeeded',
        duration_ms: 1200,
      }],
    })));

    await loginOrSkipIfAuthPending(page);
    await page.getByLabel('AI Agent 열기').click();
    await page.getByLabel('히스토리').click();
    await page.locator('.ai-agent-history-main').click();
    const turnAnswer = page.locator('.ai-agent-history-turn .ai-agent-markdown p').first();
    await expect(turnAnswer).toContainText('히스토리 결과:');
    const answerTextRect = await turnAnswer.evaluate((element) => {
      const text = Array.from(element.childNodes).find((node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim());
      if (!text || !text.textContent) return null;
      const range = document.createRange();
      range.setStart(text, 0);
      range.setEnd(text, Math.min(80, text.textContent.length));
      const rect = Array.from(range.getClientRects()).find((item) => item.width > 0 && item.height > 0);
      return rect ? { x: rect.x, y: rect.y, width: rect.width, height: rect.height } : null;
    });
    expect(answerTextRect).not.toBeNull();
    if (!answerTextRect) return;

    await page.mouse.move(answerTextRect.x + 2, answerTextRect.y + (answerTextRect.height / 2));
    await page.mouse.down();
    await page.mouse.move(answerTextRect.x + Math.min(answerTextRect.width - 2, 420), answerTextRect.y + (answerTextRect.height / 2), { steps: 14 });
    await page.mouse.up();
    await page.waitForTimeout(100);
    const selectedTurnText = await page.evaluate(() => window.getSelection()?.toString() || '');
    expect(selectedTurnText.trim().length).toBeGreaterThan(0);

    await page.evaluate(() => {
      const marker = document.createElement('div');
      marker.textContent = 'history turn selection marker';
      document.body.appendChild(marker);
      window.setTimeout(() => marker.remove(), 20);
    });
    await page.waitForTimeout(1200);
    const selectedAfterRender = await page.evaluate(() => window.getSelection()?.toString() || '');
    expect(selectedAfterRender.trim().length).toBeGreaterThan(0);
  });
});
