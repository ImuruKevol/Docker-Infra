import { expect, test } from '@playwright/test';
import { loginOrSkipIfAuthPending } from '../helpers/auth';
import { e2eEnv, skipWithoutBaseURL } from '../helpers/env';

test.describe('services page', () => {
  test.beforeEach(() => {
    skipWithoutBaseURL();
  });

  test('shows services workspace and create modal', async ({ page }) => {
    await loginOrSkipIfAuthPending(page);
    await page.goto(`${e2eEnv.baseURL}/services`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForLoadState('networkidle').catch(() => undefined);
    await expect(page.getByText('서비스 관리').first()).toBeVisible();
    await expect(page.getByTestId('services-list')).toBeVisible();
    await page.getByRole('banner').getByRole('button', { name: '새 서비스' }).click();
    await expect(page.getByTestId('service-create-modal')).toBeVisible();
    await expect(page.getByText('기본 웹 서비스').first()).toBeVisible();
  });
});
