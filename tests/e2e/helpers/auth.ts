import { expect, Page, test } from '@playwright/test';
import { e2eEnv } from './env';

export async function openAccessPage(page: Page) {
  await page.goto('/access');
  await expect(page.getByText('Docker Infra').first()).toBeVisible();
  await expect(page.getByTestId(/password-input|installer-open/)).toHaveCount(1);
}

export async function submitPassword(page: Page, password: string) {
  await page.getByTestId('password-input').fill(password);
  await page.getByTestId('login-submit').click();
}

export async function loginOrSkipIfAuthPending(page: Page) {
  test.skip(!e2eEnv.password, 'DOCKER_INFRA_TEST_PASSWORD is not set');
  await openAccessPage(page);
  if (await page.getByTestId('installer-open').isVisible().catch(() => false)) {
    test.skip(true, 'Docker Infra installer setup is not completed yet');
  }
  await submitPassword(page, e2eEnv.password || '');
  await expect(page).toHaveURL(/\/dashboard/);
  await page.waitForLoadState('domcontentloaded');
  await page.waitForLoadState('networkidle').catch(() => undefined);
}
