# 247. 스냅샷 롤백 배포 전 백업 저장소 Docker login 추가

- 날짜: 2026-05-19
- 리뷰 ID: zpohqovvxevuifffyabfrkowvcfssjat
- 분류: ux

## 원 요청

```text
아래 로그와 같이 작업 실행 대기 중에서 끝났어. 기존 실행 중이던 compose는 down이 되었는데, 새로운 이미지가 뜨지 않은 상태에서 종료처리되었어.
---
2026. 5. 19. 오후 2:15:35
stack placement
stack placement: mini2
2026. 5. 19. 오후 2:15:35
port allocation
port allocation: [{'service': 'mediawiki', 'target': 80, 'previous': 8080, 'published': 8080}]
2026. 5. 19. 오후 2:15:35
domain port mapping
domain port mapping: [{'domain': 'wiki.sub.nanoha.kr', 'target_port': 80, 'published_port': 8080}]
2026. 5. 19. 오후 2:15:35
system
[mini2] Docker insecure registry 설정을 적용합니다: 220.82.71.78:5000
2026. 5. 19. 오후 2:15:36
stdout
[mini2] configured insecure registries: 220.82.71.78:5000
Docker daemon insecure registries already configured
Docker daemon is ready
2026. 5. 19. 오후 2:15:36
stack down
기존 Docker stack을 내린 뒤 새 Compose로 다시 적용합니다.
2026. 5. 19. 오후 2:15:36
stack down
Removing service wiki_service_af4f85_db
Removing service wiki_service_af4f85_mediawiki
2026. 5. 19. 오후 2:15:36
stack down wait
stack down confirmed after 1 checks
2026. 5. 19. 오후 2:15:36
stack deploy
Creating service wiki_service_af4f85_db
Creating service wiki_service_af4f85_mediawiki
2026. 5. 19. 오후 2:17:40
runtime ready
Docker 작업 실행 대기 중입니다. 0/2
```

## 변경 파일

- `src/model/struct/services_deploy.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-19/247-snapshot-rollback-registry-login.md`

## 변경 내용

- 스냅샷 이미지가 포함된 롤백 배포에서 stack down 전에 백업 저장소 Docker login을 먼저 수행하도록 했다.
- Docker login 전에 stack deploy를 실행하는 배포 관리자 쪽 Docker daemon에도 동일한 백업 저장소 insecure registry 설정을 보장하도록 했다.
- Docker login은 `--password-stdin`으로 처리하고, 결과 요약만 배포 operation metadata에 남기도록 했다.
- 백업 저장소 login 실패 시 기존 stack을 내리기 전에 배포를 실패 처리하도록 순서를 고정했다.
- Swarm task가 reject 후 교체되어 현재 오류가 0개로 보이는 경우에도 task 오류 이력이 있으면 단순 대기 상태가 아니라 실패 원인으로 표시하도록 했다.

## 확인 결과

- `wiki_service_af4f85` 기준으로 stack service가 `0/1` 상태이며, task 이력에서 스냅샷 이미지 `No such image` reject를 확인했다.
- `src/model/struct/local_command_catalog.py`의 stack deploy가 `--with-registry-auth`를 사용함을 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_deploy.py src/model/struct/services_rollback.py src/app/page.services/api.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight tests.api.test_backup_system_ui tests.api.test_backup_system_schedule tests.api.test_backup_system_cleanup tests.api.test_images_templates_catalog` 통과 (`24 tests`, `skipped=2`).
- `wiz_project_build(projectName="main", clean=false)` 통과.
- `curl -k -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/services` 200 확인.
- `git -C /root/docker-infra/project/main diff --check` 통과.

## 남은 리스크

- 실제 `wiki_service` 재롤백/재배포는 운영 Docker stack 변경을 동반하므로 수행하지 않았다.
