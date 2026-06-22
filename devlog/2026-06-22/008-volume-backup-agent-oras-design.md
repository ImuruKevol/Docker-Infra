# named volume 백업 설계 Agent 연동과 ORAS 공급 정책 보강

- 날짜: 2026-06-22
- 작업 ID: 008
- 리뷰 ID: vgosoiiihlsnzkukbdizwwevcjgpgjcg

## 사용자 요청

> 백업 설계 문서(project/main/docs/backup-named-volume-snapshot-design.md)에 Agent 관련 연동 내용도 추가가 되어야 해.
> 템플릿 생성 시 기본적으로는 컨테이너 스냅샷 + named volume을 모두 백업을 하도록 하지만, 설정에 따라 컨테이너 스냅샷은 굳이 하지 않도록 한다던가 할 수 있어야 해. 물론 이 부분이 Agent로 템플릿 생성 시 고려가 되도록 해야겠지.
>
> 자동 백업 시에는 기본적으로 컨테이너들 스냅샷 + named volume까지 모두 백업이 되어야 해.
>
> 그리고 oras 명령어를 사용한다고 되어있는데, 현재 각 서버들에는 해당 명령어가 설치되어있지 않아. 이 부분도 고려해서 진행해줘.

## 변경 파일

- `docs/backup-named-volume-snapshot-design.md`
  - 템플릿/서비스/자동 백업 공통 정책으로 `full_state`와 `volume_only` 모드를 정의.
  - 자동 백업 기본값을 컨테이너 스냅샷과 named volume 백업을 모두 포함하는 `service_state_snapshot`으로 정리.
  - Agent 템플릿 생성/검증 계약에 백업 정책 생성, volume 후보 설명, `volume_only` 선택 조건, 응답 요약 규칙을 추가.
  - target node에 `oras`가 없는 전제를 반영해 helper image 또는 installer-bundled binary로 ORAS를 공급하는 방식을 추가.
- `tests/api/test_backup_system_cleanup.py`
  - named volume 백업 설계 문서가 Agent 연동, `full_state`, 컨테이너 스냅샷 제외 옵션, ORAS 공급 실패 코드를 포함하는지 정적 검증 추가.
- `devlog.md`, `devlog/2026-06-22/008-volume-backup-agent-oras-design.md`
  - 작업 기록 추가.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile tests/api/test_backup_system_cleanup.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_cleanup`
- `git diff --check`

## 남은 리스크

- 이번 작업은 설계 문서와 정적 계약 보강이며, 실제 volume backup runner, helper image 배포, Agent 템플릿 생성 로직 구현은 후속 작업이다.
