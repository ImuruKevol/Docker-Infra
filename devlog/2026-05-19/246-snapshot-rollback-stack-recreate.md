# 246. 스냅샷 롤백 적용 시 stack 재생성과 백업 registry 보장

- 날짜: 2026-05-19
- 리뷰 ID: zpohqovvxevuifffyabfrkowvcfssjat
- 분류: ux

## 원 요청

```text
버전 이력에서 스냅샷이 있는 버전으로 되돌리고 적용을 했어. 근데 처리 로그에서 "Docker 작업 오류 1개가 감지되었습니다." 에러 로그가 떴어. 스냅샷으로 되돌리는 기능이 개발되지 않은 것 같아. 현재 동작 중인 Compose를 down시킨 후 compose를 되돌리고, 스냅샷이 있으면 해당 스냅샷의 이미지로 compose의 이미지를 교체한 다음 다시 compose up을 해야 하는데, 동작 중인 compose가 멀쩡히 동작하고 있어.
wiki_service 기준으로 확인해줘.
```

## 변경 파일

- `src/model/struct/services_deploy.py`
- `src/app/page.services/view.ts`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-19/246-snapshot-rollback-stack-recreate.md`

## 변경 내용

- 버전 되돌리고 적용 시 배포 요청에 `force_recreate`를 전달해 기존 Docker stack을 내린 뒤 새 Compose로 다시 올리도록 했다.
- 스냅샷 이미지가 반영된 롤백이면 배포 전 대상 노드의 백업 저장소 insecure registry 설정을 보장하도록 했다.
- stack down, down 대기, registry 설정 결과를 서비스 배포 operation 로그에 남기도록 했다.

## 확인 결과

- `wiki_service_af4f85` 기준으로 `docker stack ps`를 확인해 `snapshot-db` task reject와 `snapshot-mediawiki` task pending을 확인했다.
- `/var/log/syslog`에서 백업 저장소 registry를 HTTPS로 접근해 실패한 로그를 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_deploy.py src/model/struct/services_rollback.py src/app/page.services/api.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight tests.api.test_backup_system_ui tests.api.test_backup_system_schedule tests.api.test_backup_system_cleanup tests.api.test_images_templates_catalog` 통과 (`24 tests`, `skipped=2`).
- `wiz_project_build(projectName="main", clean=false)` 통과.
- `curl -k -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/services` 200 확인.
- `git -C /root/docker-infra/project/main diff --check` 통과.

## 남은 리스크

- 실제 `wiki_service` 재롤백/재배포는 stack down과 Docker daemon registry 설정 변경을 동반하므로 수행하지 않았다.
