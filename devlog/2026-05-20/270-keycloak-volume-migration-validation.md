# 270. Keycloak named volume 마이그레이션 실검증

- 날짜: 2026-05-20
- 요청: keycloak 서비스로 실제 검증 작업을 진행해줘. named volume에 아무 파일을 만들거나 한 다음 마이그레이션했을 때 유지가 되는지 등등.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-20/270-keycloak-volume-migration-validation.md`

## 검증 작업

- Keycloak의 `keycloak_ee269a_keycloak_postgres_data` named volume에 검증 marker를 생성했다.
- 서비스 마이그레이션 API로 Keycloak 서비스를 `mini2`에서 `mini3`로 실제 마이그레이션했다.
- 마이그레이션 operation `83491ef8-ac49-4ebc-b4f2-be37d03871ce`가 `succeeded`로 완료되고 `volume_migration.status`가 `succeeded`임을 확인했다.
- 마이그레이션 후 대상 서버 `mini3`의 named volume에서 동일 marker 값이 확인되어 volume 데이터 유지가 검증됐다.
- 검증 marker는 확인 후 `mini2`, `mini3` 양쪽 volume에서 제거했다.
- `docker service ps`로 Keycloak/PostgreSQL 태스크가 `mini3`에서 `Running` 상태임을 확인했다.
- Playwright Chromium으로 `https://keycloak.imurukevol.com`에 접속해 `Sign in to Keycloak` 화면과 HTTP 200 응답을 확인했다.

## 남은 리스크

- Swarm task history에는 Keycloak의 이전 실패 태스크 1개가 남아 있지만 현재 desired task는 `mini3`에서 정상 실행 중이다.
- 이번 검증은 marker 파일 이동과 Keycloak 로그인 화면 접근까지 확인했으며, Keycloak 관리자 로그인/업무 데이터 정합성 검증은 수행하지 않았다.
