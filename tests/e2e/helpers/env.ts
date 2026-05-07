import { test } from '@playwright/test';

export const e2eEnv = {
  baseURL: process.env.DOCKER_INFRA_BASE_URL || 'http://127.0.0.1:3001',
  password: process.env.DOCKER_INFRA_TEST_PASSWORD,
  testRunId: process.env.DOCKER_INFRA_TEST_RUN_ID || `pw-${Date.now()}`,
};

export function skipWithoutBaseURL() {
  test.skip(!e2eEnv.baseURL, 'DOCKER_INFRA_BASE_URL is not set');
}

export function skipWithoutPassword() {
  test.skip(!e2eEnv.password, 'DOCKER_INFRA_TEST_PASSWORD is not set');
}
