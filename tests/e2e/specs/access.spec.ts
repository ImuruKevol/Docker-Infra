import { expect, test } from '@playwright/test';
import { openAccessPage, submitPassword } from '../helpers/auth';
import { e2eEnv, skipWithoutBaseURL, skipWithoutPassword } from '../helpers/env';

test.describe('password-only access', () => {
  test.beforeEach(() => {
    skipWithoutBaseURL();
  });

  test('shows the password-only access screen', async ({ page }) => {
    await openAccessPage(page);
    await expect(page.getByText(/운영자 접속|초기 설정/)).toBeVisible();
    await expect(page.getByRole('button', { name: /접속|설정 완료/ })).toBeVisible();
  });

  test('shows validation when password is empty', async ({ page }) => {
    await openAccessPage(page);
    if (await page.getByTestId('setup-submit').isVisible().catch(() => false)) {
      await page.getByTestId('setup-submit').click();
      await expect(page.getByText('관리자 비밀번호를 입력해주세요.')).toBeVisible();
      return;
    }
    await page.getByTestId('login-submit').click();
    await expect(page.getByText('비밀번호를 입력해주세요.')).toBeVisible();
  });

  test('submits only a password for the login flow', async ({ page }) => {
    skipWithoutPassword();
    await openAccessPage(page);
    test.skip(await page.getByTestId('setup-submit').isVisible().catch(() => false), 'Initial setup is not completed yet');
    await submitPassword(page, e2eEnv.password || '');
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByText('Docker Infra').first()).toBeVisible();
  });
});
