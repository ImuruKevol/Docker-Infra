import { expect, test } from '@playwright/test';
import { openAccessPage, submitPassword } from '../helpers/auth';
import { e2eEnv, skipWithoutBaseURL, skipWithoutPassword } from '../helpers/env';

test.describe('password-only access', () => {
  test.beforeEach(() => {
    skipWithoutBaseURL();
  });

  test('shows the password-only access screen', async ({ page }) => {
    await openAccessPage(page);
    await expect(page.getByText(/운영자 접속|설치 관리자 필요/)).toBeVisible();
    await expect(page.getByRole('button', { name: /접속|설치 관리자 열기/ })).toBeVisible();
  });

  test('shows validation when password is empty', async ({ page }) => {
    await openAccessPage(page);
    if (await page.getByTestId('installer-open').isVisible().catch(() => false)) {
      await expect(page.getByText('설치 관리자 필요')).toBeVisible();
      return;
    }
    await page.getByTestId('login-submit').click();
    await expect(page.getByText('비밀번호를 입력해주세요.')).toBeVisible();
  });

  test('submits only a password for the login flow', async ({ page }) => {
    skipWithoutPassword();
    await openAccessPage(page);
    test.skip(await page.getByTestId('installer-open').isVisible().catch(() => false), 'Docker Infra installer setup is not completed yet');
    await submitPassword(page, e2eEnv.password || '');
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByText('Docker Infra').first()).toBeVisible();
  });
});
