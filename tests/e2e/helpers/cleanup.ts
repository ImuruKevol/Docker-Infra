import fs from 'node:fs/promises';
import path from 'node:path';
import { test } from '@playwright/test';

const outputRoot = process.env.DOCKER_INFRA_E2E_OUTPUT_ROOT || '.runtime/e2e';
const cleanupRoot = path.resolve(outputRoot, 'cleanup');

type CleanupTask = {
  label: string;
  run: () => Promise<void> | void;
};

export function createCleanupRegistry() {
  const tasks: CleanupTask[] = [];
  return {
    add(label: string, run: CleanupTask['run']) {
      tasks.push({ label, run });
    },
    async run() {
      const failures: string[] = [];
      while (tasks.length) {
        const task = tasks.pop();
        if (!task) continue;
        try {
          await task.run();
        } catch (error) {
          failures.push(`${task.label}: ${String(error)}`);
        }
      }
      if (failures.length) throw new Error(`cleanup failed: ${failures.join('; ')}`);
    },
  };
}

export async function writeCleanupMarker(testRunId: string, namespace: string) {
  await fs.mkdir(cleanupRoot, { recursive: true });
  const markerPath = path.join(cleanupRoot, `${namespace}.json`);
  await fs.writeFile(
    markerPath,
    JSON.stringify({ test_run_id: testRunId, namespace, created_at: new Date().toISOString() }, null, 2),
    'utf-8',
  );
  return markerPath;
}

export function withCleanup() {
  const cleanup = createCleanupRegistry();
  test.afterEach(async () => {
    await cleanup.run();
  });
  return cleanup;
}
