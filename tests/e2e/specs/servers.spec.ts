import { expect, test } from '@playwright/test';
import { loginOrSkipIfAuthPending } from '../helpers/auth';
import { e2eEnv, skipWithoutBaseURL } from '../helpers/env';

test.describe('server detail', () => {
  test.beforeEach(() => {
    skipWithoutBaseURL();
  });

  test('shows the server detail dashboard and container list', async ({ page }) => {
    await loginOrSkipIfAuthPending(page);
    await page.goto(`${e2eEnv.baseURL}/servers`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForLoadState('networkidle').catch(() => undefined);
    await expect(page.getByText('서버 관리').first()).toBeVisible();
    await expect(page.getByTestId('servers-node-list')).toBeVisible();
    await expect(page.getByTestId('servers-detail')).toBeVisible();
    await expect(page.getByTestId('servers-containers-table')).toBeVisible();
    await expect(page.getByText('자동 갱신').first()).toBeVisible();
    await expect(page.getByText('상태 수집 준비')).toHaveCount(0);
    await expect(page.getByText('등록된 서비스').first()).toBeVisible();
    await expect(page.getByText('미등록 컨테이너')).toHaveCount(0);
    await expect(page.getByText('매크로').first()).toBeVisible();
  });

  test('shows macro and terminal tabs plus the global macros menu', async ({ page }) => {
    await loginOrSkipIfAuthPending(page);
    await page.goto(`${e2eEnv.baseURL}/servers`);
    await page.waitForLoadState('domcontentloaded');

    await page.getByRole('button', { name: '매크로' }).first().click();
    await expect(page.getByText('이 서버 전용 매크로').first()).toBeVisible();
    await expect(page.getByRole('button', { name: '추가' }).first()).toBeVisible();

    await page.getByRole('button', { name: '웹 터미널' }).click();
    await expect(page.getByRole('button', { name: '터미널 연결' }).first()).toBeVisible();
    await expect(page.getByTestId('servers-terminal-host')).toBeVisible();

    await page.goto(`${e2eEnv.baseURL}/macros`);
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByText('전역 매크로').first()).toBeVisible();
    await expect(page.getByRole('button', { name: '매크로 추가' }).first()).toBeVisible();
  });

  test('connects and disconnects the web terminal on demand', async ({ page }) => {
    await loginOrSkipIfAuthPending(page);
    await page.goto(`${e2eEnv.baseURL}/servers`);
    await page.waitForLoadState('domcontentloaded');

    await page.getByRole('button', { name: '웹 터미널' }).click();
    await page.getByRole('button', { name: '터미널 연결' }).click();
    await expect(page.getByRole('button', { name: '다시 연결' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('button', { name: '연결 종료' })).toBeEnabled({ timeout: 10000 });
    await page.getByRole('button', { name: '연결 종료' }).click();
    await expect(page.getByRole('button', { name: '터미널 연결' })).toBeVisible({ timeout: 10000 });
  });

  test('expands the web terminal to use the server list area and restores the default layout', async ({ page }) => {
    await loginOrSkipIfAuthPending(page);
    await page.goto(`${e2eEnv.baseURL}/servers`);
    await page.waitForLoadState('domcontentloaded');

    await page.getByRole('button', { name: '웹 터미널' }).click();
    await expect(page.getByTestId('servers-node-list')).toBeVisible();
    await page.getByTestId('servers-terminal-expand-toggle').click();
    await expect(page.getByTestId('servers-node-list')).toBeHidden();
    await expect(page.getByTestId('servers-terminal-host')).toBeVisible();
    await page.getByTestId('servers-terminal-expand-toggle').click();
    await expect(page.getByTestId('servers-node-list')).toBeVisible();
  });

  test('hides unmanaged container registration controls', async ({ page }) => {
    await loginOrSkipIfAuthPending(page);
    await page.goto(`${e2eEnv.baseURL}/servers`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForLoadState('networkidle').catch(() => undefined);

    await expect(page.getByText('미등록 컨테이너')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Compose 등록' })).toHaveCount(0);
  });

  test('keeps the selected server stable when an older detail response arrives late', async ({ page }) => {
    await loginOrSkipIfAuthPending(page);

    let delayed = false;
    await page.route('**/wiz/api/page.servers/cached_detail', async (route) => {
      if (!delayed) {
        delayed = true;
        await new Promise((resolve) => setTimeout(resolve, 1500));
      }
      const response = await route.fetch();
      await route.fulfill({ response });
    });

    await page.goto(`${e2eEnv.baseURL}/servers`);
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('servers-node-list')).toBeVisible();

    await page.getByRole('button', { name: /mini2/ }).click();
    await expect(page.getByTestId('servers-detail')).toContainText('mini2');
    await page.waitForTimeout(1800);
    await expect(page.getByTestId('servers-detail')).toContainText('mini2');
  });
});
