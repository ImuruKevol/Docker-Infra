# ORAS named volume 복원 경로 구현과 레이어 동작 검증

## 사용자 요청

작업 시작.
oras가 어떻게 돌아가는지 상세하게 검증을 해야해. 일반적인 docker image처럼 layer 단위로 쌓이는 형태로 동작해서 중복되는 부분은 생략되는 등 최적화가 되어있는지.
내가 듣기로는 layer 단위로 최적화되어있지는 않아서 그냥 통으로 관리하는 형태라고 들었어.
이 부분도 중점적으로 확인해줘.

## 변경 파일

- `src/model/struct/service_volume_backups.py`
- `src/model/struct/services_rollback.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `tests/api/test_backup_system_ui.py`

## 작업 내용

- ORAS에 저장된 named volume artifact를 compose version rollback 시 다시 pull하고 대상 Docker volume에 풀어쓰는 복원 경로를 추가했다.
- rollback plan에 named volume artifact 상태를 포함하고, 보존 만료 artifact가 있으면 복원을 차단하도록 연결했다.
- 서비스 버전 이력의 되돌리기 모달에 named volume 복원 요약과 대상 artifact 목록을 표시했다.
- ORAS 동작 검증을 위해 named volume만 사용하는 임시 서비스를 생성하고, 동일 archive와 변경 archive를 각각 push해 manifest layer digest를 비교했다.

## 검증 결과

- `wiz_project_build(clean=false)` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_ui tests.api.test_backup_system_schedule` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/service_volume_backups.py src/model/struct/services_rollback.py` 성공.
- 실제 검증 서비스 `oras_volume_local_103856`에서 named volume `oras_volume_local_103856_data`를 백업하고, 파일 수정 후 rollback 복원으로 `state.txt`가 `initial-from-backup`으로 돌아가고 추가 파일이 삭제되는 것을 확인했다.
- ORAS manifest는 volume tar.gz를 `application/vnd.docker-infra.volume.layer.v1+gzip` 단일 layer로 저장했다. 동일 archive 재 push는 같은 blob digest를 사용했지만, 일부 파일만 바꾼 archive는 전체 tar.gz digest와 layer digest가 바뀌었다.
- Playwright로 `/services/4c91db4b-754c-42f8-916a-88e7dce8a261/versions` 화면에서 되돌리기 모달의 `named volume 복원`, 대상 volume, `1개 가능` 표시를 확인했다. 스크린샷: `.runtime/reviewops-gmsjwhwlokicxzotzlqbhgqhznkrfucr/volume-rollback-ui.png`
- 같은 화면에서 volume 내용을 `ui-mutated-before-restore`로 다시 변경한 뒤 `되돌리고 적용` 버튼을 클릭했다. 최근 `service.compose.rollback` operation은 `succeeded`, `volume_restore_count=1`이고, volume의 `state.txt`는 `initial-from-backup`으로 복원됐으며 `ui-extra.txt`는 삭제됐다.

## 남은 리스크

- 현재 방식은 Docker image build layer처럼 파일 단위 delta를 누적하지 않고, volume tar.gz artifact 단위 content-addressed 저장에 의존한다. 동일 archive blob은 중복 저장을 피할 수 있지만, 파일 일부 변경 시 archive 전체가 새 blob이 된다.
- 실행 중 컨테이너의 volume을 tar로 읽는 방식이므로 애플리케이션 일관성이 필요한 DB류 워크로드는 별도 quiesce/snapshot 절차가 필요하다.
