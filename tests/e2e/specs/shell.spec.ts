import { expect, test } from '@playwright/test';
import { loginOrSkipIfAuthPending } from '../helpers/auth';
import { e2eEnv, skipWithoutBaseURL } from '../helpers/env';
import { createCleanupRegistry, writeCleanupMarker } from '../helpers/cleanup';

test.describe('application shell', () => {
  test.beforeEach(() => {
    skipWithoutBaseURL();
  });

  test('redirects unauthenticated protected routes to access', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/access/);
    await expect(page.getByRole('heading', { name: 'Docker Infra' })).toBeVisible();
  });

  test('loads the dashboard shell and Docker Infra navigation', async ({ page }) => {
    await loginOrSkipIfAuthPending(page);
    await page.goto('/dashboard');
    await expect(page.getByText('Docker Infra').first()).toBeVisible();
    await expect(page.getByRole('link', { name: /Docker Infra/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /Dashboard|대시보드/ })).toBeVisible();
  });

  test('can register cleanup metadata for UI-created resources', async () => {
    const cleanup = createCleanupRegistry();
    const namespace = `di_test_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}_${e2eEnv.testRunId.slice(0, 12)}`;
    const markerPath = await writeCleanupMarker(e2eEnv.testRunId, namespace);

    cleanup.add('ui-cleanup-marker', async () => {
      await import('node:fs/promises').then((fs) => fs.rm(markerPath, { force: true }));
    });

    await cleanup.run();
  });
});
