import { expect, test } from '@playwright/test';
import { loginOrSkipIfAuthPending } from '../helpers/auth';
import { e2eEnv, skipWithoutBaseURL } from '../helpers/env';

test.describe('services page', () => {
  test.beforeEach(() => {
    skipWithoutBaseURL();
  });

  test('shows services workspace and opens create page from board action', async ({ page }) => {
    await loginOrSkipIfAuthPending(page);
    await page.goto(`${e2eEnv.baseURL}/services`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForLoadState('networkidle').catch(() => undefined);
    await expect(page.getByText('서비스 관리').first()).toBeVisible();
    await expect(page.getByTestId('services-list')).toBeVisible();
    await expect(page.getByRole('banner').getByRole('link', { name: '새 서비스' })).toHaveCount(0);
    await page.getByTestId('services-list').getByRole('link', { name: '새 서비스' }).click();
    await expect(page).toHaveURL(/\/services\/create/);
    await expect(page.getByRole('heading', { name: '새 서비스 만들기' })).toBeVisible();
    await expect(page.getByText('생성 요약')).toHaveCount(0);
  });
});
