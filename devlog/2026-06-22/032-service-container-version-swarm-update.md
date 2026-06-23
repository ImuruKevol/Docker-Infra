# overlay 서비스 버전 변경 적용 경로 보정

- **ID**: 032
- **날짜**: 2026-06-22
- **유형**: 버그 수정
- **리뷰 ID**: iygagnmtnjaerziptyiubkzcapwlmyjy

## 작업 요약
버전 변경 적용 시 overlay 네트워크를 쓰는 서비스의 Compose 파일을 bridge compose 기준으로 강제 검증해 실패하던 문제를 수정했다.
서비스의 원래 deployment context를 유지해 overlay 네트워크 검증을 통과하도록 되돌리고, Swarm 서비스는 `docker service update --with-registry-auth --image`로 해당 stack service만 갱신하도록 분기했다.
Compose 서비스는 기존 `docker compose up -d --no-deps` 경로를 유지한다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

notedown-server 서비스에서 버전을 260622로 변경하려고 했는데 아래 에러가 뜨고 있어.
제대로 이 docker infra를 통해 만든 서비스인데 이상하잖아. 버그 원인을 파악하고 수정해줘.

---

Compose 검사를 통과하지 못했습니다.

- networks.docker_infra_overlay: docker_infra_bridge network만 사용할 수 있습니다.
- services.notedown-server.networks: service network는 docker_infra_bridge만 사용할 수 있습니다.

## 리뷰 요약

- 리뷰 ID: iygagnmtnjaerziptyiubkzcapwlmyjy
- 제목: 서비스 관리 상세 - 편의 기능 추가
- 요청 링크: https://infra-dev.nanoha.kr/access
```

## 변경 파일 목록
- `src/model/struct/services_update.py`: overlay context 유지, Swarm service image update 적용 경로 추가.
- `src/model/struct/local_command_catalog.py`, `config/docker_infra.py`: `service.stack.update.image` 명령과 allowlist 추가.
- `tests/api/test_services_preflight.py`: Swarm targeted update 경로와 local command 계약 토큰 추가.
- `devlog.md`, `devlog/2026-06-22/032-service-container-version-swarm-update.md`: 작업 이력 추가.

## 검증 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_update.py src/model/struct/local_command_catalog.py config/docker_infra.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_container_version_change_is_wired`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_local_executor.LocalExecutorStaticContractTest`
- 성공: `wiz_project_build(clean=false)`
- 성공: `git diff --check`
- 참고: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest` 전체 실행은 기존 `page.service.create` 템플릿 문구 기대값 불일치로 `test_service_create_preflight_contract_is_wired`, `test_service_create_supports_templates_and_draft_sources` 2건이 실패했다.
