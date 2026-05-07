# Docker Infra E2E Tests

Playwright tests verify the real browser workflow and must not call internal Python or TypeScript service functions directly.

Tests must assert the full scenario outcome: user input, HTTP-backed result, URL transition, and visible screen state. Selector-only smoke checks are not sufficient for feature completion.

## Environment

Required for live browser execution:

- `DOCKER_INFRA_BASE_URL`: running Docker Infra app URL, usually `http://127.0.0.1:3001`
- `DOCKER_INFRA_TEST_PASSWORD`: password-only login test password
- `DOCKER_INFRA_TEST_RUN_ID`: optional fixed test run id

Optional:

- `DOCKER_INFRA_E2E_OUTPUT_ROOT`: defaults to `.runtime/e2e`
- `DOCKER_INFRA_E2E_START_CMD`: optional command Playwright should start before tests

## Commands

```bash
npm run e2e:list
DOCKER_INFRA_BASE_URL=http://127.0.0.1:3001 npm run e2e
```

Failure artifacts are stored under `.runtime/e2e` by default:

- `test-results`: screenshots, traces, videos
- `playwright-report`: HTML report
- `cleanup`: UI-created test resource markers

Every E2E test that creates DB rows, files, Docker resources, DNS records, or image tags must register cleanup.
