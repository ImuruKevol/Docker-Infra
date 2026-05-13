# Codex CLI 실행 파일 탐색과 자동 빌드 fallback 보강

## 원 요청

AI로 초안 만들기를 누르니 아래 에러가 떴어.

```
수정한 Codex 소스의 실행 파일을 찾을 수 없습니다. /root/docker-infra/codex/codex-rs에서 Codex CLI를 빌드하거나 DOCKER_INFRA_CODEX_BIN을 지정하세요.
```

## 변경 파일

- `src/model/struct/codex_runtime.py`
  - WIZ 실행 위치가 달라져도 `/root/docker-infra` 워크스페이스와 `codex/codex-rs`를 상위 경로에서 재탐색하도록 보강.
  - `target/release/codex`, `target/debug/codex` 외에도 `target/**/codex` 실행 파일을 검색하도록 보강.
  - `DOCKER_INFRA_CODEX_BIN`이 잘못 지정되어도 즉시 실패하지 않고 로컬 수정본 Codex CLI 산출물로 fallback하도록 변경.
  - 산출물이 없을 때 `cargo build -p codex-cli --bin codex`를 잠금 파일 기반으로 1회 자동 실행한 뒤 재탐색하도록 추가.
- `tests/api/test_services_preflight.py`
  - Codex 실행 파일 탐색, 자동 빌드 fallback, MCP 연결 계약을 정적 테스트에 반영.

## 확인 결과

- `/root/docker-infra/codex/codex-rs/target/debug/codex --version`
  - `codex-cli 0.0.0`
- `python -m py_compile src/model/struct/codex_runtime.py tests/api/test_services_preflight.py`
  - 성공
- `python -m unittest tests.api.test_services_preflight`
  - 11개 테스트 성공
- 런타임 import smoke
  - `workspace_root=/root/docker-infra`
  - `resolved=/root/docker-infra/codex/codex-rs/target/debug/codex`
  - 잘못된 `DOCKER_INFRA_CODEX_BIN=/missing/codex`에서도 동일 바이너리로 fallback 확인
- `wiz_project_build(projectName=main, clean=false)`
  - 성공

## 남은 리스크

- 산출물이 없는 서버에서 첫 AI 요청이 들어오면 자동 빌드 때문에 최초 응답 시간이 길어질 수 있다.
- Rust/Cargo toolchain이 없는 배포 환경에서는 자동 빌드가 불가능하므로, 이 경우 사전 빌드 산출물 또는 `DOCKER_INFRA_CODEX_BIN` 지정이 필요하다.
