# 250. 롤백 배포 완료 직전 metadata datetime 직렬화 오류 수정

- 날짜: 2026-05-19
- 리뷰 ID: zpohqovvxevuifffyabfrkowvcfssjat
- 분류: ux

## 원 요청

```text
처리 로그에서 마지막 부분에 아래와 같은 에러 로그가 떴어.
2026. 5. 19. 오후 3:07:54
nginx apply
nginx 설정과 DDNS DNS 등록을 적용했습니다.
2026. 5. 19. 오후 3:07:54
background deploy
Object of type datetime is not JSON serializable
```

## 변경 파일

- `src/model/struct/services_deploy.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-19/250-rollback-deploy-metadata-serialization.md`

## 변경 내용

- 배포 완료 직전 `services.metadata.last_deploy`를 저장할 때 기존 서비스 serializer를 거쳐 datetime/date/UUID/Decimal 값을 JSONB 저장 가능 값으로 변환하도록 했다.
- `backup_registry_setup`, `backup_registry_login`, `stack_recreate`처럼 node/status 결과가 포함될 수 있는 배포 부가 정보도 안전하게 저장되도록 했다.
- 배포 계약 테스트에 metadata 직렬화 경로 검사를 추가했다.

## 확인 결과

- 오류 위치가 nginx 적용 이후 service metadata 저장 단계임을 코드 경로로 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_deploy.py src/model/struct/backup_system_runtime.py src/model/struct/local_command_catalog.py src/app/page.services/api.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_runtime tests.api.test_services_preflight tests.api.test_backup_system_ui tests.api.test_backup_system_schedule tests.api.test_backup_system_cleanup tests.api.test_images_templates_catalog` 통과 (`30 tests`, `skipped=2`).
- `wiz_project_build(projectName="main", clean=false)` 통과.
- `curl -k -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/services` 200 확인.
- `git -C /root/docker-infra/project/main diff --check` 통과.

## 남은 리스크

- 실제 `wiki_service` 재롤백/재배포는 운영 Docker stack 변경을 동반하므로 수행하지 않았다.
